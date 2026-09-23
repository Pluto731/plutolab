"""Optional, bounded Python syntax checks. Source is parsed, never imported or run."""

import ast
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StaticIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    path: str = Field(min_length=1, max_length=4096)
    line: int = Field(strict=True, ge=1)
    message: str = Field(min_length=1, max_length=500)


class StaticCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: Literal["disabled", "complete", "partial", "skipped"]
    issues: tuple[StaticIssue, ...] = ()
    warnings: tuple[str, ...] = ()


_MAX_FILES = 100
_MAX_FILE_BYTES = 1_000_000
_MAX_TOTAL_BYTES = 4_000_000


def check_python_syntax(
    sources: Mapping[str, str] | None,
    *,
    allowed_paths: frozenset[str],
    enabled: bool = False,
) -> StaticCheckResult:
    """Run `ast.parse` only for changed Python paths and caller-supplied text.

    A failure or an invalid/oversized source mapping degrades this optional check
    to partial/skipped; it never escapes into the review job as an exception.
    """
    if type(enabled) is not bool:
        return StaticCheckResult(status="skipped", warnings=("invalid_enabled_flag",))
    if not enabled:
        return StaticCheckResult(status="disabled")
    if not isinstance(sources, Mapping):
        return StaticCheckResult(status="skipped", warnings=("source_unavailable",))
    if len(sources) > _MAX_FILES:
        return StaticCheckResult(status="partial", warnings=("file_limit_exceeded",))

    issues: list[StaticIssue] = []
    warnings: list[str] = []
    total_bytes = 0
    eligible = 0
    for path, source in sources.items():
        if not isinstance(path, str) or not path.endswith(".py") or path not in allowed_paths:
            continue
        eligible += 1
        if not isinstance(source, str):
            warnings.append("invalid_source")
            continue
        try:
            byte_count = len(source.encode("utf-8", errors="strict"))
        except UnicodeError:
            warnings.append("invalid_source_encoding")
            continue
        total_bytes += byte_count
        if byte_count > _MAX_FILE_BYTES or total_bytes > _MAX_TOTAL_BYTES:
            warnings.append("source_size_limit_exceeded")
            break
        try:
            ast.parse(source, filename=path, mode="exec", type_comments=False)
        except SyntaxError as exc:
            issues.append(
                StaticIssue(
                    path=path,
                    line=max(1, exc.lineno or 1),
                    message=(exc.msg or "invalid Python syntax")[:500],
                )
            )
        except (ValueError, TypeError, RecursionError, MemoryError):
            warnings.append("syntax_check_failed")

    if not eligible:
        return StaticCheckResult(status="skipped", warnings=("no_changed_python_sources",))
    return StaticCheckResult(
        status="partial" if warnings else "complete",
        issues=tuple(issues),
        warnings=tuple(dict.fromkeys(warnings)),
    )
