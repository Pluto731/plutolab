"""Idempotent, permission-gated publication of analyzed review jobs.

GitHub writes are exposed as an injected port. The database attempt is committed
before that port is called, and its typed receipt is committed afterward.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import uuid4

import httpx
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.models.review import ReviewAttempt, ReviewJob
from plutolab_api.schemas.review import (
    PublicationReceipt,
    PublicationStopped,
    PublicationUnknown,
    ReviewError,
    ReviewFinding,
    ReviewIdentity,
)
from plutolab_api.schemas.review_diff import PreparedDiff
from plutolab_api.schemas.review_publication import (
    PublicationComment,
    PublicationSummary,
    RemotePublication,
)
from plutolab_api.services.review.jobs import (
    ReviewStateError,
    begin_publication,
    get_job,
    record_publication,
)

logger = logging.getLogger(__name__)
_FINDINGS = TypeAdapter(list[ReviewFinding])
_MAX_COMMENT_BODY = 6000
_FALLBACK_MARKER = "<!-- plutolab-review-fallback:diff_position_mismatch -->"
_PARTIAL_MARKER = "<!-- plutolab-review-status:partially_published -->"


class GitHubPublicationError(RuntimeError):
    """Safe status-only error returned by a GitHub write adapter."""

    def __init__(self, status_code: int, *, outcome_unknown: bool = False) -> None:
        super().__init__("github_publication_failed")
        self.status_code = status_code
        self.outcome_unknown = outcome_unknown


class GitHubReviewWritePort(Protocol):
    """Minimal write port; implementations must target the fixed GitHub API origin."""

    async def list_pull_request_reviews(
        self, identity: ReviewIdentity
    ) -> Sequence[RemotePublication]: ...

    async def list_issue_comments(
        self, identity: ReviewIdentity
    ) -> Sequence[RemotePublication]: ...

    async def create_pull_request_review(
        self, identity: ReviewIdentity, *, body: str, comments: list[PublicationComment]
    ) -> RemotePublication: ...

    async def create_issue_comment(
        self, identity: ReviewIdentity, *, body: str
    ) -> RemotePublication: ...

    async def update_issue_comment(
        self, identity: ReviewIdentity, comment_id: str, *, body: str
    ) -> RemotePublication: ...


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def render_publication(
    identity: ReviewIdentity,
    job: ReviewJob,
    diff: PreparedDiff,
    *,
    max_inline_comments: int,
) -> PublicationSummary:
    """Render deterministic summary and only inline findings on exact diff lines."""
    if diff.head_sha != identity.head_sha or job.head_sha != identity.head_sha:
        raise ReviewStateError("Publication diff/head mismatch")
    if job.id != identity.review_id or job.owner_id != identity.owner.user_id:
        raise ReviewStateError("Publication identity mismatch")
    if type(max_inline_comments) is not int or not 0 <= max_inline_comments <= 100:
        raise ValueError("max_inline_comments_out_of_range")

    findings = _FINDINGS.validate_python(job.findings)
    locations = {
        (file.path, line.line, line.side): line.position
        for file in diff.files
        for line in file.lines
    }
    comments: list[PublicationComment] = []
    unanchored = 0
    for finding in findings:
        location = finding.location
        position = locations.get((location.path, location.line, location.side))
        if position is None:
            unanchored += 1
            continue
        if len(comments) < max_inline_comments:
            comments.append(
                PublicationComment(
                    path=location.path,
                    line=location.line,
                    side=location.side,
                    position=position,
                    body=_finding_body(finding),
                )
            )

    omitted = len(findings) - len(comments)
    severity = Counter(finding.severity for finding in findings)
    coverage = job.coverage or {}
    skipped: Counter[str] = Counter()
    for file in diff.files:
        if file.skip_reason:
            skipped[file.skip_reason] += file.changed_lines
    for gap in coverage.get("gaps", []) if isinstance(coverage, dict) else []:
        if isinstance(gap, str) and gap:
            skipped[gap] += 1

    marker = f"<!-- plutolab-review:{identity.review_id}:{identity.head_sha} -->"
    lines = [
        "## PlutoLab AI Review",
        "",
        f"**Commit:** `{identity.head_sha}`",
        f"**Risk findings:** {len(findings)} total — "
        + ", ".join(
            f"{level.lower()} {severity.get(level, 0)}"
            for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
        ),
        "",
        "### Coverage",
        f"- Changed lines: {coverage.get('changed_lines_total', diff.total_changed_lines)}",
        f"- Reviewed lines: {coverage.get('changed_lines_reviewed', diff.included_changed_lines)}",
        f"- Files reviewed: {coverage.get('files_reviewed', sum(1 for file in diff.files if not file.skip_reason))} / "
        f"{coverage.get('files_total', len(diff.files))}",
    ]
    if skipped:
        lines.extend(["", "### Skipped coverage"])
        lines.extend(f"- {reason}: {count}" for reason, count in sorted(skipped.items()))
    if omitted:
        lines.extend(["", f"{omitted} finding(s) are included below but were not posted inline."])
    if job.summary:
        lines.extend(["", "### Summary", job.summary])
    if findings:
        lines.extend(["", "### Findings"])
        lines.extend(
            f"- **{finding.severity}** `{finding.location.path}:{finding.location.line}` "
            f"({finding.location.side}): {finding.description}"
            for finding in findings
        )
    if unanchored:
        lines.extend(
            [
                "",
                f"{unanchored} finding(s) had no exact verified diff line and remain summary-only.",
            ]
        )
    lines.extend(["", marker])
    if omitted or diff.missing_changed_lines:
        lines.extend(["", _PARTIAL_MARKER])
    body = "\n".join(lines)
    if len(body) > 60_000:
        body = body[: 60_000 - len(marker) - 2].rstrip() + "\n\n" + marker
    return PublicationSummary(
        marker=marker,
        body=body,
        comments=tuple(comments),
        finding_count=len(findings),
        inline_count=len(comments),
        omitted_inline_count=omitted,
        status="partially_published" if omitted or diff.missing_changed_lines else "published",
    )


def _finding_body(finding: ReviewFinding) -> str:
    text = f"**{finding.severity} · {finding.focus}** — {finding.description}"
    if finding.suggestion:
        text += f"\n\nSuggestion: {finding.suggestion}"
    if finding.evidence:
        text += f"\n\nEvidence: {finding.evidence}"
    return text[:_MAX_COMMENT_BODY]


def _has_marker(publication: RemotePublication, marker: str) -> bool:
    return marker in publication.body


def _fallback_reason(body: str) -> str | None:
    return "diff_position_mismatch" if _FALLBACK_MARKER in body else None


class ReviewPublisher:
    """Permission checked publication with stable marker based idempotency."""

    def __init__(
        self,
        sessions: SessionFactory,
        github: GitHubReviewWritePort,
        *,
        lease_seconds: int = 120,
    ) -> None:
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds_out_of_range")
        self.sessions = sessions
        self.github = github
        self.lease_seconds = lease_seconds

    async def publish(
        self,
        identity: ReviewIdentity,
        diff: PreparedDiff,
        *,
        publication_authorized: bool,
    ) -> PublicationReceipt | PublicationUnknown | PublicationStopped:
        """Publish one analyzed snapshot. The caller supplies server-verified identity."""
        if diff.head_sha != identity.head_sha:
            raise ReviewStateError("Publication diff/head mismatch")
        async with self.sessions() as db:
            job = await get_job(db, identity.owner.user_id, identity.review_id)
            _assert_identity(identity, job)
            if job.analysis_status not in {"analyzed", "partial"}:
                raise ReviewStateError("Only analyzed jobs may be published")
            if job.publication_status == "published":
                return PublicationReceipt.model_validate(job.publication)
            summary = render_publication(
                identity,
                job,
                diff,
                max_inline_comments=identity.policy.budgets.max_comments,
            )
            attempt = await begin_publication(
                db,
                identity.owner.user_id,
                identity.review_id,
                verified_head_sha=identity.head_sha,
                verified_rules_version=identity.policy.rules_version,
                publication_authorized=publication_authorized,
                lease_seconds=self.lease_seconds,
            )
            attempt_id = attempt.id
            await db.commit()

        try:
            existing = await self._find_existing(identity, summary.marker)
            if existing is not None:
                remote, fallback_reason = existing
                status = "partially_published" if _PARTIAL_MARKER in remote.body else "published"
            else:
                remote, status, fallback_reason = await self._release(identity, summary)
            receipt = PublicationReceipt(
                status=status,
                attempt_id=attempt_id,
                head_sha=identity.head_sha,
                github_review_ids=[remote.id],
                confirmed_at=datetime.now(UTC),
                fallback_reason=fallback_reason,
            )
        except GitHubPublicationError as exc:
            if exc.outcome_unknown:
                value = PublicationUnknown(
                    status="publish_unknown",
                    attempt_id=attempt_id,
                    head_sha=identity.head_sha,
                    error=_review_error("publication_unknown"),
                )
            else:
                value = PublicationStopped(
                    status="failed", error=_review_error("publication_failed")
                )
            await self._record(identity, value)
            return value
        except (TimeoutError, httpx.TimeoutException):
            value = PublicationUnknown(
                status="publish_unknown",
                attempt_id=attempt_id,
                head_sha=identity.head_sha,
                error=_review_error("publication_unknown"),
            )
            await self._record(identity, value)
            return value

        await self._record(identity, receipt)
        return receipt

    async def _find_existing(
        self, identity: ReviewIdentity, marker: str
    ) -> tuple[RemotePublication, str | None] | None:
        reviews = await self.github.list_pull_request_reviews(identity)
        for raw in reviews:
            item = RemotePublication.model_validate(raw)
            if _has_marker(item, marker):
                return item, _fallback_reason(item.body)
        comments = await self.github.list_issue_comments(identity)
        for raw in comments:
            item = RemotePublication.model_validate(raw)
            if _has_marker(item, marker):
                return item, _fallback_reason(item.body)
        return None

    async def _release(
        self, identity: ReviewIdentity, summary: PublicationSummary
    ) -> tuple[RemotePublication, str, str | None]:
        if summary.comments:
            try:
                review = await self.github.create_pull_request_review(
                    identity, body=summary.body, comments=list(summary.comments)
                )
                return RemotePublication.model_validate(review), summary.status, None
            except GitHubPublicationError as exc:
                if exc.status_code != 422:
                    raise
                logger.info("GitHub rejected inline positions; falling back to summary comment")
                body = f"{summary.body}\n\n{_PARTIAL_MARKER}\n{_FALLBACK_MARKER}"
                comment = await self.github.create_issue_comment(identity, body=body)
                return (
                    RemotePublication.model_validate(comment),
                    "partially_published",
                    "diff_position_mismatch",
                )
        comment = await self.github.create_issue_comment(identity, body=summary.body)
        status = "partially_published" if summary.omitted_inline_count else summary.status
        return RemotePublication.model_validate(comment), status, None

    async def _record(
        self,
        identity: ReviewIdentity,
        value: PublicationReceipt | PublicationUnknown | PublicationStopped,
    ) -> None:
        async with self.sessions() as db:
            await record_publication(db, identity.owner.user_id, identity.review_id, value)
            if isinstance(value, PublicationStopped):
                attempt = await db.scalar(
                    select(ReviewAttempt)
                    .where(
                        ReviewAttempt.job_id == identity.review_id,
                        ReviewAttempt.kind == "publication",
                        ReviewAttempt.status == "running",
                    )
                    .with_for_update()
                )
                if attempt is not None:
                    attempt.status = "failed"
                    attempt.finished_at = datetime.now(UTC)
            await db.commit()


def _assert_identity(identity: ReviewIdentity, job: ReviewJob) -> None:
    if (
        job.id != identity.review_id
        or job.owner_id != identity.owner.user_id
        or job.installation_id != identity.owner.installation_id
        or job.repo_id != identity.repo.id
        or job.pr_number != identity.pr_number
        or job.head_sha != identity.head_sha
        or job.policy != identity.policy.model_dump(mode="json")
    ):
        raise ReviewStateError("Publication identity mismatch")


def _review_error(code: Literal["publication_unknown", "publication_failed"]) -> ReviewError:
    return ReviewError(code=code, message=code, retryable=False, request_id=uuid4())
