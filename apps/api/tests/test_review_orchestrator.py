"""Slice 13 pipeline checks use only local fakes; no database or outbound calls."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from plutolab_api.schemas.review import ReviewIdentity, ReviewOwner, ReviewRepository
from plutolab_api.services.review.budget import ProviderProfile
from plutolab_api.services.review.github_client import PullRequest, PullRequestHead, Repository
from plutolab_api.services.review.orchestrator import ReviewOrchestrator
from plutolab_api.services.review.worker import WorkLease
from tests.test_review_jobs import request as job_request

HEAD = "a" * 40
NEW_HEAD = "c" * 40
BASE = "b" * 40
PATCH = """diff --git a/src/app.py b/src/app.py
index 0000000..1111111 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1 +1 @@
-old
+new
"""
PROVIDER_RESPONSE = (
    '{"summary":"Reviewed the changed lines.","findings":[{"file_path":"src/app.py",'
    '"line":99,"side":"RIGHT","severity":"HIGH","category":"quality",'
    '"title":"Check the changed behavior","comment_body":"The changed value is unsafe.",'
    '"suggestion":null}]}'
)


class FakeGitHub:
    def __init__(self) -> None:
        self.head_sha = HEAD
        self.pull_calls = 0

    async def get_repository(self, installation_id: str, owner: str, name: str) -> Repository:
        assert (installation_id, owner, name) == ("301", "owner", "repo")
        return Repository(id="401", full_name="owner/repo", private=True)

    async def get_pull_request(
        self, installation_id: str, owner: str, name: str, number: int
    ) -> PullRequest:
        assert (installation_id, owner, name, number) == ("301", "owner", "repo", 7)
        self.pull_calls += 1
        return PullRequest(
            number=7,
            state="open",
            title="Synthetic change",
            head=PullRequestHead(sha=self.head_sha, ref="feature"),
            base=PullRequestHead(sha=BASE, ref="main"),
            additions=1,
            deletions=1,
            changed_files=1,
        )

    async def get_pinned_diff(
        self, installation_id: str, owner: str, name: str, base_sha: str, head_sha: str
    ) -> str:
        assert (installation_id, owner, name, base_sha, head_sha) == (
            "301",
            "owner",
            "repo",
            BASE,
            HEAD,
        )
        return PATCH


class FakeProvider:
    def __init__(
        self,
        *,
        fail_count: int = 0,
        on_call=None,
        github: FakeGitHub | None = None,
    ) -> None:
        self.calls = 0
        self.fail_count = fail_count
        self.on_call = on_call
        self.github = github

    async def complete(self, _payload: str) -> str:
        self.calls += 1
        if self.on_call is not None:
            self.on_call()
        if self.github is not None:
            self.github.head_sha = NEW_HEAD
        if self.calls <= self.fail_count:
            raise TimeoutError("synthetic timeout")
        return PROVIDER_RESPONSE


def _profile() -> ProviderProfile:
    return ProviderProfile(
        provider="anthropic",
        model="local-test-model",
        pricing_version="synthetic-test-v1",
        context_window_tokens=2000,
        max_output_tokens=500,
        framing_tokens=10,
        input_usd_per_million="1.000000",
        output_usd_per_million="2.000000",
    )


def _lease(attempt_id=None) -> WorkLease:
    request = job_request()
    return WorkLease(
        job_id=uuid4(),
        owner_id=uuid4(),
        attempt_id=attempt_id or uuid4(),
        number=1,
        max_attempts=2,
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=1),
        head_sha=HEAD,
        policy=request.policy,
    )


def _identity(lease: WorkLease) -> ReviewIdentity:
    return ReviewIdentity(
        review_id=lease.job_id,
        owner=ReviewOwner(user_id=lease.owner_id, installation_id="301"),
        repo=ReviewRepository(id="401", owner_login="owner", name="repo"),
        pr_number=7,
        head_sha=HEAD,
        policy=lease.policy,
    )


def _orchestrator(
    github, provider, *, attempts=3, sleep=None, owner_remaining_usd="5.000000"
) -> ReviewOrchestrator:
    async def unused_sessions():
        raise AssertionError("test replaced every database boundary")

    async def remaining(_owner_id):
        return owner_remaining_usd

    async def no_wait(_delay):
        return None

    return ReviewOrchestrator(
        unused_sessions,
        github,
        provider,
        _profile(),
        system_prompt="Review only the supplied changed lines.",
        owner_remaining_usd=remaining,
        chunk_attempts=attempts,
        retry_base_seconds=1,
        retry_max_seconds=4,
        sleep=sleep or no_wait,
    )


def _mock_database_boundaries(monkeypatch, *, identity, cache=None, preempted=None):
    checkpoints: list[tuple[str, dict[str, object]]] = []
    saved_chunks = cache if cache is not None else {}
    preempted_jobs = preempted if preempted is not None else []

    async def load_identity(_self, _lease):
        return identity, object()

    async def checkpoint(_self, _lease, phase, **values):
        checkpoints.append((phase, values))

    async def recoverable(_self, _lease):
        return saved_chunks

    async def save_chunk(_self, _lease, chunk, payload_sha256, report):
        saved_chunks[chunk.id] = {
            "payload_sha256": payload_sha256,
            "report": report.model_dump(mode="json"),
        }
        return True

    async def preempt(_self, lease, stale):
        preempted_jobs.append((lease.job_id, stale.head_sha))

    monkeypatch.setattr(ReviewOrchestrator, "_identity", load_identity)
    monkeypatch.setattr(ReviewOrchestrator, "_checkpoint", checkpoint)
    monkeypatch.setattr(ReviewOrchestrator, "_recoverable_chunks", recoverable)
    monkeypatch.setattr(ReviewOrchestrator, "_checkpoint_chunk_result", save_chunk)
    monkeypatch.setattr(ReviewOrchestrator, "_preempt_stale", preempt)
    return checkpoints, saved_chunks, preempted_jobs


@pytest.mark.asyncio
async def test_full_pipeline_builds_verified_findings_and_checkpoints_before_provider(monkeypatch):
    lease = _lease()
    github = FakeGitHub()
    checkpoints: list[tuple[str, dict[str, object]]] = []
    provider = FakeProvider(on_call=lambda: assert_checkpoint(checkpoints))
    orchestrator = _orchestrator(github, provider)
    checkpoints, _, _ = _mock_database_boundaries(monkeypatch, identity=_identity(lease), cache={})

    result = await orchestrator(lease)

    assert result.status == "analyzed"
    assert (result.coverage.files_total, result.coverage.files_reviewed) == (1, 1)
    assert (result.coverage.changed_lines_total, result.coverage.changed_lines_reviewed) == (2, 2)
    assert len(result.findings) == 1
    assert result.findings[0].location.line == 1
    assert result.verified_diff is not None
    assert result.verified_diff.head_sha == HEAD
    verified = result.verified_diff.findings[str(result.findings[0].id)]
    assert (verified.path, verified.line, verified.side) == ("src/app.py", 1, "RIGHT")
    assert verified.position > 0 and "+new" in verified.comment_context
    assert "Check the changed behavior" in result.findings[0].description
    assert provider.calls == 1
    assert github.pull_calls >= 4
    assert [phase for phase, _ in checkpoints][-1] == "analysis_ready"


def assert_checkpoint(checkpoints: list[tuple[str, dict[str, object]]]) -> None:
    assert any(phase == "chunk_running" for phase, _ in checkpoints)


@pytest.mark.asyncio
async def test_new_head_during_provider_call_preempts_without_analysis_or_publication(monkeypatch):
    lease = _lease()
    github = FakeGitHub()
    provider = FakeProvider(github=github)
    _, _, preempted = _mock_database_boundaries(monkeypatch, identity=_identity(lease))
    result = await _orchestrator(github, provider)(lease)

    assert result.status == "partial"  # fenced placeholder cannot be persisted by the worker
    assert preempted == [(lease.job_id, NEW_HEAD)]
    assert provider.calls == 1
    assert not hasattr(result, "publication_status")


@pytest.mark.asyncio
async def test_transient_chunk_failures_retry_with_cap_and_return_explicit_partial(monkeypatch):
    lease = _lease()
    waits: list[float] = []

    async def record_wait(delay: float) -> None:
        waits.append(delay)

    github = FakeGitHub()
    provider = FakeProvider(fail_count=4)
    _mock_database_boundaries(monkeypatch, identity=_identity(lease))
    result = await _orchestrator(github, provider, attempts=2, sleep=record_wait)(lease)

    assert provider.calls == 2
    assert waits == [1]
    assert result.status == "partial"
    assert result.coverage.changed_lines_reviewed == 0
    assert "chunk_failed:chunk-1" in result.coverage.gaps


@pytest.mark.asyncio
async def test_retry_reservation_respects_remaining_owner_cost_budget(monkeypatch):
    lease = _lease()
    github = FakeGitHub()
    provider = FakeProvider(fail_count=2)
    _mock_database_boundaries(monkeypatch, identity=_identity(lease))

    result = await _orchestrator(
        github,
        provider,
        attempts=3,
        owner_remaining_usd="0.002000",
    )(lease)

    assert provider.calls == 1
    assert result.status == "partial"
    assert "retry_budget_exhausted" in result.coverage.gaps


@pytest.mark.asyncio
async def test_recovery_reuses_successful_chunk_checkpoint_without_provider_redelivery(monkeypatch):
    first_lease = _lease()
    github = FakeGitHub()
    provider = FakeProvider()
    _, cache, _ = _mock_database_boundaries(monkeypatch, identity=_identity(first_lease))
    first = await _orchestrator(github, provider)(first_lease)
    assert first.status == "analyzed"
    assert "chunk-1" in cache

    next_lease = _lease()
    _mock_database_boundaries(monkeypatch, identity=_identity(next_lease), cache=cache)
    resumed = await _orchestrator(github, provider)(next_lease)

    assert resumed.status == "analyzed"
    assert provider.calls == 1
