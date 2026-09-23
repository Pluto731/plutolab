"""Installation API acceptance: mocked GitHub/Redis, disposable loopback PostgreSQL."""

import asyncio
import copy
import json
import socket
from dataclasses import dataclass
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import fakeredis.aioredis
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from pydantic import SecretStr
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from plutolab_api.api.v1.review import get_installation_github
from plutolab_api.api.v1.router import api_router
from plutolab_api.core.github_app import GitHubAppCredentials, GitHubAppError
from plutolab_api.core.redis import get_redis
from plutolab_api.core.security import create_access_token
from plutolab_api.db.deps import get_db
from plutolab_api.models.review import GitHubInstallation
from plutolab_api.models.user import User
from plutolab_api.services.review import installations
from plutolab_api.services.review.installations import (
    InstallationGitHubClient,
    InstallationStateError,
    _consume_state,
)
from plutolab_api.services.review.jobs import (
    begin_analysis,
    begin_publication,
    enqueue_review,
    finish_analysis,
)
from plutolab_api.services.review.settings import (
    ReviewAccessDeniedError,
    ReviewRules,
    create_installation,
    create_settings,
)
from tests.test_review_domain import owners as owners
from tests.test_review_domain import review_db as review_db
from tests.test_review_domain import review_engine as review_engine
from tests.test_review_jobs import request as job_request
from tests.test_review_jobs import result as analysis_result

PREFIX = "/api/v1/review/installations"
FAKE_JWT = "fake-app-jwt-no-real-key"
EVIDENCE = {
    "id": 301,
    "app_id": 123,
    "account": {"id": 101, "type": "User"},
    "suspended_at": None,
    "permissions": {"metadata": "read", "contents": "read", "pull_requests": "write"},
}


@pytest.fixture(autouse=True)
def local_only(monkeypatch):
    original = socket.socket.connect

    def connect(sock, address):
        if (
            not isinstance(address, tuple)
            or address[0] not in {"127.0.0.1", "::1"}
            or address[1] != 5432
        ):
            raise AssertionError("Only disposable loopback PostgreSQL is permitted")
        return original(sock, address)

    async def deny_http(*args, **kwargs):
        raise AssertionError("Real HTTP transport forbidden in Slice 5 tests")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", deny_http)
    monkeypatch.setattr(GitHubAppCredentials, "create_jwt", lambda self: SecretStr(FAKE_JWT))


@dataclass
class Harness:
    client: httpx.AsyncClient
    store: fakeredis.aioredis.FakeRedis
    users: tuple[User, User]
    requests: list[httpx.Request]
    evidence: dict
    upstream_status: int = 200
    app: dict | None = None

    async def start(self, *, headers=None):
        response = await self.client.post(f"{PREFIX}/start", headers=headers)
        assert response.status_code == 200, response.text
        return parse_qs(urlparse(response.json()["installation_url"]).query)["state"][0]

    async def callback(self, state, **kwargs):
        return await self.client.post(
            f"{PREFIX}/callback", json={"installation_id": "301", "state": state}, **kwargs
        )

    def other_auth(self):
        return {"Authorization": f"Bearer {create_access_token(str(self.users[1].id))}"}


@pytest_asyncio.fixture
async def api(review_db, owners):
    owners[0].github_id = 101
    owners[1].github_id = 202
    await review_db.flush()
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    store = fakeredis.aioredis.FakeRedis(decode_responses=True)
    requests = []

    def respond(request):
        requests.append(request)
        assert request.url.scheme == "https"
        assert request.url.host == "api.github.com"
        assert request.method == "GET"
        assert request.headers["authorization"] == f"Bearer {FAKE_JWT}"
        if request.url.path == "/app":
            return httpx.Response(200, json=harness.app or {"id": 123, "slug": "plutolab-review"})
        assert request.url.path.startswith("/app/installations/")
        return httpx.Response(harness.upstream_status, json=harness.evidence)

    async def no_sleep(seconds):
        pass

    async with InstallationGitHubClient(
        GitHubAppCredentials("123", SecretStr("fake-key")),
        transport=httpx.MockTransport(respond),
        sleep=no_sleep,
    ) as github:

        async def database():
            yield review_db

        app.dependency_overrides[get_db] = database
        app.dependency_overrides[get_redis] = lambda: store
        app.dependency_overrides[get_installation_github] = lambda: github
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {create_access_token(str(owners[0].id))}"},
        ) as client:
            harness = Harness(client, store, owners, requests, copy.deepcopy(EVIDENCE))
            try:
                yield harness
            finally:
                await store.aclose()


async def test_start_high_entropy_ttl_hashed_storage_and_fixed_url(api):
    response = await api.client.post(f"{PREFIX}/start")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    url = urlparse(response.json()["installation_url"])
    assert url.scheme == "https"
    assert url.netloc == "github.com"
    assert url.path == "/apps/plutolab-review/installations/new"
    state = parse_qs(url.query)["state"][0]
    assert len(state) == 43
    assert response.json()["expires_in_seconds"] == 300
    keys = await api.store.keys("review:installation-state:*")
    assert len(keys) == 1
    assert state not in keys[0]
    assert 0 < await api.store.ttl(keys[0]) <= 300
    payload = await api.store.get(keys[0])
    assert state not in payload
    assert json.loads(payload)["owner_id"] == str(api.users[0].id)
    assert await api.start() != state


async def test_verified_binding_and_status_use_authenticated_owner(api, review_db):
    response = await api.callback(await api.start())
    assert response.status_code == 200, response.text
    assert response.json() == {"installation_id": "301", "active": True, "revoked_at": None}
    row = await review_db.get(GitHubInstallation, "301")
    assert row.owner_id == api.users[0].id
    assert [r.url.path for r in api.requests] == ["/app", "/app/installations/301"]
    status = await api.client.get(f"{PREFIX}/301")
    assert status.status_code == 200
    assert status.json()["active"]
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "body",
    [
        {"installation_id": "301"},
        {"state": "x" * 43},
        {"installation_id": "301", "state": "x" * 43, "user_id": "spoofed"},
    ],
)
async def test_missing_or_extra_callback_fields_rejected(api, body, review_db):
    response = await api.client.post(f"{PREFIX}/callback", json=body)
    assert response.status_code == 422
    assert api.requests == []
    assert await review_db.get(GitHubInstallation, "301") is None


@pytest.mark.parametrize("mutation", ["tampered", "unknown", "malformed", "expired"])
async def test_bad_states_fail_before_github_or_binding(api, review_db, mutation):
    state = await api.start()
    if mutation == "tampered":
        state = ("B" if state[0] == "A" else "A") + state[1:]
    elif mutation == "unknown":
        state = "z" * 43
    elif mutation == "malformed":
        state = "not-a-state"
    else:
        key = (await api.store.keys("review:installation-state:*"))[0]
        await api.store.pexpire(key, 1)
        await asyncio.sleep(0.02)
    response = await api.callback(state)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "access_denied"
    assert state not in response.text
    assert len(api.requests) == 1
    assert await review_db.get(GitHubInstallation, "301") is None


async def test_replayed_callback_rejected(api, review_db):
    state = await api.start()
    assert (await api.callback(state)).status_code == 200
    response = await api.callback(state)
    assert response.status_code == 403
    assert len(api.requests) == 2
    assert await review_db.scalar(select(func.count()).select_from(GitHubInstallation)) == 1


async def test_concurrent_state_consumption_has_one_winner(api):
    state = await api.start()
    results = await asyncio.gather(
        *(_consume_state(api.store, api.users[0].id, 101, state) for _ in range(8)),
        return_exceptions=True,
    )
    assert sum(isinstance(result, InstallationStateError) for result in results) == 7
    assert sum(not isinstance(result, Exception) for result in results) == 1


async def test_cross_user_state_rejected_without_burning_original(api):
    state = await api.start()
    assert (await api.callback(state, headers=api.other_auth())).status_code == 403
    assert len(api.requests) == 1
    assert (await api.callback(state)).status_code == 200


async def test_forged_query_user_id_has_no_authority(api, review_db):
    response = await api.client.post(
        f"{PREFIX}/callback?user_id={api.users[1].id}&installation_id=999",
        json={"state": await api.start(), "installation_id": "301"},
    )
    assert response.status_code == 200
    assert (await review_db.get(GitHubInstallation, "301")).owner_id == api.users[0].id
    assert api.requests[-1].url.path == "/app/installations/301"


@pytest.mark.parametrize(
    "change",
    [
        {"id": 999},
        {"app_id": 999},
        {"account": {"id": 202, "type": "User"}},
        {"account": {"id": 101, "type": "Organization"}},
        {"suspended_at": "2026-09-18T00:00:00Z"},
        {"permissions": {"contents": "write", "pull_requests": "write"}},
        {"permissions": {"contents": "read", "pull_requests": "write", "administration": "write"}},
        {"permissions": {"contents": "read"}},
    ],
)
async def test_unverified_installation_and_excess_permissions_rejected(api, review_db, change):
    state = await api.start()
    api.evidence.update(change)
    response = await api.callback(state)
    assert response.status_code == 403
    assert await review_db.get(GitHubInstallation, "301") is None
    assert (await api.callback(state)).status_code == 403
    assert len(api.requests) == 2


@pytest.mark.parametrize(
    "status,expected", [(401, 502), (403, 403), (404, 403), (429, 429), (503, 502)]
)
async def test_upstream_verification_errors_fail_closed(api, review_db, status, expected):
    state = await api.start()
    api.upstream_status = status
    api.evidence = {"secret": FAKE_JWT, "message": "sensitive-upstream"}
    response = await api.callback(state)
    assert response.status_code == expected
    assert FAKE_JWT not in response.text
    assert "sensitive-upstream" not in response.text
    assert await review_db.get(GitHubInstallation, "301") is None
    assert await api.store.keys("review:installation-state:*") == []


async def test_existing_other_owner_cannot_be_attached(api, review_db):
    await create_installation(review_db, api.users[1].id, "301")
    response = await api.callback(await api.start())
    assert response.status_code == 403
    assert (await review_db.get(GitHubInstallation, "301")).owner_id == api.users[1].id


async def test_existing_same_owner_is_idempotent_with_fresh_verified_state(api, review_db):
    assert (await api.callback(await api.start())).status_code == 200
    assert (await api.callback(await api.start())).status_code == 200
    assert await review_db.scalar(select(func.count()).select_from(GitHubInstallation)) == 1


@pytest.mark.parametrize(
    "method,path", [("POST", "/start"), ("POST", "/callback"), ("GET", "/301"), ("DELETE", "/301")]
)
async def test_routes_require_authentication(api, method, path):
    response = await api.client.request(method, PREFIX + path, headers={"Authorization": ""})
    assert response.status_code == 401
    assert api.requests == []


@pytest.mark.parametrize("method", ["GET", "DELETE"])
async def test_other_users_cannot_view_or_revoke_binding(api, review_db, method):
    assert (await api.callback(await api.start())).status_code == 200
    response = await api.client.request(method, f"{PREFIX}/301", headers=api.other_auth())
    assert response.status_code == 403
    assert (await review_db.get(GitHubInstallation, "301")).revoked_at is None


async def test_unlinked_user_cannot_initiate(api, review_db):
    api.users[0].github_id = None
    await review_db.flush()
    response = await api.client.post(f"{PREFIX}/start")
    assert response.status_code == 403
    assert api.requests == []
    assert await api.store.keys("*") == []


async def test_linked_identity_change_invalidates_state(api, review_db):
    state = await api.start()
    api.users[0].github_id = 303
    await review_db.flush()
    response = await api.callback(state)
    assert response.status_code == 403
    assert len(api.requests) == 1


@pytest.mark.parametrize("operation", ["set", "getdel"])
async def test_redis_unavailable_fails_closed(api, monkeypatch, operation):
    state = await api.start() if operation == "getdel" else None
    monkeypatch.setattr(
        api.store, operation, AsyncMock(side_effect=RedisConnectionError("secret-backend-error"))
    )
    response = await api.callback(state) if state else await api.client.post(f"{PREFIX}/start")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "persistence_failed"
    assert "secret-backend-error" not in response.text


async def test_revocation_disables_rules_and_blocks_analysis_and_publication(api, review_db):
    assert (await api.callback(await api.start())).status_code == 200
    owner_id = api.users[0].id
    rules = await create_settings(
        review_db, owner_id, "301", "401", "pluto/lab", rules=ReviewRules(enabled=True)
    )
    queued = (await enqueue_review(review_db, owner_id, job_request())).job
    analyzed = (await enqueue_review(review_db, owner_id, job_request(head_sha="b" * 40))).job
    attempt = await begin_analysis(review_db, owner_id, analyzed.id, lease_seconds=60)
    await finish_analysis(review_db, owner_id, analyzed.id, attempt.id, analysis_result())
    response = await api.client.delete(f"{PREFIX}/301")
    assert response.status_code == 200
    assert response.json()["active"] is False
    assert response.json()["revoked_at"] is not None
    await review_db.refresh(rules)
    assert not rules.enabled
    assert rules.rules_version == 2
    with pytest.raises(ReviewAccessDeniedError):
        await enqueue_review(review_db, owner_id, job_request(head_sha="c" * 40))
    with pytest.raises(ReviewAccessDeniedError):
        await begin_analysis(review_db, owner_id, queued.id, lease_seconds=60)
    with pytest.raises(ReviewAccessDeniedError):
        await begin_publication(
            review_db,
            owner_id,
            analyzed.id,
            verified_head_sha="b" * 40,
            verified_rules_version=1,
            publication_authorized=True,
            lease_seconds=60,
        )
    again = await api.client.delete(f"{PREFIX}/301")
    assert again.json() == response.json()
    await review_db.refresh(rules)
    assert rules.rules_version == 2
    assert len(api.requests) == 2


async def test_old_pending_callback_cannot_undo_revocation(api):
    assert (await api.callback(await api.start())).status_code == 200
    pending_state = await api.start()
    assert (await api.client.delete(f"{PREFIX}/301")).status_code == 200
    assert (await api.callback(pending_state)).status_code == 409
    assert (await api.client.get(f"{PREFIX}/301")).json()["active"] is False


async def test_navigation_callback_alone_cannot_bind(api, review_db):
    response = await api.client.get(
        f"{PREFIX}/callback?state={await api.start()}&installation_id=301"
    )
    assert response.status_code in {405, 422}
    assert await review_db.get(GitHubInstallation, "301") is None
    assert len(api.requests) == 1


@pytest.mark.parametrize("kind", ["corrupt_json", "wrong_owner", "wrong_github_id"])
async def test_corrupt_or_mismatched_stored_state_is_consumed_and_rejected(api, kind):
    state = await api.start()
    key = (await api.store.keys("review:installation-state:*"))[0]
    stored = json.loads(await api.store.get(key))
    if kind == "wrong_owner":
        stored["owner_id"] = str(api.users[1].id)
    if kind == "wrong_github_id":
        stored["github_id"] = 202
    await api.store.set(key, "not-json" if kind == "corrupt_json" else json.dumps(stored), ex=300)
    response = await api.callback(state)
    assert response.status_code == 403
    assert len(api.requests) == 1
    assert not await api.store.exists(key)


async def test_state_collision_never_overwrites_existing_flow(api, monkeypatch):
    calls = []

    def collide(size):
        calls.append(size)
        return "a" * 43

    monkeypatch.setattr(installations.secrets, "token_urlsafe", collide)
    assert await api.start() == "a" * 43
    response = await api.client.post(f"{PREFIX}/start")
    assert response.status_code == 503
    assert calls == [32, 32, 32, 32]
    assert (await api.callback("a" * 43)).status_code == 200


async def test_malformed_upstream_evidence_fails_closed_without_leaking(api, review_db):
    state = await api.start()
    api.evidence = {"id": FAKE_JWT}
    response = await api.callback(state)
    assert response.status_code == 502
    assert FAKE_JWT not in response.text
    assert await review_db.get(GitHubInstallation, "301") is None


async def test_untrusted_app_slug_cannot_generate_redirect(api):
    api.app = {"id": 123, "slug": "../evil?redirect=https://evil.invalid"}
    response = await api.client.post(f"{PREFIX}/start")
    assert response.status_code == 502
    assert "evil.invalid" not in response.text
    assert await api.store.keys("*") == []


async def test_read_only_pr_permission_is_sufficient_for_binding(api):
    api.evidence["permissions"]["pull_requests"] = "read"
    assert (await api.callback(await api.start())).status_code == 200


async def test_unconfigured_credentials_fail_before_http(api, monkeypatch):
    def unconfigured(self):
        raise GitHubAppError("app_not_configured")

    monkeypatch.setattr(GitHubAppCredentials, "create_jwt", unconfigured)
    response = await api.client.post(f"{PREFIX}/start")
    assert response.status_code == 503
    assert api.requests == []
    assert await api.store.keys("*") == []


async def test_revocation_database_failure_rolls_back_installation_and_rules(
    api, review_db, monkeypatch
):
    assert (await api.callback(await api.start())).status_code == 200
    owner_id = api.users[0].id
    rules = await create_settings(
        review_db, owner_id, "301", "401", "pluto/lab", rules=ReviewRules(enabled=True)
    )
    original = installations.revoke_installation

    async def fail_after_flush(*args, **kwargs):
        await original(*args, **kwargs)
        raise SQLAlchemyError("private-database-details")

    monkeypatch.setattr(installations, "revoke_installation", fail_after_flush)
    response = await api.client.delete(f"{PREFIX}/301")
    assert response.status_code == 503
    assert "private-database-details" not in response.text
    await review_db.refresh(rules)
    assert rules.enabled
    assert rules.rules_version == 1
    row = await review_db.get(GitHubInstallation, "301")
    await review_db.refresh(row)
    assert row.revoked_at is None
