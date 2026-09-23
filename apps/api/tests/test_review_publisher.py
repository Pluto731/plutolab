"""Publication rendering and write behavior use local fakes only."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from plutolab_api.schemas.review import (
    FindingLocation,
    ReviewFinding,
    ReviewIdentity,
    ReviewOwner,
    ReviewRepository,
)
from plutolab_api.schemas.review_diff import PreparedDiff
from plutolab_api.schemas.review_publication import RemotePublication
from plutolab_api.services.review.diff import prepare_diff
from plutolab_api.services.review.jobs import ReviewStateError
from plutolab_api.services.review.publisher import (
    GitHubPublicationError,
    ReviewPublisher,
    render_publication,
)
from tests.test_review_jobs import request

HEAD = "a" * 40
PATCH = """diff --git a/src/app.py b/src/app.py
index 0000000..1111111 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,2 +1,2 @@
 before
-old_value
+new_value
"""


def fixture():
    owner_id = uuid4()
    job_id = uuid4()
    enqueue = request(head_sha=HEAD)
    identity = ReviewIdentity(
        review_id=job_id,
        owner=ReviewOwner(user_id=owner_id, installation_id="301"),
        repo=ReviewRepository(id="401", owner_login="owner", name="repo"),
        pr_number=7,
        head_sha=HEAD,
        policy=enqueue.policy,
    )
    finding = ReviewFinding(
        id=uuid4(),
        fingerprint="finding-1",
        focus="security",
        severity="HIGH",
        location=FindingLocation(path="src/app.py", line=2, side="RIGHT"),
        description="Validate this value before use.",
        suggestion="Check the input.",
        evidence="The new value reaches the parser.",
    )
    diff = prepare_diff(PATCH, head_sha=HEAD, policy=enqueue.policy)
    job = SimpleNamespace(
        id=job_id,
        owner_id=owner_id,
        installation_id="301",
        repo_id="401",
        pr_number=7,
        head_sha=HEAD,
        rules_version=enqueue.policy.rules_version,
        policy=enqueue.policy.model_dump(mode="json"),
        analysis_status="analyzed",
        publication_status="preview_ready",
        publication={"status": "preview_ready"},
        findings=[finding.model_dump(mode="json")],
        coverage={
            "files_total": 1,
            "files_reviewed": 1,
            "changed_lines_total": 2,
            "changed_lines_reviewed": 2,
            "gaps": [],
        },
        summary="The changed value should be validated.",
    )
    return identity, job, diff, finding


def test_summary_and_inline_comment_use_exact_verified_diff_position():
    identity, job, diff, _finding = fixture()

    rendered = render_publication(identity, job, diff, max_inline_comments=5)

    assert rendered.finding_count == 1
    assert rendered.inline_count == 1
    assert rendered.omitted_inline_count == 0
    comment = rendered.comments[0]
    assert (comment.path, comment.line, comment.side) == ("src/app.py", 2, "RIGHT")
    assert comment.position == 3
    assert "risk findings" in rendered.body.lower()
    assert "Changed lines: 2" in rendered.body
    assert "HIGH" in rendered.body and rendered.marker in rendered.body


def test_unmapped_or_over_limit_findings_fall_back_to_summary_without_fake_position():
    identity, job, diff, _finding = fixture()
    diff = PreparedDiff.model_validate({**diff.model_dump(), "missing_changed_lines": 1})

    rendered = render_publication(identity, job, diff, max_inline_comments=0)

    assert rendered.comments == ()
    assert rendered.omitted_inline_count == 1
    assert rendered.status == "partially_published"
    assert "src/app.py:2" in rendered.body
    with pytest.raises(ReviewStateError, match="diff/head mismatch"):
        render_publication(
            identity,
            job,
            PreparedDiff.model_validate({**diff.model_dump(), "head_sha": "b" * 40}),
            max_inline_comments=1,
        )


class _FakeDB:
    async def commit(self):
        return None


class _FakeGitHub:
    def __init__(self, *, existing=None, reject_inline=False):
        self.existing = existing or []
        self.reject_inline = reject_inline
        self.review_calls = 0
        self.comment_calls = 0
        self.last_body = None

    async def list_pull_request_reviews(self, _identity):
        return self.existing

    async def list_issue_comments(self, _identity):
        return self.existing

    async def create_pull_request_review(self, _identity, *, body, comments):
        self.review_calls += 1
        assert comments and "plutolab-review:" in body
        if self.reject_inline:
            raise GitHubPublicationError(422)
        self.last_body = body
        return RemotePublication(id="901", body=body)

    async def create_issue_comment(self, _identity, *, body):
        self.comment_calls += 1
        self.last_body = body
        return RemotePublication(id="902", body=body)

    async def update_issue_comment(self, _identity, comment_id, *, body):
        raise AssertionError(f"publisher should not edit comment {comment_id}")


@pytest.mark.asyncio
async def test_existing_marker_skips_duplicate_github_writes(monkeypatch):
    identity, job, diff, _finding = fixture()
    marker = f"<!-- plutolab-review:{identity.review_id}:{HEAD} -->"
    github = _FakeGitHub(existing=[RemotePublication(id="903", body=f"old\n{marker}")])
    db = _FakeDB()

    @asynccontextmanager
    async def sessions():
        yield db

    attempt_id = uuid4()

    async def get_job(*_):
        return job

    async def begin(*_args, **_kwargs):
        return SimpleNamespace(id=attempt_id)

    async def record(*_args, **_kwargs):
        return job

    monkeypatch.setattr("plutolab_api.services.review.publisher.get_job", get_job)
    monkeypatch.setattr("plutolab_api.services.review.publisher.begin_publication", begin)
    monkeypatch.setattr("plutolab_api.services.review.publisher.record_publication", record)

    receipt = await ReviewPublisher(sessions, github).publish(
        identity, diff, publication_authorized=True
    )

    assert receipt.status == "published"
    assert receipt.github_review_ids == ["903"]
    assert github.review_calls == github.comment_calls == 0
    assert job.analysis_status == "analyzed"


@pytest.mark.asyncio
async def test_inline_422_falls_back_to_summary_comment_and_records_partial(monkeypatch):
    identity, job, diff, _finding = fixture()
    github = _FakeGitHub(reject_inline=True)
    db = _FakeDB()
    attempt_id = uuid4()
    recorded = []

    @asynccontextmanager
    async def sessions():
        yield db

    async def get_job(*_):
        return job

    async def begin(*_args, **_kwargs):
        return SimpleNamespace(id=attempt_id)

    async def record(_db, _owner_id, _job_id, value):
        recorded.append(value)
        return job

    monkeypatch.setattr("plutolab_api.services.review.publisher.get_job", get_job)
    monkeypatch.setattr("plutolab_api.services.review.publisher.begin_publication", begin)
    monkeypatch.setattr("plutolab_api.services.review.publisher.record_publication", record)

    receipt = await ReviewPublisher(sessions, github).publish(
        identity, diff, publication_authorized=True
    )

    assert receipt.status == "partially_published"
    assert github.review_calls == github.comment_calls == 1
    assert "src/app.py:2" in github.last_body
    assert recorded == [receipt]


def test_head_mismatch_is_rejected_before_any_publication():
    identity, job, diff, _finding = fixture()
    bad_diff = PreparedDiff.model_validate({**diff.model_dump(), "head_sha": "b" * 40})

    with pytest.raises(ReviewStateError, match="diff/head mismatch"):
        render_publication(identity, job, bad_diff, max_inline_comments=10)
