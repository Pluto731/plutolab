"""Real PostgreSQL checks; only UUID-named disposable loopback databases.

Reuse Slice 2's restricted DB lifecycle, never conftest's shared pluto_test.
All provider/GitHub data is synthetic; no HTTP, broker or model calls are made.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from pydantic import ValidationError
from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from plutolab_api.db.base import Base
from plutolab_api.models.review import ReviewAttempt, ReviewDelivery, ReviewJob, ReviewOutbox
from plutolab_api.models.user import User
from plutolab_api.schemas.review import (
    AnalysisResult,
    AnalysisStopped,
    PublicationDraft,
    PublicationReceipt,
    PublicationUnknown,
    ReviewBudgets,
    ReviewCoverage,
    ReviewError,
    ReviewFinding,
    ReviewPolicy,
    ReviewUsage,
)
from plutolab_api.services.review.jobs import (
    EnqueueReview,
    ReviewStateError,
    begin_analysis,
    begin_publication,
    enqueue_review,
    finish_analysis,
    get_job,
    record_publication,
    recover_expired_attempt,
    retry_analysis,
    stop_analysis,
)
from plutolab_api.services.review.settings import (
    ReviewAccessDeniedError,
    ReviewConflictError,
    ReviewRules,
    create_installation,
    create_settings,
    replace_rules,
    revoke_installation,
)
from tests.test_review_domain import API_ROOT, disposable_database, migrate
from tests.test_review_domain import owners as owners
from tests.test_review_domain import review_db as review_db
from tests.test_review_domain import review_engine as review_engine

JOB_TABLES = {"review_jobs", "review_deliveries", "review_attempts", "review_outbox"}


def request(**overrides: object) -> EnqueueReview:
    values: dict[str, object] = {
        "installation_id": "301",
        "repo_id": "401",
        "pr_number": 7,
        "head_sha": "a" * 40,
        "delivery_id": str(uuid4()),
        "action": "opened",
        "max_attempts": 2,
        "policy": ReviewPolicy(
            rules_version=1,
            enabled=True,
            focus=["security", "performance", "quality"],
            skip_paths=[],
            provider="anthropic",
            model="local-test-model",
            publication_mode="comment",
            budgets=ReviewBudgets(
                max_files=10,
                min_changed_lines=1,
                max_changed_lines=1000,
                max_context_lines_per_file=30,
                max_chunks=10,
                context_window_tokens=2000,
                max_request_input_tokens=1500,
                reserved_output_tokens=500,
                max_total_input_tokens=5000,
                max_total_output_tokens=2000,
                max_findings=10,
                max_comments=10,
                max_cost_usd="1.000000",
                max_owner_daily_cost_usd="5.000000",
                token_count_mode="conservative_estimate",
            ),
        ),
    }
    values.update(overrides)
    return EnqueueReview.model_validate(values)


def failure(*, retryable: bool = False) -> ReviewError:
    return ReviewError(
        code="provider_failed", message="Synthetic failure", retryable=retryable, request_id=uuid4()
    )


def result(*, partial: bool = False) -> AnalysisResult:
    return AnalysisResult(
        status="partial" if partial else "analyzed",
        summary="Synthetic result",
        findings=[
            ReviewFinding(
                id=uuid4(),
                fingerprint="finding-1",
                focus="security",
                severity="HIGH",
                location={"path": "src/app.py", "line": 4, "side": "RIGHT"},
                description="Synthetic description",
                suggestion="Synthetic suggestion",
                evidence="Synthetic evidence",
            )
        ],
        coverage=ReviewCoverage(
            files_total=2,
            files_reviewed=1 if partial else 2,
            changed_lines_total=10,
            changed_lines_reviewed=5 if partial else 10,
            gaps=["missing patch"] if partial else [],
        ),
        usage=ReviewUsage(
            input_tokens=100,
            output_tokens=20,
            cost_usd="0.010000",
            token_count_mode="conservative_estimate",
        ),
    )


@pytest_asyncio.fixture
async def owner(review_db: AsyncSession, owners: tuple[User, User]) -> UUID:
    owner_id = owners[0].id
    await create_installation(review_db, owner_id, "301")
    await create_settings(
        review_db, owner_id, "301", "401", "owner/repo", rules=ReviewRules(enabled=True)
    )
    return owner_id


async def count(
    db: AsyncSession, model: type[ReviewJob] | type[ReviewDelivery] | type[ReviewOutbox]
) -> int:
    return await db.scalar(select(func.count()).select_from(model)) or 0


async def analyzed(
    db: AsyncSession, owner_id: UUID, *, req: EnqueueReview | None = None
) -> ReviewJob:
    job = (await enqueue_review(db, owner_id, req or request())).job
    attempt = await begin_analysis(db, owner_id, job.id, lease_seconds=60)
    return await finish_analysis(db, owner_id, job.id, attempt.id, result())


async def publishing(db: AsyncSession, owner_id: UUID) -> tuple[ReviewJob, ReviewAttempt]:
    job = await analyzed(db, owner_id)
    await record_publication(db, owner_id, job.id, PublicationDraft(status="preview_ready"))
    attempt = await begin_publication(
        db,
        owner_id,
        job.id,
        verified_head_sha=job.head_sha,
        verified_rules_version=job.rules_version,
        publication_authorized=True,
        lease_seconds=60,
    )
    return job, attempt


async def expire(db: AsyncSession, attempt: ReviewAttempt) -> None:
    attempt.started_at = datetime.now(UTC) - timedelta(seconds=120)
    attempt.lease_until = datetime.now(UTC) - timedelta(seconds=60)
    await db.flush()


async def test_delivery_and_job_deduplication(review_db: AsyncSession, owner: UUID) -> None:
    req = request()
    first = await enqueue_review(review_db, owner, req)
    duplicate = await enqueue_review(review_db, owner, req)
    another = await enqueue_review(review_db, owner, request(action="synchronize"))
    assert first.job_created and first.delivery_created
    assert not duplicate.job_created and not duplicate.delivery_created
    assert not another.job_created and another.delivery_created
    assert first.job.id == duplicate.job.id == another.job.id
    assert await count(review_db, ReviewJob) == 1
    assert await count(review_db, ReviewDelivery) == 2
    assert await count(review_db, ReviewOutbox) == 1
    assert first.job.analysis_status == "queued" and first.job.publication_status == "not_requested"


@pytest.mark.parametrize(
    "change", [{"head_sha": "b" * 40}, {"pr_number": 8}, {"action": "synchronize"}]
)
async def test_delivery_collision_rejected(
    review_db: AsyncSession, owner: UUID, change: dict[str, object]
) -> None:
    req = request()
    await enqueue_review(review_db, owner, req)
    with pytest.raises(ReviewConflictError):
        await enqueue_review(review_db, owner, request(delivery_id=req.delivery_id, **change))
    assert await count(review_db, ReviewJob) == 1


async def test_policy_snapshot_and_version_identity(review_db: AsyncSession, owner: UUID) -> None:
    req = request()
    first = (await enqueue_review(review_db, owner, req)).job
    updated = await replace_rules(
        review_db, owner, "301", "401", ReviewRules(enabled=True, min_pr_lines=2)
    )
    replay = await enqueue_review(review_db, owner, req)
    assert replay.job.id == first.id
    with pytest.raises(ReviewStateError, match="Stale"):
        await enqueue_review(review_db, owner, request())
    policy = req.policy.model_copy(deep=True)
    policy.rules_version = updated.rules_version
    policy.budgets.min_changed_lines = 2
    second = (await enqueue_review(review_db, owner, request(policy=policy))).job
    assert first.id != second.id
    assert first.policy["rules_version"] == 1


async def test_job_key_rejects_changed_immutable_policy(
    review_db: AsyncSession, owner: UUID
) -> None:
    req = request()
    await enqueue_review(review_db, owner, req)
    policy = req.policy.model_copy(update={"model": "different-model"})
    with pytest.raises(ReviewConflictError):
        await enqueue_review(review_db, owner, request(policy=policy))


@pytest.mark.parametrize(
    "change",
    [
        {"pr_number": True},
        {"pr_number": 0},
        {"pr_number": 2**31},
        {"head_sha": "bad"},
        {"delivery_id": "../bad"},
        {"event_type": "push"},
        {"action": "closed"},
        {"max_attempts": 0},
    ],
)
def test_invalid_enqueue_input(change: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        request(**change)


async def test_disabled_and_inconsistent_budget_rejected(
    review_db: AsyncSession, owner: UUID
) -> None:
    req = request()
    req.policy.budgets.reserved_output_tokens = 1000
    with pytest.raises(ReviewStateError, match="budget"):
        await enqueue_review(review_db, owner, req)
    await replace_rules(review_db, owner, "301", "401", ReviewRules(enabled=False))
    with pytest.raises(ReviewStateError, match="disabled"):
        await enqueue_review(review_db, owner, request())
    assert await count(review_db, ReviewJob) == 0


async def test_tenant_isolation_and_revocation(
    review_db: AsyncSession, owner: UUID, owners: tuple[User, User]
) -> None:
    job = (await enqueue_review(review_db, owner, request())).job
    other = owners[1].id
    for operation in (
        get_job(review_db, other, job.id),
        begin_analysis(review_db, other, job.id, lease_seconds=60),
        enqueue_review(review_db, other, request()),
    ):
        with pytest.raises(ReviewAccessDeniedError):
            await operation
    with pytest.raises(IntegrityError):
        async with review_db.begin_nested():
            review_db.add(ReviewOutbox(job_id=job.id, owner_id=other, version=2, kind="analyze"))
            await review_db.flush()
    await revoke_installation(review_db, owner, "301")
    with pytest.raises(ReviewAccessDeniedError):
        await begin_analysis(review_db, owner, job.id, lease_seconds=60)


@pytest.mark.parametrize("partial", [False, True])
async def test_result_persistence_and_no_implicit_publication(
    review_db: AsyncSession, owner: UUID, partial: bool
) -> None:
    job = (await enqueue_review(review_db, owner, request())).job
    attempt = await begin_analysis(review_db, owner, job.id, lease_seconds=60)
    payload = result(partial=partial)
    await finish_analysis(review_db, owner, job.id, attempt.id, payload)
    await review_db.refresh(job)
    assert job.analysis_status == payload.status
    assert job.findings == [finding.model_dump(mode="json") for finding in payload.findings]
    assert job.coverage == payload.coverage.model_dump(mode="json")
    assert job.usage == payload.usage.model_dump(mode="json")
    assert job.publication_status == "not_requested"
    assert attempt.status == "succeeded"
    with pytest.raises(ReviewStateError):
        await finish_analysis(review_db, owner, job.id, attempt.id, payload)


@pytest.mark.parametrize("bad", ["coverage", "partial", "path", "duplicate", "tokens", "cost"])
async def test_result_validation_leaves_attempt_usable(
    review_db: AsyncSession, owner: UUID, bad: str
) -> None:
    job = (await enqueue_review(review_db, owner, request())).job
    job_id = job.id
    attempt = await begin_analysis(review_db, owner, job_id, lease_seconds=60)
    attempt_id = attempt.id
    payload = result()
    if bad == "coverage":
        payload.coverage.files_reviewed = 3
    elif bad == "partial":
        payload.status = "partial"
    elif bad == "path":
        payload.findings[0].location.path = "../private"
    elif bad == "duplicate":
        payload.findings *= 2
    elif bad == "tokens":
        payload.usage.input_tokens = 5001
    else:
        payload.usage.cost_usd = "2.000000"
    with pytest.raises(ReviewStateError):
        await finish_analysis(review_db, owner, job_id, attempt_id, payload)
    valid = await finish_analysis(review_db, owner, job_id, attempt_id, result())
    assert valid.analysis_status == "analyzed"


async def test_illegal_transitions_and_terminal_failure(
    review_db: AsyncSession, owner: UUID
) -> None:
    job = (await enqueue_review(review_db, owner, request())).job
    job_id = job.id
    with pytest.raises(ReviewStateError):
        await record_publication(review_db, owner, job_id, PublicationDraft(status="preview_ready"))
    attempt = await begin_analysis(review_db, owner, job_id, lease_seconds=60)
    attempt_id = attempt.id
    with pytest.raises(ReviewStateError):
        await begin_analysis(review_db, owner, job_id, lease_seconds=60)
    await finish_analysis(
        review_db, owner, job_id, attempt_id, AnalysisStopped(status="failed", error=failure())
    )
    with pytest.raises(ReviewStateError):
        await begin_analysis(review_db, owner, job_id, lease_seconds=60)
    assert (await get_job(review_db, owner, job_id)).analysis_status == "failed"


async def test_bounded_retry_and_attempt_fencing(review_db: AsyncSession, owner: UUID) -> None:
    job_id = (await enqueue_review(review_db, owner, request())).job.id
    first_id = (await begin_analysis(review_db, owner, job_id, lease_seconds=60)).id
    with pytest.raises(ReviewStateError):
        await retry_analysis(review_db, owner, job_id, first_id, failure(), budget_available=True)
    with pytest.raises(ReviewStateError):
        await retry_analysis(
            review_db, owner, job_id, first_id, failure(retryable=True), budget_available=False
        )
    await retry_analysis(
        review_db, owner, job_id, first_id, failure(retryable=True), budget_available=True
    )
    second_id = (await begin_analysis(review_db, owner, job_id, lease_seconds=60)).id
    with pytest.raises(ReviewStateError):
        await finish_analysis(review_db, owner, job_id, first_id, result())
    with pytest.raises(ReviewStateError):
        await retry_analysis(
            review_db, owner, job_id, second_id, failure(retryable=True), budget_available=True
        )
    await finish_analysis(review_db, owner, job_id, second_id, result())
    assert await count(review_db, ReviewOutbox) == 2


@pytest.mark.parametrize(
    "budget_available,attempts,expected",
    [(True, 2, "queued"), (False, 2, "failed"), (True, 1, "failed")],
)
async def test_expired_analysis_recovery(
    review_db: AsyncSession, owner: UUID, budget_available: bool, attempts: int, expected: str
) -> None:
    job_id = (await enqueue_review(review_db, owner, request(max_attempts=attempts))).job.id
    attempt = await begin_analysis(review_db, owner, job_id, lease_seconds=60)
    attempt_id = attempt.id
    with pytest.raises(ReviewStateError):
        await recover_expired_attempt(
            review_db, owner, job_id, attempt_id, budget_available=budget_available
        )
    await expire(review_db, attempt)
    with pytest.raises(ReviewStateError):
        await finish_analysis(review_db, owner, job_id, attempt_id, result())
    recovered = await recover_expired_attempt(
        review_db, owner, job_id, attempt_id, budget_available=budget_available
    )
    assert recovered.analysis_status == expected
    with pytest.raises(ReviewStateError):
        await recover_expired_attempt(
            review_db, owner, job_id, attempt_id, budget_available=budget_available
        )


async def test_new_delivery_does_not_guess_head_order(review_db: AsyncSession, owner: UUID) -> None:
    first = (await enqueue_review(review_db, owner, request())).job
    later = (await enqueue_review(review_db, owner, request(head_sha="b" * 40))).job
    assert first.id != later.id and first.analysis_status == "queued"
    stopped = AnalysisStopped(
        status="superseded",
        error=ReviewError(
            code="stale_head", message="Head changed", retryable=False, request_id=uuid4()
        ),
    )
    first_id = first.id
    with pytest.raises(ReviewStateError):
        await stop_analysis(review_db, owner, first_id, stopped, verified_head_sha="a" * 40)
    await stop_analysis(review_db, owner, first_id, stopped, verified_head_sha="b" * 40)
    assert (await get_job(review_db, owner, first_id)).analysis_status == "superseded"
    assert (
        await review_db.scalar(select(ReviewOutbox.status).where(ReviewOutbox.job_id == first_id))
        == "cancelled"
    )


@pytest.mark.parametrize("status", ["skipped", "cancelled"])
async def test_stop_queued_job(review_db: AsyncSession, owner: UUID, status: str) -> None:
    job_id = (await enqueue_review(review_db, owner, request())).job.id
    stopped = AnalysisStopped.model_validate({"status": status, "error": failure().model_dump()})
    job = await stop_analysis(review_db, owner, job_id, stopped)
    assert job.analysis_status == status and job.publication_status == "blocked"


async def test_unknown_publication_requires_reconciliation(
    review_db: AsyncSession, owner: UUID
) -> None:
    job, attempt = await publishing(review_db, owner)
    job_id, attempt_id = job.id, attempt.id
    await expire(review_db, attempt)
    await recover_expired_attempt(review_db, owner, job_id, attempt_id)
    assert (await get_job(review_db, owner, job_id)).publication_status == "publish_unknown"
    with pytest.raises(ReviewStateError):
        await begin_publication(
            review_db,
            owner,
            job_id,
            verified_head_sha="a" * 40,
            verified_rules_version=1,
            publication_authorized=True,
            lease_seconds=60,
        )
    with pytest.raises(ReviewStateError):
        await record_publication(review_db, owner, job_id, PublicationDraft(status="preview_ready"))
    receipt = PublicationReceipt(
        status="published",
        attempt_id=attempt_id,
        head_sha="a" * 40,
        github_review_ids=["999"],
        confirmed_at=datetime.now(UTC),
    )
    await record_publication(review_db, owner, job_id, receipt)
    assert (await get_job(review_db, owner, job_id)).publication["github_review_ids"] == ["999"]
    assert (
        await review_db.scalar(
            select(func.count()).select_from(ReviewOutbox).where(ReviewOutbox.status == "pending")
        )
        == 0
    )


async def test_confirmed_no_write_allows_preview_retry(
    review_db: AsyncSession, owner: UUID
) -> None:
    job, attempt = await publishing(review_db, owner)
    await record_publication(
        review_db,
        owner,
        job.id,
        PublicationUnknown(
            status="publish_unknown",
            attempt_id=attempt.id,
            head_sha=job.head_sha,
            error=ReviewError(
                code="publication_unknown",
                message="Response lost",
                retryable=False,
                request_id=uuid4(),
            ),
        ),
    )
    await record_publication(
        review_db, owner, job.id, PublicationDraft(status="preview_ready"), confirmed_no_write=True
    )
    retried = await begin_publication(
        review_db,
        owner,
        job.id,
        verified_head_sha=job.head_sha,
        verified_rules_version=1,
        publication_authorized=True,
        lease_seconds=60,
    )
    assert retried.number == 2


@pytest.mark.parametrize("bad", ["head", "rules", "authorization", "preview_only", "revoked"])
async def test_publication_guards(review_db: AsyncSession, owner: UUID, bad: str) -> None:
    req = request()
    if bad == "preview_only":
        req.policy.publication_mode = "preview_only"
    job = await analyzed(review_db, owner, req=req)
    await record_publication(review_db, owner, job.id, PublicationDraft(status="preview_ready"))
    if bad == "revoked":
        await revoke_installation(review_db, owner, "301")
    with pytest.raises((ReviewStateError, ReviewAccessDeniedError)):
        await begin_publication(
            review_db,
            owner,
            job.id,
            verified_head_sha="b" * 40 if bad == "head" else job.head_sha,
            verified_rules_version=2 if bad == "rules" else 1,
            publication_authorized=bad != "authorization",
            lease_seconds=60,
        )


async def test_partial_receipt_and_superseded_receipt_retention(
    review_db: AsyncSession, owner: UUID
) -> None:
    job, attempt = await publishing(review_db, owner)
    await record_publication(
        review_db,
        owner,
        job.id,
        PublicationReceipt(
            status="partially_published",
            attempt_id=attempt.id,
            head_sha=job.head_sha,
            github_review_ids=["901"],
            confirmed_at=datetime.now(UTC),
        ),
    )
    stopped = AnalysisStopped(
        status="superseded",
        error=ReviewError(
            code="stale_head", message="New head", retryable=False, request_id=uuid4()
        ),
    )
    await stop_analysis(review_db, owner, job.id, stopped, verified_head_sha="b" * 40)
    assert job.publication_status == "partially_published" and job.publication[
        "github_review_ids"
    ] == ["901"]
    with pytest.raises(ReviewStateError):
        await begin_publication(
            review_db,
            owner,
            job.id,
            verified_head_sha="b" * 40,
            verified_rules_version=1,
            publication_authorized=True,
            lease_seconds=60,
        )


async def test_supersede_inflight_publication_preserves_unknown(
    review_db: AsyncSession, owner: UUID
) -> None:
    job, attempt = await publishing(review_db, owner)
    await stop_analysis(
        review_db,
        owner,
        job.id,
        AnalysisStopped(
            status="superseded",
            error=ReviewError(
                code="stale_head", message="New head", retryable=False, request_id=uuid4()
            ),
        ),
        verified_head_sha="b" * 40,
    )
    assert job.publication_status == "publish_unknown" and attempt.status == "unknown"
    assert (
        await review_db.scalar(
            select(ReviewOutbox.kind).where(
                ReviewOutbox.job_id == job.id, ReviewOutbox.status == "pending"
            )
        )
        == "reconcile_publication"
    )


async def test_job_and_outbox_rollback_on_insert_failure(
    review_db: AsyncSession, owner: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = ReviewOutbox.__init__

    def fail_outbox(self: ReviewOutbox, **kwargs: object) -> None:
        original(self, **kwargs)
        self.kind = "invalid-kind"

    with monkeypatch.context() as patch:
        patch.setattr(ReviewOutbox, "__init__", fail_outbox)
        with pytest.raises(IntegrityError):
            await enqueue_review(review_db, owner, request())
    assert await count(review_db, ReviewJob) == 0
    assert await count(review_db, ReviewDelivery) == 0
    assert await count(review_db, ReviewOutbox) == 0
    assert (await enqueue_review(review_db, owner, request())).job_created


async def test_retry_outbox_failure_rolls_back_state(
    review_db: AsyncSession, owner: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = (await enqueue_review(review_db, owner, request())).job.id
    attempt_id = (await begin_analysis(review_db, owner, job_id, lease_seconds=60)).id
    original = ReviewOutbox.__init__

    def fail_outbox(self: ReviewOutbox, **kwargs: object) -> None:
        original(self, **kwargs)
        self.kind = "invalid-kind"

    with monkeypatch.context() as patch:
        patch.setattr(ReviewOutbox, "__init__", fail_outbox)
        with pytest.raises(IntegrityError):
            await retry_analysis(
                review_db, owner, job_id, attempt_id, failure(retryable=True), budget_available=True
            )
    assert (await get_job(review_db, owner, job_id)).analysis_status == "processing"
    await finish_analysis(review_db, owner, job_id, attempt_id, result())


async def seed(engine: AsyncEngine) -> UUID:
    async with AsyncSession(engine, expire_on_commit=False) as db:
        user = User(email=f"{uuid4()}@jobs.test")
        db.add(user)
        await db.flush()
        await create_installation(db, user.id, "301")
        await create_settings(
            db, user.id, "301", "401", "owner/repo", rules=ReviewRules(enabled=True)
        )
        await db.commit()
        return user.id


@pytest.mark.parametrize("same_delivery", [True, False])
async def test_concurrent_delivery_and_job_suppression(same_delivery: bool) -> None:
    async with disposable_database() as url:
        migrate(url, "upgrade", "head")
        engine = create_async_engine(url)
        try:
            owner_id = await seed(engine)
            req = request()

            async def submit(value: EnqueueReview) -> tuple[UUID, bool]:
                async with AsyncSession(engine) as db:
                    outcome = await enqueue_review(db, owner_id, value)
                    identity = outcome.job.id
                    await db.commit()
                    return identity, outcome.job_created

            outcomes = await asyncio.gather(
                submit(req), submit(req if same_delivery else request())
            )
            assert outcomes[0][0] == outcomes[1][0]
            assert sum(created for _, created in outcomes) == 1
            async with AsyncSession(engine) as db:
                assert await count(db, ReviewOutbox) == 1
                assert await count(db, ReviewDelivery) == (1 if same_delivery else 2)
        finally:
            await engine.dispose()


async def test_caller_rollback_and_cross_session_commit_visibility() -> None:
    async with disposable_database() as url:
        migrate(url, "upgrade", "head")
        engine = create_async_engine(url)
        try:
            owner_id = await seed(engine)
            async with AsyncSession(engine) as writer, AsyncSession(engine) as reader:
                await enqueue_review(writer, owner_id, request())
                assert await count(reader, ReviewJob) == await count(reader, ReviewOutbox) == 0
                await writer.rollback()
                assert await count(reader, ReviewJob) == await count(reader, ReviewDelivery) == 0
                await enqueue_review(writer, owner_id, request())
                await writer.commit()
                assert await count(reader, ReviewJob) == await count(reader, ReviewOutbox) == 1
        finally:
            await engine.dispose()


async def test_migration_round_trip_and_metadata() -> None:
    async with disposable_database() as url:
        migrate(url, "upgrade", "0013")
        engine = create_async_engine(url)
        try:
            # Seed the historical schema without using today's expanded ORM fields.
            owner_id = uuid4()
            async with engine.begin() as conn:
                await conn.execute(
                    text("INSERT INTO users (id, email) VALUES (:id, 'legacy@jobs.test')"),
                    {"id": owner_id},
                )
                await conn.execute(
                    text(
                        "INSERT INTO github_installations (installation_id, owner_id) VALUES ('301', :id)"
                    ),
                    {"id": owner_id},
                )
                await conn.execute(
                    text(
                        "INSERT INTO review_settings (installation_id, owner_id, repo_id, repo_name, enabled) VALUES ('301', :id, '401', 'owner/repo', true)"
                    ),
                    {"id": owner_id},
                )
            migrate(url, "upgrade", "head")

            def check(sync: Connection) -> None:
                assert set(inspect(sync).get_table_names()) >= JOB_TABLES
                context = MigrationContext.configure(
                    sync,
                    opts={
                        "include_object": lambda obj, name, kind, reflected, compare: (
                            kind != "table" or name in JOB_TABLES
                        ),
                        "compare_server_default": True,
                    },
                )
                assert compare_metadata(context, Base.metadata) == []

            async with engine.connect() as conn:
                await conn.run_sync(check)
                assert (
                    await conn.scalar(text("SELECT version_num FROM alembic_version"))
                    == ScriptDirectory(str(API_ROOT / "alembic")).get_current_head()
                )
            async with AsyncSession(engine) as db:
                await enqueue_review(db, owner_id, request())
                await db.commit()
            migrate(url, "downgrade", "0013")
            async with engine.connect() as conn:
                tables = await conn.run_sync(lambda sync: set(inspect(sync).get_table_names()))
                assert not JOB_TABLES & tables
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM review_settings WHERE repo_id='401'")
                    )
                    == 1
                )
                assert (
                    await conn.scalar(
                        text(
                            "SELECT count(*) FROM github_installations WHERE installation_id='301'"
                        )
                    )
                    == 1
                )
                assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == "0013"
            migrate(url, "upgrade", "head")
            async with engine.connect() as conn:
                await conn.run_sync(check)
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM users WHERE id=:id"), {"id": owner_id}
                    )
                    == 1
                )
        finally:
            await engine.dispose()


async def test_superseded_worker_cannot_write_results(review_db: AsyncSession, owner: UUID) -> None:
    job_id = (await enqueue_review(review_db, owner, request())).job.id
    attempt_id = (await begin_analysis(review_db, owner, job_id, lease_seconds=60)).id
    await stop_analysis(
        review_db,
        owner,
        job_id,
        AnalysisStopped(
            status="superseded",
            error=ReviewError(
                code="stale_head",
                message="Verified new head",
                retryable=False,
                request_id=uuid4(),
            ),
        ),
        verified_head_sha="b" * 40,
    )
    with pytest.raises(ReviewStateError):
        await finish_analysis(review_db, owner, job_id, attempt_id, result())
    job = await get_job(review_db, owner, job_id)
    assert job.analysis_status == "superseded" and job.findings == []


async def test_revoked_expired_attempt_fails_without_requeue(
    review_db: AsyncSession, owner: UUID
) -> None:
    job_id = (await enqueue_review(review_db, owner, request())).job.id
    attempt = await begin_analysis(review_db, owner, job_id, lease_seconds=60)
    await expire(review_db, attempt)
    await revoke_installation(review_db, owner, "301")
    job = await recover_expired_attempt(review_db, owner, job_id, attempt.id, budget_available=True)
    assert job.analysis_status == "failed"
    assert await count(review_db, ReviewOutbox) == 1


@pytest.mark.parametrize("bad", ["head", "attempt", "naive_time", "duplicate_ids"])
async def test_publication_receipt_validation(
    review_db: AsyncSession, owner: UUID, bad: str
) -> None:
    job, attempt = await publishing(review_db, owner)
    job_id, attempt_id = job.id, attempt.id
    value = PublicationReceipt(
        status="published",
        attempt_id=uuid4() if bad == "attempt" else attempt_id,
        head_sha="b" * 40 if bad == "head" else "a" * 40,
        github_review_ids=["901", "901"] if bad == "duplicate_ids" else ["901"],
        confirmed_at=datetime.now() if bad == "naive_time" else datetime.now(UTC),
    )
    with pytest.raises(ReviewStateError):
        await record_publication(review_db, owner, job_id, value)
    assert (await get_job(review_db, owner, job_id)).publication_status == "publishing"


async def test_receipts_survive_unknown_and_next_attempt(
    review_db: AsyncSession, owner: UUID
) -> None:
    job, attempt = await publishing(review_db, owner)
    job_id, attempt_id = job.id, attempt.id
    await record_publication(
        review_db,
        owner,
        job_id,
        PublicationReceipt(
            status="partially_published",
            attempt_id=attempt_id,
            head_sha="a" * 40,
            github_review_ids=["901"],
            confirmed_at=datetime.now(UTC),
        ),
    )
    await record_publication(
        review_db,
        owner,
        job_id,
        PublicationUnknown(
            status="publish_unknown",
            attempt_id=attempt_id,
            head_sha="a" * 40,
            error=ReviewError(
                code="publication_unknown",
                message="Unknown remainder",
                retryable=False,
                request_id=uuid4(),
            ),
        ),
    )
    await review_db.refresh(attempt)
    assert attempt.evidence is not None
    assert attempt.evidence["receipt"]["github_review_ids"] == ["901"]
    with pytest.raises(ReviewStateError, match="contradicts"):
        await record_publication(
            review_db,
            owner,
            job_id,
            PublicationDraft(status="preview_ready"),
            confirmed_no_write=True,
        )
    with pytest.raises(ReviewStateError, match="discard"):
        await record_publication(
            review_db,
            owner,
            job_id,
            PublicationReceipt(
                status="published",
                attempt_id=attempt_id,
                head_sha="a" * 40,
                github_review_ids=["902"],
                confirmed_at=datetime.now(UTC),
            ),
        )
    await record_publication(
        review_db,
        owner,
        job_id,
        PublicationReceipt(
            status="partially_published",
            attempt_id=attempt_id,
            head_sha="a" * 40,
            github_review_ids=["901", "902"],
            confirmed_at=datetime.now(UTC),
        ),
    )
    next_attempt = await begin_publication(
        review_db,
        owner,
        job_id,
        verified_head_sha="a" * 40,
        verified_rules_version=1,
        publication_authorized=True,
        lease_seconds=60,
    )
    await review_db.refresh(attempt)
    assert next_attempt.id != attempt.id
    assert attempt.evidence["receipt"]["github_review_ids"] == ["901", "902"]


async def test_database_identity_and_status_constraints(
    review_db: AsyncSession, owner: UUID
) -> None:
    job = (await enqueue_review(review_db, owner, request())).job
    job_id = job.id
    with pytest.raises(IntegrityError):
        async with review_db.begin_nested():
            await review_db.execute(
                text("UPDATE review_jobs SET analysis_status='invalid' WHERE id=:id"),
                {"id": job_id},
            )
    with pytest.raises(IntegrityError):
        async with review_db.begin_nested():
            await review_db.execute(
                text(
                    "INSERT INTO review_jobs (owner_id, installation_id, repo_id, pr_number, head_sha, "
                    "rules_version, provider, policy, max_attempts) "
                    "SELECT owner_id, installation_id, repo_id, pr_number, head_sha, rules_version, "
                    "provider, policy, max_attempts FROM review_jobs WHERE id=:id"
                ),
                {"id": job_id},
            )
    assert await count(review_db, ReviewJob) == 1
