"""Pure fixtures and MockTransport: no sockets, test databases, or private keys."""

import socket
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from plutolab_api.core.github_app import GitHubAppCredentials, GitHubAppError
from plutolab_api.schemas.review import ReviewBudgets, ReviewIdentity, ReviewPolicy
from plutolab_api.services.review.diff import (
    MAX_DIFF_BYTES,
    MAX_LINE_LENGTH,
    DiffError,
    ReviewDiffGitHubClient,
    fetch_review_diff,
    prepare_diff,
)

SHA = "a" * 40
BASE = "b" * 40
STANDARD = """diff --git a/src/a.py b/src/a.py
index 123..456 100644
--- a/src/a.py
+++ b/src/a.py
@@ -10,3 +10,4 @@ def f():
 same
-old
+new
+extra
 tail
@@ -30 +31 @@
-before
+after
"""


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Slice 10 forbids sockets")

    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, reject)
    monkeypatch.setattr(socket, "getaddrinfo", reject)


def policy(*, maximum=100, minimum=1, skip=(), enabled=True, files=10, context=10):
    return ReviewPolicy(
        rules_version=3,
        enabled=enabled,
        focus=["quality"],
        skip_paths=list(skip),
        provider="anthropic",
        model="local",
        budgets=ReviewBudgets(
            max_files=files,
            min_changed_lines=minimum,
            max_changed_lines=maximum,
            max_context_lines_per_file=context,
            max_chunks=10,
            context_window_tokens=2000,
            max_request_input_tokens=1000,
            reserved_output_tokens=500,
            max_total_input_tokens=4000,
            max_total_output_tokens=2000,
            max_findings=10,
            max_comments=10,
            max_cost_usd="1.000000",
            max_owner_daily_cost_usd="5.000000",
            token_count_mode="conservative_estimate",
        ),
    )


def prepare(text=STANDARD, **kwargs):
    return prepare_diff(text, head_sha=SHA, policy=policy(**kwargs))


def addition(path="src/a.py"):
    return f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1 @@\n+hello\n"


def identity():
    return ReviewIdentity(
        review_id=uuid4(),
        owner={"user_id": uuid4(), "installation_id": "301"},
        repo={"id": "401", "owner_login": "pluto", "name": "repo"},
        pr_number=7,
        head_sha=SHA,
        policy=policy(),
    )


def test_multi_hunk_mapping():
    result = prepare()
    assert [
        (x.old_line, x.new_line, x.line, x.side, x.position) for x in result.files[0].lines
    ] == [
        (10, 10, 10, "RIGHT", 1),
        (11, None, 11, "LEFT", 2),
        (None, 11, 11, "RIGHT", 3),
        (None, 12, 12, "RIGHT", 4),
        (12, 13, 13, "RIGHT", 5),
        (30, None, 30, "LEFT", 7),
        (None, 31, 31, "RIGHT", 8),
    ]
    assert result.files[0].lines[-1].comment_context == "@@ -30 +31 @@\n+after"
    assert result.total_changed_lines == result.included_changed_lines == 5
    assert result.skipped_changed_lines == 0
    assert result.coverage_complete and result == prepare()


@pytest.mark.parametrize("kind", ["added", "deleted", "renamed"])
def test_lifecycle(kind):
    text = addition()
    if kind == "deleted":
        text = "diff --git a/src/a.py b/src/a.py\ndeleted file mode 100644\n--- a/src/a.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-hello\n"
    elif kind == "renamed":
        text = "diff --git a/old.py b/new.py\nsimilarity index 90%\nrename from old.py\nrename to new.py\n--- a/old.py\n+++ b/new.py\n@@ -1 +1 @@\n-old\n+new\n"
    file = prepare(text).files[0]
    assert file.status == kind and file.lines[-1].line == 1
    assert file.lines[-1].side == ("LEFT" if kind == "deleted" else "RIGHT")


@pytest.mark.parametrize(
    ("pattern", "path", "skipped"),
    [
        ("**/*.py", "a.py", True),
        ("**/*.py", "src/deep/a.py", True),
        ("src/*.py", "src/deep/a.py", False),
        ("src/?.py", "src/a.py", True),
        ("src/?.py", "src/ab.py", False),
        ("docs/**", "docs/deep/a.md", True),
        ("**/vendor/**", "vendor/a.py", True),
    ],
)
def test_globs(pattern, path, skipped):
    assert (prepare(addition(path), skip=[pattern]).files[0].skip_reason == "skip_paths") == skipped


@pytest.mark.parametrize(
    "path",
    [
        "package-lock.json",
        "nested/uv.lock",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Cargo.lock",
        "go.sum",
        "Pipfile.lock",
    ],
)
def test_lockfiles(path):
    assert prepare(addition(path)).files[0].skip_reason == "lockfile"


@pytest.mark.parametrize(
    "path", ["dist/a.js", "src/__generated__/a.ts", "a.min.js", "api_pb2.py", "images/a.PNG"]
)
def test_assets(path):
    assert prepare(addition(path)).files[0].skip_reason in {"generated", "binary"}


def test_generated_marker():
    assert (
        prepare(addition().replace("+hello", "+# @generated")).files[0].skip_reason == "generated"
    )


def test_rename_old_path_filter():
    text = "diff --git a/secret.py b/a.py\nrename from secret.py\nrename to a.py\n--- a/secret.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new\n"
    assert prepare(text, skip=["secret.py"]).files[0].skip_reason == "skip_paths"


def test_budget():
    result = prepare(maximum=2)
    assert (
        result.total_changed_lines,
        result.included_changed_lines,
        result.skipped_changed_lines,
    ) == (5, 2, 3)
    assert result.truncated and not result.coverage_complete
    assert "max_pr_lines" in result.notes
    assert [(x.line, x.side) for x in result.files[0].lines if x.kind != "context"] == [
        (11, "LEFT"),
        (11, "RIGHT"),
    ]


def test_context_budget():
    result = prepare(context=0)
    assert len(result.files[0].lines) == result.included_changed_lines == 5


@pytest.mark.parametrize(
    ("options", "reason"),
    [({"minimum": 6}, "below_min_pr_lines"), ({"enabled": False}, "disabled")],
)
def test_skips(options, reason):
    result = prepare(**options)
    assert result.included_changed_lines == 0 and result.files[0].skip_reason == reason


def test_file_limit():
    result = prepare(addition("a.py") + addition("b.py"), files=1)
    assert result.included_changed_lines == 1 and result.truncated
    assert result.files[1].skip_reason == "max_files"


def test_binary_missing_coverage():
    result = prepare_diff(
        "diff --git a/a.png b/a.png\nBinary files a/a.png and b/a.png differ\n",
        head_sha=SHA,
        policy=policy(),
        expected_changed_lines=8,
        expected_files=2,
    )
    assert result.missing_changed_lines == result.skipped_changed_lines == 8
    assert set(result.notes) == {"binary", "missing_patch_coverage"}
    assert not result.coverage_complete


def test_rename_only():
    assert (
        prepare(
            "diff --git a/a.py b/b.py\nsimilarity index 100%\nrename from a.py\nrename to b.py\n"
        )
        .files[0]
        .skip_reason
        == "no_patch"
    )


@pytest.mark.parametrize("path", ["../a.py", "/a.py", "a/../b.py", "a//b.py"])
def test_unsafe_paths(path):
    with pytest.raises(DiffError):
        prepare(addition(path))


def test_unicode_paths():
    text = 'diff --git "a/\\344\\270\\255.py" "b/\\344\\270\\255.py"\n--- "a/\\344\\270\\255.py"\n+++ "b/\\344\\270\\255.py"\n@@ -1 +1 @@\n-x\n+y\n'
    assert prepare(text).files[0].path == "中.py"


def test_spaces():
    assert prepare(addition("hello world.py")).files[0].path == "hello world.py"


def test_no_newline_marker():
    text = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x\n\\ No newline at end of file\n+y\n\\ No newline at end of file\n"
    assert [x.position for x in prepare(text).files[0].lines] == [1, 3]


@pytest.mark.parametrize(
    "text",
    [
        STANDARD.rsplit("+after", 1)[0],
        STANDARD.replace("@@ -30 +31 @@", "@@ -1 +1 @@"),
        STANDARD.replace("@@ -30 +31 @@", "@@@ -30 +31 @@@"),
        STANDARD + "+extra\n",
        "not a diff",
        STANDARD + STANDARD,
    ],
)
def test_malformed(text):
    with pytest.raises(DiffError):
        prepare(text)


@pytest.mark.parametrize(
    "text", ["x" * (MAX_DIFF_BYTES + 1), addition().replace("+hello", "+" + "x" * MAX_LINE_LENGTH)]
)
def test_bounds(text):
    with pytest.raises(DiffError, match=r"too_large|too_long"):
        prepare(text)


def test_missing():
    result = prepare_diff(
        "", head_sha=SHA, policy=policy(), expected_changed_lines=10, expected_files=1
    )
    assert result.included_changed_lines == 0 and result.missing_changed_lines == 10
    assert "missing_patch_coverage" in result.notes


def test_metadata_mismatch():
    with pytest.raises(DiffError, match="diff_metadata_mismatch"):
        prepare_diff(STANDARD, head_sha=SHA, policy=policy(), expected_changed_lines=1)


class Harness:
    def __init__(
        self, monkeypatch, *, head=SHA, later_head=SHA, repo_id=401, diff=STANDARD, status=200
    ):
        self.requests = []
        self.reads = 0
        monkeypatch.setattr(GitHubAppCredentials, "create_jwt", lambda _: SecretStr("mock-jwt"))

        def respond(request):
            self.requests.append(request)
            assert request.url.host == "api.github.com"
            if request.method == "POST":
                return httpx.Response(
                    201,
                    json={
                        "token": "mock-installation-token",
                        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                    },
                )
            if "/compare/" in request.url.path:
                return httpx.Response(status, content=diff)
            if "/pulls/" in request.url.path:
                self.reads += 1
                return httpx.Response(
                    200,
                    json={
                        "number": 7,
                        "state": "open",
                        "title": "local",
                        "head": {"sha": head if self.reads == 1 else later_head, "ref": "feature"},
                        "base": {"sha": BASE, "ref": "main"},
                        "additions": 3,
                        "deletions": 2,
                        "changed_files": 1,
                        "diff_url": "https://evil.invalid/secret",
                    },
                )
            return httpx.Response(
                200, json={"id": repo_id, "full_name": "pluto/repo", "private": True}
            )

        self.client = ReviewDiffGitHubClient(
            GitHubAppCredentials("1", SecretStr("not-a-key")),
            transport=httpx.MockTransport(respond),
        )


@pytest.mark.asyncio
async def test_fetch(monkeypatch):
    h = Harness(monkeypatch)
    async with h.client as client:
        result = await fetch_review_diff(client, identity())
    assert result.included_changed_lines == 5 and h.reads == 2
    compare = [r for r in h.requests if "/compare/" in r.url.path]
    assert len(compare) == 1 and compare[0].url.path.endswith(f"/{BASE}...{SHA}")
    assert compare[0].headers["accept"] == "application/vnd.github.diff"


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["before", "after", "repository"])
async def test_stale(monkeypatch, phase):
    h = Harness(
        monkeypatch,
        head="c" * 40 if phase == "before" else SHA,
        later_head="c" * 40 if phase == "after" else SHA,
        repo_id=402 if phase == "repository" else 401,
    )
    async with h.client as client:
        with pytest.raises(DiffError, match=r"stale_head|repository_mismatch"):
            await fetch_review_diff(client, identity())
    if phase != "after":
        assert not any("/compare/" in r.url.path for r in h.requests)


@pytest.mark.asyncio
async def test_redaction(monkeypatch):
    h = Harness(monkeypatch, status=404, diff="mock-installation-token private-source")
    async with h.client as client:
        with pytest.raises(GitHubAppError) as caught:
            await fetch_review_diff(client, identity())
    assert "mock-installation-token" not in str(caught.value) and "private-source" not in str(
        caught.value
    )


@pytest.mark.parametrize(
    "pattern", ["[abc]", "../secret", "src/**bad", "src//bad", "a\\b", "a" * 257]
)
def test_invalid_frozen_globs_rejected(pattern):
    with pytest.raises(ValueError):
        prepare(skip=[pattern])


def test_many_recursive_globs_are_bounded():
    result = prepare(addition("a/" * 40 + "file.py"), skip=["**/" * 40 + "missing.py"])
    assert result.included_changed_lines == 1


def test_vertical_tab_is_source_content_not_a_diff_separator():
    result = prepare(addition().replace("+hello", "+a\vb"))
    assert result.files[0].lines[0].content == "a\vb"


@pytest.mark.parametrize(
    "text",
    [
        STANDARD.replace("+++ b/src/a.py", "+++ b/other.py"),
        STANDARD.replace("--- a/src/a.py\n", ""),
        STANDARD.replace("@@ -30 +31 @@", "@@ -" + "9" * 100 + " +31 @@"),
        addition().replace("@@ -0,0 +1 @@", "@@ -0,0 +0 @@"),
    ],
)
def test_bad_headers_and_ranges(text):
    with pytest.raises(DiffError):
        prepare(text)


def test_multiple_files_budget_and_filter_accounting():
    result = prepare(addition("uv.lock") + addition("a.py") + addition("b.py"), maximum=1)
    assert result.total_changed_lines == 3
    assert result.included_changed_lines == 1
    assert result.skipped_changed_lines == 2
    assert result.missing_changed_lines == 0
    assert result.truncated
    assert result.files[1].lines[0].position == 1


@pytest.mark.asyncio
async def test_invalid_diff_encoding(monkeypatch):
    h = Harness(monkeypatch, diff=b"\xff")
    async with h.client as client:
        with pytest.raises(GitHubAppError, match="invalid_diff_encoding"):
            await fetch_review_diff(client, identity())


@pytest.mark.asyncio
@pytest.mark.parametrize("component", ["owner", "repo", "sha"])
async def test_pinned_path_rejects_external_components(monkeypatch, component):
    h = Harness(monkeypatch)
    async with h.client as client:
        with pytest.raises(ValueError):
            await client.get_pinned_diff(
                "301",
                "https://evil.invalid" if component == "owner" else "pluto",
                "../repo" if component == "repo" else "repo",
                BASE,
                "main" if component == "sha" else SHA,
            )
    assert not h.requests


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["base", "additions", "changed_files", "state", "number"])
async def test_metadata_changes_during_fetch_fail_closed(monkeypatch, field):
    h = Harness(monkeypatch)
    original = h.client.get_pull_request

    async def changed(*args):
        pr = await original(*args)
        if h.reads == 2:
            values = pr.model_dump()
            values[field] = (
                {"sha": "c" * 40, "ref": "main"}
                if field == "base"
                else "closed"
                if field == "state"
                else 99
            )
            return type(pr).model_validate(values)
        return pr

    monkeypatch.setattr(h.client, "get_pull_request", changed)
    async with h.client as client:
        with pytest.raises(DiffError, match="stale_head"):
            await fetch_review_diff(client, identity())


def test_rename_metadata_cannot_replace_header_identity():
    with pytest.raises(DiffError, match="inconsistent_path"):
        prepare("diff --git a/secret.py b/a.py\nrename from public.py\nrename to a.py\n")


@pytest.mark.asyncio
async def test_encoding_error_keeps_no_upstream_exception(monkeypatch):
    h = Harness(monkeypatch, diff=b"private-source\xff")
    async with h.client as client:
        with pytest.raises(GitHubAppError) as caught:
            await fetch_review_diff(client, identity())
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
