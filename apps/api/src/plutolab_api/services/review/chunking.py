"""Deterministic first-fit-in-source-order hunk packing, with exact line coverage.

Never split a source hunk or combine files. Slice 10 may already have removed
context/changes: the payload is explicitly structured excerpts, not a patch to
apply. Preserve original headers/positions, and report unavailable lines rather
than manufacturing mappings for content no longer present in PreparedDiff.
"""

import json
import re
from fractions import Fraction
from typing import Literal

from plutolab_api.schemas.review import HeadSha, NonNegativeInt, ReviewPolicy
from plutolab_api.schemas.review_diff import DiffLine, PreparedDiff
from plutolab_api.services.review.budget import (
    BudgetContract,
    BudgetLedger,
    BudgetTotals,
    ProviderProfile,
    Rejection,
    Reservation,
)

Selection = Literal["included", "skipped_budget", "skipped_filter"]


class Hunk(BudgetContract):
    id: str
    path: str
    old_path: str | None
    new_path: str | None
    source_header: str
    lines: tuple[DiffLine, ...]
    old_range: tuple[int, int] | None
    new_range: tuple[int, int] | None
    positions: tuple[int, ...]
    changed_lines: NonNegativeInt


class HunkCoverage(BudgetContract):
    id: str
    path: str
    source_header: str | None
    changed_lines: NonNegativeInt
    status: Selection
    reason: str | None
    chunk_id: str | None


class FileCoverage(BudgetContract):
    path: str
    status: Selection
    total_lines: NonNegativeInt
    included_lines: NonNegativeInt
    skipped_budget: NonNegativeInt
    skipped_filter: NonNegativeInt
    reasons: tuple[str, ...]


class Chunk(BudgetContract):
    id: str
    status: Literal["included"] = "included"
    hunks: tuple[Hunk, ...]
    payload: str
    reservation: Reservation


class Coverage(BudgetContract):
    """reviewed_line_ratio is planned selection, not evidence of LLM execution."""

    total_lines: NonNegativeInt
    included_lines: NonNegativeInt
    skipped_budget: NonNegativeInt
    skipped_filter: NonNegativeInt
    missing_lines: NonNegativeInt
    reviewed_line_ratio: str
    status: Literal["complete", "partial", "skipped"]
    reasons: tuple[str, ...]


class ChunkPlan(BudgetContract):
    head_sha: HeadSha
    rules_version: int
    profile: ProviderProfile
    token_count_mode: Literal["conservative_estimate"] = "conservative_estimate"
    chunks: tuple[Chunk, ...]
    hunks: tuple[HunkCoverage, ...]
    files: tuple[FileCoverage, ...]
    coverage: Coverage
    totals: BudgetTotals


def _range(lines: tuple[DiffLine, ...], *, old: bool) -> tuple[int, int] | None:
    values = [n for line in lines if (n := line.old_line if old else line.new_line) is not None]
    return (min(values), max(values)) if values else None


def _hunks(
    path: str,
    lines: tuple[DiffLine, ...],
    file_index: int,
    *,
    old_path: str | None,
    new_path: str | None,
) -> list[Hunk]:
    groups: list[list[DiffLine]] = []
    previous_header = None
    previous_position = 0
    previous_old = previous_new = 0
    for line in lines:
        header, separator, source = line.comment_context.partition("\n")
        prefix = {"addition": "+", "deletion": "-", "context": " "}[line.kind]
        if (
            not separator
            or not header.startswith("@@ ")
            or source != prefix + line.content
            or line.position <= previous_position
        ):
            raise ValueError("invalid_diff_mapping")
        if line.kind == "addition" and (line.old_line is not None or line.new_line is None):
            raise ValueError("invalid_diff_mapping")
        if line.kind == "deletion" and (line.new_line is not None or line.old_line is None):
            raise ValueError("invalid_diff_mapping")
        if line.kind == "context" and (line.old_line is None or line.new_line is None):
            raise ValueError("invalid_diff_mapping")
        if line.line != (line.old_line if line.side == "LEFT" else line.new_line):
            raise ValueError("invalid_diff_mapping")
        match = re.fullmatch(
            r"@@ -(\d{1,10})(?:,(\d{1,10}))? \+(\d{1,10})(?:,(\d{1,10}))? @@(?: .*)?", header
        )
        if match is None or line.side != ("LEFT" if line.kind == "deletion" else "RIGHT"):
            raise ValueError("invalid_diff_mapping")
        old_start, old_count, new_start, new_count = match.groups()
        for number, start, count, previous in (
            (line.old_line, int(old_start), int(old_count or 1), previous_old),
            (line.new_line, int(new_start), int(new_count or 1), previous_new),
        ):
            if number is not None and (not start <= number < start + count or number <= previous):
                raise ValueError("invalid_diff_mapping")
        previous_old = line.old_line or previous_old
        previous_new = line.new_line or previous_new
        if header != previous_header:
            groups.append([])
        groups[-1].append(line)
        previous_header, previous_position = header, line.position
    return [
        Hunk(
            id=f"{file_index}:{i}",
            path=path,
            old_path=old_path,
            new_path=new_path,
            source_header=group[0].comment_context.partition("\n")[0],
            lines=tuple(group),
            old_range=_range(tuple(group), old=True),
            new_range=_range(tuple(group), old=False),
            positions=tuple(line.position for line in group),
            changed_lines=sum(line.kind != "context" for line in group),
        )
        for i, group in enumerate(groups)
    ]


def _payload(hunks: list[Hunk], *, system_prompt: str, policy: ReviewPolicy, head_sha: str) -> str:
    # This exact JSON envelope is counted, including prompt, metadata and escaping.
    return json.dumps(
        {
            "format": "review_hunk_excerpts_v1",
            "system_prompt": system_prompt,
            "head_sha": head_sha,
            "rules_version": policy.rules_version,
            "focus": policy.focus,
            "hunks": [h.model_dump(mode="json") for h in hunks],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def plan_chunks(
    diff: PreparedDiff,
    policy: ReviewPolicy,
    profile: ProviderProfile,
    *,
    system_prompt: str,
    owner_remaining_usd: str,
) -> ChunkPlan:
    """Source order wins; an unfit hunk is skipped and later smaller hunks may fit.

    A chunk holds adjacent available hunks from one file. A filtered/unfit hunk
    flushes the current chunk. Caller-supplied prices are test/config inputs;
    neither profile correctness nor real provider token usage is verified here.
    """
    policy = ReviewPolicy.model_validate(policy.model_dump())
    diff = PreparedDiff.model_validate(diff.model_dump())
    profile = ProviderProfile.model_validate(profile.model_dump())
    if (
        not isinstance(system_prompt, str)
        or not system_prompt
        or len(system_prompt.encode("utf-8")) > 2 * 1024 * 1024
    ):
        raise ValueError("invalid_system_prompt")
    ledger = BudgetLedger(policy, profile, owner_remaining_usd=owner_remaining_usd)
    actual = sum(line.kind != "context" for f in diff.files for line in f.lines)
    if (
        actual != diff.included_changed_lines
        or diff.total_changed_lines
        != sum(f.changed_lines for f in diff.files) + diff.missing_changed_lines
        or diff.total_changed_lines != diff.included_changed_lines + diff.skipped_changed_lines
    ):
        raise ValueError("invalid_diff_coverage")
    if (
        actual > policy.budgets.max_changed_lines
        or sum(bool(f.lines) for f in diff.files) > policy.budgets.max_files
    ):
        raise ValueError("diff_policy_mismatch")
    chunks: list[Chunk] = []
    decisions: list[HunkCoverage] = []
    files: list[FileCoverage] = []
    paths: set[str] = set()
    for file_index, file in enumerate(diff.files):
        if file.path in paths:
            raise ValueError("duplicate_diff_path")
        paths.add(file.path)
        groups = _hunks(
            file.path, file.lines, file_index, old_path=file.old_path, new_path=file.new_path
        )
        available = sum(h.changed_lines for h in groups)
        if available > file.changed_lines or (file.skip_reason is not None and available):
            raise ValueError("invalid_diff_coverage")
        start = len(decisions)
        missing = file.changed_lines - available
        if missing or not groups:
            reason = file.skip_reason or ("diff_line_limit" if missing else "no_patch")
            status: Selection = (
                "skipped_budget"
                if reason in {"max_pr_lines", "max_files", "diff_line_limit"}
                else "skipped_filter"
            )
            decisions.append(
                HunkCoverage(
                    id=f"{file_index}:unavailable",
                    path=file.path,
                    source_header=None,
                    changed_lines=missing,
                    status=status,
                    reason=reason,
                    chunk_id=None,
                )
            )
        pending: list[Hunk] = []

        def flush(pending: list[Hunk]) -> None:
            if not pending:
                return
            payload = _payload(
                pending, system_prompt=system_prompt, policy=policy, head_sha=diff.head_sha
            )
            reservation = ledger.reserve(payload)
            if isinstance(reservation, Rejection):
                raise RuntimeError("reservation_invariant_failed")
            chunk_id = f"chunk-{len(chunks) + 1}"
            chunks.append(
                Chunk(id=chunk_id, hunks=tuple(pending), payload=payload, reservation=reservation)
            )
            decisions.extend(
                HunkCoverage(
                    id=h.id,
                    path=h.path,
                    source_header=h.source_header,
                    changed_lines=h.changed_lines,
                    status="included",
                    reason=None,
                    chunk_id=chunk_id,
                )
                for h in pending
            )
            pending.clear()

        for hunk in groups:
            if (
                not policy.enabled
                or diff.total_changed_lines < policy.budgets.min_changed_lines
                or hunk.changed_lines == 0
            ):
                flush(pending)
                reason = (
                    "disabled"
                    if not policy.enabled
                    else "below_min_pr_lines"
                    if diff.total_changed_lines < policy.budgets.min_changed_lines
                    else "context_only"
                )
                decisions.append(
                    HunkCoverage(
                        id=hunk.id,
                        path=hunk.path,
                        source_header=hunk.source_header,
                        changed_lines=hunk.changed_lines,
                        status="skipped_filter",
                        reason=reason,
                        chunk_id=None,
                    )
                )
                continue
            candidate = [*pending, hunk]
            decision = ledger.preview(
                _payload(
                    candidate, system_prompt=system_prompt, policy=policy, head_sha=diff.head_sha
                )
            )
            if isinstance(decision, Rejection) and pending:
                flush(pending)
                candidate = [hunk]
                decision = ledger.preview(
                    _payload(
                        candidate,
                        system_prompt=system_prompt,
                        policy=policy,
                        head_sha=diff.head_sha,
                    )
                )
            if isinstance(decision, Rejection):
                decisions.append(
                    HunkCoverage(
                        id=hunk.id,
                        path=hunk.path,
                        source_header=hunk.source_header,
                        changed_lines=hunk.changed_lines,
                        status="skipped_budget",
                        reason=decision.reason,
                        chunk_id=None,
                    )
                )
            else:
                pending = candidate
        flush(pending)
        selected = decisions[start:]
        included = sum(d.changed_lines for d in selected if d.status == "included")
        budget = sum(d.changed_lines for d in selected if d.status == "skipped_budget")
        filtered = sum(d.changed_lines for d in selected if d.status == "skipped_filter")
        files.append(
            FileCoverage(
                path=file.path,
                status="included" if included else "skipped_budget" if budget else "skipped_filter",
                total_lines=file.changed_lines,
                included_lines=included,
                skipped_budget=budget,
                skipped_filter=filtered,
                reasons=tuple(sorted({d.reason for d in selected if d.reason})),
            )
        )
    included = sum(f.included_lines for f in files)
    budget = sum(f.skipped_budget for f in files)
    filtered = sum(f.skipped_filter for f in files) + diff.missing_changed_lines
    reasons = tuple(sorted(set(diff.notes) | {r for f in files for r in f.reasons}))
    return ChunkPlan(
        head_sha=diff.head_sha,
        rules_version=policy.rules_version,
        profile=profile,
        chunks=tuple(chunks),
        hunks=tuple(decisions),
        files=tuple(files),
        totals=ledger.totals,
        coverage=Coverage(
            total_lines=diff.total_changed_lines,
            included_lines=included,
            skipped_budget=budget,
            skipped_filter=filtered,
            missing_lines=diff.missing_changed_lines,
            reviewed_line_ratio=str(Fraction(included, diff.total_changed_lines))
            if diff.total_changed_lines
            else "0",
            status="skipped"
            if not included
            else "complete"
            if included == diff.total_changed_lines and diff.coverage_complete
            else "partial",
            reasons=reasons,
        ),
    )
