"""Local review dispatch/consumer primitives. No provider or GitHub implementation.

DB intent is authoritative; broker receipts are at-least-once. Callers commit a
lease before invoking a handler and commit results before acknowledging messages.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.models.review import GitHubInstallation, ReviewAttempt, ReviewJob, ReviewOutbox
from plutolab_api.schemas.review import AnalysisResult, AnalysisStopped, ReviewError, ReviewPolicy
from plutolab_api.services.review.jobs import (
    ReviewStateError,
    begin_analysis,
    finish_analysis,
    recover_expired_attempt,
    retry_analysis,
    stop_analysis,
)
from plutolab_api.services.review.settings import ReviewAccessDeniedError


class WorkMessage(BaseModel):
    """Only job ID and stable outbox/task ID cross the broker boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    outbox_id: UUID
    job_id: UUID


@dataclass(frozen=True)
class BrokerReceipt:
    receipt_id: str
    message: WorkMessage


class Broker(Protocol):
    async def publish(self, message: WorkMessage) -> str: ...

    async def receive(self) -> BrokerReceipt | None: ...

    async def acknowledge(self, receipt: BrokerReceipt) -> None: ...


@dataclass(frozen=True)
class WorkLease:
    job_id: UUID
    owner_id: UUID
    attempt_id: UUID
    number: int
    max_attempts: int
    lease_expires_at: datetime
    head_sha: str
    policy: ReviewPolicy


def backoff_seconds(attempt: int, *, base: int = 1, maximum: int = 300) -> int:
    if any(type(value) is not int for value in (attempt, base, maximum)):
        raise ValueError("Retry limits must be integers")
    if not 1 <= attempt <= 100 or not 1 <= base <= maximum <= 3600:
        raise ValueError("Retry limits are outside bounded ranges")
    return min(maximum, base * (2 ** min(attempt - 1, 20)))


async def acquire_work(
    db: AsyncSession, message: WorkMessage, *, lease_seconds: int = 60
) -> WorkLease | None:
    """Caller owns commit. None means stale/duplicate/ineligible; no handler may run.

    Read IDs first, then lock installation -> job, matching the existing domain.
    Broker owner claims are never accepted. Lease storage remains ReviewAttempt.
    """
    if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
        raise ValueError("Lease must be 1..3600 seconds")
    outbox = await db.get(ReviewOutbox, message.outbox_id)
    if outbox is None or outbox.job_id != message.job_id or outbox.kind != "analyze":
        return None
    job = await db.get(ReviewJob, outbox.job_id)
    if job is None:
        return None
    installation = await db.scalar(
        select(GitHubInstallation)
        .where(
            GitHubInstallation.installation_id == job.installation_id,
            GitHubInstallation.owner_id == outbox.owner_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if installation is None:
        return None
    job = await db.scalar(
        select(ReviewJob)
        .where(ReviewJob.id == message.job_id, ReviewJob.owner_id == outbox.owner_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    outbox = await db.get(ReviewOutbox, message.outbox_id, populate_existing=True)
    if (
        job is None
        or outbox is None
        or job.dispatch_version != outbox.version
        or outbox.status not in {"pending", "dispatched"}
        or job.analysis_status != "queued"
    ):
        return None
    if installation.revoked_at is not None:
        await stop_analysis(
            db,
            job.owner_id,
            job.id,
            AnalysisStopped(
                status="cancelled",
                error=ReviewError(
                    code="installation_revoked",
                    message="Installation is revoked",
                    retryable=False,
                    request_id=uuid4(),
                ),
            ),
        )
        return None
    attempt = await begin_analysis(db, job.owner_id, job.id, lease_seconds=lease_seconds)
    return WorkLease(
        job.id,
        job.owner_id,
        attempt.id,
        attempt.number,
        job.max_attempts,
        attempt.lease_until,
        job.head_sha,
        ReviewPolicy.model_validate(job.policy),
    )


class WorkerOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    lease_seconds: int = Field(default=60, ge=1, le=3600)
    dispatch_lease_seconds: int = Field(default=30, ge=2, le=3600)
    broker_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    max_dispatch_attempts: int = Field(default=5, ge=1, le=100)
    retry_base_seconds: int = Field(default=1, ge=1, le=3600)
    retry_max_seconds: int = Field(default=300, ge=1, le=3600)
    poll_seconds: float = Field(default=1.0, gt=0, le=60)

    @model_validator(mode="after")
    def valid_windows(self) -> "WorkerOptions":
        if self.dispatch_lease_seconds <= self.broker_timeout_seconds:
            raise ValueError("Dispatch lease must exceed broker timeout")
        if self.retry_base_seconds > self.retry_max_seconds:
            raise ValueError("Retry base exceeds maximum")
        return self


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
Handler = Callable[[WorkLease], Awaitable[AnalysisResult]]
BudgetGate = Callable[[WorkLease], Awaitable[bool]]
Clock = Callable[[], datetime]
logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


async def deny_retry_budget(lease: WorkLease) -> bool:
    # No provider ledger exists in this slice; callers must explicitly prove a
    # retry's remaining budget. Never infer it from a crashed worker's silence.
    return False


@dataclass(frozen=True)
class DispatchClaim:
    message: WorkMessage
    token: UUID


class Dispatcher:
    def __init__(
        self,
        sessions: SessionFactory,
        broker: Broker,
        *,
        options: WorkerOptions | None = None,
        clock: Clock = utc_now,
    ):
        self.sessions = sessions
        self.broker = broker
        self.options = options or WorkerOptions()
        self.clock = clock

    async def claim_one(self) -> DispatchClaim | str | None:
        now = self.clock()
        async with self.sessions() as db:
            # A consumer can cancel an intent while its dispatcher crashes. Clear
            # only expired, non-pending claims; never change terminal status.
            await db.execute(
                update(ReviewOutbox)
                .where(
                    ReviewOutbox.id.in_(
                        select(ReviewOutbox.id)
                        .where(ReviewOutbox.status != "pending", ReviewOutbox.claim_until <= now)
                        .order_by(ReviewOutbox.claim_until, ReviewOutbox.id)
                        .with_for_update(skip_locked=True)
                        .limit(100)
                    )
                )
                .values(claim_token=None, claim_until=None)
            )
            await db.commit()
            row = await db.scalar(
                select(ReviewOutbox)
                .where(
                    ReviewOutbox.status == "pending",
                    ReviewOutbox.kind == "analyze",
                    ReviewOutbox.available_at <= now,
                    or_(ReviewOutbox.claim_until.is_(None), ReviewOutbox.claim_until <= now),
                )
                .order_by(ReviewOutbox.available_at, ReviewOutbox.created_at, ReviewOutbox.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if row is None:
                return None
            if row.dispatch_attempts >= self.options.max_dispatch_attempts:
                row.status = "failed"
                row.claim_token = row.claim_until = None
                row.last_error = "dispatch_retries_exhausted"
                outbox_id = row.id
                await db.commit()
                logger.warning("review_outbox_retry_exhausted", extra={"outbox_id": str(outbox_id)})
                return "failed"
            row.dispatch_attempts += 1
            row.claim_token = uuid4()
            row.claim_until = now + timedelta(seconds=self.options.dispatch_lease_seconds)
            claim = DispatchClaim(WorkMessage(job_id=row.job_id, outbox_id=row.id), row.claim_token)
            await db.commit()
            return claim

    async def settle(self, claim: DispatchClaim, *, published: bool) -> str:
        now = self.clock()
        async with self.sessions() as db:
            row = await db.scalar(
                select(ReviewOutbox)
                .where(ReviewOutbox.id == claim.message.outbox_id)
                .with_for_update()
            )
            if (
                row is None
                or row.claim_token != claim.token
                or row.claim_until is None
                or row.claim_until <= now
            ):
                return "stale"
            row.claim_token = row.claim_until = None
            if row.status != "pending":
                await db.commit()
                return "stale"
            if published:
                row.status = "dispatched"
                row.dispatched_at = now
                row.last_error = None
            else:
                row.last_error = "broker_failure"
                if row.dispatch_attempts >= self.options.max_dispatch_attempts:
                    row.status = "failed"
                else:
                    row.available_at = now + timedelta(
                        seconds=backoff_seconds(
                            row.dispatch_attempts,
                            base=self.options.retry_base_seconds,
                            maximum=self.options.retry_max_seconds,
                        )
                    )
            outcome = row.status
            await db.commit()
        if outcome == "failed":
            logger.warning(
                "review_outbox_retry_exhausted", extra={"outbox_id": str(claim.message.outbox_id)}
            )
        return outcome

    async def dispatch_once(self, *, limit: int = 25) -> dict[str, int]:
        _check_limit(limit)
        totals = {"dispatched": 0, "pending": 0, "failed": 0, "stale": 0}
        for _ in range(limit):
            # Claim just one entry before IO so a batch cannot consume its own
            # lease while waiting for earlier publications to finish.
            claim = await self.claim_one()
            if claim is None:
                break
            if isinstance(claim, str):
                totals[claim] += 1
                continue
            try:
                receipt = await asyncio.wait_for(
                    self.broker.publish(claim.message), self.options.broker_timeout_seconds
                )
                published = isinstance(receipt, str) and bool(receipt)
            except Exception:
                # Publication might have reached the broker despite the exception.
                # Retry the same task ID; the DB consumer fences any duplicates.
                published = False
            outcome = await self.settle(claim, published=published)
            totals[outcome] += 1
        return totals


def _check_limit(limit: int) -> None:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Batch limit must be 1..100")


def _failure(*, retryable: bool) -> ReviewError:
    return ReviewError(
        code="provider_failed",
        message="Review worker task failed",
        retryable=retryable,
        request_id=uuid4(),
    )


class RetryableWorkError(Exception):
    """A handler reports a transient failure; text is never logged or persisted."""


class Consumer:
    def __init__(
        self,
        sessions: SessionFactory,
        broker: Broker,
        handler: Handler,
        *,
        options: WorkerOptions | None = None,
        budget_gate: BudgetGate = deny_retry_budget,
    ):
        self.sessions = sessions
        self.broker = broker
        self.handler = handler
        self.options = options or WorkerOptions()
        self.budget_gate = budget_gate

    async def _budget(self, lease: WorkLease) -> bool:
        try:
            return await self.budget_gate(lease) is True
        except Exception:
            logger.warning("review_worker_budget_gate_failed", extra={"job_id": str(lease.job_id)})
            return False

    async def consume_once(self) -> str:
        receipt = await asyncio.wait_for(self.broker.receive(), self.options.broker_timeout_seconds)
        if receipt is None:
            return "idle"
        async with self.sessions() as db:
            lease = await acquire_work(
                db, receipt.message, lease_seconds=self.options.lease_seconds
            )
            await db.commit()
        if lease is None:
            await asyncio.wait_for(
                self.broker.acknowledge(receipt), self.options.broker_timeout_seconds
            )
            return "duplicate"
        failed = retryable = False
        result = None
        try:
            remaining = max(0.0, (lease.lease_expires_at - utc_now()).total_seconds())
            async with asyncio.timeout(remaining):
                result = await self.handler(lease)
        except Exception as error:
            failed = True
            retryable = isinstance(error, (RetryableWorkError, TimeoutError))
        can_retry = (
            failed and retryable and lease.number < lease.max_attempts and await self._budget(lease)
        )
        try:
            async with self.sessions() as db:
                if can_retry:
                    job = await retry_analysis(
                        db,
                        lease.owner_id,
                        lease.job_id,
                        lease.attempt_id,
                        _failure(retryable=True),
                        budget_available=True,
                    )
                    await _defer_retry(db, job, lease.number, self.options)
                    outcome = "retry"
                else:
                    if failed:
                        result = AnalysisStopped(status="failed", error=_failure(retryable=False))
                    assert result is not None
                    job = await finish_analysis(
                        db, lease.owner_id, lease.job_id, lease.attempt_id, result
                    )
                    outcome = job.analysis_status
                await db.commit()
        except (ReviewStateError, ReviewAccessDeniedError, ValidationError):
            # A reaper, revocation or a rejected result may fence this completion.
            # The committed lease remains recoverable; do not write through it.
            logger.warning("review_worker_result_rejected", extra={"job_id": str(lease.job_id)})
            outcome = "stale"
        if outcome == "failed":
            logger.warning(
                "review_worker_retry_stopped",
                extra={"job_id": str(lease.job_id), "attempt": lease.number},
            )
        await asyncio.wait_for(
            self.broker.acknowledge(receipt), self.options.broker_timeout_seconds
        )
        return outcome

    async def reap_once(self, *, limit: int = 25) -> int:
        _check_limit(limit)
        async with self.sessions() as db:
            rows = (
                await db.execute(
                    select(ReviewAttempt, ReviewJob)
                    .join(ReviewJob, ReviewJob.id == ReviewAttempt.job_id)
                    .where(
                        ReviewAttempt.status == "running", ReviewAttempt.lease_until <= utc_now()
                    )
                    .order_by(ReviewAttempt.lease_until, ReviewAttempt.id)
                    .limit(limit)
                )
            ).all()
            candidates = [
                (
                    WorkLease(
                        job.id,
                        job.owner_id,
                        attempt.id,
                        attempt.number,
                        job.max_attempts,
                        attempt.lease_until,
                        job.head_sha,
                        ReviewPolicy.model_validate(job.policy),
                    ),
                    attempt.kind,
                )
                for attempt, job in rows
            ]
        recovered = 0
        for lease, kind in candidates:
            allowed = (
                kind == "analysis"
                and lease.number < lease.max_attempts
                and await self._budget(lease)
            )
            try:
                async with self.sessions() as db:
                    job = await recover_expired_attempt(
                        db, lease.owner_id, lease.job_id, lease.attempt_id, budget_available=allowed
                    )
                    if kind == "analysis" and job.analysis_status == "queued":
                        await _defer_retry(db, job, lease.number, self.options)
                    terminal = kind == "analysis" and job.analysis_status == "failed"
                    await db.commit()
                recovered += 1
                if terminal:
                    logger.warning(
                        "review_worker_retry_stopped",
                        extra={"job_id": str(lease.job_id), "attempt": lease.number},
                    )
            except (ReviewStateError, ReviewAccessDeniedError):
                # Another reaper/completion won the installation->job->attempt lock.
                continue
        return recovered


async def _defer_retry(
    db: AsyncSession, job: ReviewJob, number: int, options: WorkerOptions
) -> None:
    row = await db.scalar(
        select(ReviewOutbox).where(
            ReviewOutbox.job_id == job.id, ReviewOutbox.version == job.dispatch_version
        )
    )
    assert row is not None
    row.available_at = utc_now() + timedelta(
        seconds=backoff_seconds(
            number, base=options.retry_base_seconds, maximum=options.retry_max_seconds
        )
    )


async def run_worker(dispatcher: Dispatcher, consumer: Consumer, stop: asyncio.Event) -> None:
    """One local async loop; durable claims survive cancellation/process death."""
    while not stop.is_set():
        try:
            await dispatcher.dispatch_once()
            await consumer.reap_once()
            await consumer.consume_once()
        except Exception:
            logger.warning("review_worker_iteration_failed")
        try:
            await asyncio.wait_for(stop.wait(), dispatcher.options.poll_seconds)
        except TimeoutError:
            continue
