"""Provider-injected structured analysis with verified diff-position mapping."""

import asyncio
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Protocol

from pydantic import ValidationError

from plutolab_api.schemas.review_analysis import (
    AnalysisReport,
    FindingCandidate,
    ProviderResponse,
    StructuredFinding,
)
from plutolab_api.services.review.chunking import ChunkPlan
from plutolab_api.services.review.linter import StaticCheckResult, check_python_syntax

logger = logging.getLogger(__name__)
_MAX_RESPONSE_BYTES = 256_000
_MAX_TIMEOUT_SECONDS = 120


class ReviewProvider(Protocol):
    async def complete(self, payload: str) -> str: ...


ProviderCall = Callable[[str], Awaitable[str]]


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def parse_provider_response(raw: str) -> ProviderResponse:
    """Parse bounded JSON (optionally a single JSON code fence) with no extras."""
    if not isinstance(raw, str):
        raise ValueError("invalid_provider_response")
    if len(raw.encode("utf-8", errors="replace")) > _MAX_RESPONSE_BYTES:
        raise ValueError("provider_response_too_large")
    text = raw.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    try:
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=lambda _: 1 / 0)
        return ProviderResponse.model_validate(value)
    except (
        json.JSONDecodeError,
        ValueError,
        TypeError,
        ValidationError,
        ZeroDivisionError,
        RecursionError,
    ) as exc:
        raise ValueError("invalid_provider_response") from exc


def _position_index(plan: ChunkPlan) -> dict[str, list[tuple[int, str, str, int]]]:
    index: dict[str, list[tuple[int, str, str, int]]] = {}
    for chunk in plan.chunks:
        for hunk in chunk.hunks:
            entries = index.setdefault(hunk.path, [])
            for line in hunk.lines:
                entries.append((line.line, line.side, line.content, line.position))
    for entries in index.values():
        entries.sort(key=lambda item: item[3])
    return index


def _normalise_finding(
    candidate: FindingCandidate,
    positions: dict[str, list[tuple[int, str, str, int]]],
) -> StructuredFinding | None:
    entries = positions.get(candidate.file_path)
    if not entries:
        return None
    same_side = [item for item in entries if item[1] == candidate.side]
    choices = same_side or entries
    match = min(choices, key=lambda item: (abs(item[0] - candidate.line), item[3]))
    line, side, evidence, _ = match
    normalized_evidence = evidence[:16384] or "(empty changed line)"
    canonical = json.dumps(
        {
            "file_path": candidate.file_path,
            "line": line,
            "side": side,
            "severity": candidate.severity,
            "category": candidate.category,
            "title": candidate.title,
            "comment_body": candidate.comment_body,
            "suggestion": candidate.suggestion,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return StructuredFinding(
        file_path=candidate.file_path,
        line=line,
        side=side,
        severity=candidate.severity,
        category=candidate.category,
        title=candidate.title,
        comment_body=candidate.comment_body,
        suggestion=candidate.suggestion,
        fingerprint=fingerprint,
        evidence=normalized_evidence,
        line_was_clamped=line != candidate.line or side != candidate.side,
    )


def _static_candidate(path: str, line: int, message: str) -> FindingCandidate:
    return FindingCandidate(
        file_path=path,
        line=line,
        side="RIGHT",
        severity="LOW",
        category="quality",
        title="Python syntax error",
        comment_body=f"Python syntax check: {message}",
    )


async def analyze_plan(
    provider: ReviewProvider | ProviderCall,
    plan: ChunkPlan,
    *,
    static_sources: Mapping[str, str] | None = None,
    include_static_checks: bool = False,
    timeout_seconds: int = 30,
) -> AnalysisReport:
    """Analyze selected chunks; malformed/failed responses reduce coverage safely.

    Provider implementations are injected. This module itself has no SDK,
    credentials, HTTP client, database, or implicit network path.
    """
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= _MAX_TIMEOUT_SECONDS:
        raise ValueError("timeout_seconds_out_of_range")
    if type(include_static_checks) is not bool:
        raise ValueError("include_static_checks_must_be_bool")

    positions = _position_index(plan)
    findings: list[StructuredFinding] = []
    fingerprints: set[str] = set()
    warnings: list[str] = []
    failed_chunks = 0
    summaries: list[str] = []
    call: ProviderCall = provider.complete if hasattr(provider, "complete") else provider

    for chunk in plan.chunks:
        try:
            raw = await asyncio.wait_for(call(chunk.payload), timeout=timeout_seconds)
            response = parse_provider_response(raw)
        except TimeoutError:
            failed_chunks += 1
            warnings.append("provider_timeout")
            continue
        except Exception as exc:
            failed_chunks += 1
            warnings.append(
                "provider_response_invalid"
                if isinstance(exc, ValueError)
                else "provider_unavailable"
            )
            logger.info("review provider chunk failed: %s", warnings[-1])
            continue
        summaries.append(response.summary)
        for candidate in response.findings:
            finding = _normalise_finding(candidate, positions)
            if finding is None:
                warnings.append("finding_outside_prepared_diff")
                continue
            if finding.fingerprint not in fingerprints:
                if len(findings) >= 1000:
                    warnings.append("finding_limit_exceeded")
                    continue
                fingerprints.add(finding.fingerprint)
                findings.append(finding)

    static = StaticCheckResult(status="disabled")
    if include_static_checks:
        try:
            static = check_python_syntax(
                static_sources,
                allowed_paths=frozenset(positions),
                enabled=True,
            )
        except Exception:
            static = StaticCheckResult(status="partial", warnings=("syntax_check_failed",))
        warnings.extend(static.warnings)
        for issue in static.issues:
            candidate = _static_candidate(issue.path, issue.line, issue.message)
            finding = _normalise_finding(candidate, positions)
            if finding is not None and finding.fingerprint not in fingerprints:
                if len(findings) >= 1000:
                    warnings.append("finding_limit_exceeded")
                else:
                    fingerprints.add(finding.fingerprint)
                    findings.append(finding)

    combined_summary = " ".join(summaries)
    if len(combined_summary) > 10000:
        warnings.append("summary_truncated")
    warnings = list(dict.fromkeys(warnings))[:100]
    if not plan.chunks and not findings:
        status = "skipped"
    elif failed_chunks or warnings or static.status in {"partial", "skipped"}:
        status = "partial"
    else:
        status = "complete"
    summary = combined_summary[:10000] or (
        "No selected diff chunks were available."
        if not plan.chunks
        else "Review analysis was incomplete."
    )
    return AnalysisReport(
        status=status,
        summary=summary,
        findings=tuple(findings[:1000]),
        failed_chunks=failed_chunks,
        static_check_status=static.status,
        warnings=tuple(warnings),
    )
