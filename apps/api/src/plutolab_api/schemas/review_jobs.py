"""Owner-scoped response contracts for review job list and detail reads."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from plutolab_api.schemas.review import (
    AnalysisStatus,
    FindingLocation,
    Focus,
    GitHubId,
    HeadSha,
    PublicationStatus,
    ReviewUsage,
    Severity,
    VerifiedDiffPosition,
)

JobListStatus = Literal["QUEUED", "ANALYZED", "PUBLISHED", "PARTIAL", "FAILED"]
PublicationFallbackReason = Literal["diff_position_mismatch"]


class ReviewJobReadContract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ReviewJobListItem(ReviewJobReadContract):
    id: UUID
    installation_id: GitHubId
    repo_id: GitHubId
    pr_number: int = Field(gt=0)
    head_sha: HeadSha
    analysis_status: AnalysisStatus
    publication_status: PublicationStatus
    publication_fallback_reason: PublicationFallbackReason | None
    created_at: datetime
    processing_started_at: datetime | None
    completed_at: datetime | None


class ReviewFindingView(ReviewJobReadContract):
    id: UUID
    severity: Severity
    focus: Focus
    location: FindingLocation
    verified_diff: VerifiedDiffPosition | None
    description: str
    suggestion: str | None = None
    evidence: str | None = None


class ReviewJobCoverage(ReviewJobReadContract):
    files_total: int = Field(ge=0)
    files_reviewed: int = Field(ge=0)
    changed_lines_total: int = Field(ge=0)
    changed_lines_reviewed: int = Field(ge=0)
    gaps: list[str]
    truncated: bool
    truncation_reason: str | None


class ReviewPublicationRead(ReviewJobReadContract):
    status: PublicationStatus
    github_review_ids: list[GitHubId]


class ReviewJobList(ReviewJobReadContract):
    jobs: list[ReviewJobListItem]
    total_count: int = Field(ge=0)
    page: int = Field(ge=1)
    per_page: int = Field(ge=1)


class ReviewJobDetail(ReviewJobListItem):
    summary: str | None
    coverage: ReviewJobCoverage | None
    usage: ReviewUsage | None
    findings: list[ReviewFindingView]
    publication: ReviewPublicationRead
