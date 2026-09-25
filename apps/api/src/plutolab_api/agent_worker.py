"""Explicit local Agent worker with mock or user-key OpenAI provider modes."""

import argparse
import asyncio
import os
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url

from plutolab_api.core.config import settings
from plutolab_api.db.session import AsyncSessionLocal, dispose_engine
from plutolab_api.services.agent_provider import (
    OpenAITextProvider,
    ProviderReply,
    ProviderRequest,
    TextProvider,
)
from plutolab_api.services.agent_run_queue import (
    RedisRunBroker,
    dispatch_due,
    process_run_receipt,
    release_expired_dispatch_claims,
)


class LocalMockProvider:
    """Return fixed output without reading prompts, user input, or stored keys."""

    requires_api_key = False

    async def complete(self, _: ProviderRequest) -> ProviderReply:
        return ProviderReply(
            text="本地模拟执行完成。",
            tool=None,
            input_tokens=1,
            output_tokens=1,
        )


def require_local_development() -> None:
    if settings.env.lower() != "development":
        raise RuntimeError("Local Agent worker requires PLUTOLAB_ENV=development")
    for label, raw_url in (
        ("database", settings.database_url),
        ("redis", settings.redis_url),
    ):
        try:
            hostname = make_url(raw_url).host
        except Exception as exc:
            raise RuntimeError(f"Local Agent worker rejected {label} URL") from exc
        if hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError(f"Local Agent worker requires loopback {label}")


def require_production_worker() -> None:
    if settings.env.lower() != "production":
        raise RuntimeError("Production Agent worker requires ENV=production")
    try:
        database_host = make_url(settings.database_url).host
        redis_url = urlsplit(settings.redis_url)
    except Exception as exc:
        raise RuntimeError("Production Agent worker rejected service URL") from exc
    if database_host != "postgres":
        raise RuntimeError(
            "Production Agent worker requires the private Compose PostgreSQL service"
        )
    if (
        redis_url.scheme != "redis"
        or redis_url.hostname != "redis"
        or redis_url.query
        or redis_url.fragment
    ):
        raise RuntimeError("Production Agent worker requires the private Compose Redis service")


async def process_one(sessions, broker: RedisRunBroker, provider: TextProvider) -> str:
    """Relay due outbox rows, then process at most one broker receipt."""
    await broker.initialize()
    async with sessions() as db:
        await release_expired_dispatch_claims(db)
        await dispatch_due(db, broker, limit=20)
    receipt = await broker.receive()
    if receipt is None:
        return "idle"
    return await process_run_receipt(sessions, broker, receipt, provider)


async def run_continuously(sessions, broker: RedisRunBroker, provider: TextProvider) -> None:
    """Poll until the process is interrupted; each receipt remains independently leased."""
    while True:
        await process_one(sessions, broker, provider)


async def _run(stream: str, group: str, provider: TextProvider, *, continuous: bool) -> str | None:
    broker_factory = (
        RedisRunBroker.production if settings.env.lower() == "production" else RedisRunBroker.local
    )
    broker = broker_factory(
        settings.redis_url,
        stream=stream,
        group=group,
        consumer=f"worker-{os.getpid()}",
    )
    try:
        if continuous:
            await run_continuously(AsyncSessionLocal, broker, provider)
        return await process_one(AsyncSessionLocal, broker, provider)
    finally:
        await broker.close()
        await dispose_engine()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local Agent worker")
    run_mode = parser.add_mutually_exclusive_group(required=True)
    run_mode.add_argument("--once", action="store_true")
    run_mode.add_argument("--continuous", action="store_true")
    provider_mode = parser.add_mutually_exclusive_group(required=True)
    provider_mode.add_argument("--mock-provider", action="store_true")
    provider_mode.add_argument("--openai-provider", action="store_true")
    parser.add_argument("--production-worker", action="store_true")
    parser.add_argument("--stream")
    parser.add_argument("--group")
    return parser


def validate_runtime(parser: argparse.ArgumentParser, args: argparse.Namespace) -> tuple[str, str]:
    if args.production_worker:
        if not args.continuous or not args.openai_provider:
            parser.error("--production-worker requires --continuous and --openai-provider")
        require_production_worker()
        return (
            "plutolab:agent-runs:production",
            "production-agent-workers",
        )

    require_local_development()
    return "plutolab:agent-runs:local", "local-mock-workers"


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    default_stream, default_group = validate_runtime(parser, args)
    provider: TextProvider = LocalMockProvider() if args.mock_provider else OpenAITextProvider()
    mode = "mock" if args.mock_provider else "openai"
    environment = "production" if args.production_worker else "local"
    stream, group = args.stream or default_stream, args.group or default_group
    if args.continuous:
        print(f"{environment} {mode} worker: running; press Ctrl-C to stop")
        try:
            asyncio.run(_run(stream, group, provider, continuous=True))
        except KeyboardInterrupt:
            print(f"{environment} {mode} worker: stopped")
        return
    result = asyncio.run(_run(stream, group, provider, continuous=False))
    print(f"{environment} {mode} worker: {result}")


if __name__ == "__main__":
    main()
