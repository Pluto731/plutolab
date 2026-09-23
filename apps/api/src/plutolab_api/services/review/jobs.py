"""Local durable review state. Callers authenticate owners and own commit/rollback.

Webhook signatures, repository membership and current remote head must be verified
by future adapters. No network, broker, scheduler or provider is invoked here.
Every mutation uses a savepoint so a rejected operation leaves the caller usable.
Lock order is installation -> job -> attempt, shared with settings/revocation.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.models.review import ReviewAttempt, ReviewDelivery, ReviewJob, ReviewOutbox
from plutolab_api.schemas.review import (
    ANALYSIS_TRANSITIONS,
    PUBLICATION_TRANSITIONS,
    AnalysisResult,
    AnalysisStatus,
    AnalysisStopped,
    HeadSha,
    Publication,
    PublicationReceipt,
    PublicationStatus,
    PublicationUnknown,
    ReviewError,
    ReviewPolicy,
)
from plutolab_api.services.review.settings import (
    GitHubId,
    ReviewAccessDeniedError,
    ReviewConflictError,
    get_installation,
    get_settings,
)


class ReviewStateError(ValueError):
    """Invalid transition, stale attempt or invalid recovery evidence."""


class EnqueueReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    installation_id: GitHubId
    repo_id: GitHubId
    pr_number: int = Field(gt=0, le=2_147_483_647)
    head_sha: HeadSha
    delivery_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9-]{1,128}$")]
    event_type: Literal["pull_request"] = "pull_request"
    action: Literal["opened", "synchronize", "reopened"]
    policy: ReviewPolicy
    max_attempts: int = Field(gt=0, le=100)


@dataclass(frozen=True)
class EnqueueResult:
    job: ReviewJob
    delivery_created: bool
    job_created: bool


def _edge(current: str, target: str, *, publication: bool = False) -> None:
    if publication:
        state = TypeAdapter(PublicationStatus).validate_python(current)
        allowed = PUBLICATION_TRANSITIONS[state]
    else:
        state = TypeAdapter(AnalysisStatus).validate_python(current)
        allowed = ANALYSIS_TRANSITIONS[state]
    if target not in allowed:
        raise ReviewStateError(f"Invalid {'publication' if publication else 'analysis'} transition")


def _error(
    code: Literal["provider_failed", "stale_head", "publication_unknown"],
    *,
    retryable: bool = False,
) -> ReviewError:
    return ReviewError(code=code, message=code, retryable=retryable, request_id=uuid4())


async def get_job(db: AsyncSession, owner_id: UUID, job_id: UUID) -> ReviewJob:
    job = await db.scalar(
        select(ReviewJob)
        .where(ReviewJob.id == job_id, ReviewJob.owner_id == owner_id)
        .execution_options(populate_existing=True)
    )
    if job is None:
        raise ReviewAccessDeniedError("Review job unavailable")
    return job


async def _locked_job(
    db: AsyncSession, owner_id: UUID, job_id: UUID, *, active: bool = False
) -> ReviewJob:
    job = await get_job(db, owner_id, job_id)
    await get_installation(db, owner_id, job.installation_id, active=active, lock=True)
    locked = await db.scalar(
        select(ReviewJob)
        .where(ReviewJob.id == job_id, ReviewJob.owner_id == owner_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked is None:
        raise ReviewAccessDeniedError("Review job unavailable")
    return locked


def _validate_policy(policy: ReviewPolicy) -> None:
    budget = policy.budgets
    if (
        budget.min_changed_lines > budget.max_changed_lines
        or budget.max_request_input_tokens + budget.reserved_output_tokens
        > budget.context_window_tokens
        or budget.max_request_input_tokens > budget.max_total_input_tokens
        or budget.reserved_output_tokens > budget.max_total_output_tokens
        or Decimal(budget.max_cost_usd) > Decimal(budget.max_owner_daily_cost_usd)
        or policy.rules_version > 2_147_483_647
    ):
        raise ReviewStateError("Inconsistent review budget or rules version")


async def enqueue_review(db: AsyncSession, owner_id: UUID, request: EnqueueReview) -> EnqueueResult:
    request = EnqueueReview.model_validate(request.model_dump())
    _validate_policy(request.policy)
    try:
        async with db.begin_nested():
            await get_installation(db, owner_id, request.installation_id, active=True, lock=True)
            existing_delivery = await db.get(ReviewDelivery, request.delivery_id)
            if existing_delivery is not None:
                if existing_delivery.job_id is None:
                    raise ReviewConflictError("Delivery was already ignored")
                job = await get_job(db, owner_id, existing_delivery.job_id)
                if (
                    existing_delivery.owner_id != owner_id
                    or existing_delivery.event_type != request.event_type
                    or existing_delivery.action != request.action
                    or (job.installation_id, job.repo_id, job.pr_number, job.head_sha)
                    != (
                        request.installation_id,
                        request.repo_id,
                        request.pr_number,
                        request.head_sha,
                    )
                ):
                    raise ReviewConflictError("Delivery identity already used")
                # The original policy snapshot wins even if settings have changed.
                return EnqueueResult(job, False, False)
            settings = await get_settings(db, owner_id, request.installation_id, request.repo_id)
            policy = request.policy
            if not settings.enabled or not policy.enabled:
                raise ReviewStateError("Review is disabled")
            if (
                settings.rules_version != policy.rules_version
                or settings.focus != policy.focus
                or settings.skip_paths != policy.skip_paths
                or settings.min_pr_lines != policy.budgets.min_changed_lines
                or (
                    settings.max_pr_lines is not None
                    and policy.budgets.max_changed_lines > settings.max_pr_lines
                )
            ):
                raise ReviewStateError("Stale repository policy")
            job = await db.scalar(
                select(ReviewJob).where(
                    ReviewJob.owner_id == owner_id,
                    ReviewJob.installation_id == request.installation_id,
                    ReviewJob.repo_id == request.repo_id,
                    ReviewJob.pr_number == request.pr_number,
                    ReviewJob.head_sha == request.head_sha,
                    ReviewJob.rules_version == policy.rules_version,
                    ReviewJob.provider == policy.provider,
                )
            )
            created = job is None
            if job is None:
                job = ReviewJob(
                    owner_id=owner_id,
                    installation_id=request.installation_id,
                    repo_id=request.repo_id,
                    pr_number=request.pr_number,
                    head_sha=request.head_sha,
                    rules_version=policy.rules_version,
                    provider=policy.provider,
                    policy=policy.model_dump(mode="json"),
                    max_attempts=request.max_attempts,
                )
                db.add(job)
                await db.flush()
                db.add(ReviewOutbox(job_id=job.id, owner_id=owner_id, version=1, kind="analyze"))
            elif (
                job.policy != policy.model_dump(mode="json")
                or job.max_attempts != request.max_attempts
            ):
                raise ReviewConflictError("Job identity has a different immutable policy")
            db.add(
                ReviewDelivery(
                    delivery_id=request.delivery_id,
                    owner_id=owner_id,
                    job_id=job.id,
                    event_type=request.event_type,
                    action=request.action,
                )
            )
            await db.flush()
            return EnqueueResult(job, True, created)
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise ReviewConflictError("Review identity already used") from exc
        raise


async def _cancel_pending(db: AsyncSession, job: ReviewJob, *, kind: str | None = None) -> None:
    statement = update(ReviewOutbox).where(
        ReviewOutbox.job_id == job.id, ReviewOutbox.status == "pending"
    )
    if kind is not None:
        statement = statement.where(ReviewOutbox.kind == kind)
    await db.execute(statement.values(status="cancelled"))


async def _intent(
    db: AsyncSession, job: ReviewJob, kind: Literal["analyze", "reconcile_publication"]
) -> None:
    await _cancel_pending(db, job, kind=kind)
    job.dispatch_version += 1
    db.add(
        ReviewOutbox(job_id=job.id, owner_id=job.owner_id, version=job.dispatch_version, kind=kind)
    )


async def _new_attempt(
    db: AsyncSession, job: ReviewJob, kind: Literal["analysis", "publication"], lease_seconds: int
) -> ReviewAttempt:
    if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
        raise ReviewStateError("Lease must be 1..3600 seconds")
    count = await db.scalar(
        select(func.count())
        .select_from(ReviewAttempt)
        .where(
            ReviewAttempt.job_id == job.id,
            ReviewAttempt.kind == kind,
        )
    )
    number = (count or 0) + 1
    if number > job.max_attempts:
        raise ReviewStateError("Attempt budget exhausted")
    now = datetime.now(UTC)
    attempt = ReviewAttempt(
        job_id=job.id,
        owner_id=job.owner_id,
        kind=kind,
        number=number,
        head_sha=job.head_sha,
        started_at=now,
        lease_until=now + timedelta(seconds=lease_seconds),
    )
    db.add(attempt)
    await db.flush()
    return attempt


async def _attempt(
    db: AsyncSession, job: ReviewJob, attempt_id: UUID, kind: str, *, expired: bool = False
) -> ReviewAttempt:
    attempt = await db.scalar(
        select(ReviewAttempt)
        .where(
            ReviewAttempt.id == attempt_id,
            ReviewAttempt.job_id == job.id,
            ReviewAttempt.owner_id == job.owner_id,
            ReviewAttempt.kind == kind,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = datetime.now(UTC)
    if attempt is None or attempt.status != "running":
        raise ReviewStateError("Attempt is stale or unavailable")
    if (attempt.lease_until <= now) != expired:
        raise ReviewStateError("Attempt lease does not permit this operation")
    return attempt


async def begin_analysis(
    db: AsyncSession, owner_id: UUID, job_id: UUID, *, lease_seconds: int
) -> ReviewAttempt:
    async with db.begin_nested():
        job = await _locked_job(db, owner_id, job_id, active=True)
        _edge(job.analysis_status, "processing")
        attempt = await _new_attempt(db, job, "analysis", lease_seconds)
        job.analysis_status = "processing"
        await _cancel_pending(db, job, kind="analyze")
        await db.flush()
        return attempt


def _validate_result(job: ReviewJob, result: AnalysisResult) -> None:
    coverage = result.coverage
    policy = ReviewPolicy.model_validate(job.policy)
    budget = policy.budgets
    if (
        coverage.files_reviewed > coverage.files_total
        or coverage.changed_lines_reviewed > coverage.changed_lines_total
        or coverage.files_reviewed > budget.max_files
        or coverage.changed_lines_reviewed > budget.max_changed_lines
        or len(result.findings) > budget.max_findings
        or result.usage.input_tokens > budget.max_total_input_tokens
        or result.usage.output_tokens > budget.max_total_output_tokens
        or Decimal(result.usage.cost_usd) > Decimal(budget.max_cost_usd)
        or result.usage.token_count_mode != budget.token_count_mode
    ):
        raise ReviewStateError("Result exceeds coverage or budget bounds")
    incomplete = (
        bool(coverage.gaps)
        or coverage.files_reviewed < coverage.files_total
        or coverage.changed_lines_reviewed < coverage.changed_lines_total
    )
    if (result.status == "partial") != incomplete:
        raise ReviewStateError("Coverage must explain partial versus analyzed status")
    if len({finding.fingerprint for finding in result.findings}) != len(result.findings) or len(
        {finding.id for finding in result.findings}
    ) != len(result.findings):
        raise ReviewStateError("Duplicate finding")
    for finding in result.findings:
        path = finding.location.path
        if (
            path.startswith("/")
            or "\\" in path
            or ":" in path
            or not path.isprintable()
            or any(part in {"", ".", ".."} for part in path.split("/"))
            or finding.focus not in policy.focus
        ):
            raise ReviewStateError("Invalid finding location or focus")
    if result.verified_diff is not None:
        if result.verified_diff.head_sha != job.head_sha:
            raise ReviewStateError("Verified diff head does not match the review job")
        findings_by_id = {str(finding.id): finding for finding in result.findings}
        if not set(result.verified_diff.findings).issubset(findings_by_id):
            raise ReviewStateError("Verified diff contains an unknown finding")
        for finding_id, position in result.verified_diff.findings.items():
            location = findings_by_id[finding_id].location
            if (position.path, position.line, position.side) != (
                location.path,
                location.line,
                location.side,
            ):
                raise ReviewStateError("Verified diff location does not match its finding")


async def finish_analysis(
    db: AsyncSession,
    owner_id: UUID,
    job_id: UUID,
    attempt_id: UUID,
    result: AnalysisResult | AnalysisStopped,
) -> ReviewJob:
    result = TypeAdapter(AnalysisResult | AnalysisStopped).validate_python(result.model_dump())
    if isinstance(result, AnalysisStopped) and result.status != "failed":
        raise ReviewStateError("Use stop_analysis for cancellation or supersession")
    async with db.begin_nested():
        job = await _locked_job(db, owner_id, job_id, active=True)
        _edge(job.analysis_status, result.status)
        attempt = await _attempt(db, job, attempt_id, "analysis")
        if isinstance(result, AnalysisResult):
            _validate_result(job, result)
            job.findings = [finding.model_dump(mode="json") for finding in result.findings]
            job.verified_diff = (
                result.verified_diff.model_dump(mode="json")
                if result.verified_diff is not None
                else None
            )
            job.coverage = result.coverage.model_dump(mode="json")
            job.usage = result.usage.model_dump(mode="json")
            job.summary = result.summary
            job.error = None
            attempt.status = "succeeded"
        else:
            job.error = result.error.model_dump(mode="json")
            attempt.status = "failed"
        attempt.finished_at = datetime.now(UTC)
        job.analysis_status = result.status
        await db.flush()
        return job


async def retry_analysis(
    db: AsyncSession,
    owner_id: UUID,
    job_id: UUID,
    attempt_id: UUID,
    error: ReviewError,
    *,
    budget_available: bool,
) -> ReviewJob:
    error = ReviewError.model_validate(error.model_dump())
    async with db.begin_nested():
        job = await _locked_job(db, owner_id, job_id, active=True)
        _edge(job.analysis_status, "queued")
        attempt = await _attempt(db, job, attempt_id, "analysis")
        if (
            not error.retryable
            or budget_available is not True
            or attempt.number >= job.max_attempts
        ):
            raise ReviewStateError("Retry is not permitted")
        attempt.status = "failed"
        attempt.finished_at = datetime.now(UTC)
        job.analysis_status = "queued"
        job.error = error.model_dump(mode="json")
        await _intent(db, job, "analyze")
        await db.flush()
        return job


async def _unknown_publication(db: AsyncSession, job: ReviewJob, attempt: ReviewAttempt) -> None:
    _edge(job.publication_status, "publish_unknown", publication=True)
    value = PublicationUnknown(
        status="publish_unknown",
        attempt_id=attempt.id,
        head_sha=job.head_sha,
        error=_error("publication_unknown"),
    )
    job.publication_status = value.status
    job.publication = value.model_dump(mode="json")
    _publication_evidence(attempt, value)
    attempt.status = "unknown"
    attempt.finished_at = datetime.now(UTC)
    await _intent(db, job, "reconcile_publication")


def _publication_evidence(
    attempt: ReviewAttempt, value: PublicationReceipt | PublicationUnknown
) -> None:
    """Keep confirmed IDs even when a partial attempt later becomes unknown."""
    evidence = dict(attempt.evidence or {})
    evidence["outcome"] = value.model_dump(mode="json")
    if isinstance(value, PublicationReceipt):
        previous = evidence.get("receipt")
        if isinstance(previous, dict):
            receipt = PublicationReceipt.model_validate(previous)
            if not set(receipt.github_review_ids) <= set(value.github_review_ids):
                raise ReviewStateError("Receipt cannot discard previously confirmed IDs")
        evidence["receipt"] = value.model_dump(mode="json")
    attempt.evidence = evidence


async def stop_analysis(
    db: AsyncSession,
    owner_id: UUID,
    job_id: UUID,
    result: AnalysisStopped,
    *,
    verified_head_sha: str | None = None,
) -> ReviewJob:
    result = AnalysisStopped.model_validate(result.model_dump())
    if result.status not in {"cancelled", "skipped", "superseded"}:
        raise ReviewStateError("Failure requires an active attempt")
    async with db.begin_nested():
        job = await _locked_job(db, owner_id, job_id)
        _edge(job.analysis_status, result.status)
        if result.status == "superseded":
            head = TypeAdapter(HeadSha).validate_python(verified_head_sha)
            if head == job.head_sha or result.error.code != "stale_head":
                raise ReviewStateError("Supersession requires a verified different head")
        job.analysis_status = result.status
        job.error = result.error.model_dump(mode="json")
        await _cancel_pending(db, job, kind="analyze")
        attempts = (
            await db.scalars(
                select(ReviewAttempt)
                .where(
                    ReviewAttempt.job_id == job.id,
                    ReviewAttempt.status == "running",
                )
                .with_for_update()
            )
        ).all()
        for attempt in attempts:
            if attempt.kind == "publication":
                await _unknown_publication(db, job, attempt)
            else:
                attempt.status = "abandoned"
                attempt.finished_at = datetime.now(UTC)
        # Preserve published receipts and unknown outcomes for reconciliation.
        if job.publication_status in {"not_requested", "preview_ready", "failed"}:
            job.publication_status = "blocked"
            job.publication = {"status": "blocked", "error": result.error.model_dump(mode="json")}
        await db.flush()
        return job


async def begin_publication(
    db: AsyncSession,
    owner_id: UUID,
    job_id: UUID,
    *,
    verified_head_sha: str,
    verified_rules_version: int,
    publication_authorized: bool,
    lease_seconds: int,
) -> ReviewAttempt:
    """Record a publish attempt only after the future publisher's permission checks."""
    async with db.begin_nested():
        job = await _locked_job(db, owner_id, job_id, active=True)
        settings = await get_settings(db, owner_id, job.installation_id, job.repo_id)
        policy = ReviewPolicy.model_validate(job.policy)
        if (
            publication_authorized is not True
            or policy.publication_mode != "comment"
            or job.analysis_status not in {"analyzed", "partial"}
            or verified_head_sha != job.head_sha
            or type(verified_rules_version) is not int
            or verified_rules_version != job.rules_version
            or not settings.enabled
            or settings.rules_version != job.rules_version
        ):
            raise ReviewStateError("Publication is not authorized for this snapshot")
        _edge(job.publication_status, "publishing", publication=True)
        attempt = await _new_attempt(db, job, "publication", lease_seconds)
        job.publication_status = "publishing"
        job.publication = {
            "status": "publishing",
            "attempt_id": str(attempt.id),
            "head_sha": job.head_sha,
            "event": "COMMENT",
        }
        await db.flush()
        return attempt


async def record_publication(
    db: AsyncSession,
    owner_id: UUID,
    job_id: UUID,
    value: Publication,
    *,
    confirmed_no_write: bool = False,
) -> ReviewJob:
    """Persist typed receipts/reconciliation evidence; never dispatch a publication."""
    value = TypeAdapter(Publication).validate_python(value.model_dump())
    async with db.begin_nested():
        job = await _locked_job(db, owner_id, job_id)
        _edge(job.publication_status, value.status, publication=True)
        if value.status == "publishing":
            raise ReviewStateError("Use begin_publication with explicit authorization")
        if value.status == "preview_ready":
            if job.analysis_status not in {"analyzed", "partial"}:
                raise ReviewStateError("Preview requires analyzed results")
            if job.publication_status == "publish_unknown" and confirmed_no_write is not True:
                raise ReviewStateError("Unknown publication must be reconciled before retry")
        if (
            job.publication_status == "publish_unknown"
            and value.status == "blocked"
            and confirmed_no_write is not True
        ):
            raise ReviewStateError("Do not discard an unresolved publication outcome")
        if job.publication_status == "publish_unknown" and value.status in {
            "preview_ready",
            "blocked",
        }:
            prior = PublicationUnknown.model_validate(job.publication)
            prior_attempt = await db.get(ReviewAttempt, prior.attempt_id)
            if prior_attempt is None or (prior_attempt.evidence or {}).get("receipt"):
                raise ReviewStateError("No-write evidence contradicts a confirmed receipt")
        if isinstance(value, (PublicationReceipt, PublicationUnknown)):
            if value.head_sha != job.head_sha or str(value.attempt_id) != job.publication.get(
                "attempt_id"
            ):
                raise ReviewStateError("Publication evidence does not match the attempt/head")
            attempt = await db.get(ReviewAttempt, value.attempt_id)
            if (
                attempt is None
                or attempt.job_id != job.id
                or attempt.kind != "publication"
                or attempt.status not in {"running", "unknown", "succeeded"}
            ):
                raise ReviewStateError("Publication attempt unavailable")
            if isinstance(value, PublicationReceipt):
                if (
                    value.confirmed_at.utcoffset() is None
                    or value.confirmed_at < attempt.started_at
                ):
                    raise ReviewStateError("Receipt confirmation time is invalid")
                if len(set(value.github_review_ids)) != len(value.github_review_ids):
                    raise ReviewStateError("Duplicate receipt IDs")
                for review_id in value.github_review_ids:
                    TypeAdapter(GitHubId).validate_python(review_id)
                attempt.status = "succeeded"
                await _cancel_pending(db, job, kind="reconcile_publication")
            else:
                attempt.status = "unknown"
                await _intent(db, job, "reconcile_publication")
            attempt.finished_at = datetime.now(UTC)
            _publication_evidence(attempt, value)
        elif job.publication_status == "publishing":
            raise ReviewStateError("In-flight publication needs a receipt or unknown outcome")
        if job.publication_status == "publish_unknown" and value.status in {
            "preview_ready",
            "blocked",
        }:
            await _cancel_pending(db, job, kind="reconcile_publication")
        job.publication_status = value.status
        job.publication = value.model_dump(mode="json")
        if isinstance(value, PublicationReceipt):
            job.publication_fallback_reason = value.fallback_reason
        elif value.status in {"preview_ready", "failed", "blocked"}:
            job.publication_fallback_reason = None
        await db.flush()
        return job


async def recover_expired_attempt(
    db: AsyncSession,
    owner_id: UUID,
    job_id: UUID,
    attempt_id: UUID,
    *,
    budget_available: bool = False,
) -> ReviewJob:
    """Expired analysis requeues within budget; expired publication only reconciles."""
    async with db.begin_nested():
        job = await _locked_job(db, owner_id, job_id)
        stored = await db.get(ReviewAttempt, attempt_id)
        if stored is None or stored.job_id != job.id:
            raise ReviewStateError("Attempt unavailable")
        attempt = await _attempt(db, job, attempt_id, stored.kind, expired=True)
        if attempt.kind == "publication":
            await _unknown_publication(db, job, attempt)
        else:
            installation = await get_installation(db, owner_id, job.installation_id)
            retry = (
                budget_available is True
                and attempt.number < job.max_attempts
                and installation.revoked_at is None
            )
            target = "queued" if retry else "failed"
            _edge(job.analysis_status, target)
            job.analysis_status = target
            job.error = _error("provider_failed", retryable=retry).model_dump(mode="json")
            attempt.status = "abandoned"
            attempt.finished_at = datetime.now(UTC)
            if retry:
                await _intent(db, job, "analyze")
        await db.flush()
        return job
