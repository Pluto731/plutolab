"""Full local Phase 5 chain from signed webhook to owner-scoped read response."""

from collections import deque
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from plutolab_api.api.v1.router import api_router
from plutolab_api.core.security import create_access_token
from plutolab_api.db.deps import get_db
from plutolab_api.models.review import ReviewJob
from plutolab_api.schemas.review import (
    PublicationDraft,
    ReviewIdentity,
    ReviewOwner,
    ReviewPolicy,
    ReviewRepository,
    VerifiedDiffPosition,
)
from plutolab_api.schemas.review_publication import RemotePublication
from plutolab_api.services.review.diff import fetch_review_diff
from plutolab_api.services.review.jobs import record_publication
from plutolab_api.services.review.orchestrator import ReviewOrchestrator
from plutolab_api.services.review.publisher import GitHubPublicationError, ReviewPublisher
from plutolab_api.services.review.worker import (
    BrokerReceipt,
    Consumer,
    Dispatcher,
    WorkMessage,
)
from tests.test_review_domain import owners as owners
from tests.test_review_domain import review_db as review_db
from tests.test_review_domain import review_engine as review_engine
from tests.test_review_orchestrator import FakeGitHub, FakeProvider, _profile
from tests.test_review_webhook_api import post_event
from tests.test_review_webhook_api import webhook_api as webhook_api

PATCH = """diff --git a/src/app.py b/src/app.py
index 0000000..1111111 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1 +1 @@
-old = 1
+new = 2
diff --git a/package-lock.json b/package-lock.json
index 0000000..1111111 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -1 +1 @@
-{}
+{\"version\":2}
"""


class LocalGitHub(FakeGitHub):
    async def get_pull_request(self, *args):
        pull = await super().get_pull_request(*args)
        return pull.model_copy(update={"additions": 2, "deletions": 2, "changed_files": 2})

    async def get_pinned_diff(self, *_args):
        return PATCH


class LocalBroker:
    def __init__(self):
        self.messages = deque()
        self.acknowledged = []

    async def publish(self, message: WorkMessage) -> str:
        receipt = BrokerReceipt(receipt_id=str(uuid4()), message=message)
        self.messages.append(receipt)
        return receipt.receipt_id

    async def receive(self) -> BrokerReceipt | None:
        return self.messages.popleft() if self.messages else None

    async def acknowledge(self, receipt: BrokerReceipt) -> None:
        self.acknowledged.append(receipt.receipt_id)


class RejectInlinePublisher:
    async def list_pull_request_reviews(self, _identity):
        return []

    async def list_issue_comments(self, _identity):
        return []

    async def create_pull_request_review(self, _identity, *, body, comments):
        assert comments and all(comment.position > 0 for comment in comments)
        raise GitHubPublicationError(422)

    async def create_issue_comment(self, _identity, *, body):
        return RemotePublication(id="99002", body=body)

    async def update_issue_comment(self, *_args, **_kwargs):
        raise AssertionError("unexpected comment edit")


@pytest.mark.asyncio
async def test_signed_webhook_to_publish_fallback_and_owner_scoped_read(
    webhook_api, review_db, owners
):
    first, _second = owners
    accepted = await post_event(webhook_api, delivery=str(uuid4()))
    assert accepted.status_code == 202
    job = await review_db.scalar(select(ReviewJob).where(ReviewJob.owner_id == first.id))
    assert job is not None
    job.policy = {**job.policy, "publication_mode": "comment"}
    await review_db.flush()

    @asynccontextmanager
    async def sessions():
        yield review_db

    broker = LocalBroker()
    dispatch = await Dispatcher(sessions, broker).dispatch_once()
    assert dispatch["dispatched"] == 1

    async def remaining_budget(_owner_id):
        return "5.000000"

    github = LocalGitHub()
    orchestrator = ReviewOrchestrator(
        sessions,
        github,
        FakeProvider(),
        _profile(),
        system_prompt="Review only verified changed lines.",
        owner_remaining_usd=remaining_budget,
        static_sources={"src/app.py": "new = 2\n"},
        include_static_checks=True,
    )
    assert await Consumer(sessions, broker, orchestrator).consume_once() == "partial"
    assert len(broker.acknowledged) == 1

    job = await review_db.scalar(select(ReviewJob).where(ReviewJob.owner_id == first.id))
    assert job is not None and job.verified_diff is not None
    assert job.analysis_status == "partial"
    positions = job.verified_diff["findings"]
    assert positions and all(value["position"] > 0 for value in positions.values())
    assert job.coverage["files_total"] == 2
    assert job.coverage["files_reviewed"] == 1
    await record_publication(review_db, first.id, job.id, PublicationDraft(status="preview_ready"))
    await review_db.commit()

    identity = ReviewIdentity(
        review_id=job.id,
        owner=ReviewOwner(user_id=first.id, installation_id=job.installation_id),
        repo=ReviewRepository(id=job.repo_id, owner_login="owner", name="repo"),
        pr_number=job.pr_number,
        head_sha=job.head_sha,
        policy=ReviewPolicy.model_validate(job.policy),
    )
    diff = await fetch_review_diff(github, identity)
    receipt = await ReviewPublisher(sessions, RejectInlinePublisher()).publish(
        identity, diff, publication_authorized=True
    )
    assert receipt.status == "partially_published"
    assert receipt.fallback_reason == "diff_position_mismatch"

    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")

    async def database():
        yield review_db

    app.dependency_overrides[get_db] = database
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://local.e2e",
        headers={"Authorization": f"Bearer {create_access_token(str(first.id))}"},
    ) as client:
        response = await client.get(f"/api/v1/review/jobs/{job.id}")
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["publication_fallback_reason"] == "diff_position_mismatch"
    assert detail["findings"]
    persisted = detail["findings"][0]["verified_diff"]
    assert VerifiedDiffPosition.model_validate(persisted).position > 0
    assert persisted["comment_context"]
