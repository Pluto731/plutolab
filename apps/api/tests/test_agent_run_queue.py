"""Run scheduler and transactional outbox acceptance using local DB and mock transport."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from plutolab_api.models.agent_run import AgentRun, AgentRunEvent, AgentRunNode, AgentRunOutbox
from plutolab_api.models.user import User
from plutolab_api.services.agent_provider import OpenAITextProvider
from plutolab_api.services.agent_run_queue import (
    RunMessage,
    RunReceipt,
    dispatch_due,
    process_run_receipt,
)
from plutolab_api.services.agent_runs import start_run
from tests.test_agent_runs import setup_run
from tests.test_agents import local_only as local_only
from tests.test_review_domain import review_engine as review_engine


class MemoryBroker:
    def __init__(self):
        self.messages = []
        self.acked = []

    async def publish(self, message):
        self.messages.append(message)
        return str(len(self.messages))

    async def receive(self):
        return None

    async def acknowledge(self, receipt):
        self.acked.append(receipt.receipt_id)


async def committed_run(engine, **kwargs):
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        owner = User(email=f"{uuid4()}@run.test")
        db.add(owner)
        await db.flush()
        run, _agent, _workflow = await setup_run(db, owner, **kwargs)
        await db.commit()
        return run.id


async def test_transactional_dispatch_and_parallel_dag_finishes_once(
    review_engine,
):
    run_id = await committed_run(
        review_engine, nodes=("a", "b", "c"), edges=(("a", "c"), ("b", "c"))
    )
    broker = MemoryBroker()
    sessions = async_sessionmaker(review_engine, expire_on_commit=False)
    async with sessions() as db:
        assert await dispatch_due(db, broker) == 1
    assert broker.messages == [RunMessage(run_id=run_id)]
    async with sessions() as db:
        outbox = await db.get(AgentRunOutbox, run_id)
        assert outbox.status == "queued"

    def handler(_request):
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": "safe"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            },
        )

    receipt = RunReceipt("memory-1", RunMessage(run_id=run_id))
    state = await process_run_receipt(
        sessions, broker, receipt, OpenAITextProvider(transport=httpx.MockTransport(handler))
    )
    assert state == "succeeded"
    assert broker.acked == ["memory-1"]
    async with sessions() as db:
        persisted = await db.get(AgentRun, run_id)
        nodes = list(await db.scalars(select(AgentRunNode).where(AgentRunNode.run_id == run_id)))
        outbox = await db.get(AgentRunOutbox, run_id)
        assert persisted.state == "succeeded"
        assert {n.node_id for n in nodes if n.state == "succeeded"} == {"a", "b", "c"}
        assert outbox.status == "completed" and outbox.run_lease_until is None


async def test_duplicate_message_is_acked_without_provider_call(review_engine):
    run_id = await committed_run(review_engine)
    broker = MemoryBroker()
    sessions = async_sessionmaker(review_engine, expire_on_commit=False)
    async with sessions() as db:
        await dispatch_due(db, broker)
    called = False

    def handler(_request):
        nonlocal called
        called = True
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": "safe"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            },
        )

    provider = OpenAITextProvider(transport=httpx.MockTransport(handler))
    receipt = RunReceipt("first", RunMessage(run_id=run_id))
    assert await process_run_receipt(sessions, broker, receipt, provider) == "succeeded"
    duplicate = RunReceipt("duplicate", RunMessage(run_id=run_id))
    assert await process_run_receipt(sessions, broker, duplicate, provider) == "duplicate"
    assert called
    assert broker.acked == ["first", "duplicate"]


async def test_fail_fast_records_failures_and_skips_dependents(review_engine):
    run_id = await committed_run(
        review_engine, nodes=("a", "b", "c"), edges=(("a", "c"), ("b", "c"))
    )
    broker = MemoryBroker()
    sessions = async_sessionmaker(review_engine, expire_on_commit=False)
    async with sessions() as db:
        assert await dispatch_due(db, broker) == 1

    def fail(_request):
        return httpx.Response(503)

    state = await process_run_receipt(
        sessions,
        broker,
        RunReceipt("fail-fast", RunMessage(run_id=run_id)),
        OpenAITextProvider(transport=httpx.MockTransport(fail)),
    )
    assert state == "failed"
    async with sessions() as db:
        nodes = {
            row.node_id: row
            for row in await db.scalars(select(AgentRunNode).where(AgentRunNode.run_id == run_id))
        }
        assert nodes["a"].state == nodes["b"].state == "failed"
        assert nodes["c"].state == "skipped" and nodes["c"].error_code == "dependency_failed"
        events = list(
            await db.scalars(
                select(AgentRunEvent)
                .where(AgentRunEvent.run_id == run_id)
                .order_by(AgentRunEvent.sequence)
            )
        )
        assert [event.sequence for event in events] == list(range(1, len(events) + 1))
        assert any(event.event_type == "node_skipped" and event.node_id == "c" for event in events)
        assert "PRIVATE_PROMPT" not in " ".join(event.summary or "" for event in events)


async def test_expired_worker_lease_charges_uncertain_reservation_without_replay(review_engine):
    run_id = await committed_run(review_engine)
    sessions = async_sessionmaker(review_engine, expire_on_commit=False)
    async with sessions() as db:
        run = await db.get(AgentRun, run_id)
        await start_run(db, run.user_id, run_id)
        node = await db.get(AgentRunNode, (run_id, "a"))
        node.state = "running"
        node.started_at = datetime.now(UTC) - timedelta(seconds=5)
        node.reserved_tokens, node.reserved_cost = 100, 25
        run.reserved_tokens, run.reserved_cost = 100, 25
        outbox = await db.get(AgentRunOutbox, run_id)
        outbox.status = "running"
        outbox.run_lease_until = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()

    class NeverProvider:
        async def complete(self, _request):
            raise AssertionError("An expired in-flight Provider call must never be replayed")

    broker = MemoryBroker()
    receipt = RunReceipt("expired-lease", RunMessage(run_id=run_id))
    assert await process_run_receipt(sessions, broker, receipt, NeverProvider()) == "recovered"
    assert broker.acked == ["expired-lease"]
    async with sessions() as db:
        run = await db.get(AgentRun, run_id)
        node = await db.get(AgentRunNode, (run_id, "a"))
        outbox = await db.get(AgentRunOutbox, run_id)
        events = list(
            await db.scalars(
                select(AgentRunEvent)
                .where(AgentRunEvent.run_id == run_id)
                .order_by(AgentRunEvent.sequence)
            )
        )
        assert run.state == "failed" and run.charged_tokens == 100
        assert run.reserved_tokens == 0 and run.reserved_cost == 0
        assert (
            node.state == "failed"
            and node.error_code == "provider_timeout"
            and node.usage_uncertain
        )
        assert outbox.status == "completed" and outbox.run_lease_until is None
        assert [event.sequence for event in events] == list(range(1, len(events) + 1))
