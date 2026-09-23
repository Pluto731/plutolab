"""Strict local provider-response contracts for structured review analysis."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from plutolab_api.schemas.review import NonNegativeInt, PositiveInt, Severity

ReviewCategory = Literal["security", "performance", "quality"]


class AnalysisContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FindingCandidate(AnalysisContract):
    """Untrusted provider output before it is resolved against the prepared diff."""

    file_path: str = Field(min_length=1, max_length=4096)
    line: PositiveInt
    side: Literal["LEFT", "RIGHT"]
    severity: Severity
    category: ReviewCategory
    title: str = Field(min_length=1, max_length=200)
    comment_body: str = Field(min_length=1, max_length=4000)
    suggestion: str | None = Field(default=None, max_length=4000)

    @field_validator("file_path")
    @classmethod
    def safe_relative_path(cls, value: str) -> str:
        if (
            value.startswith(("/", "\\"))
            or "\\" in value
            or ":" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
        ):
            raise ValueError("file_path_must_be_repository_relative")
        return value

    @field_validator("title", "comment_body")
    @classmethod
    def non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text_must_not_be_blank")
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError("text_must_be_valid_unicode") from exc
        return value

    @field_validator("suggestion")
    @classmethod
    def non_blank_suggestion(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("suggestion_must_not_be_blank")
        if value is not None:
            try:
                value.encode("utf-8", errors="strict")
            except UnicodeEncodeError as exc:
                raise ValueError("suggestion_must_be_valid_unicode") from exc
        return value


class ProviderResponse(AnalysisContract):
    summary: str = Field(min_length=1, max_length=10000)
    findings: tuple[FindingCandidate, ...] = Field(max_length=200)

    @field_validator("summary")
    @classmethod
    def valid_summary_unicode(cls, value: str) -> str:
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError("summary_must_be_valid_unicode") from exc
        return value

    @field_validator("findings", mode="before")
    @classmethod
    def freeze_json_array(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value


class StructuredFinding(AnalysisContract):
    file_path: str
    line: PositiveInt
    side: Literal["LEFT", "RIGHT"]
    severity: Severity
    category: ReviewCategory
    title: str
    comment_body: str
    suggestion: str | None
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence: str = Field(min_length=1, max_length=16384)
    line_was_clamped: bool


class AnalysisReport(AnalysisContract):
    status: Literal["complete", "partial", "skipped"]
    summary: str = Field(min_length=1, max_length=10000)
    findings: tuple[StructuredFinding, ...] = Field(max_length=1000)
    failed_chunks: NonNegativeInt
    static_check_status: Literal["disabled", "complete", "partial", "skipped"]
    warnings: tuple[str, ...] = Field(max_length=100)
