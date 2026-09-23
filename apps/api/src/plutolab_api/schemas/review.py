"""Phase 5 v1 contract drafts; no routes, persistence, workers, or external calls.

HTTP errors retain FastAPI's ``detail`` envelope. Analysis and publication are
separate tagged unions: an analyzed result is never proof of publication.
Transition maps describe permitted edges; enforcement belongs to later slices.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

GitHubId = Annotated[str, Field(pattern=r"^[1-9][0-9]*$")]
HeadSha = Annotated[str, Field(pattern=r"^([0-9a-f]{40}|[0-9a-f]{64})$")]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
MoneyUSD = Annotated[str, Field(pattern=r"^(0|[1-9][0-9]*)\.[0-9]{6}$")]
Focus = Literal["security", "performance", "quality"]
Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
AnalysisStatus = Literal[
    "draft",
    "queued",
    "processing",
    "analyzed",
    "partial",
    "failed",
    "skipped",
    "superseded",
    "cancelled",
]
PublicationStatus = Literal[
    "not_requested",
    "preview_ready",
    "publishing",
    "published",
    "partially_published",
    "publish_unknown",
    "failed",
    "blocked",
]
ErrorCode = Literal[
    "validation_failed",
    "access_denied",
    "installation_revoked",
    "stale_head",
    "budget_exceeded",
    "diff_unavailable",
    "provider_failed",
    "invalid_findings",
    "rate_limited",
    "persistence_failed",
    "publication_failed",
    "publication_unknown",
    "cancelled",
    "not_applicable",
]

ANALYSIS_TRANSITIONS: dict[AnalysisStatus, tuple[AnalysisStatus, ...]] = {
    "draft": ("queued", "cancelled"),
    "queued": ("processing", "skipped", "superseded", "cancelled"),
    "processing": ("queued", "analyzed", "partial", "failed", "superseded", "cancelled"),
    "analyzed": ("superseded",),
    "partial": ("superseded",),
    "failed": (),
    "skipped": (),
    "superseded": (),
    "cancelled": (),
}
PUBLICATION_TRANSITIONS: dict[PublicationStatus, tuple[PublicationStatus, ...]] = {
    "not_requested": ("preview_ready", "blocked"),
    "preview_ready": ("publishing", "blocked"),
    "publishing": ("published", "partially_published", "publish_unknown", "failed", "blocked"),
    "published": (),
    "partially_published": ("publishing", "publish_unknown", "blocked"),
    "publish_unknown": ("published", "partially_published", "preview_ready", "blocked"),
    "failed": ("preview_ready", "blocked"),
    "blocked": (),
}


class ReviewContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewOwner(ReviewContract):
    """Server-derived owner; never accepted as client authorization evidence."""

    user_id: UUID
    installation_id: GitHubId


class ReviewRepository(ReviewContract):
    id: GitHubId
    owner_login: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)


class ReviewBudgets(ReviewContract):
    """Required policy inputs: no implicit spend or hard-coded provider window."""

    max_files: PositiveInt
    min_changed_lines: NonNegativeInt
    max_changed_lines: PositiveInt
    max_context_lines_per_file: NonNegativeInt
    max_chunks: PositiveInt
    context_window_tokens: PositiveInt
    max_request_input_tokens: PositiveInt
    reserved_output_tokens: PositiveInt
    max_total_input_tokens: PositiveInt
    max_total_output_tokens: PositiveInt
    max_findings: PositiveInt
    max_comments: PositiveInt
    max_cost_usd: MoneyUSD
    max_owner_daily_cost_usd: MoneyUSD
    token_count_mode: Literal["provider_exact", "conservative_estimate"]


class ReviewPolicy(ReviewContract):
    rules_version: PositiveInt
    enabled: bool = False
    focus: list[Focus] = Field(min_length=1, max_length=3)
    skip_paths: list[str] = Field(max_length=100)
    provider: Literal["anthropic"]
    model: str = Field(min_length=1, max_length=200)
    budgets: ReviewBudgets
    publication_mode: Literal["preview_only", "comment"] = "preview_only"


class ReviewIdentity(ReviewContract):
    contract_version: Literal["1"] = "1"
    review_id: UUID
    owner: ReviewOwner
    repo: ReviewRepository
    pr_number: PositiveInt
    head_sha: HeadSha
    policy: ReviewPolicy


class FindingLocation(ReviewContract):
    """Repository-relative path and new/old diff line; never a URL or command."""

    path: str = Field(min_length=1, max_length=4096)
    line: PositiveInt
    side: Literal["LEFT", "RIGHT"]


class VerifiedDiffPosition(ReviewContract):
    path: str = Field(min_length=1, max_length=4096)
    line: PositiveInt
    side: Literal["LEFT", "RIGHT"]
    position: PositiveInt
    comment_context: str = Field(min_length=1, max_length=20_000)


class VerifiedDiffSnapshot(ReviewContract):
    head_sha: HeadSha
    findings: dict[str, VerifiedDiffPosition] = Field(max_length=100)


class ReviewFinding(ReviewContract):
    id: UUID
    fingerprint: str = Field(min_length=1, max_length=128)
    focus: Focus
    severity: Severity
    location: FindingLocation
    description: str = Field(min_length=1, max_length=2000)
    suggestion: str = Field(min_length=1, max_length=4000)
    evidence: str = Field(min_length=1, max_length=4000)


class ReviewError(ReviewContract):
    code: ErrorCode
    message: str = Field(min_length=1, max_length=1000)
    retryable: bool
    request_id: UUID
    retry_after_seconds: NonNegativeInt | None = None


class ReviewHTTPError(ReviewContract):
    """Review-specific HTTPException detail; no new global response envelope."""

    detail: ReviewError


class ReviewCoverage(ReviewContract):
    files_total: NonNegativeInt
    files_reviewed: NonNegativeInt
    changed_lines_total: NonNegativeInt
    changed_lines_reviewed: NonNegativeInt
    gaps: list[str] = Field(max_length=100)


class ReviewUsage(ReviewContract):
    input_tokens: NonNegativeInt
    output_tokens: NonNegativeInt
    cost_usd: MoneyUSD
    token_count_mode: Literal["provider_exact", "conservative_estimate"]


class AnalysisDraft(ReviewContract):
    status: Literal["draft", "queued", "processing"]


class AnalysisResult(ReviewContract):
    status: Literal["analyzed", "partial"]
    summary: str = Field(min_length=1, max_length=10000)
    findings: list[ReviewFinding]
    coverage: ReviewCoverage
    usage: ReviewUsage
    verified_diff: VerifiedDiffSnapshot | None = None


class AnalysisStopped(ReviewContract):
    status: Literal["failed", "skipped", "superseded", "cancelled"]
    error: ReviewError


Analysis = Annotated[
    AnalysisDraft | AnalysisResult | AnalysisStopped, Field(discriminator="status")
]


class PublicationDraft(ReviewContract):
    status: Literal["not_requested", "preview_ready"]


class PublicationAttempt(ReviewContract):
    status: Literal["publishing"]
    attempt_id: UUID
    head_sha: HeadSha
    event: Literal["COMMENT"] = "COMMENT"


class PublicationReceipt(ReviewContract):
    status: Literal["published", "partially_published"]
    attempt_id: UUID
    head_sha: HeadSha
    event: Literal["COMMENT"] = "COMMENT"
    github_review_ids: list[GitHubId] = Field(min_length=1)
    confirmed_at: datetime
    fallback_reason: Literal["diff_position_mismatch"] | None = None


class PublicationUnknown(ReviewContract):
    status: Literal["publish_unknown"]
    attempt_id: UUID
    head_sha: HeadSha
    error: ReviewError


class PublicationStopped(ReviewContract):
    status: Literal["failed", "blocked"]
    error: ReviewError


Publication = Annotated[
    PublicationDraft
    | PublicationAttempt
    | PublicationReceipt
    | PublicationUnknown
    | PublicationStopped,
    Field(discriminator="status"),
]


class ReviewRecord(ReviewIdentity):
    analysis: Analysis
    publication: Publication
