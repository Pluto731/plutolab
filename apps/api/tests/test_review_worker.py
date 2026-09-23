"""Local review worker acceptance; no real provider or external broker traffic."""

import asyncio
import socket
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from plutolab_api.models.review import GitHubInstallation, ReviewAttempt, ReviewJob, ReviewOutbox
from plutolab_api.models.user import User
from plutolab_api.services.review.broker import RedisStreamsBroker
from plutolab_api.services.review.jobs import (
    ReviewStateError,
    enqueue_review,
    finish_analysis,
    recover_expired_attempt,
)
from plutolab_api.services.review.settings import ReviewRules, create_installation, create_settings
from plutolab_api.services.review.worker import (
    BrokerReceipt,
    Consumer,
    Dispatcher,
    RetryableWorkError,
    WorkerOptions,
    WorkMessage,
    acquire_work,
    backoff_seconds,
)
from tests.test_review_domain import disposable_database, migrate
from tests.test_review_domain import owners as owners
from tests.test_review_domain import review_db as review_db
from tests.test_review_domain import review_engine as review_engine
from tests.test_review_jobs import request as job_request
from tests.test_review_jobs import result as analysis_result


@pytest_asyncio.fixture
async def queued(review_db, owners):
    await create_installation(review_db, owners[0].id, "301")
    await create_settings(
        review_db, owners[0].id, "301", "401", "owner/repo", rules=ReviewRules(enabled=True)
    )
    result = await enqueue_review(review_db, owners[0].id, job_request())
    outbox = await review_db.scalar(
        select(ReviewOutbox).where(ReviewOutbox.job_id == result.job.id)
    )
    await review_db.commit()
    return WorkMessage(job_id=result.job.id, outbox_id=outbox.id)


def test_backoff_is_exponential_and_bounded():
    assert [backoff_seconds(n, base=2, maximum=10) for n in range(1, 7)] == [2, 4, 8, 10, 10, 10]


@pytest.mark.parametrize("value", [0, -1, 101, True, 1.5])
def test_bad_attempt_count_rejected(value):
    with pytest.raises(ValueError):
        backoff_seconds(value)


@pytest.mark.parametrize(
    "extra", [{"owner_id": str(uuid4())}, {"source": "private code"}, {"task": "eval"}]
)
def test_broker_message_allows_only_identifiers(extra):
    with pytest.raises(ValidationError):
        WorkMessage(job_id=uuid4(), outbox_id=uuid4(), **extra)


async def test_consumer_acquires_one_lease_for_duplicate_message(review_db, queued):
    first = await acquire_work(review_db, queued)
    await review_db.commit()
    assert first is not None
    assert first.lease_expires_at > datetime.now(UTC)
    assert await acquire_work(review_db, queued) is None
    assert await review_db.scalar(select(func.count()).select_from(ReviewAttempt)) == 1
    job = await review_db.get(ReviewJob, queued.job_id)
    assert job.analysis_status == "processing"


async def test_completed_message_does_not_run_again(review_db, queued):
    lease = await acquire_work(review_db, queued)
    await review_db.commit()
    await finish_analysis(
        review_db, lease.owner_id, lease.job_id, lease.attempt_id, analysis_result()
    )
    await review_db.commit()
    assert await acquire_work(review_db, queued) is None
    assert await review_db.scalar(select(func.count()).select_from(ReviewAttempt)) == 1


async def test_mismatched_job_identifier_cannot_acquire_lease(review_db, queued):
    assert (
        await acquire_work(review_db, WorkMessage(job_id=uuid4(), outbox_id=queued.outbox_id))
        is None
    )
    assert await review_db.scalar(select(func.count()).select_from(ReviewAttempt)) == 0


async def test_revoked_installation_is_cancelled_without_handler_lease(review_db, queued):
    installation = await review_db.get(GitHubInstallation, "301")
    installation.revoked_at = datetime.now(UTC)
    await review_db.commit()
    assert await acquire_work(review_db, queued) is None
    job = await review_db.get(ReviewJob, queued.job_id)
    assert job.analysis_status == "cancelled"
    assert await review_db.scalar(select(func.count()).select_from(ReviewAttempt)) == 0


async def test_old_dispatch_version_cannot_acquire_lease(review_db, queued):
    job = await review_db.get(ReviewJob, queued.job_id)
    job.dispatch_version += 1
    await review_db.commit()
    assert await acquire_work(review_db, queued) is None
    assert await review_db.scalar(select(func.count()).select_from(ReviewAttempt)) == 0


async def test_recovered_attempt_fences_old_message_and_old_completion(review_db, queued):
    first = await acquire_work(review_db, queued)
    await review_db.commit()
    attempt = await review_db.get(ReviewAttempt, first.attempt_id)
    attempt.started_at = datetime.now(UTC) - timedelta(seconds=120)
    attempt.lease_until = datetime.now(UTC) - timedelta(seconds=60)
    await review_db.commit()
    await recover_expired_attempt(
        review_db, first.owner_id, first.job_id, first.attempt_id, budget_available=True
    )
    await review_db.commit()
    assert await acquire_work(review_db, queued) is None
    successor = await review_db.scalar(
        select(ReviewOutbox).where(ReviewOutbox.job_id == first.job_id, ReviewOutbox.version == 2)
    )
    second = await acquire_work(review_db, WorkMessage(job_id=first.job_id, outbox_id=successor.id))
    assert second is not None and second.number == 2
    await review_db.commit()
    with pytest.raises(ReviewStateError):
        await finish_analysis(
            review_db, first.owner_id, first.job_id, first.attempt_id, analysis_result()
        )
    await finish_analysis(
        review_db, second.owner_id, second.job_id, second.attempt_id, analysis_result()
    )
    await review_db.commit()
    assert (await review_db.get(ReviewJob, first.job_id)).analysis_status == "analyzed"


async def test_concurrent_consumers_acquire_only_one_committed_lease():
    async with disposable_database() as url:
        migrate(url, "upgrade", "head")
        engine = create_async_engine(url)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                owner = User(email=f"{uuid4()}@worker.test")
                db.add(owner)
                await db.flush()
                await create_installation(db, owner.id, "301")
                await create_settings(
                    db, owner.id, "301", "401", "owner/repo", rules=ReviewRules(enabled=True)
                )
                result = await enqueue_review(db, owner.id, job_request())
                row = await db.scalar(
                    select(ReviewOutbox).where(ReviewOutbox.job_id == result.job.id)
                )
                message = WorkMessage(job_id=result.job.id, outbox_id=row.id)
                await db.commit()

            async def claim():
                async with AsyncSession(engine) as db:
                    result = await acquire_work(db, message)
                    await db.commit()
                    return result

            claims = await asyncio.gather(*[claim() for _ in range(4)])
            assert sum(claim is not None for claim in claims) == 1
            async with AsyncSession(engine) as observer:
                assert await observer.scalar(select(func.count()).select_from(ReviewAttempt)) == 1
                assert (
                    await observer.get(ReviewJob, message.job_id)
                ).analysis_status == "processing"
        finally:
            await engine.dispose()


@pytest.fixture(autouse=True)
def local_only(monkeypatch):
    original = socket.socket.connect

    def connect(sock, address):
        if (
            not isinstance(address, tuple)
            or address[0] not in {"127.0.0.1", "::1"}
            or address[1] not in {5432, 6379}
        ):
            raise AssertionError("Only loopback test PostgreSQL/Redis permitted")
        return original(sock, address)

    async def deny_http(*args, **kwargs):
        raise AssertionError("Outbound HTTP forbidden")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", deny_http)


class MemoryBroker:
    def __init__(self):
        self.messages = []
        self.acks = []
        self.failure = False

    async def publish(self, message):
        if self.failure:
            raise ConnectionError("secret-broker-credential")
        self.messages.append(BrokerReceipt(str(len(self.messages) + 1), message))
        return self.messages[-1].receipt_id

    async def receive(self):
        return self.messages.pop(0) if self.messages else None

    async def acknowledge(self, receipt):
        self.acks.append(receipt)


@pytest.fixture
def sessions(review_db):
    @asynccontextmanager
    async def factory():
        yield review_db

    return factory


async def test_dispatch_ack_and_consume_deduplicated(review_db, queued, sessions):
    broker = MemoryBroker()
    dispatcher = Dispatcher(sessions, broker)
    assert (await dispatcher.dispatch_once())["dispatched"] == 1
    row = await review_db.get(ReviewOutbox, queued.outbox_id)
    assert row.status == "dispatched" and row.dispatch_attempts == 1
    assert row.claim_token is None and row.dispatched_at is not None
    calls = []

    async def handler(lease):
        calls.append(lease)
        assert (await review_db.get(ReviewJob, lease.job_id)).analysis_status == "processing"
        return analysis_result()

    broker.messages.append(BrokerReceipt("duplicate", queued))
    consumer = Consumer(sessions, broker, handler)
    assert await consumer.consume_once() == "analyzed"
    assert await consumer.consume_once() == "duplicate"
    assert len(calls) == 1 and len(broker.acks) == 2


async def test_dispatch_failure_backoff_exhaustion_and_redaction(
    review_db, queued, sessions, caplog
):
    broker = MemoryBroker()
    broker.failure = True
    now = datetime.now(UTC) + timedelta(seconds=1)
    dispatcher = Dispatcher(
        sessions, broker, options=WorkerOptions(max_dispatch_attempts=3), clock=lambda: now
    )
    for attempt, delay in [(1, 1), (2, 2), (3, 0)]:
        counts = await dispatcher.dispatch_once()
        row = await review_db.get(ReviewOutbox, queued.outbox_id)
        assert row.dispatch_attempts == attempt
        assert row.claim_token is None and row.last_error == "broker_failure"
        if delay:
            assert counts["pending"] == 1
            assert row.available_at == now + timedelta(seconds=delay)
            assert sum((await dispatcher.dispatch_once()).values()) == 0
            now = row.available_at
        else:
            assert counts["failed"] == 1 and row.status == "failed"
    assert "secret-broker-credential" not in caplog.text
    assert "review_outbox_retry_exhausted" in caplog.text


async def test_expired_dispatch_claim_fences_late_settlement(review_db, queued, sessions):
    now = datetime.now(UTC) + timedelta(seconds=1)
    dispatcher = Dispatcher(sessions, MemoryBroker(), clock=lambda: now)
    first = await dispatcher.claim_one()
    assert await dispatcher.claim_one() is None
    now += timedelta(seconds=31)
    second = await dispatcher.claim_one()
    assert second.token != first.token
    assert await dispatcher.settle(first, published=True) == "stale"
    assert await dispatcher.settle(second, published=True) == "dispatched"
    assert (await review_db.get(ReviewOutbox, queued.outbox_id)).dispatch_attempts == 2


async def test_consumption_before_dispatch_settlement_is_safe(review_db, queued, sessions):
    class FastBroker(MemoryBroker):
        async def publish(self, message):
            assert await acquire_work(review_db, message) is not None
            await review_db.commit()
            return "accepted"

    assert (await Dispatcher(sessions, FastBroker()).dispatch_once())["stale"] == 1
    assert (await review_db.get(ReviewOutbox, queued.outbox_id)).status == "cancelled"


@pytest.mark.parametrize("allow", [False, True])
async def test_retry_requires_budget_and_stops_at_max(review_db, queued, sessions, caplog, allow):
    broker = MemoryBroker()

    async def handler(lease):
        raise RetryableWorkError("secret-provider-token")

    async def budget(lease):
        return allow

    consumer = Consumer(sessions, broker, handler, budget_gate=budget)
    await Dispatcher(sessions, broker).dispatch_once()
    assert await consumer.consume_once() == ("retry" if allow else "failed")
    if allow:
        row = await review_db.scalar(select(ReviewOutbox).where(ReviewOutbox.version == 2))
        assert row.available_at > datetime.now(UTC)
        row.available_at = datetime.now(UTC) - timedelta(seconds=1)
        await review_db.commit()
        await Dispatcher(sessions, broker).dispatch_once()
        assert await consumer.consume_once() == "failed"
    assert "secret-provider-token" not in caplog.text
    assert "review_worker_retry_stopped" in caplog.text


@pytest.mark.parametrize("allow", [False, True])
async def test_reaper_crash_recovery_is_budget_gated(review_db, queued, sessions, allow):
    lease = await acquire_work(review_db, queued)
    attempt = await review_db.get(ReviewAttempt, lease.attempt_id)
    attempt.started_at = datetime.now(UTC) - timedelta(seconds=100)
    attempt.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    await review_db.commit()

    async def handler(lease):
        return analysis_result()

    async def budget(lease):
        return allow

    consumer = Consumer(sessions, MemoryBroker(), handler, budget_gate=budget)
    assert await consumer.reap_once() == 1
    assert await consumer.reap_once() == 0
    assert attempt.status == "abandoned"
    assert (await review_db.get(ReviewJob, queued.job_id)).analysis_status == (
        "queued" if allow else "failed"
    )


async def test_ack_loss_does_not_repeat_handler(review_db, queued, sessions):
    broker = MemoryBroker()
    calls = []

    async def handler(lease):
        calls.append(lease)
        return analysis_result()

    async def lost_ack(receipt):
        raise ConnectionError("ack lost")

    await Dispatcher(sessions, broker).dispatch_once()
    consumer = Consumer(sessions, broker, handler)
    broker.acknowledge = lost_ack
    with pytest.raises(ConnectionError):
        await consumer.consume_once()
    broker.messages.append(BrokerReceipt("redelivery", queued))
    broker.acknowledge = MemoryBroker.acknowledge.__get__(broker)
    assert await consumer.consume_once() == "duplicate"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "url", ["redis://evil.example", "https://127.0.0.1", "redis://127.0.0.1?host=evil"]
)
def test_external_broker_origin_rejected(url):
    with pytest.raises(ValueError):
        RedisStreamsBroker.local(url, stream="test", group="test", consumer="test")


async def test_real_local_redis_relay_reclaim_and_ack(review_db, queued, sessions):
    namespace = "slice9-test:" + uuid4().hex
    broker = RedisStreamsBroker.local(
        "redis://127.0.0.1:6379/15",
        stream=namespace,
        group="test",
        consumer="one",
        block_ms=1,
        reclaim_ms=1,
    )
    try:
        await broker.initialize()
        await broker.initialize()
        assert (await Dispatcher(sessions, broker).dispatch_once())["dispatched"] == 1
        receipt = await broker.receive()
        assert receipt.message == queued
        await broker.client.xclaim(namespace, "test", "crashed", 0, [receipt.receipt_id], idle=100)
        reclaimed = await broker.receive()
        assert reclaimed.message == queued
        await broker.acknowledge(reclaimed)
        assert (await broker.client.xpending(namespace, "test"))["pending"] == 0
        assert await broker.client.xlen(namespace) == 0
        await broker.publish(queued)

        async def handler(lease):
            return analysis_result()

        assert await Consumer(sessions, broker, handler).consume_once() == "analyzed"
        assert await broker.client.xlen(namespace) == 0
    finally:
        await broker.client.delete(namespace)
        assert await broker.client.exists(namespace) == 0
        await broker.close()


async def test_migration_0017_roundtrip():
    async with disposable_database() as url:
        await asyncio.to_thread(migrate, url, "upgrade", "0016")
        await asyncio.to_thread(migrate, url, "upgrade", "0017")
        engine = create_async_engine(url)
        try:
            async with engine.connect() as db:
                names = (
                    (
                        await db.execute(
                            text(
                                "SELECT column_name FROM information_schema.columns WHERE table_name='review_outbox'"
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                assert {
                    "claim_token",
                    "claim_until",
                    "dispatch_attempts",
                    "available_at",
                    "last_error",
                } <= set(names)
        finally:
            await engine.dispose()
        await asyncio.to_thread(migrate, url, "downgrade", "0016")
        await asyncio.to_thread(migrate, url, "upgrade", "0017")


@pytest_asyncio.fixture
async def durable():
    async with disposable_database() as url:
        await asyncio.to_thread(migrate, url, "upgrade", "head")
        engine = create_async_engine(url)

        @asynccontextmanager
        async def sessions():
            async with AsyncSession(engine, expire_on_commit=False) as db:
                yield db

        try:
            async with sessions() as db:
                owner = User(email=f"{uuid4()}@worker.test")
                db.add(owner)
                await db.flush()
                await create_installation(db, owner.id, "301")
                await create_settings(
                    db, owner.id, "301", "401", "owner/repo", rules=ReviewRules(enabled=True)
                )
                result = await enqueue_review(db, owner.id, job_request())
                row = await db.scalar(
                    select(ReviewOutbox).where(ReviewOutbox.job_id == result.job.id)
                )
                message = WorkMessage(job_id=result.job.id, outbox_id=row.id)
                await db.commit()
            yield sessions, message, engine, url
        finally:
            await engine.dispose()


async def test_concurrent_dispatchers_claim_once(durable):
    sessions, message, _, _ = durable
    brokers = [MemoryBroker() for _ in range(4)]
    results = await asyncio.gather(
        *(Dispatcher(sessions, broker).dispatch_once() for broker in brokers)
    )
    assert sum(result["dispatched"] for result in results) == 1
    assert sum(len(broker.messages) for broker in brokers) == 1
    async with sessions() as db:
        assert (await db.get(ReviewOutbox, message.outbox_id)).dispatch_attempts == 1


async def test_commits_visible_before_broker_and_handler_and_ack(durable):
    sessions, message, _, _ = durable

    class ObservedBroker(MemoryBroker):
        async def publish(self, message):
            async with sessions() as db:
                row = await db.get(ReviewOutbox, message.outbox_id)
                assert row.status == "pending" and row.claim_token is not None
                assert row.dispatch_attempts == 1
            return await super().publish(message)

        async def acknowledge(self, receipt):
            async with sessions() as db:
                assert (await db.get(ReviewJob, message.job_id)).analysis_status == "analyzed"
            await super().acknowledge(receipt)

    async def handler(lease):
        async with sessions() as db:
            assert (await db.get(ReviewAttempt, lease.attempt_id)).status == "running"
        return analysis_result()

    broker = ObservedBroker()
    assert (await Dispatcher(sessions, broker).dispatch_once())["dispatched"] == 1
    assert await Consumer(sessions, broker, handler).consume_once() == "analyzed"
    assert len(broker.acks) == 1


async def test_publish_ack_loss_retries_same_task_safely(durable):
    sessions, message, _, _ = durable

    class UncertainBroker(MemoryBroker):
        async def publish(self, message):
            result = await super().publish(message)
            if len(self.messages) == 1:
                raise ConnectionError("ack lost after append")
            return result

    broker = UncertainBroker()
    now = datetime.now(UTC) + timedelta(seconds=1)
    dispatcher = Dispatcher(sessions, broker, clock=lambda: now)
    assert (await dispatcher.dispatch_once())["pending"] == 1
    now += timedelta(seconds=1)
    assert (await dispatcher.dispatch_once())["dispatched"] == 1
    assert [receipt.message for receipt in broker.messages] == [message, message]
    calls = []

    async def handler(lease):
        calls.append(lease)
        return analysis_result()

    consumer = Consumer(sessions, broker, handler)
    assert await consumer.consume_once() == "analyzed"
    assert await consumer.consume_once() == "duplicate"
    assert len(calls) == 1


async def test_result_commit_failure_leaves_receipt_unacked(durable, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    sessions, message, _, _ = durable
    broker = MemoryBroker()
    await Dispatcher(sessions, broker).dispatch_once()
    original = AsyncSession.commit

    async def broken_commit(self):
        raise SQLAlchemyError("synthetic commit failure")

    async def handler(lease):
        monkeypatch.setattr(AsyncSession, "commit", broken_commit)
        return analysis_result()

    with pytest.raises(SQLAlchemyError):
        await Consumer(sessions, broker, handler).consume_once()
    monkeypatch.setattr(AsyncSession, "commit", original)
    assert broker.acks == []
    async with sessions() as db:
        assert (await db.get(ReviewJob, message.job_id)).analysis_status == "processing"
        assert (await db.scalar(select(ReviewAttempt))).status == "running"


async def test_dispatch_commit_failure_recovers_claim(durable, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    sessions, message, _, _ = durable
    original = AsyncSession.commit

    async def broken_commit(self):
        raise SQLAlchemyError("synthetic settle failure")

    class AcceptedBroker(MemoryBroker):
        async def publish(self, message):
            result = await super().publish(message)
            monkeypatch.setattr(AsyncSession, "commit", broken_commit)
            return result

    now = datetime.now(UTC) + timedelta(seconds=1)
    dispatcher = Dispatcher(sessions, AcceptedBroker(), clock=lambda: now)
    with pytest.raises(SQLAlchemyError):
        await dispatcher.dispatch_once()
    monkeypatch.setattr(AsyncSession, "commit", original)
    async with sessions() as db:
        row = await db.get(ReviewOutbox, message.outbox_id)
        assert row.status == "pending" and row.claim_token is not None
    now += timedelta(seconds=31)
    dispatcher.broker = MemoryBroker()
    assert (await dispatcher.dispatch_once())["dispatched"] == 1


async def test_timeout_is_bounded_and_persisted(review_db, queued, sessions):
    class TimeoutBroker(MemoryBroker):
        async def publish(self, message):
            await asyncio.Event().wait()

    options = WorkerOptions(broker_timeout_seconds=0.01)
    assert (await Dispatcher(sessions, TimeoutBroker(), options=options).dispatch_once())[
        "pending"
    ] == 1
    assert (await review_db.get(ReviewOutbox, queued.outbox_id)).dispatch_attempts == 1


async def test_cancellation_leaves_recoverable_lease(review_db, queued, sessions):
    broker = MemoryBroker()
    await Dispatcher(sessions, broker).dispatch_once()

    async def handler(lease):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await Consumer(sessions, broker, handler).consume_once()
    assert broker.acks == []
    assert (await review_db.get(ReviewJob, queued.job_id)).analysis_status == "processing"
    assert (await review_db.scalar(select(ReviewAttempt))).status == "running"


@pytest.mark.parametrize("blocked", ["failed", "claimed"])
async def test_migration_refuses_lossy_downgrade_and_preserves_legacy_row(durable, blocked):
    sessions, message, engine, url = durable
    async with sessions() as db:
        row = await db.get(ReviewOutbox, message.outbox_id)
        if blocked == "failed":
            row.status = "failed"
        else:
            row.claim_token = uuid4()
            row.claim_until = datetime.now(UTC) + timedelta(seconds=60)
        await db.commit()
    await engine.dispose()
    with pytest.raises(pytest.fail.Exception, match="Cannot downgrade 0017"):
        await asyncio.to_thread(migrate, url, "downgrade", "0016")
    async with sessions() as db:
        row = await db.get(ReviewOutbox, message.outbox_id)
        assert row.status == ("failed" if blocked == "failed" else "pending")
        row.status = "pending"
        row.claim_token = row.claim_until = None
        await db.commit()
    await engine.dispose()
    await asyncio.to_thread(migrate, url, "downgrade", "0016")
    await asyncio.to_thread(migrate, url, "upgrade", "0017")
    async with sessions() as db:
        row = await db.get(ReviewOutbox, message.outbox_id)
        assert row.job_id == message.job_id and row.status == "pending"
        assert row.dispatch_attempts == 0 and row.claim_token is None


async def test_cancelled_expired_claim_is_released(review_db, queued, sessions):
    now = datetime.now(UTC) + timedelta(seconds=1)
    dispatcher = Dispatcher(sessions, MemoryBroker(), clock=lambda: now)
    await dispatcher.claim_one()
    await acquire_work(review_db, queued)
    await review_db.commit()
    now += timedelta(seconds=31)
    assert await dispatcher.claim_one() is None
    row = await review_db.get(ReviewOutbox, queued.outbox_id)
    assert row.status == "cancelled" and row.claim_token is None


async def test_repeated_dispatch_crashes_exhaust_claim_limit(review_db, queued, sessions):
    now = datetime.now(UTC) + timedelta(seconds=1)
    dispatcher = Dispatcher(
        sessions, MemoryBroker(), clock=lambda: now, options=WorkerOptions(max_dispatch_attempts=1)
    )
    assert await dispatcher.claim_one() is not None
    now += timedelta(seconds=31)
    assert await dispatcher.claim_one() == "failed"
    row = await review_db.get(ReviewOutbox, queued.outbox_id)
    assert row.status == "failed" and row.last_error == "dispatch_retries_exhausted"


async def test_default_budget_never_retries(review_db, queued, sessions):
    broker = MemoryBroker()
    await Dispatcher(sessions, broker).dispatch_once()

    async def handler(lease):
        raise RetryableWorkError("transient")

    assert await Consumer(sessions, broker, handler).consume_once() == "failed"
    assert await review_db.scalar(select(func.count()).select_from(ReviewOutbox)) == 1


async def test_broker_poison_message_is_acknowledged_without_payload_log(caplog):
    namespace = "slice9-test:" + uuid4().hex
    broker = RedisStreamsBroker.local(
        "redis://127.0.0.1:6379/15", stream=namespace, group="test", consumer="test", block_ms=1
    )
    try:
        await broker.initialize()
        await broker.client.xadd(namespace, {"secret": "sensitive-source"})
        assert await broker.receive() is None
        assert (await broker.client.xpending(namespace, "test"))["pending"] == 0
        assert "review_broker_invalid_message" in caplog.text
        assert "sensitive-source" not in caplog.text
    finally:
        await broker.client.delete(namespace)
        assert await broker.client.exists(namespace) == 0
        await broker.close()


@pytest.mark.parametrize(
    "options",
    [
        {"max_dispatch_attempts": 0},
        {"lease_seconds": 3601},
        {"dispatch_lease_seconds": 2, "broker_timeout_seconds": 3.0},
        {"retry_base_seconds": 10, "retry_max_seconds": 1},
    ],
)
def test_invalid_worker_windows_rejected(options):
    with pytest.raises(ValidationError):
        WorkerOptions(**options)


async def test_local_loop_stops_after_committed_work(review_db, queued, sessions):
    from plutolab_api.services.review.worker import run_worker

    stop = asyncio.Event()
    broker = MemoryBroker()

    async def handler(lease):
        stop.set()
        return analysis_result()

    await asyncio.wait_for(
        run_worker(Dispatcher(sessions, broker), Consumer(sessions, broker, handler), stop),
        timeout=2,
    )
    assert len(broker.acks) == 1
    assert (await review_db.get(ReviewJob, queued.job_id)).analysis_status == "analyzed"


@pytest.mark.parametrize(
    "values", [{"dispatch_attempts": -1}, {"dispatch_attempts": 101}, {"claim_token": uuid4()}]
)
async def test_dispatch_schema_rejects_invalid_state(review_db, queued, values):
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        async with review_db.begin_nested():
            await review_db.execute(
                update(ReviewOutbox).where(ReviewOutbox.id == queued.outbox_id).values(**values)
            )
