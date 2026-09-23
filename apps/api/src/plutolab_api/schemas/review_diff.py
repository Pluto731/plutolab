"""Immutable, local diff preparation contracts; reviewed means selected, not analyzed."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from plutolab_api.schemas.review import HeadSha, NonNegativeInt, PositiveInt


class DiffContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class DiffLine(DiffContract):
    kind: Literal["addition", "deletion", "context"]
    old_line: PositiveInt | None
    new_line: PositiveInt | None
    line: PositiveInt
    side: Literal["LEFT", "RIGHT"]
    position: PositiveInt
    content: str
    comment_context: str


class DiffFile(DiffContract):
    path: str
    old_path: str | None
    new_path: str | None
    status: Literal["added", "deleted", "renamed", "modified"]
    changed_lines: NonNegativeInt
    lines: tuple[DiffLine, ...]
    skip_reason: str | None = None


class PreparedDiff(DiffContract):
    head_sha: HeadSha
    files: tuple[DiffFile, ...]
    total_changed_lines: NonNegativeInt
    included_changed_lines: NonNegativeInt
    skipped_changed_lines: NonNegativeInt
    missing_changed_lines: NonNegativeInt
    truncated: bool
    coverage_complete: bool
    notes: tuple[str, ...] = Field(max_length=100)
