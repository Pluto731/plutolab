"""Bounded unified diff parsing and SHA-pinned fetching. No worker/provider side effects."""

import ast
import re
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import PurePosixPath

from pydantic import TypeAdapter

from plutolab_api.core.github_app import GitHubAppError
from plutolab_api.schemas.review import HeadSha, ReviewIdentity, ReviewPolicy
from plutolab_api.schemas.review_diff import DiffFile, DiffLine, PreparedDiff
from plutolab_api.services.review.github_client import GitHubAppClient, PullRequest
from plutolab_api.services.review.settings import ReviewRules

MAX_DIFF_BYTES = 2 * 1024 * 1024
MAX_LINE_LENGTH = 16_384
MAX_FILES = 10_000
_HUNK = re.compile(r"^@@ -(\d{1,10})(?:,(\d{1,10}))? \+(\d{1,10})(?:,(\d{1,10}))? @@(?: .*)?$")
_LOCKS = {
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "Gemfile.lock",
    "composer.lock",
    "go.sum",
}
_BINARY = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".woff",
    ".woff2",
    ".ttf",
    ".mp4",
    ".mp3",
    ".exe",
    ".dll",
    ".so",
    ".pyc",
}
_GENERATED_DIRS = {
    "node_modules",
    "vendor",
    "dist",
    "build",
    ".next",
    "__pycache__",
    "generated",
    "__generated__",
}


class DiffError(ValueError):
    """Stable error code only; never include repository contents or credentials."""


class ReviewDiffGitHubClient(GitHubAppClient):
    async def get_pinned_diff(
        self, installation_id: str, owner: str, repo: str, base_sha: str, head_sha: str
    ) -> str:
        # Validate components before constructing a fixed-origin adapter path.
        if (
            not re.fullmatch(r"[A-Za-z0-9-]{1,100}", owner)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repo)
            or repo in {".", ".."}
        ):
            raise DiffError("invalid_repository")
        for sha in (base_sha, head_sha):
            TypeAdapter(HeadSha).validate_python(sha)
        response = await self._get(
            installation_id,
            f"/repos/{owner}/{repo}/compare/{base_sha}...{head_sha}",
            accept="application/vnd.github.diff",
        )
        try:
            return response.content.decode("utf-8")
        except UnicodeDecodeError:
            pass
        raise GitHubAppError("invalid_diff_encoding")


def _path(value: str, prefix: str = "") -> str | None:
    if value.startswith('"'):
        try:
            # Git quotes UTF-8 bytes using C octal escapes.
            decoded = ast.literal_eval(value)
            if not isinstance(decoded, str):
                raise ValueError
            value = decoded.encode("latin1").decode("utf-8") if "\\" in value else decoded
        except (ValueError, SyntaxError, UnicodeError) as exc:
            raise DiffError("invalid_path") from exc
    if value == "/dev/null":
        return None
    if prefix:
        if not value.startswith(prefix):
            raise DiffError("invalid_path_prefix")
        value = value[len(prefix) :]
    if (
        len(value) > 4096
        or not value.isprintable()
        or "\\" in value
        or any(p in {"", ".", ".."} for p in value.split("/"))
    ):
        raise DiffError("invalid_path")
    return value


def _matches(pattern: str, path: str) -> bool:
    """Segment DP avoids exponential backtracking with repeated ** components."""
    parts = path.split("/")
    previous = [True] + [False] * len(parts)
    for segment in pattern.split("/"):
        current = [segment == "**" and previous[0]] + [False] * len(parts)
        for i, part in enumerate(parts, 1):
            current[i] = (
                (previous[i] or current[i - 1])
                if segment == "**"
                else previous[i - 1] and fnmatchcase(part, segment)
            )
        previous = current
    return previous[-1]


@dataclass
class _File:
    old: str | None
    new: str | None
    lines: list[DiffLine] = field(default_factory=list)
    binary: bool = False
    old_header: bool = False
    new_header: bool = False
    hunk_seen: bool = False


def _parse(text: str) -> list[_File]:
    if len(text) > MAX_DIFF_BYTES or len(text.encode("utf-8")) > MAX_DIFF_BYTES:
        raise DiffError("diff_too_large")
    files: list[_File] = []
    current = None
    old = new = old_left = new_left = position = 0
    context = ""
    raw_lines = text.split("\n")
    if raw_lines[-1] == "":
        raw_lines.pop()
    for raw in raw_lines:
        if len(raw) > MAX_LINE_LENGTH:
            raise DiffError("diff_line_too_long")
        if raw.startswith("diff --git "):
            if old_left or new_left:
                raise DiffError("incomplete_hunk")
            header = raw[11:]
            match = re.fullmatch(r'("(?:\\.|[^"\\])*"|a/.*?) ("(?:\\.|[^"\\])*"|b/.*)', header)
            tokens = list(match.groups()) if match else []
            if len(tokens) != 2:
                raise DiffError("invalid_file_header")
            current = _File(_path(tokens[0], "a/"), _path(tokens[1], "b/"))
            files.append(current)
            if len(files) > MAX_FILES:
                raise DiffError("too_many_files")
            position = 0
            continue
        if current is None:
            if raw:
                raise DiffError("invalid_diff_header")
            continue
        if raw.startswith("@@"):
            if not current.old_header or not current.new_header or current.binary:
                raise DiffError("missing_patch_headers")
            if old_left or new_left:
                raise DiffError("incomplete_hunk")
            match = _HUNK.fullmatch(raw)
            if not match:
                raise DiffError("invalid_hunk")
            a, alen, b, blen = match.groups()
            next_old, next_new = int(a), int(b)
            if current.hunk_seen and (next_old < old or next_new < new):
                raise DiffError("overlapping_hunks")
            old, new = next_old, next_new
            old_left, new_left = int(alen or 1), int(blen or 1)
            if (old_left and (not old or current.old is None)) or (
                new_left and (not new or current.new is None)
            ):
                raise DiffError("invalid_hunk_range")
            position += int(current.hunk_seen)
            current.hunk_seen = True
            context = raw
            continue
        if raw == "\\ No newline at end of file":
            if not current.lines:
                raise DiffError("invalid_newline_marker")
            position += 1
            continue
        if old_left or new_left:
            prefix = raw[:1]
            if prefix not in {"+", "-", " "}:
                raise DiffError("invalid_hunk_line")
            left, right = prefix != "+", prefix != "-"
            if (left and not old_left) or (right and not new_left):
                raise DiffError("invalid_hunk_count")
            position += 1
            current.lines.append(
                DiffLine(
                    kind={"+": "addition", "-": "deletion", " ": "context"}[prefix],
                    old_line=old if left else None,
                    new_line=new if right else None,
                    line=new if right else old,
                    side="RIGHT" if right else "LEFT",
                    position=position,
                    content=raw[1:],
                    comment_context=context + "\n" + raw,
                )
            )
            if left:
                old += 1
                old_left -= 1
            if right:
                new += 1
                new_left -= 1
            continue
        if current.hunk_seen:
            raise DiffError("unexpected_hunk_content")
        if raw.startswith("--- "):
            value = _path(raw[4:], "a/")
            if current.old_header or (value is not None and value != current.old):
                raise DiffError("inconsistent_path")
            current.old = value
            current.old_header = True
        elif raw.startswith("+++ "):
            value = _path(raw[4:], "b/")
            if current.new_header or (value is not None and value != current.new):
                raise DiffError("inconsistent_path")
            current.new = value
            current.new_header = True
        elif raw.startswith("rename from "):
            if _path(raw[12:]) != current.old:
                raise DiffError("inconsistent_path")
        elif raw.startswith("rename to "):
            if _path(raw[10:]) != current.new:
                raise DiffError("inconsistent_path")
        elif raw.startswith("Binary files ") or raw == "GIT binary patch":
            current.binary = True
        elif raw.startswith("new file mode "):
            current.old = None
        elif raw.startswith("deleted file mode "):
            current.new = None
        elif (
            not current.binary
            and raw
            and not raw.startswith(
                (
                    "index ",
                    "old mode ",
                    "new mode ",
                    "similarity index ",
                    "dissimilarity index ",
                    "copy from ",
                    "copy to ",
                )
            )
        ):
            raise DiffError("invalid_file_metadata")
    if old_left or new_left:
        raise DiffError("incomplete_hunk")
    return files


def prepare_diff(
    text: str,
    *,
    head_sha: str,
    policy: ReviewPolicy,
    expected_changed_lines: int | None = None,
    expected_files: int | None = None,
) -> PreparedDiff:
    """Selection metrics count additions plus deletions, never context or LLM analysis."""
    TypeAdapter(HeadSha).validate_python(head_sha)
    ReviewRules(skip_paths=policy.skip_paths)
    parsed = _parse(text)
    observed = sum(line.kind != "context" for f in parsed for line in f.lines)
    for number in (expected_changed_lines, expected_files):
        if number is not None and (type(number) is not int or number < 0):
            raise DiffError("invalid_expected_coverage")
    if (expected_changed_lines is not None and observed > expected_changed_lines) or (
        expected_files is not None and len(parsed) > expected_files
    ):
        raise DiffError("diff_metadata_mismatch")
    total = observed if expected_changed_lines is None else expected_changed_lines
    missing = total - observed
    budget = policy.budgets
    remaining = budget.max_changed_lines
    notes: set[str] = set()
    output: list[DiffFile] = []
    included = selected_files = 0
    truncated = False
    seen: set[str] = set()
    for f in parsed:
        path = f.new or f.old
        if path is None or path in seen:
            raise DiffError("invalid_or_duplicate_path")
        seen.add(path)
        paths = [p for p in (f.old, f.new) if p is not None]
        changed = sum(line.kind != "context" for line in f.lines)
        reason = None
        if not f.hunk_seen and not f.binary:
            reason = "no_patch"
        elif not policy.enabled:
            reason = "disabled"
        elif total < budget.min_changed_lines:
            reason = "below_min_pr_lines"
        elif any(_matches(pattern, p) for p in paths for pattern in policy.skip_paths):
            reason = "skip_paths"
        elif any(PurePosixPath(p).name in _LOCKS or p.endswith(".lock") for p in paths):
            reason = "lockfile"
        elif f.binary or any(PurePosixPath(p).suffix.lower() in _BINARY for p in paths):
            reason = "binary"
        elif any(
            set(PurePosixPath(p).parts) & _GENERATED_DIRS
            or p.endswith((".min.js", ".min.css", ".map", ".generated.ts", "_pb2.py", ".pb.go"))
            for p in paths
        ) or any(
            "@generated" in line.content or "Code generated" in line.content
            for line in f.lines[:20]
        ):
            reason = "generated"
        elif selected_files >= budget.max_files:
            reason = "max_files"
            truncated = True
        elif remaining == 0:
            reason = "max_pr_lines"
            truncated = True
        lines: list[DiffLine] = []
        if reason:
            notes.add(reason)
        else:
            context_left = budget.max_context_lines_per_file
            for line in f.lines:
                if line.kind == "context":
                    if context_left and remaining:
                        lines.append(line)
                        context_left -= 1
                elif remaining:
                    lines.append(line)
                    remaining -= 1
                    included += 1
                else:
                    truncated = True
                    notes.add("max_pr_lines")
            selected_files += 1
        output.append(
            DiffFile(
                path=path,
                old_path=f.old,
                new_path=f.new,
                status="added"
                if f.old is None
                else "deleted"
                if f.new is None
                else "renamed"
                if f.old != f.new
                else "modified",
                changed_lines=changed,
                lines=tuple(lines),
                skip_reason=reason,
            )
        )
    if missing or (expected_files is not None and len(parsed) < expected_files):
        notes.add("missing_patch_coverage")
        truncated = True
    return PreparedDiff(
        head_sha=head_sha,
        files=tuple(output),
        total_changed_lines=total,
        included_changed_lines=included,
        skipped_changed_lines=total - included,
        missing_changed_lines=missing,
        truncated=truncated,
        coverage_complete=not notes and included == total,
        notes=tuple(sorted(notes)),
    )


def _fingerprint(pr: PullRequest) -> tuple[object, ...]:
    return (
        pr.number,
        pr.state,
        pr.head.sha,
        pr.base.sha,
        pr.additions,
        pr.deletions,
        pr.changed_files,
    )


async def fetch_review_diff(client: ReviewDiffGitHubClient, job: ReviewIdentity) -> PreparedDiff:
    """Use server-owned job identity and frozen policy, never webhook URLs/live rules.

    A compare request is pinned to immutable base/head SHAs. Metadata reads alone
    around a mutable PR diff would not protect against an ABA head change.
    """
    args = (job.owner.installation_id, job.repo.owner_login, job.repo.name)
    repository = await client.get_repository(*args)
    if (
        repository.id != job.repo.id
        or repository.full_name.lower() != f"{job.repo.owner_login}/{job.repo.name}".lower()
    ):
        raise DiffError("repository_mismatch")
    before = await client.get_pull_request(*args, job.pr_number)
    if before.number != job.pr_number or before.head.sha != job.head_sha or before.state != "open":
        raise DiffError("stale_head")
    text = await client.get_pinned_diff(*args, before.base.sha, job.head_sha)
    after = await client.get_pull_request(*args, job.pr_number)
    if _fingerprint(before) != _fingerprint(after):
        raise DiffError("stale_head")
    return prepare_diff(
        text,
        head_sha=job.head_sha,
        policy=job.policy,
        expected_changed_lines=before.additions + before.deletions,
        expected_files=before.changed_files,
    )
