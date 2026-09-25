"""Agent run outbox relay and idempotent Redis Streams transport primitives."""

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, ValidationError
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.models.agent_run import AgentRun, AgentRunNode, AgentRunOutbox
from plutolab_api.services.agent_provider import TextProvider
from plutolab_api.services.agent_runs import record_run_event, start_run
from plutolab_api.services.agent_scheduler import execute_run

logger = logging.getLogger(__name__)


class RunMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: UUID


@dataclass(frozen=True)
class RunReceipt:
    receipt_id: str
    message: RunMessage


class RunBroker(Protocol):
    async def publish(self, message: RunMessage) -> str: ...
    async def receive(self) -> RunReceipt | None: ...
    async def acknowledge(self, receipt: RunReceipt) -> None: ...


class RedisRunBroker:
    def __init__(
        self,
        client: Redis,
        *,
        stream: str,
        group: str,
        consumer: str,
        reclaim_ms: int = 660000,
        block_ms: int = 1000,
    ):
        if any(
            not re.fullmatch(r"[A-Za-z0-9:_-]{1,128}", name) for name in (stream, group, consumer)
        ):
            raise ValueError("Invalid broker namespace")
        if type(reclaim_ms) is not int or not 1000 <= reclaim_ms <= 3600000:
            raise ValueError("Invalid reclaim window")
        self.client, self.stream, self.group, self.consumer = client, stream, group, consumer
        self.reclaim_ms, self.block_ms, self.cursor = reclaim_ms, block_ms, "0-0"

    @classmethod
    def local(cls, url: str, **kwargs) -> "RedisRunBroker":
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"redis", "rediss"}
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Broker must use a loopback Redis origin")
        userinfo, separator, host = parsed.netloc.rpartition("@")
        authority = (userinfo + separator if separator else "") + host.replace(
            "localhost", "127.0.0.1"
        )
        client = Redis.from_url(
            urlunsplit(parsed._replace(netloc=authority)),
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=2,
        )
        return cls(client, **kwargs)

    @classmethod
    def production(cls, url: str, **kwargs) -> "RedisRunBroker":
        parsed = urlsplit(url)
        if (
            parsed.scheme != "redis"
            or parsed.hostname != "redis"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Production worker requires the private Compose Redis service")
        client = Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=2,
        )
        return cls(client, **kwargs)

    async def initialize(self) -> None:
        try:
            await self.client.xgroup_create(self.stream, self.group, id="0-0", mkstream=True)
        except ResponseError as exc:
            if not str(exc).startswith("BUSYGROUP "):
                raise

    async def publish(self, message: RunMessage) -> str:
        return await self.client.xadd(self.stream, message.model_dump(mode="json"))

    async def receive(self) -> RunReceipt | None:
        claimed = await self.client.xautoclaim(
            self.stream, self.group, self.consumer, self.reclaim_ms, start_id=self.cursor, count=1
        )
        self.cursor, entries = claimed[0], claimed[1]
        if not entries:
            rows = await self.client.xreadgroup(
                self.group, self.consumer, {self.stream: ">"}, count=1, block=self.block_ms
            )
            entries = rows[0][1] if rows else []
        if not entries:
            return None
        receipt_id, payload = entries[0]
        try:
            return RunReceipt(receipt_id, RunMessage.model_validate(payload))
        except ValidationError:
            await self.acknowledge(RunReceipt(receipt_id, RunMessage(run_id=uuid4())))
            logger.warning("agent_run_broker_invalid_message")
            return None

    async def acknowledge(self, receipt: RunReceipt) -> None:
        await self.client.eval(
            "local n=redis.call('XACK',KEYS[1],ARGV[1],ARGV[2]); if n==1 then redis.call('XDEL',KEYS[1],ARGV[2]); end; return n",
            1,
            self.stream,
            self.group,
            receipt.receipt_id,
        )

    async def close(self) -> None:
        await self.client.aclose()


def _backoff(attempt: int) -> int:
    if type(attempt) is not int or not 1 <= attempt <= 100:
        raise ValueError("Attempt outside supported range")
    return min(300, 2 ** min(attempt - 1, 8))


async def dispatch_due(
    db: AsyncSession, broker: RunBroker, *, limit: int = 20, claim_seconds: int = 30
) -> int:
    """Publish stable run IDs; expired relay claims safely republish the same message."""
    if (
        type(limit) is not int
        or not 1 <= limit <= 100
        or type(claim_seconds) is not int
        or not 5 <= claim_seconds <= 300
    ):
        raise ValueError("Invalid dispatch bounds")
    now = datetime.now(UTC)
    rows = list(
        await db.scalars(
            select(AgentRunOutbox)
            .where(
                or_(
                    (AgentRunOutbox.status == "pending") & (AgentRunOutbox.available_at <= now),
                    (AgentRunOutbox.status == "claimed") & (AgentRunOutbox.claim_until <= now),
                )
            )
            .order_by(AgentRunOutbox.available_at, AgentRunOutbox.run_id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    claims = []
    for row in rows:
        if row.attempts >= 100:
            row.status = "failed"
            continue
        token = uuid4()
        row.status, row.claim_token, row.claim_until = (
            "claimed",
            token,
            now + timedelta(seconds=claim_seconds),
        )
        row.attempts += 1
        claims.append((row.run_id, token, row.attempts))
    await db.commit()
    sent = 0
    for run_id, token, attempt in claims:
        try:
            await broker.publish(RunMessage(run_id=run_id))
        except Exception:
            row = await db.scalar(
                select(AgentRunOutbox).where(AgentRunOutbox.run_id == run_id).with_for_update()
            )
            if row and row.status == "claimed" and row.claim_token == token:
                row.status, row.claim_token, row.claim_until = "pending", None, None
                row.available_at = datetime.now(UTC) + timedelta(seconds=_backoff(attempt))
                await db.commit()
            continue
        row = await db.scalar(
            select(AgentRunOutbox).where(AgentRunOutbox.run_id == run_id).with_for_update()
        )
        if row and row.status == "claimed" and row.claim_token == token:
            row.status, row.claim_token, row.claim_until = "queued", None, None
            row.updated_at = datetime.now(UTC)
            await db.commit()
        sent += 1
    return sent


async def release_expired_dispatch_claims(
    db: AsyncSession, *, now: datetime | None = None, limit: int = 100
) -> int:
    now = now or datetime.now(UTC)
    rows = list(
        await db.scalars(
            select(AgentRunOutbox)
            .where(
                AgentRunOutbox.status == "claimed",
                AgentRunOutbox.claim_until <= now,
            )
            .order_by(AgentRunOutbox.claim_until)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for row in rows:
        row.status, row.claim_token, row.claim_until = "pending", None, None
        row.available_at = now
    await db.commit()
    return len(rows)


async def _recover_running(db: AsyncSession, run: AgentRun, outbox: AgentRunOutbox) -> None:
    """Fence an expired worker; uncertain provider reservations are charged, never replayed."""
    nodes = list(
        await db.scalars(
            select(AgentRunNode).where(AgentRunNode.run_id == run.id).with_for_update()
        )
    )
    succeeded = 0
    now = datetime.now(UTC)
    for node in nodes:
        if node.state == "running":
            run.reserved_tokens -= node.reserved_tokens
            run.reserved_cost -= node.reserved_cost
            run.charged_tokens += node.reserved_tokens
            run.charged_cost += node.reserved_cost
            node.reserved_tokens = node.reserved_cost = 0
            node.usage_uncertain = True
            node.state, node.error_code, node.finished_at = "failed", "provider_timeout", now
            await record_run_event(
                db, run, "node_finished", "failed", node_id=node.node_id, summary="provider_timeout"
            )
        elif node.state == "pending":
            node.state, node.error_code, node.finished_at = "skipped", "dependency_failed", now
            await record_run_event(
                db,
                run,
                "node_skipped",
                "skipped",
                node_id=node.node_id,
                summary="dependency_failed",
            )
        elif node.state == "succeeded":
            succeeded += 1
    run.state = "partial" if succeeded else "failed"
    run.finished_at = now
    run.checkpoint = {
        "completed_node_ids": sorted(n.node_id for n in nodes if n.state == "succeeded")
    }
    run.checkpoint_version += 1
    await record_run_event(db, run, "run_finished", run.state)
    outbox.status, outbox.run_lease_until, outbox.updated_at = "completed", None, now
    await db.commit()


async def process_run_receipt(
    sessions,
    broker: RunBroker,
    receipt: RunReceipt,
    provider: TextProvider,
    *,
    concurrency: int = 4,
    lease_seconds: int = 660,
) -> str:
    """Claim once, execute once, persist terminal state before acknowledging delivery."""
    if type(lease_seconds) is not int or not 610 <= lease_seconds <= 1200:
        raise ValueError("Run lease must cover the maximum execution timeout")
    owner: UUID | None = None
    run_id = receipt.message.run_id
    async with sessions() as db:
        run = await db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        outbox = await db.scalar(
            select(AgentRunOutbox).where(AgentRunOutbox.run_id == run_id).with_for_update()
        )
        if outbox is None or run is None:
            await db.rollback()
            await broker.acknowledge(receipt)
            return "stale"
        now = datetime.now(UTC)
        if outbox.status == "completed" or outbox.status == "failed":
            await db.rollback()
            await broker.acknowledge(receipt)
            return "duplicate"
        if outbox.status == "running":
            if outbox.run_lease_until and outbox.run_lease_until > now:
                await db.rollback()
                await broker.acknowledge(receipt)
                return "already_running"
            await _recover_running(db, run, outbox)
            await broker.acknowledge(receipt)
            return "recovered"
        if run.expires_at <= now and run.state == "pending":
            run.state, run.finished_at = "cancelled", now
            outbox.status, outbox.updated_at = "failed", now
            await db.commit()
            await broker.acknowledge(receipt)
            return "expired"
        if outbox.status == "queued" and run.state not in {"pending", "running"}:
            outbox.status, outbox.updated_at = "completed", now
            await db.commit()
            await broker.acknowledge(receipt)
            return "duplicate"
        if outbox.status != "queued" or run.state != "pending":
            await db.rollback()
            await broker.acknowledge(receipt)
            return "stale"
        owner = run.user_id
        await start_run(db, owner, run_id)
        outbox.status, outbox.run_lease_until, outbox.updated_at = (
            "running",
            now + timedelta(seconds=lease_seconds),
            now,
        )
        await db.commit()
    try:
        state = await execute_run(sessions, owner, run_id, provider, concurrency=concurrency)
    except Exception:
        # Execution may have crossed the provider boundary. Charge reservations
        # conservatively and terminalize so the broker can never replay model work.
        async with sessions() as db:
            run = await db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
            outbox = await db.scalar(
                select(AgentRunOutbox).where(AgentRunOutbox.run_id == run_id).with_for_update()
            )
            if outbox and run and outbox.status == "running":
                await _recover_running(db, run, outbox)
        await broker.acknowledge(receipt)
        return "recovered"
    async with sessions() as db:
        await db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        outbox = await db.scalar(
            select(AgentRunOutbox).where(AgentRunOutbox.run_id == run_id).with_for_update()
        )
        if outbox and outbox.status == "running":
            outbox.status, outbox.run_lease_until, outbox.updated_at = (
                "completed",
                None,
                datetime.now(UTC),
            )
            await db.commit()
    await broker.acknowledge(receipt)
    return state
