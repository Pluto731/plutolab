"""Bounded, checkpointed orchestration for the local review worker.

The worker owns leases and final result persistence. This handler composes the
existing diff, budget, chunking, analysis, and job-domain services without
holding a database transaction across GitHub or provider calls.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid5

from sqlalchemy import select

from plutolab_api.models.review import ReviewAttempt, ReviewJob, ReviewSettings
from plutolab_api.schemas.review import (
    AnalysisResult,
    AnalysisStopped,
    FindingLocation,
    ReviewBudgets,
    ReviewCoverage,
    ReviewError,
    ReviewFinding,
    ReviewIdentity,
    ReviewOwner,
    ReviewRepository,
    ReviewUsage,
    VerifiedDiffPosition,
    VerifiedDiffSnapshot,
)
from plutolab_api.schemas.review_analysis import AnalysisReport
from plutolab_api.services.review.analyzer import ReviewProvider, analyze_plan
from plutolab_api.services.review.budget import ProviderProfile
from plutolab_api.services.review.chunking import Chunk, ChunkPlan, plan_chunks
from plutolab_api.services.review.diff import DiffError, ReviewDiffGitHubClient, fetch_review_diff
from plutolab_api.services.review.jobs import (
    ReviewAccessDeniedError,
    ReviewStateError,
    stop_analysis,
)
from plutolab_api.services.review.settings import ReviewRules
from plutolab_api.services.review.worker import RetryableWorkError, SessionFactory, WorkLease

logger = logging.getLogger(__name__)
_CHECKPOINT_LIMIT_BYTES = 1_000_000
_CHUNK_RETRY_MAX = 5
_FINDING_NAMESPACE = UUID("01bd437e-f372-4c51-b165-a7b77a806590")


class ReviewPipelineError(RuntimeError):
    """Safe terminal pipeline failure; caller details are never persisted."""


class ReviewTransientError(RetryableWorkError):
    """Provider or GitHub adapter reports a retryable transient failure."""


OwnerBudget = Callable[[UUID], Awaitable[str]]
Sleep = Callable[[float], Awaitable[None]]


class ReviewOrchestrator:
    """Callable handler for ``worker.Consumer`` with provider/client injection.

    ``profile`` and ``system_prompt`` are explicit deployment configuration.
    The default path has no provider SDK, credentials, or implicit network use;
    callers supply the read-only GitHub adapter and provider implementation.
    """

    def __init__(
        self,
        sessions: SessionFactory,
        github: ReviewDiffGitHubClient,
        provider: ReviewProvider,
        profile: ProviderProfile,
        *,
        system_prompt: str,
        owner_remaining_usd: OwnerBudget,
        static_sources: Mapping[str, str] | None = None,
        include_static_checks: bool = False,
        chunk_attempts: int = 3,
        retry_base_seconds: int = 1,
        retry_max_seconds: int = 8,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if type(chunk_attempts) is not int or not 1 <= chunk_attempts <= _CHUNK_RETRY_MAX:
            raise ValueError("chunk_attempts_out_of_range")
        if (
            type(retry_base_seconds) is not int
            or type(retry_max_seconds) is not int
            or not 0 <= retry_base_seconds <= retry_max_seconds <= 60
        ):
            raise ValueError("retry_window_out_of_range")
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError("system_prompt_required")
        if type(include_static_checks) is not bool:
            raise ValueError("include_static_checks_must_be_bool")
        self.sessions = sessions
        self.github = github
        self.provider = provider
        self.profile = ProviderProfile.model_validate(profile.model_dump())
        self.system_prompt = system_prompt
        self.owner_remaining_usd = owner_remaining_usd
        self.static_sources = dict(static_sources) if static_sources is not None else None
        self.include_static_checks = include_static_checks
        self.chunk_attempts = chunk_attempts
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds
        self.sleep = sleep

    async def __call__(self, lease: WorkLease) -> AnalysisResult:
        """Run one leased job; terminal stale outcomes are committed immediately.

        The existing Consumer expects an AnalysisResult. For superseded work we
        commit the terminal state here; its subsequent fenced finish is rejected
        and acknowledged as stale, so no analysis result can overwrite it.
        """
        identity, _job = await self._identity(lease)
        if (
            self.profile.provider != lease.policy.provider
            or self.profile.model != lease.policy.model
        ):
            raise ReviewPipelineError("configured_provider_does_not_match_job")

        await self._checkpoint(lease, "fetching_diff")
        try:
            diff = await fetch_review_diff(self.github, identity)
        except DiffError as exc:
            if str(exc) == "stale_head":
                try:
                    await self._verify_current_head(lease, identity)
                except _StaleHeadError as stale:
                    await self._preempt_stale(lease, stale)
                    return self._fenced_result(lease)
            raise ReviewPipelineError("diff_fetch_failed") from exc
        except Exception as exc:
            if _retryable(exc):
                raise ReviewTransientError("review_diff_adapter_transient_failure") from exc
            raise ReviewPipelineError("diff_fetch_failed") from exc
        await self._checkpoint(lease, "diff_fetched", diff_head=diff.head_sha)

        try:
            remaining = await self.owner_remaining_usd(lease.owner_id)
            plan = plan_chunks(
                diff,
                lease.policy,
                self.profile,
                system_prompt=self.system_prompt,
                owner_remaining_usd=remaining,
            )
        except Exception as exc:
            raise ReviewPipelineError("budget_or_chunk_planning_failed") from exc
        await self._checkpoint(lease, "chunks_planned", chunk_count=len(plan.chunks))

        reusable = await self._recoverable_chunks(lease)
        retry_budget = _RetryBudget(plan, lease.policy.budgets, Decimal(remaining))
        merged_reports: list[AnalysisReport] = []
        successful_chunks: set[str] = set()
        failed_chunks: set[str] = set()
        checkpoint_warnings: list[str] = []
        stale_head: _StaleHeadError | None = None
        retryable_adapter_error: Exception | None = None

        for chunk in plan.chunks:
            payload_hash = _payload_hash(chunk.payload)
            cached = reusable.get(chunk.id)
            if isinstance(cached, dict) and cached.get("payload_sha256") == payload_hash:
                try:
                    report = AnalysisReport.model_validate_json(json.dumps(cached["report"]))
                except (KeyError, TypeError, ValueError):
                    report = None
                if report is not None and report.status in {"complete", "partial"}:
                    merged_reports.append(report)
                    if report.status == "complete":
                        successful_chunks.add(chunk.id)
                    else:
                        failed_chunks.add(chunk.id)
                    saved = await self._checkpoint_chunk_result(lease, chunk, payload_hash, report)
                    if not saved:
                        checkpoint_warnings.append(
                            f"recovery_checkpoint_capacity_exceeded:{chunk.id}"
                        )
                    await self._checkpoint(
                        lease, "chunk_reused", chunk_id=chunk.id, payload_sha256=payload_hash
                    )
                    continue

            chunk_plan = plan.model_copy(update={"chunks": (chunk,)})
            runner = _CheckpointingProvider(
                self,
                lease,
                identity,
                chunk,
                payload_hash,
                retry_budget,
            )
            report = await analyze_plan(
                runner,
                chunk_plan,
                timeout_seconds=30,
            )
            if runner.stale_head is not None:
                stale_head = runner.stale_head
                break
            if runner.retryable_error is not None:
                retryable_adapter_error = runner.retryable_error
                break
            if runner.fatal_error is not None:
                raise ReviewPipelineError("checkpoint_or_adapter_failure") from runner.fatal_error
            if runner.budget_exhausted:
                report = report.model_copy(
                    update={
                        "status": "partial",
                        "warnings": tuple(
                            dict.fromkeys((*report.warnings, "retry_budget_exhausted"))
                        ),
                    }
                )
            merged_reports.append(report)
            if report.status == "complete" and report.failed_chunks == 0:
                successful_chunks.add(chunk.id)
                saved = await self._checkpoint_chunk_result(lease, chunk, payload_hash, report)
                if not saved:
                    checkpoint_warnings.append(f"recovery_checkpoint_capacity_exceeded:{chunk.id}")
            else:
                failed_chunks.add(chunk.id)
                saved = await self._checkpoint_chunk_result(lease, chunk, payload_hash, report)
                if not saved:
                    checkpoint_warnings.append(f"recovery_checkpoint_capacity_exceeded:{chunk.id}")
                await self._checkpoint(
                    lease,
                    "chunk_partial",
                    chunk_id=chunk.id,
                    payload_sha256=payload_hash,
                    warnings=list(report.warnings[:20]),
                )

        if retryable_adapter_error is not None:
            if _retryable(retryable_adapter_error):
                raise ReviewTransientError(
                    "review_adapter_transient_failure"
                ) from retryable_adapter_error
            raise ReviewPipelineError("review_adapter_failure") from retryable_adapter_error
        if stale_head is not None:
            await self._preempt_stale(lease, stale_head)
            return self._fenced_result(lease)

        if self.include_static_checks:
            # A no-op provider keeps static parsing on the same path/position
            # validation as model findings and invokes it only once per job.
            static_report = await analyze_plan(
                _EmptyProvider(),
                plan,
                static_sources=self.static_sources,
                include_static_checks=True,
                timeout_seconds=30,
            )
            if static_report.static_check_status in {"partial", "skipped"}:
                merged_reports.append(
                    AnalysisReport(
                        status="partial",
                        summary="Optional static checks were incomplete.",
                        findings=(),
                        failed_chunks=0,
                        static_check_status=static_report.static_check_status,
                        warnings=static_report.warnings,
                    )
                )
            elif static_report.findings:
                merged_reports.append(static_report)

        try:
            await self._verify_current_head(lease, identity)
        except _StaleHeadError as exc:
            await self._preempt_stale(lease, exc)
            return self._fenced_result(lease)
        except Exception as exc:
            if _retryable(exc):
                raise ReviewTransientError("review_head_check_transient_failure") from exc
            raise ReviewPipelineError("review_head_check_failed") from exc
        result = _result_from_reports(
            plan,
            merged_reports,
            successful_chunks=successful_chunks,
            failed_chunks=failed_chunks,
            extra_gaps=checkpoint_warnings,
            max_findings=lease.policy.budgets.max_findings,
            allowed_focus=frozenset(lease.policy.focus),
            usage=retry_budget.usage(),
        )
        await self._checkpoint(lease, "analysis_ready", result_status=result.status)
        return result

    async def _identity(self, lease: WorkLease) -> tuple[ReviewIdentity, ReviewJob]:
        async with self.sessions() as db:
            job = await db.scalar(
                select(ReviewJob).where(
                    ReviewJob.id == lease.job_id,
                    ReviewJob.owner_id == lease.owner_id,
                )
            )
            settings = (
                await db.scalar(
                    select(ReviewSettings).where(
                        ReviewSettings.installation_id == job.installation_id,
                        ReviewSettings.owner_id == lease.owner_id,
                        ReviewSettings.repo_id == job.repo_id,
                    )
                )
                if job is not None
                else None
            )
            attempt = await db.get(ReviewAttempt, lease.attempt_id)
        if (
            job is None
            or settings is None
            or attempt is None
            or job.analysis_status != "processing"
            or attempt.status != "running"
            or attempt.lease_until <= datetime.now(UTC)
            or job.head_sha != lease.head_sha
            or job.rules_version != lease.policy.rules_version
            or job.provider != lease.policy.provider
            or job.policy != lease.policy.model_dump(mode="json")
        ):
            raise ReviewAccessDeniedError("Review job lease unavailable")
        try:
            owner_login, repo_name = settings.repo_name.split("/", maxsplit=1)
            ReviewRules(
                enabled=settings.enabled,
                skip_paths=settings.skip_paths,
                min_pr_lines=settings.min_pr_lines,
                max_pr_lines=settings.max_pr_lines,
                focus=settings.focus,
            )
            identity = ReviewIdentity(
                review_id=job.id,
                owner=ReviewOwner(user_id=job.owner_id, installation_id=job.installation_id),
                repo=ReviewRepository(id=job.repo_id, owner_login=owner_login, name=repo_name),
                pr_number=job.pr_number,
                head_sha=job.head_sha,
                policy=lease.policy,
            )
        except (ValueError, TypeError) as exc:
            raise ReviewPipelineError("persisted_review_identity_invalid") from exc
        return identity, job

    async def _verify_current_head(self, lease: WorkLease, identity: ReviewIdentity) -> None:
        pull = await self.github.get_pull_request(
            identity.owner.installation_id,
            identity.repo.owner_login,
            identity.repo.name,
            identity.pr_number,
        )
        if pull.number != identity.pr_number:
            raise ReviewPipelineError("pull_request_identity_mismatch")
        if pull.head.sha != lease.head_sha or pull.state != "open":
            raise _StaleHeadError(pull.head.sha)

    async def _preempt_stale(self, lease: WorkLease, stale: _StaleHeadError) -> None:
        status = "superseded" if stale.head_sha != lease.head_sha else "cancelled"
        result = AnalysisStopped(
            status=status,
            error=ReviewError(
                code="stale_head",
                message=(
                    "A newer pull request head replaced this review."
                    if status == "superseded"
                    else "The pull request is no longer open."
                ),
                retryable=False,
                request_id=UUID(int=0),
            ),
        )
        async with self.sessions() as db:
            await stop_analysis(
                db,
                lease.owner_id,
                lease.job_id,
                result,
                verified_head_sha=stale.head_sha,
            )
            await db.commit()

    async def _checkpoint(self, lease: WorkLease, phase: str, **values: object) -> None:
        checkpoint = {"phase": phase, "at": datetime.now(UTC).isoformat(), **values}
        async with self.sessions() as db:
            attempt = await db.scalar(
                select(ReviewAttempt)
                .where(
                    ReviewAttempt.id == lease.attempt_id,
                    ReviewAttempt.job_id == lease.job_id,
                    ReviewAttempt.owner_id == lease.owner_id,
                    ReviewAttempt.head_sha == lease.head_sha,
                    ReviewAttempt.kind == "analysis",
                    ReviewAttempt.status == "running",
                    ReviewAttempt.lease_until > datetime.now(UTC),
                )
                .with_for_update()
            )
            if attempt is None:
                raise ReviewStateError("Review attempt lease expired during orchestration")
            evidence = dict(attempt.evidence or {})
            evidence.update(checkpoint)
            if _json_size(evidence) > _CHECKPOINT_LIMIT_BYTES:
                raise ReviewPipelineError("checkpoint_size_limit_exceeded")
            attempt.evidence = evidence
            await db.commit()

    async def _checkpoint_chunk_result(
        self, lease: WorkLease, chunk: Chunk, payload_sha256: str, report: AnalysisReport
    ) -> bool:
        async with self.sessions() as db:
            attempt = await db.scalar(
                select(ReviewAttempt)
                .where(
                    ReviewAttempt.id == lease.attempt_id,
                    ReviewAttempt.job_id == lease.job_id,
                    ReviewAttempt.owner_id == lease.owner_id,
                    ReviewAttempt.head_sha == lease.head_sha,
                    ReviewAttempt.kind == "analysis",
                    ReviewAttempt.status == "running",
                    ReviewAttempt.lease_until > datetime.now(UTC),
                )
                .with_for_update()
            )
            if attempt is None:
                raise ReviewStateError("Review attempt lease expired during chunk analysis")
            evidence = dict(attempt.evidence or {})
            chunks = dict(evidence.get("chunks", {}))
            chunks[chunk.id] = {
                "payload_sha256": payload_sha256,
                "report": report.model_dump(mode="json"),
            }
            evidence.update({"phase": "analyzing", "chunks": chunks})
            if _json_size(evidence) > _CHECKPOINT_LIMIT_BYTES:
                return False
            attempt.evidence = evidence
            await db.commit()
            return True

    async def _recoverable_chunks(self, lease: WorkLease) -> dict[str, object]:
        async with self.sessions() as db:
            previous = await db.scalar(
                select(ReviewAttempt)
                .where(
                    ReviewAttempt.job_id == lease.job_id,
                    ReviewAttempt.owner_id == lease.owner_id,
                    ReviewAttempt.kind == "analysis",
                    ReviewAttempt.head_sha == lease.head_sha,
                    ReviewAttempt.number < lease.number,
                    ReviewAttempt.status.in_(("abandoned", "failed")),
                )
                .order_by(ReviewAttempt.number.desc())
                .limit(1)
            )
            evidence = dict(previous.evidence or {}) if previous is not None else {}
        chunks = evidence.get("chunks", {})
        return chunks if isinstance(chunks, dict) else {}

    def _fenced_result(self, lease: WorkLease) -> AnalysisResult:
        return AnalysisResult(
            status="partial",
            summary="This review was superseded and its result was discarded.",
            findings=[],
            coverage=ReviewCoverage(
                files_total=0,
                files_reviewed=0,
                changed_lines_total=0,
                changed_lines_reviewed=0,
                gaps=[],
            ),
            usage=ReviewUsage(
                input_tokens=0,
                output_tokens=0,
                cost_usd="0.000000",
                token_count_mode=lease.policy.budgets.token_count_mode,
            ),
        )


class _CheckpointingProvider:
    def __init__(
        self,
        orchestrator: ReviewOrchestrator,
        lease: WorkLease,
        identity: ReviewIdentity,
        chunk: Chunk,
        payload_sha256: str,
        retry_budget: _RetryBudget,
    ) -> None:
        self.orchestrator = orchestrator
        self.lease = lease
        self.identity = identity
        self.chunk = chunk
        self.payload_sha256 = payload_sha256
        self.retry_budget = retry_budget
        self.stale_head: _StaleHeadError | None = None
        self.retryable_error: Exception | None = None
        self.fatal_error: Exception | None = None
        self.budget_exhausted = False

    async def complete(self, payload: str) -> str:
        if _payload_hash(payload) != self.payload_sha256:
            self.fatal_error = ReviewPipelineError("chunk_payload_changed")
            return _EMPTY_ANALYSIS
        for number in range(1, self.orchestrator.chunk_attempts + 1):
            try:
                await self.orchestrator._verify_current_head(self.lease, self.identity)
            except _StaleHeadError as exc:
                self.stale_head = exc
                return _EMPTY_ANALYSIS
            except Exception as exc:
                self.retryable_error = exc
                return _EMPTY_ANALYSIS
            try:
                await self.orchestrator._checkpoint(
                    self.lease,
                    "chunk_running",
                    chunk_id=self.chunk.id,
                    chunk_attempt=number,
                    payload_sha256=self.payload_sha256,
                )
            except Exception as exc:
                self.fatal_error = exc
                return _EMPTY_ANALYSIS
            try:
                raw = await self.orchestrator.provider.complete(payload)
            except Exception as exc:
                if not _retryable(exc) or number == self.orchestrator.chunk_attempts:
                    raise
                if not self.retry_budget.reserve(self.chunk):
                    self.budget_exhausted = True
                    raise
                try:
                    await self.orchestrator._checkpoint(
                        self.lease,
                        "chunk_retry_wait",
                        chunk_id=self.chunk.id,
                        chunk_attempt=number,
                        error_class=type(exc).__name__[:80],
                    )
                except Exception as checkpoint_error:
                    self.fatal_error = checkpoint_error
                    return _EMPTY_ANALYSIS
                delay = min(
                    self.orchestrator.retry_max_seconds,
                    self.orchestrator.retry_base_seconds * (2 ** min(number - 1, 10)),
                )
                if delay:
                    await self.orchestrator.sleep(delay)
                continue
            try:
                await self.orchestrator._verify_current_head(self.lease, self.identity)
            except _StaleHeadError as exc:
                self.stale_head = exc
                return _EMPTY_ANALYSIS
            except Exception as exc:
                self.retryable_error = exc
                return _EMPTY_ANALYSIS
            try:
                await self.orchestrator._checkpoint(
                    self.lease,
                    "chunk_received",
                    chunk_id=self.chunk.id,
                    chunk_attempt=number,
                    payload_sha256=self.payload_sha256,
                )
            except Exception as exc:
                self.fatal_error = exc
                return _EMPTY_ANALYSIS
            return raw
        raise AssertionError("bounded chunk retry loop exhausted unexpectedly")


class _EmptyProvider:
    async def complete(self, _payload: str) -> str:
        return '{"summary":"Static analysis only","findings":[]}'


_EMPTY_ANALYSIS = '{"summary":"Analysis was preempted.","findings":[]}'


class _StaleHeadError(Exception):
    def __init__(self, head_sha: str) -> None:
        super().__init__("stale_head")
        self.head_sha = head_sha


def _retryable(error: Exception) -> bool:
    return (
        isinstance(error, (TimeoutError, ConnectionError))
        or getattr(error, "retryable", False) is True
    )


class _RetryBudget:
    """Reserve every repeated provider request against the immutable hard caps."""

    def __init__(
        self, plan: ChunkPlan, budgets: ReviewBudgets, owner_remaining_usd: Decimal
    ) -> None:
        self.budgets = budgets
        self.owner_remaining_usd = owner_remaining_usd
        self.input_tokens = plan.totals.input_tokens
        self.output_tokens = plan.totals.output_tokens
        self.cost = Decimal(plan.totals.estimated_cost_usd)
        self.token_count_mode = plan.token_count_mode

    def reserve(self, chunk: Chunk) -> bool:
        reservation = chunk.reservation
        next_input = self.input_tokens + reservation.input_tokens
        next_output = self.output_tokens + reservation.output_tokens
        next_cost = self.cost + Decimal(reservation.estimated_cost_usd)
        if (
            next_input > self.budgets.max_total_input_tokens
            or next_output > self.budgets.max_total_output_tokens
            or next_cost > Decimal(self.budgets.max_cost_usd)
            or next_cost > self.owner_remaining_usd
        ):
            return False
        self.input_tokens = next_input
        self.output_tokens = next_output
        self.cost = next_cost
        return True

    def usage(self) -> ReviewUsage:
        return ReviewUsage(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cost_usd=f"{self.cost:.6f}",
            token_count_mode=self.token_count_mode,
        )


def _payload_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json_size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _result_from_reports(
    plan: ChunkPlan,
    reports: list[AnalysisReport],
    *,
    successful_chunks: set[str],
    failed_chunks: set[str],
    extra_gaps: list[str],
    max_findings: int,
    allowed_focus: frozenset[str],
    usage: ReviewUsage,
) -> AnalysisResult:
    findings: list[ReviewFinding] = []
    seen: set[str] = set()
    warnings = list(plan.coverage.reasons)
    summaries: list[str] = []
    for report in reports:
        summaries.append(report.summary)
        warnings.extend(report.warnings)
        for finding in report.findings:
            if finding.category not in allowed_focus:
                warnings.append("finding_focus_not_enabled")
                continue
            if finding.fingerprint in seen:
                continue
            seen.add(finding.fingerprint)
            description = f"{finding.title}\n\n{finding.comment_body}"[:2000]
            findings.append(
                ReviewFinding(
                    id=uuid5(_FINDING_NAMESPACE, finding.fingerprint),
                    fingerprint=finding.fingerprint,
                    focus=finding.category,
                    severity=finding.severity,
                    location=FindingLocation(
                        path=finding.file_path,
                        line=finding.line,
                        side=finding.side,
                    ),
                    description=description,
                    suggestion=(finding.suggestion or "No code suggestion provided.")[:4000],
                    evidence=finding.evidence[:4000] or "No source evidence was retained.",
                )
            )

    if len(findings) > max_findings:
        findings = findings[:max_findings]
        warnings.append("finding_limit_exceeded")
    unique_complete = {chunk_id for chunk_id in successful_chunks if chunk_id not in failed_chunks}
    chunks_by_id = {chunk.id: chunk for chunk in plan.chunks}
    successful = [
        chunks_by_id[chunk_id] for chunk_id in sorted(unique_complete) if chunk_id in chunks_by_id
    ]
    reviewed_lines = sum(hunk.changed_lines for chunk in successful for hunk in chunk.hunks)
    reviewed_files = {hunk.path for chunk in successful for hunk in chunk.hunks}
    gaps = list(dict.fromkeys((*warnings, *extra_gaps)))
    for chunk_id in sorted(failed_chunks):
        gaps.append(f"chunk_failed:{chunk_id}")
    if len(successful_chunks) < len(plan.chunks):
        gaps.append("analysis_chunks_incomplete")
    gaps = list(dict.fromkeys(gaps))[:100]
    coverage = ReviewCoverage(
        files_total=len(plan.files),
        files_reviewed=len(reviewed_files),
        changed_lines_total=plan.coverage.total_lines,
        changed_lines_reviewed=min(reviewed_lines, plan.coverage.total_lines),
        gaps=gaps,
    )
    incomplete = (
        bool(gaps)
        or coverage.files_reviewed < coverage.files_total
        or coverage.changed_lines_reviewed < coverage.changed_lines_total
    )
    summary = " ".join(part.strip() for part in summaries if part.strip())[:10000]
    if not summary:
        summary = "No reviewable diff chunks were produced."
    result = AnalysisResult(
        status="partial" if incomplete else "analyzed",
        summary=summary,
        findings=findings,
        coverage=coverage,
        usage=usage,
    )
    verified_lines = {
        (hunk.path, line.line, line.side): line
        for chunk in plan.chunks
        for hunk in chunk.hunks
        for line in hunk.lines
    }
    verified_findings = {}
    for finding in result.findings:
        location = finding.location
        line = verified_lines.get((location.path, location.line, location.side))
        if line is not None:
            verified_findings[str(finding.id)] = VerifiedDiffPosition(
                path=location.path,
                line=location.line,
                side=location.side,
                position=line.position,
                comment_context=line.comment_context,
            )
    return result.model_copy(
        update={
            "verified_diff": VerifiedDiffSnapshot(
                head_sha=plan.head_sha,
                findings=verified_findings,
            )
        }
    )
