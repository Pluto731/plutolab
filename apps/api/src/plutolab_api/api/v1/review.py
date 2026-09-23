"""Authenticated review installation API; callbacks carry claims, not authority."""

import logging
import math
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, TypeAdapter, ValidationError
from redis.asyncio import Redis
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from plutolab_api.api.deps import CurrentUser
from plutolab_api.core.config import settings
from plutolab_api.core.github_app import GitHubAppError
from plutolab_api.core.redis import get_redis
from plutolab_api.db.deps import get_db
from plutolab_api.models.review import GitHubInstallation, ReviewAttempt, ReviewJob, ReviewSettings
from plutolab_api.schemas.review import (
    ErrorCode,
    Focus,
    ReviewCoverage,
    ReviewError,
    ReviewFinding,
    ReviewUsage,
    VerifiedDiffPosition,
)
from plutolab_api.schemas.review_jobs import (
    JobListStatus,
    ReviewFindingView,
    ReviewJobCoverage,
    ReviewJobDetail,
    ReviewJobList,
    ReviewJobListItem,
    ReviewPublicationRead,
)
from plutolab_api.services.review.installations import (
    InstallationGitHubClient,
    InstallationStart,
    InstallationStateError,
    InstallationStateUnavailableError,
    bind_installation,
    initiate_installation,
    installation_status,
    unbind_installation,
)
from plutolab_api.services.review.jobs import ReviewStateError
from plutolab_api.services.review.settings import (
    AccessibleRepositories,
    RepositoryQuery,
    ReviewAccessDeniedError,
    ReviewConflictError,
    ReviewRepositoryGitHubClient,
    ReviewRules,
    get_installation,
    list_accessible_repositories,
    read_repository_rules,
    update_repository_rules,
)
from plutolab_api.services.review.webhook import WebhookError, ingest_event, verify_request


def _http_error(
    status: int,
    code: ErrorCode,
    message: str,
    *,
    retryable: bool = False,
    retry_after: int | None = None,
) -> HTTPException:
    detail = ReviewError(
        code=code,
        message=message,
        retryable=retryable,
        request_id=uuid4(),
        retry_after_seconds=retry_after,
    )
    return HTTPException(
        status_code=status,
        detail=detail.model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )


async def _review_errors() -> AsyncIterator[None]:
    try:
        yield
    except InstallationStateError:
        raise _http_error(403, "access_denied", "Invalid or expired installation state") from None
    except InstallationStateUnavailableError:
        raise _http_error(
            503, "persistence_failed", "Installation state unavailable", retryable=True
        ) from None
    except ReviewAccessDeniedError:
        raise _http_error(
            403, "access_denied", "Installation unavailable or ownership unverified"
        ) from None
    except ReviewConflictError:
        raise _http_error(
            409, "validation_failed", "Installation binding conflicts with existing state"
        ) from None
    except GitHubAppError as error:
        if error.code == "repository_search_limit":
            raise _http_error(
                422, "validation_failed", "Search supports at most 10000 installation repositories"
            ) from None
        if error.code in {"app_not_configured", "jwt_signing_failed"}:
            raise _http_error(503, "access_denied", "GitHub App credentials unavailable") from None
        if error.code == "rate_limited":
            raise _http_error(
                429,
                "rate_limited",
                "GitHub rate limit reached",
                retryable=True,
                retry_after=math.ceil(error.retry_after_seconds)
                if error.retry_after_seconds is not None
                else None,
            ) from None
        if error.status_code in {403, 404}:
            raise _http_error(403, "access_denied", "Installation could not be verified") from None
        raise _http_error(
            502, "access_denied", "GitHub App verification unavailable", retryable=error.retryable
        ) from None
    except SQLAlchemyError:
        raise _http_error(
            503, "persistence_failed", "Installation storage unavailable", retryable=True
        ) from None


router = APIRouter(
    prefix="/review/installations",
    tags=["review-installations"],
    dependencies=[Depends(_review_errors)],
)
DbSession = Annotated[AsyncSession, Depends(get_db)]
StateStore = Annotated[Redis, Depends(get_redis)]
InstallationId = Annotated[str, Path(pattern=r"^[1-9][0-9]{0,19}$")]


async def get_installation_github() -> AsyncIterator[InstallationGitHubClient]:
    async with InstallationGitHubClient.from_settings(settings) as client:
        yield client


InstallationGitHub = Annotated[InstallationGitHubClient, Depends(get_installation_github)]


class InstallationCallback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: SecretStr
    installation_id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")


class InstallationPublic(BaseModel):
    installation_id: str
    active: bool
    revoked_at: datetime | None

    @classmethod
    def from_row(cls, row: GitHubInstallation) -> "InstallationPublic":
        return cls(
            installation_id=row.installation_id,
            active=row.revoked_at is None,
            revoked_at=row.revoked_at,
        )


class InstallationList(BaseModel):
    installations: list[InstallationPublic]
    github_account_id: str | None


@router.get("", response_model=InstallationList)
async def list_bound_installations(
    user: CurrentUser, db: DbSession, response: Response
) -> InstallationList:
    """Discover only local bindings belonging to the authenticated owner; no GitHub call."""
    rows = await db.scalars(
        select(GitHubInstallation)
        .where(GitHubInstallation.owner_id == user.id)
        .order_by(GitHubInstallation.created_at, GitHubInstallation.installation_id)
    )
    response.headers["Cache-Control"] = "no-store"
    return InstallationList(
        installations=[InstallationPublic.from_row(row) for row in rows],
        github_account_id=str(user.github_id) if user.github_id is not None else None,
    )


@router.post("/start", response_model=InstallationStart)
async def start_installation(
    user: CurrentUser, store: StateStore, github: InstallationGitHub, response: Response
) -> InstallationStart:
    response.headers["Cache-Control"] = "no-store"
    return await initiate_installation(store, github, user.id, user.github_id)


@router.post("/callback", response_model=InstallationPublic)
async def installation_callback(
    body: InstallationCallback,
    user: CurrentUser,
    db: DbSession,
    store: StateStore,
    github: InstallationGitHub,
    response: Response,
) -> InstallationPublic:
    # The future frontend relays the GitHub navigation callback as authenticated JSON.
    # No GET callback, query user_id, or callback-only ownership proof is accepted.
    row = await bind_installation(
        db,
        store,
        github,
        user.id,
        user.github_id,
        state=body.state.get_secret_value(),
        installation_id=body.installation_id,
    )
    result = InstallationPublic.from_row(row)
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/{installation_id}", response_model=InstallationPublic)
async def get_installation_status(
    installation_id: InstallationId, user: CurrentUser, db: DbSession, response: Response
) -> InstallationPublic:
    response.headers["Cache-Control"] = "no-store"
    return InstallationPublic.from_row(await installation_status(db, user.id, installation_id))


@router.delete("/{installation_id}", response_model=InstallationPublic)
async def revoke_bound_installation(
    installation_id: InstallationId, user: CurrentUser, db: DbSession, response: Response
) -> InstallationPublic:
    row = await unbind_installation(db, user.id, installation_id)
    result = InstallationPublic.from_row(row)
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


async def get_repository_github() -> AsyncIterator[ReviewRepositoryGitHubClient]:
    async with ReviewRepositoryGitHubClient.from_settings(settings) as client:
        yield client


RepositoryGitHub = Annotated[ReviewRepositoryGitHubClient, Depends(get_repository_github)]


class RepositoryRulesUpdate(ReviewRules):
    expected_rules_version: int = Field(ge=1, le=2_147_483_647)
    focus: list[Focus] = Field(
        default_factory=lambda: ["security", "performance", "quality"],
        min_length=1,
        max_length=3,
        alias="focus_areas",
    )


class RepositoryRulesPublic(BaseModel):
    repo_id: str
    repo_name: str
    installation_id: str
    enabled: bool
    min_pr_lines: int
    max_pr_lines: int | None
    skip_paths: list[str]
    focus_areas: list[Focus]
    rules_version: int


def _rules_public(row: ReviewSettings) -> RepositoryRulesPublic:
    return RepositoryRulesPublic(
        repo_id=row.repo_id,
        repo_name=row.repo_name,
        installation_id=row.installation_id,
        enabled=row.enabled,
        min_pr_lines=row.min_pr_lines,
        max_pr_lines=row.max_pr_lines,
        skip_paths=row.skip_paths,
        focus_areas=row.focus,
        rules_version=row.rules_version,
    )


@router.get("/{installation_id}/repositories", response_model=AccessibleRepositories)
async def repository_list(
    installation_id: InstallationId,
    query: Annotated[RepositoryQuery, Query()],
    user: CurrentUser,
    db: DbSession,
    github: RepositoryGitHub,
    response: Response,
) -> AccessibleRepositories:
    result = await list_accessible_repositories(db, github, user.id, installation_id, query)
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get(
    "/{installation_id}/repositories/{repo_id}/settings", response_model=RepositoryRulesPublic
)
async def repository_rules(
    installation_id: InstallationId,
    repo_id: InstallationId,
    user: CurrentUser,
    db: DbSession,
    github: RepositoryGitHub,
    response: Response,
) -> RepositoryRulesPublic:
    row = await read_repository_rules(db, github, user.id, installation_id, repo_id)
    result = _rules_public(row)
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.put(
    "/{installation_id}/repositories/{repo_id}/settings", response_model=RepositoryRulesPublic
)
async def save_repository_rules(
    installation_id: InstallationId,
    repo_id: InstallationId,
    body: RepositoryRulesUpdate,
    user: CurrentUser,
    db: DbSession,
    github: RepositoryGitHub,
    response: Response,
) -> RepositoryRulesPublic:
    rules = ReviewRules.model_validate(body.model_dump(exclude={"expected_rules_version"}))
    row = await update_repository_rules(
        db,
        github,
        user.id,
        installation_id,
        repo_id,
        rules,
        expected_rules_version=body.expected_rules_version,
    )
    result = _rules_public(row)
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


# Keep all existing installation paths/dependencies intact while adding a sibling
# webhook path. The webhook authenticates its raw body, never a site JWT.
installation_router = router
router = APIRouter()
router.include_router(installation_router)

_REVIEW_FINDINGS = TypeAdapter(list[ReviewFinding])
_ANALYSIS_FAILED = ReviewJob.analysis_status == "failed"
_PUBLICATION_FAILED = ReviewJob.publication_status == "failed"
_FAILED_FILTER = or_(_ANALYSIS_FAILED, _PUBLICATION_FAILED)
_PARTIAL_FILTER = or_(
    ReviewJob.analysis_status == "partial",
    ReviewJob.publication_status.in_(("partially_published", "publish_unknown")),
)
_PUBLISHED_FILTER = and_(
    ReviewJob.publication_status == "published", ~_FAILED_FILTER, ~_PARTIAL_FILTER
)
_ANALYZED_FILTER = and_(
    ReviewJob.analysis_status == "analyzed",
    ~_FAILED_FILTER,
    ~_PARTIAL_FILTER,
    ~_PUBLISHED_FILTER,
)
_QUEUED_FILTER = and_(~_FAILED_FILTER, ~_PARTIAL_FILTER, ~_PUBLISHED_FILTER, ~_ANALYZED_FILTER)
_JOB_STATUS_FILTERS = {
    "QUEUED": _QUEUED_FILTER,
    "ANALYZED": _ANALYZED_FILTER,
    "PUBLISHED": _PUBLISHED_FILTER,
    "PARTIAL": _PARTIAL_FILTER,
    "FAILED": _FAILED_FILTER,
}


async def _analysis_timing(
    db: AsyncSession, job_ids: list[UUID]
) -> dict[UUID, tuple[datetime | None, datetime | None]]:
    if not job_ids:
        return {}
    rows = await db.execute(
        select(
            ReviewAttempt.job_id,
            func.min(ReviewAttempt.started_at),
            func.max(ReviewAttempt.finished_at),
        )
        .where(ReviewAttempt.job_id.in_(job_ids), ReviewAttempt.kind == "analysis")
        .group_by(ReviewAttempt.job_id)
    )
    return {job_id: (started, finished) for job_id, started, finished in rows}


def _job_list_item(
    job: ReviewJob, timing: tuple[datetime | None, datetime | None] | None
) -> ReviewJobListItem:
    started, completed = timing or (None, None)
    return ReviewJobListItem(
        id=job.id,
        installation_id=job.installation_id,
        repo_id=job.repo_id,
        pr_number=job.pr_number,
        head_sha=job.head_sha,
        analysis_status=job.analysis_status,
        publication_status=job.publication_status,
        publication_fallback_reason=job.publication_fallback_reason,
        created_at=job.created_at,
        processing_started_at=started,
        completed_at=completed,
    )


@router.get("/review/jobs", response_model=ReviewJobList, tags=["review-jobs"])
async def list_review_jobs(
    user: CurrentUser,
    db: DbSession,
    response: Response,
    installation_id: Annotated[str | None, Query(pattern=r"^[1-9][0-9]{0,31}$")] = None,
    repo_id: Annotated[str | None, Query(pattern=r"^[1-9][0-9]{0,31}$")] = None,
    pr_number: Annotated[int | None, Query(ge=1, le=2_147_483_647)] = None,
    status: JobListStatus | None = None,
    page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReviewJobList:
    """List jobs only through active installation bindings of the authenticated owner."""
    if installation_id is not None:
        try:
            await get_installation(db, user.id, installation_id, active=True)
        except ReviewAccessDeniedError:
            raise HTTPException(status_code=404, detail="Review jobs unavailable") from None

    conditions = [
        GitHubInstallation.owner_id == user.id,
        GitHubInstallation.revoked_at.is_(None),
    ]
    if installation_id is not None:
        conditions.append(ReviewJob.installation_id == installation_id)
    if repo_id is not None:
        conditions.append(ReviewJob.repo_id == repo_id)
    if pr_number is not None:
        conditions.append(ReviewJob.pr_number == pr_number)
    if status is not None:
        conditions.append(_JOB_STATUS_FILTERS[status])

    total_count = await db.scalar(
        select(func.count(ReviewJob.id))
        .join(
            GitHubInstallation,
            and_(
                GitHubInstallation.installation_id == ReviewJob.installation_id,
                GitHubInstallation.owner_id == ReviewJob.owner_id,
            ),
        )
        .where(*conditions)
    )
    rows = (
        await db.scalars(
            select(ReviewJob)
            .join(
                GitHubInstallation,
                and_(
                    GitHubInstallation.installation_id == ReviewJob.installation_id,
                    GitHubInstallation.owner_id == ReviewJob.owner_id,
                ),
            )
            .where(*conditions)
            .order_by(ReviewJob.created_at.desc(), ReviewJob.id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()
    timings = await _analysis_timing(db, [job.id for job in rows])
    response.headers["Cache-Control"] = "no-store"
    return ReviewJobList(
        jobs=[_job_list_item(job, timings.get(job.id)) for job in rows],
        total_count=total_count or 0,
        page=page,
        per_page=per_page,
    )


@router.get("/review/jobs/{job_id}", response_model=ReviewJobDetail, tags=["review-jobs"])
async def get_review_job(
    job_id: UUID, user: CurrentUser, db: DbSession, response: Response
) -> ReviewJobDetail:
    job = await db.scalar(
        select(ReviewJob)
        .join(
            GitHubInstallation,
            and_(
                GitHubInstallation.installation_id == ReviewJob.installation_id,
                GitHubInstallation.owner_id == ReviewJob.owner_id,
            ),
        )
        .where(
            ReviewJob.id == job_id,
            ReviewJob.owner_id == user.id,
            GitHubInstallation.owner_id == user.id,
            GitHubInstallation.revoked_at.is_(None),
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Review job unavailable")

    started, completed = (await _analysis_timing(db, [job.id])).get(job.id, (None, None))
    base = _job_list_item(job, (started, completed))
    coverage = None
    if job.coverage is not None:
        review_coverage = ReviewCoverage.model_validate(job.coverage)
        gaps = review_coverage.gaps
        truncated = bool(gaps) or (
            review_coverage.changed_lines_reviewed < review_coverage.changed_lines_total
            or review_coverage.files_reviewed < review_coverage.files_total
        )
        coverage = ReviewJobCoverage(
            **review_coverage.model_dump(),
            truncated=truncated,
            truncation_reason="; ".join(gaps) if gaps else None,
        )
    verified_positions: dict[str, object] = {}
    if isinstance(job.verified_diff, dict) and job.verified_diff.get("head_sha") == job.head_sha:
        raw_positions = job.verified_diff.get("findings")
        if isinstance(raw_positions, dict):
            verified_positions = raw_positions
    findings = []
    for finding in _REVIEW_FINDINGS.validate_python(job.findings):
        verified_position = None
        raw_position = verified_positions.get(str(finding.id))
        if isinstance(raw_position, dict):
            try:
                candidate = VerifiedDiffPosition.model_validate(raw_position)
            except ValidationError:
                candidate = None
            if candidate is not None and (
                candidate.path,
                candidate.line,
                candidate.side,
            ) == (finding.location.path, finding.location.line, finding.location.side):
                verified_position = candidate
        findings.append(
            ReviewFindingView(
                id=finding.id,
                severity=finding.severity,
                focus=finding.focus,
                location=finding.location,
                verified_diff=verified_position,
                description=finding.description,
                suggestion=finding.suggestion or None,
                evidence=finding.evidence or None,
            )
        )
    publication_data = job.publication if isinstance(job.publication, dict) else {}
    raw_ids = publication_data.get("github_review_ids", [])
    review_ids = (
        [value for value in raw_ids if isinstance(value, str)] if isinstance(raw_ids, list) else []
    )
    response.headers["Cache-Control"] = "no-store"
    return ReviewJobDetail(
        **base.model_dump(),
        summary=job.summary,
        coverage=coverage,
        usage=ReviewUsage.model_validate(job.usage) if job.usage is not None else None,
        findings=findings,
        publication=ReviewPublicationRead(
            status=job.publication_status,
            github_review_ids=review_ids,
        ),
    )


async def _rollback_webhook(db: AsyncSession) -> None:
    try:
        await db.rollback()
    except SQLAlchemyError:
        # The request-scoped session still closes on exit; never log DB exception
        # text/connection strings or turn an ambiguous commit into an acknowledgment.
        logging.getLogger(__name__).warning("review_webhook_rollback_failed")


@router.post("/review/webhook", tags=["review-webhook"], status_code=202)
async def receive_review_webhook(request: Request, db: DbSession) -> JSONResponse:
    try:
        event = await verify_request(request, settings.github_app_webhook_secret)
    except WebhookError as error:
        raise _http_error(
            error.status,
            "access_denied" if error.status == 403 else "validation_failed",
            str(error),
            retryable=error.status == 503,
        ) from None
    try:
        result = await ingest_event(
            db,
            event,
            model=settings.review_webhook_model,
            budgets=settings.review_webhook_budgets,
            max_attempts=settings.review_webhook_max_attempts,
        )
        await db.commit()
    except WebhookError as error:
        await _rollback_webhook(db)
        raise _http_error(
            error.status, "validation_failed", str(error), retryable=error.status == 503
        ) from None
    except ReviewConflictError:
        await _rollback_webhook(db)
        raise _http_error(
            409, "validation_failed", "Delivery or policy identity conflicts"
        ) from None
    except (ReviewStateError, ValidationError):
        await _rollback_webhook(db)
        raise _http_error(
            503, "validation_failed", "Review execution policy is invalid", retryable=True
        ) from None
    except SQLAlchemyError:
        await _rollback_webhook(db)
        raise _http_error(
            503, "persistence_failed", "Webhook storage unavailable", retryable=True
        ) from None
    return JSONResponse(
        {"status": result.disposition, "duplicate": result.duplicate},
        status_code=202 if result.disposition == "accepted" else 200,
        headers={"Cache-Control": "no-store"},
    )
