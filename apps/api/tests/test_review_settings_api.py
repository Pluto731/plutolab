"""Tenant-scoped settings API: MockTransport and disposable PostgreSQL only."""

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from plutolab_api.api.v1.review import get_repository_github
from plutolab_api.api.v1.router import api_router
from plutolab_api.core.github_app import GitHubAppCredentials
from plutolab_api.core.security import create_access_token
from plutolab_api.db.base import Base
from plutolab_api.db.deps import get_db
from plutolab_api.models.review import ReviewSettings
from plutolab_api.models.user import User
from plutolab_api.services.review.jobs import ReviewStateError, enqueue_review
from plutolab_api.services.review.settings import (
    ReviewRepositoryGitHubClient,
    create_installation,
    revoke_installation,
)
from tests.test_review_domain import disposable_database, migrate
from tests.test_review_domain import owners as owners
from tests.test_review_domain import review_db as review_db
from tests.test_review_domain import review_engine as review_engine
from tests.test_review_installations_api import local_only as local_only
from tests.test_review_jobs import request as job_request

PREFIX = "/api/v1/review/installations/301/repositories"


def repo(number: int, name: str | None = None) -> dict[str, object]:
    return {
        "id": number,
        "full_name": name or f"pluto/repo{number}",
        "private": True,
        "default_branch": "main",
    }


def update(**changes) -> dict[str, object]:
    body = {
        "enabled": True,
        "min_pr_lines": 1,
        "skip_paths": ["vendor/**"],
        "focus_areas": ["security"],
        "expected_rules_version": 1,
    }
    body.update(changes)
    return body


@dataclass
class Harness:
    client: httpx.AsyncClient
    users: tuple[User, User]
    repositories: list[dict[str, object]] = field(
        default_factory=lambda: [repo(401), repo(402), repo(403)]
    )
    requests: list[httpx.Request] = field(default_factory=list)
    status: int = 200
    returned_id: int | None = None
    total_override: int | None = None

    def other_auth(self):
        return {"Authorization": f"Bearer {create_access_token(str(self.users[1].id))}"}

    async def get_rules(self, repo_id="401", **kwargs):
        return await self.client.get(f"{PREFIX}/{repo_id}/settings", **kwargs)

    async def put_rules(self, body=None, **kwargs):
        return await self.client.put(f"{PREFIX}/401/settings", json=body or update(), **kwargs)


@pytest_asyncio.fixture
async def api(review_db, owners):
    await create_installation(review_db, owners[0].id, "301")
    await create_installation(review_db, owners[1].id, "302")
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")

    def respond(request):
        harness.requests.append(request)
        assert request.url.host == "api.github.com"
        assert request.url.scheme == "https"
        if request.method == "POST":
            assert request.url.path == "/app/installations/301/access_tokens"
            return httpx.Response(
                201,
                json={
                    "token": "fake-token-301",
                    "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                },
            )
        assert request.method == "GET"
        assert request.headers["authorization"] == "Bearer fake-token-301"
        if harness.status != 200:
            return httpx.Response(
                harness.status, json={"message": "private-upstream fake-token-301"}
            )
        if request.url.path == "/installation/repositories":
            page, size = int(request.url.params["page"]), int(request.url.params["per_page"])
            return httpx.Response(
                200,
                json={
                    "total_count": harness.total_override
                    if harness.total_override is not None
                    else len(harness.repositories),
                    "repositories": harness.repositories[(page - 1) * size : page * size],
                },
                headers={"Link": '<https://evil.invalid/steal>; rel="next"'},
            )
        assert request.url.path.startswith("/repositories/")
        repo_id = int(request.url.path.rsplit("/", 1)[1])
        matching = next((r for r in harness.repositories if r["id"] == repo_id), None)
        if matching is None:
            return httpx.Response(404, json={"message": "not installed"})
        payload = copy.deepcopy(matching)
        if harness.returned_id is not None:
            payload["id"] = harness.returned_id
        return httpx.Response(200, json=payload)

    async def sleep(seconds):
        pass

    async with ReviewRepositoryGitHubClient(
        GitHubAppCredentials("123", SecretStr("fake-key")),
        transport=httpx.MockTransport(respond),
        sleep=sleep,
    ) as github:

        async def database():
            yield review_db

        app.dependency_overrides[get_db] = database
        app.dependency_overrides[get_repository_github] = lambda: github
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {create_access_token(str(owners[0].id))}"},
        ) as client:
            harness = Harness(client, owners)
            yield harness


async def test_listing_pagination_syncs_only_visible_page_disabled_by_default(api, review_db):
    response = await api.client.get(PREFIX, params={"page": 2, "per_page": 1})
    assert response.status_code == 200, response.text
    assert response.json()["total_count"] == 3
    assert response.json()["page"] == 2
    assert response.json()["repositories"][0]["repo_id"] == "402"
    assert response.json()["repositories"][0]["enabled"] is False
    assert response.headers["cache-control"] == "no-store"
    rows = (await review_db.scalars(select(ReviewSettings))).all()
    assert len(rows) == 1
    assert rows[0].repo_id == "402"
    assert rows[0].owner_id == api.users[0].id


async def test_search_enumerates_all_pages_then_filters_and_paginates(api):
    api.repositories = [repo(400 + index, f"pluto/repo{index}") for index in range(101)]
    api.repositories[-1]["full_name"] = "pluto/MATCH-two"
    api.repositories[0]["full_name"] = "pluto/match-one"
    response = await api.client.get(PREFIX, params={"q": "match", "page": 2, "per_page": 1})
    assert response.status_code == 200
    assert response.json()["total_count"] == 2
    assert [r["repo_name"] for r in response.json()["repositories"]] == ["pluto/MATCH-two"]
    assert [dict(r.url.params) for r in api.requests if r.method == "GET"] == [
        {"page": "1", "per_page": "100"},
        {"page": "2", "per_page": "100"},
    ]


async def test_empty_search_and_out_of_range_pages_are_empty(api, review_db):
    for params in ({"q": "not-found"}, {"page": 99}):
        response = await api.client.get(PREFIX, params=params)
        assert response.status_code == 200
        assert response.json()["repositories"] == []
    assert await review_db.scalar(select(func.count()).select_from(ReviewSettings)) == 0


async def test_get_put_readback_versions_and_noop(api):
    initial = await api.get_rules()
    assert initial.status_code == 200
    assert initial.json()["rules_version"] == 1
    assert initial.json()["enabled"] is False
    updated = await api.put_rules()
    assert updated.status_code == 200, updated.text
    assert updated.json()["rules_version"] == 2
    assert updated.json()["skip_paths"] == ["vendor/**"]
    assert updated.json()["focus_areas"] == ["security"]
    assert (await api.get_rules()).json() == updated.json()
    no_op = await api.put_rules(update(expected_rules_version=2))
    assert no_op.json()["rules_version"] == 2
    disabled = await api.put_rules(update(expected_rules_version=2, enabled=False))
    assert disabled.json()["rules_version"] == 3
    assert disabled.json()["enabled"] is False


async def test_stale_version_rejected_without_overwriting_rules(api):
    assert (await api.put_rules()).status_code == 200
    response = await api.put_rules(update(enabled=False))
    assert response.status_code == 409
    current = (await api.get_rules()).json()
    assert current["enabled"] is True
    assert current["rules_version"] == 2


@pytest.mark.parametrize(
    "method,suffix", [("GET", ""), ("GET", "/401/settings"), ("PUT", "/401/settings")]
)
async def test_cross_tenant_blocked_before_github(api, method, suffix):
    response = await api.client.request(
        method,
        PREFIX + suffix,
        headers=api.other_auth(),
        json=update() if method == "PUT" else None,
    )
    assert response.status_code in {403, 404}
    assert api.requests == []


@pytest.mark.parametrize(
    "method,suffix", [("GET", ""), ("GET", "/401/settings"), ("PUT", "/401/settings")]
)
async def test_revoked_installation_blocked_before_github(api, review_db, method, suffix):
    await revoke_installation(review_db, api.users[0].id, "301")
    response = await api.client.request(
        method, PREFIX + suffix, json=update() if method == "PUT" else None
    )
    assert response.status_code in {403, 404}
    assert api.requests == []


@pytest.mark.parametrize("method", ["GET", "PUT"])
async def test_repository_no_longer_accessible_is_not_configurable(api, method):
    assert (await api.put_rules()).status_code == 200
    api.repositories = []
    response = await api.client.request(
        method,
        f"{PREFIX}/401/settings",
        json=update(expected_rules_version=2) if method == "PUT" else None,
    )
    assert response.status_code in {403, 404}


async def test_spoofed_upstream_repository_id_rejected(api, review_db):
    api.returned_id = 999
    response = await api.get_rules()
    assert response.status_code == 502
    assert await review_db.scalar(select(func.count()).select_from(ReviewSettings)) == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"min_pr_lines": -1},
        {"min_pr_lines": 0},
        {"min_pr_lines": True},
        {"min_pr_lines": "5"},
        {"min_pr_lines": 2147483648},
        {"enabled": "yes"},
        {"skip_paths": ["../secret"]},
        {"skip_paths": ["/absolute"]},
        {"skip_paths": ["[invalid"]},
        {"skip_paths": ["(?=secret)"]},
        {"skip_paths": ["src/**oops"]},
        {"skip_paths": ["x" * 257]},
        {"skip_paths": ["*.py", "*.py"]},
        {"skip_paths": [f"file{i}" for i in range(101)]},
        {"focus_areas": []},
        {"focus_areas": ["unknown"]},
        {"focus_areas": ["security", "security"]},
        {"expected_rules_version": 0},
        {"rules_version": 999},
        {"user_id": "spoofed"},
    ],
)
async def test_invalid_rules_rejected_422_before_io(api, changes):
    response = await api.put_rules(update(**changes))
    assert response.status_code == 422
    assert api.requests == []


@pytest.mark.parametrize(
    "params", [{"page": 0}, {"per_page": 101}, {"q": "x" * 101}, {"q": "(bad.*"}]
)
async def test_invalid_listing_query_422(api, params):
    response = await api.client.get(PREFIX, params=params)
    assert response.status_code == 422
    assert api.requests == []


async def test_listing_rename_preserves_rules_and_version(api):
    assert (await api.put_rules()).status_code == 200
    api.repositories[0]["full_name"] = "pluto/renamed"
    listed = await api.client.get(PREFIX)
    assert listed.status_code == 200
    current = (await api.get_rules()).json()
    assert current["repo_name"] == "pluto/renamed"
    assert current["rules_version"] == 2
    assert current["enabled"] is True


async def test_incomplete_or_overlarge_search_never_returns_partial_results(api, review_db):
    api.total_override = 10001
    assert (await api.client.get(PREFIX, params={"q": "repo"})).status_code == 422
    api.total_override = 4
    assert (await api.client.get(PREFIX, params={"q": "repo"})).status_code == 502
    assert await review_db.scalar(select(func.count()).select_from(ReviewSettings)) == 0


async def test_upstream_failure_does_not_leak_token_or_sync(api, review_db):
    api.status = 403
    response = await api.client.get(PREFIX)
    assert response.status_code == 403
    assert "fake-token-301" not in response.text
    assert "private-upstream" not in response.text
    assert await review_db.scalar(select(func.count()).select_from(ReviewSettings)) == 0


async def test_listing_sync_rolls_back_entire_page_on_invalid_metadata(api, review_db):
    api.repositories[1]["full_name"] = "../invalid"
    response = await api.client.get(PREFIX)
    assert response.status_code == 502
    assert await review_db.scalar(select(func.count()).select_from(ReviewSettings)) == 0


@pytest.mark.parametrize("method", ["GET", "PUT", "LIST"])
async def test_revocation_during_remote_verification_is_rechecked(
    api, review_db, monkeypatch, method
):
    name = "list_repositories" if method == "LIST" else "repository_by_id"
    original = getattr(ReviewRepositoryGitHubClient, name)

    async def revoke_after_read(client, *args, **kwargs):
        result = await original(client, *args, **kwargs)
        await revoke_installation(review_db, api.users[0].id, "301")
        return result

    monkeypatch.setattr(ReviewRepositoryGitHubClient, name, revoke_after_read)
    if method == "LIST":
        response = await api.client.get(PREFIX)
    elif method == "PUT":
        response = await api.put_rules()
    else:
        response = await api.get_rules()
    assert response.status_code == 403
    assert await review_db.scalar(select(func.count()).select_from(ReviewSettings)) == 0


@pytest.mark.parametrize(
    "method,suffix", [("GET", ""), ("GET", "/401/settings"), ("PUT", "/401/settings")]
)
async def test_new_routes_require_authentication(api, method, suffix):
    response = await api.client.request(
        method,
        PREFIX + suffix,
        headers={"Authorization": ""},
        json=update() if method == "PUT" else None,
    )
    assert response.status_code == 401
    assert api.requests == []


async def test_rule_updates_leave_existing_job_policy_immutable(api, review_db):
    assert (await api.put_rules()).status_code == 200
    request = job_request()
    request.policy = request.policy.model_copy(
        update={"rules_version": 2, "focus": ["security"], "skip_paths": ["vendor/**"]}
    )
    job = (await enqueue_review(review_db, api.users[0].id, request)).job
    previous = copy.deepcopy(job.policy)
    response = await api.put_rules(update(expected_rules_version=2, focus_areas=["performance"]))
    assert response.status_code == 200
    assert response.json()["rules_version"] == 3
    await review_db.refresh(job)
    assert job.rules_version == 2
    assert job.policy == previous


async def test_version_exhaustion_rejected_without_overflow(api, review_db):
    assert (await api.get_rules()).status_code == 200
    row = await review_db.scalar(select(ReviewSettings))
    row.rules_version = 2147483647
    await review_db.flush()
    response = await api.put_rules(update(expected_rules_version=2147483647))
    assert response.status_code == 409
    await review_db.refresh(row)
    assert row.rules_version == 2147483647
    assert row.enabled is False


async def test_max_lines_persist_version_and_can_be_cleared(api, review_db):
    assert (await api.get_rules()).json()["max_pr_lines"] is None
    capped = await api.put_rules(update(max_pr_lines=500))
    assert capped.status_code == 200
    assert capped.json()["max_pr_lines"] == 500
    assert capped.json()["rules_version"] == 2
    assert (await api.get_rules()).json()["max_pr_lines"] == 500
    row = await review_db.scalar(select(ReviewSettings))
    await review_db.refresh(row)
    assert row.max_pr_lines == 500
    unchanged = await api.put_rules(update(max_pr_lines=500, expected_rules_version=2))
    assert unchanged.json()["rules_version"] == 2
    revised = await api.put_rules(update(max_pr_lines=750, expected_rules_version=2))
    assert revised.json()["rules_version"] == 3
    cleared = await api.put_rules(update(max_pr_lines=None, expected_rules_version=3))
    assert cleared.json()["rules_version"] == 4
    assert cleared.json()["max_pr_lines"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"max_pr_lines": -1},
        {"max_pr_lines": 0},
        {"max_pr_lines": True},
        {"max_pr_lines": "500"},
        {"max_pr_lines": 2147483648},
        {"min_pr_lines": 501, "max_pr_lines": 500},
    ],
)
async def test_invalid_max_lines_rejected_before_io(api, changes):
    response = await api.put_rules(update(**changes))
    assert response.status_code == 422
    assert api.requests == []


async def test_equal_threshold_boundary_is_valid(api):
    response = await api.put_rules(update(min_pr_lines=500, max_pr_lines=500))
    assert response.status_code == 200
    assert response.json()["min_pr_lines"] == response.json()["max_pr_lines"] == 500


async def test_job_cap_enforcement_and_existing_snapshot_preservation(api, review_db):
    assert (await api.put_rules(update(max_pr_lines=500))).status_code == 200
    request = job_request()
    request.policy = request.policy.model_copy(
        update={"rules_version": 2, "focus": ["security"], "skip_paths": ["vendor/**"]}
    )
    with pytest.raises(ReviewStateError, match="Stale repository policy"):
        await enqueue_review(review_db, api.users[0].id, request)
    request.policy.budgets.max_changed_lines = 500
    job = (await enqueue_review(review_db, api.users[0].id, request)).job
    previous = copy.deepcopy(job.policy)
    assert (
        await api.put_rules(update(max_pr_lines=250, expected_rules_version=2))
    ).status_code == 200
    await review_db.refresh(job)
    assert job.policy == previous
    assert job.policy["budgets"]["max_changed_lines"] == 500
    assert job.rules_version == 2
    new_request = job_request(head_sha="b" * 40)
    new_request.policy = request.policy.model_copy(deep=True, update={"rules_version": 3})
    with pytest.raises(ReviewStateError, match="Stale repository policy"):
        await enqueue_review(review_db, api.users[0].id, new_request)
    new_request.policy.budgets.max_changed_lines = 200
    tighter_job = (await enqueue_review(review_db, api.users[0].id, new_request)).job
    assert tighter_job.policy["budgets"]["max_changed_lines"] == 200


async def test_max_lines_database_constraint(review_db, api):
    assert (await api.get_rules()).status_code == 200
    with pytest.raises(IntegrityError):
        async with review_db.begin_nested():
            await review_db.execute(
                text("UPDATE review_settings SET min_pr_lines=50, max_pr_lines=49")
            )
    row = await review_db.scalar(select(ReviewSettings))
    assert row.min_pr_lines == 1
    assert row.max_pr_lines is None


async def test_max_lines_migration_round_trip_preserves_legacy_rules():
    async with disposable_database() as url:
        migrate(url, "upgrade", "0014")
        engine = create_async_engine(url)
        owner_id = uuid4()
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("INSERT INTO users (id,email) VALUES (:id,'max-sentinel@review.test')"),
                    {"id": owner_id},
                )
                await conn.execute(
                    text(
                        "INSERT INTO github_installations (installation_id,owner_id) VALUES ('901',:id)"
                    ),
                    {"id": owner_id},
                )
                await conn.execute(
                    text(
                        "INSERT INTO review_settings (installation_id,owner_id,repo_id,repo_name,enabled,min_pr_lines,rules_version) VALUES ('901',:id,'902','owner/repo',true,25,7)"
                    ),
                    {"id": owner_id},
                )
            migrate(url, "upgrade", "0015")

            def check_schema(conn):
                context = MigrationContext.configure(
                    conn,
                    opts={
                        "compare_server_default": True,
                        "include_object": lambda obj, name, kind, reflected, compare: (
                            kind != "table" or name == "review_settings"
                        ),
                    },
                )
                assert compare_metadata(context, Base.metadata) == []
                assert "max_pr_lines" in {
                    column["name"] for column in inspect(conn).get_columns("review_settings")
                }

            async with engine.begin() as conn:
                await conn.run_sync(check_schema)
                row = (
                    await conn.execute(
                        text(
                            "SELECT enabled,min_pr_lines,max_pr_lines,rules_version FROM review_settings WHERE repo_id='902'"
                        )
                    )
                ).one()
                assert tuple(row) == (True, 25, None, 7)
                await conn.execute(
                    text("UPDATE review_settings SET max_pr_lines=100 WHERE repo_id='902'")
                )
            migrate(url, "downgrade", "0014")
            async with engine.connect() as conn:
                columns = await conn.run_sync(
                    lambda sync: {c["name"] for c in inspect(sync).get_columns("review_settings")}
                )
                assert "max_pr_lines" not in columns
                row = (
                    await conn.execute(
                        text(
                            "SELECT enabled,min_pr_lines,rules_version FROM review_settings WHERE repo_id='902'"
                        )
                    )
                ).one()
                assert tuple(row) == (True, 25, 7)
            migrate(url, "upgrade", "0015")
            async with engine.connect() as conn:
                await conn.run_sync(check_schema)
                assert (
                    await conn.scalar(
                        text("SELECT max_pr_lines FROM review_settings WHERE repo_id='902'")
                    )
                    is None
                )
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM users WHERE id=:id"), {"id": owner_id}
                    )
                    == 1
                )
        finally:
            await engine.dispose()
