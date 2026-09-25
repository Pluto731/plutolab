"""Safety and lifecycle behavior for local and production Agent workers."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from plutolab_api.services.agent_provider import ProviderRequest
from plutolab_api.services.agent_run_queue import RedisRunBroker, RunMessage, RunReceipt


def test_cli_requires_explicit_run_and_provider_modes():
    from plutolab_api.agent_worker import build_parser

    parser = build_parser()
    assert parser.parse_args(["--once", "--mock-provider"]).once
    assert parser.parse_args(["--continuous", "--openai-provider"]).continuous
    assert parser.parse_args(
        ["--continuous", "--openai-provider", "--production-worker"]
    ).production_worker
    with pytest.raises(SystemExit):
        parser.parse_args(["--once", "--continuous", "--mock-provider"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--once"])


def test_production_worker_requires_continuous_openai_mode():
    from plutolab_api.agent_worker import build_parser, validate_runtime

    parser = build_parser()
    args = parser.parse_args(["--once", "--openai-provider", "--production-worker"])
    with pytest.raises(SystemExit):
        validate_runtime(parser, args)


def test_production_worker_accepts_only_compose_service_hosts(monkeypatch):
    from plutolab_api import agent_worker

    monkeypatch.setattr(
        agent_worker,
        "settings",
        SimpleNamespace(
            env="production",
            database_url="postgresql+asyncpg://pluto:secret@postgres:5432/pluto",
            redis_url="redis://redis:6379/0",
        ),
    )
    agent_worker.require_production_worker()

    monkeypatch.setattr(
        agent_worker,
        "settings",
        SimpleNamespace(
            env="production",
            database_url="postgresql+asyncpg://pluto:secret@postgres:5432/pluto",
            redis_url="redis://outside.example:6379/0",
        ),
    )
    with pytest.raises(RuntimeError, match="private Compose Redis"):
        agent_worker.require_production_worker()


def test_production_broker_only_accepts_private_compose_redis(monkeypatch):
    from redis.asyncio import Redis

    client = object()
    monkeypatch.setattr(Redis, "from_url", lambda *_args, **_kwargs: client)
    broker = RedisRunBroker.production(
        "redis://redis:6379/0", stream="runs", group="workers", consumer="test"
    )
    assert broker.client is client
    with pytest.raises(ValueError, match="private Compose Redis"):
        RedisRunBroker.production(
            "redis://external.example:6379/0", stream="runs", group="workers", consumer="test"
        )


@pytest.mark.asyncio
async def test_mock_provider_ignores_request_and_returns_fixed_safe_output():
    from plutolab_api.agent_worker import LocalMockProvider

    request = ProviderRequest(
        key="secret-must-not-be-read",
        messages=[{"role": "user", "content": "private user input"}],
    )

    reply = await LocalMockProvider().complete(request)

    assert reply.text == "本地模拟执行完成。"
    assert reply.tool is None
    assert (reply.input_tokens, reply.output_tokens) == (1, 1)


@pytest.mark.asyncio
async def test_process_one_relays_and_processes_at_most_one_receipt(monkeypatch):
    from plutolab_api import agent_worker

    calls = []
    receipt = RunReceipt("1-0", RunMessage(run_id=uuid4()))

    class Broker:
        async def initialize(self):
            calls.append("initialize")

        async def receive(self):
            calls.append("receive")
            return receipt

    @asynccontextmanager
    async def sessions():
        yield object()

    async def release(db):
        calls.append("release")
        return 0

    async def dispatch(db, broker, *, limit):
        calls.append(("dispatch", limit))
        return 1

    async def process(sessions_arg, broker, received, provider):
        assert received is receipt
        assert isinstance(provider, agent_worker.LocalMockProvider)
        calls.append("process")
        return "succeeded"

    monkeypatch.setattr(agent_worker, "release_expired_dispatch_claims", release)
    monkeypatch.setattr(agent_worker, "dispatch_due", dispatch)
    monkeypatch.setattr(agent_worker, "process_run_receipt", process)

    result = await agent_worker.process_one(sessions, Broker(), agent_worker.LocalMockProvider())

    assert result == "succeeded"
    assert calls == ["initialize", "release", ("dispatch", 20), "receive", "process"]


@pytest.mark.asyncio
async def test_continuous_worker_keeps_polling_until_interrupted(monkeypatch):
    from plutolab_api import agent_worker

    calls = 0

    async def process_one(sessions, broker, provider):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise asyncio.CancelledError
        return "idle"

    monkeypatch.setattr(agent_worker, "process_one", process_one)
    with pytest.raises(asyncio.CancelledError):
        await agent_worker.run_continuously(object(), object(), agent_worker.LocalMockProvider())
    assert calls == 2


def test_local_worker_rejects_non_development_and_non_loopback(monkeypatch):
    from plutolab_api import agent_worker

    monkeypatch.setattr(
        agent_worker,
        "settings",
        SimpleNamespace(
            env="production",
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            redis_url="redis://localhost:6379/0",
        ),
    )
    with pytest.raises(RuntimeError, match="PLUTOLAB_ENV=development"):
        agent_worker.require_local_development()

    monkeypatch.setattr(
        agent_worker,
        "settings",
        SimpleNamespace(
            env="development",
            database_url="postgresql+asyncpg://user:pass@db.internal/db",
            redis_url="redis://localhost:6379/0",
        ),
    )
    with pytest.raises(RuntimeError, match="loopback database"):
        agent_worker.require_local_development()

    monkeypatch.setattr(
        agent_worker,
        "settings",
        SimpleNamespace(
            env="development",
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            redis_url="redis://cache.internal:6379/0",
        ),
    )
    with pytest.raises(RuntimeError, match="loopback redis"):
        agent_worker.require_local_development()
