"""Owner-scoped job reads and fallback telemetry against disposable PostgreSQL."""

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from plutolab_api.api.v1.router import api_router
from plutolab_api.core.security import create_access_token
from plutolab_api.db.deps import get_db
from plutolab_api.schemas.review import (
    PublicationDraft,
    PublicationReceipt,
    VerifiedDiffPosition,
    VerifiedDiffSnapshot,
)
from plutolab_api.services.review.jobs import (
    begin_publication,
    enqueue_review,
    record_publication,
)
from plutolab_api.services.review.settings import (
    ReviewRules,
    create_installation,
    create_settings,
)
from tests.test_review_domain import disposable_database, migrate
from tests.test_review_domain import owners as owners
from tests.test_review_domain import review_db as review_db
from tests.test_review_domain import review_engine as review_engine
from tests.test_review_jobs import analyzed
from tests.test_review_jobs import request as job_request

LIST_URL = "/api/v1/review/jobs"


@pytest_asyncio.fixture
async def api(review_db, owners):
    first, second = owners
    await create_installation(review_db, first.id, "301")
    await create_installation(review_db, second.id, "302")
    for owner_id, installation_id, repo_id in (
        (first.id, "301", "401"),
        (first.id, "301", "402"),
        (second.id, "302", "403"),
    ):
        await create_settings(
            review_db,
            owner_id,
            installation_id,
            repo_id,
            f"owner/repo-{repo_id}",
            rules=ReviewRules(enabled=True),
        )

    completed = await analyzed(
        review_db,
        first.id,
        req=job_request(repo_id="401", pr_number=17, head_sha="a" * 40),
    )
    finding = completed.findings[0]
    completed.verified_diff = VerifiedDiffSnapshot(
        head_sha=completed.head_sha,
        findings={
            str(finding["id"]): VerifiedDiffPosition(
                path="src/app.py",
                line=4,
                side="RIGHT",
                position=8,
                comment_context="@@ -1 +1 @@\n+new",
            ).model_dump(mode="json")
        },
    ).model_dump(mode="json")
    await review_db.flush()
    publishing = await enqueue_review(
        review_db,
        first.id,
        job_request(repo_id="402", pr_number=18, head_sha="b" * 40, delivery_id=str(uuid4())),
    )
    foreign = await enqueue_review(
        review_db,
        second.id,
        job_request(
            installation_id="302",
            repo_id="403",
            pr_number=99,
            head_sha="c" * 40,
            delivery_id=str(uuid4()),
        ),
    )

    await record_publication(
        review_db, first.id, completed.id, PublicationDraft(status="preview_ready")
    )
    attempt = await begin_publication(
        review_db,
        first.id,
        completed.id,
        verified_head_sha=completed.head_sha,
        verified_rules_version=completed.rules_version,
        publication_authorized=True,
        lease_seconds=60,
    )
    receipt = PublicationReceipt(
        status="partially_published",
        attempt_id=attempt.id,
        head_sha=completed.head_sha,
        github_review_ids=["99001"],
        confirmed_at=datetime.now(UTC),
        fallback_reason="diff_position_mismatch",
    )
    await record_publication(review_db, first.id, completed.id, receipt)
    await review_db.flush()

    app = FastAPI()

    app.include_router(api_router, prefix="/api/v1")

    async def database():
        yield review_db

    app.dependency_overrides[get_db] = database
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://local.test",
        headers={"Authorization": f"Bearer {create_access_token(str(first.id))}"},
    ) as client:
        yield client, first, second, completed, publishing.job, foreign.job


async def test_job_list_is_owner_scoped_and_supports_status_pr_and_pagination(api):
    client, _first, second, _completed, _queued, _foreign = api
    response = await client.get(
        LIST_URL, params={"installation_id": "301", "page": 1, "per_page": 1}
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total_count"] == 2
    assert payload["page"] == 1 and payload["per_page"] == 1
    assert len(payload["jobs"]) == 1
    assert payload["jobs"][0]["installation_id"] == "301"
    assert response.headers["cache-control"] == "no-store"

    pr = await client.get(LIST_URL, params={"repo_id": "401", "pr_number": 17})
    assert pr.status_code == 200
    assert [item["pr_number"] for item in pr.json()["jobs"]] == [17]

    partial = await client.get(LIST_URL, params={"status": "PARTIAL"})
    assert partial.status_code == 200
    assert [item["pr_number"] for item in partial.json()["jobs"]] == [17]

    foreign_install = await client.get(LIST_URL, params={"installation_id": "302"})
    assert foreign_install.status_code == 404
    other_token = {"Authorization": f"Bearer {create_access_token(str(second.id))}"}
    own_view = await client.get(LIST_URL, headers=other_token)
    assert own_view.status_code == 200
    assert all(item["pr_number"] == 99 for item in own_view.json()["jobs"])


async def test_detail_returns_metrics_findings_and_exact_422_fallback_reason(api):
    client, _first, _second, job, _queued, _foreign = api
    response = await client.get(f"{LIST_URL}/{job.id}")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["analysis_status"] == "analyzed"
    assert payload["publication_status"] == "partially_published"
    assert payload["publication_fallback_reason"] == "diff_position_mismatch"
    assert payload["publication"]["github_review_ids"] == ["99001"]
    assert payload["coverage"]["changed_lines_total"] == 10
    assert payload["usage"]["cost_usd"] == "0.010000"
    assert payload["findings"][0]["location"]["path"] == "src/app.py"
    assert payload["findings"][0]["verified_diff"] == {
        "path": "src/app.py",
        "line": 4,
        "side": "RIGHT",
        "position": 8,
        "comment_context": "@@ -1 +1 @@\n+new",
    }
    assert payload["processing_started_at"] is not None
    assert payload["completed_at"] is not None


async def test_detail_tolerates_missing_verified_diff_mapping(api, review_db):
    client, _first, _second, job, _queued, _foreign = api
    job.verified_diff = None
    await review_db.flush()

    response = await client.get(f"{LIST_URL}/{job.id}")

    assert response.status_code == 200, response.text
    findings = response.json()["findings"]
    assert findings and findings[0]["verified_diff"] is None


async def test_job_detail_hides_foreign_and_unbound_installation_jobs(api, review_db):
    client, _first, second, _job, _queued, foreign = api
    response = await client.get(f"{LIST_URL}/{foreign.id}")
    assert response.status_code == 404

    await client.delete("/api/v1/review/installations/301")
    hidden = await client.get(f"{LIST_URL}/{_job.id}")
    assert hidden.status_code == 404
    assert second.id == foreign.owner_id


@pytest.mark.asyncio
async def test_verified_diff_migration_upgrade_downgrade_and_reupgrade():
    async with disposable_database() as url:
        migrate(url, "upgrade", "0018")
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                before = await conn.run_sync(lambda sync: inspect(sync).get_columns("review_jobs"))
            assert "verified_diff" not in {column["name"] for column in before}
        finally:
            await engine.dispose()

        migrate(url, "upgrade", "head")
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                after = await conn.run_sync(lambda sync: inspect(sync).get_columns("review_jobs"))
            assert "publication_fallback_reason" in {column["name"] for column in after}
            assert "verified_diff" in {column["name"] for column in after}
        finally:
            await engine.dispose()
        migrate(url, "downgrade", "0018")
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                downgraded = await conn.run_sync(
                    lambda sync: inspect(sync).get_columns("review_jobs")
                )
            assert "publication_fallback_reason" in {column["name"] for column in downgraded}
            assert "verified_diff" not in {column["name"] for column in downgraded}
        finally:
            await engine.dispose()
        migrate(url, "upgrade", "head")
