"""Offline adapter acceptance: fake signer, MockTransport, no keys or databases."""

import asyncio
import gzip
import json
import socket
import traceback
from datetime import UTC, datetime
from email.utils import format_datetime

import httpx
import pytest
from pydantic import SecretStr

from plutolab_api.core.config import Settings
from plutolab_api.core.github_app import GitHubAppCredentials, GitHubAppError
from plutolab_api.services.review.github_client import API_ORIGIN, GitHubAppClient

NOW = 1_800_000_000.0
APP_JWT = "fake-app-jwt-never-signed"
KEY = "fake-key-never-generated"
TOKEN = "ghs_fake-installation-token"
REPO = {"id": 42, "full_name": "pluto/lab", "private": True, "default_branch": "main"}
PR = {
    "number": 3,
    "state": "open",
    "title": "Test PR",
    "head": {"sha": "a" * 40, "ref": "feature"},
    "base": {"sha": "b" * 40, "ref": "main"},
    "additions": 4,
    "deletions": 2,
    "changed_files": 1,
    "url": "https://evil.invalid/steal",
    "diff_url": "http://127.0.0.1/private",
}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Network access forbidden in Slice 4 tests")

    monkeypatch.setattr(socket.socket, "connect", reject)
    monkeypatch.setattr(socket.socket, "connect_ex", reject)
    monkeypatch.setattr(socket, "getaddrinfo", reject)


@pytest.fixture
def signer(monkeypatch):
    calls = []

    def encode(claims, key, algorithm):
        calls.append((claims, key, algorithm))
        return APP_JWT

    monkeypatch.setattr("plutolab_api.core.github_app.jwt.encode", encode)
    return calls


class Harness:
    def __init__(self, handler=None):
        self.now = NOW
        self.requests = []
        self.sleeps = []
        self.exchanges = 0
        self.handler = handler
        self.credentials = GitHubAppCredentials("123", SecretStr(KEY), clock=lambda: self.now)
        self.client = GitHubAppClient(
            self.credentials,
            transport=httpx.MockTransport(self.respond),
            clock=lambda: self.now,
            sleep=self.sleep,
        )

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def token_response(self, *, expires_in=3600, token=TOKEN):
        return httpx.Response(
            201,
            json={
                "token": token,
                "expires_at": datetime.fromtimestamp(self.now + expires_in, UTC).isoformat(),
            },
        )

    def respond(self, request):
        self.requests.append(request)
        assert str(request.url).startswith(API_ORIGIN + "/")
        if request.method == "POST":
            self.exchanges += 1
        if self.handler is not None:
            result = self.handler(request)
            if result is not None:
                return result
        if request.method == "POST":
            return self.token_response()
        return httpx.Response(200, json=REPO)


def assert_safe(error):
    rendered = "".join(traceback.format_exception(error)) + repr(vars(error))
    for secret in (APP_JWT, KEY, TOKEN, "raw-sensitive-body"):
        assert secret not in rendered
    assert error.__cause__ is None
    assert error.__context__ is None


def test_jwt_rs256_claims_and_secret_representations(signer):
    config = Settings(_env_file=None, github_app_id="123", github_app_private_key=KEY)
    credentials = GitHubAppCredentials.from_settings(config)
    credentials._clock = lambda: NOW
    token = credentials.create_jwt()
    assert signer == [({"iss": "123", "iat": int(NOW) - 60, "exp": int(NOW) + 540}, KEY, "RS256")]
    assert token.get_secret_value() == APP_JWT
    assert APP_JWT not in str(token) + repr(token) + repr(credentials)
    assert KEY not in repr(config) + config.model_dump_json() + repr(credentials)
    assert config.github_client_id == ""
    assert config.github_client_secret == ""


@pytest.mark.parametrize("app_id,key", [("", KEY), ("0", KEY), ("abc", KEY), ("123", "")])
def test_missing_app_credentials_fail_closed(app_id, key, signer):
    with pytest.raises(GitHubAppError, match="app_not_configured") as caught:
        GitHubAppCredentials(app_id, SecretStr(key)).create_jwt()
    assert signer == []
    assert_safe(caught.value)


def test_signing_error_does_not_retain_key_or_exception(monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError(KEY + APP_JWT)

    monkeypatch.setattr("plutolab_api.core.github_app.jwt.encode", fail)
    with pytest.raises(GitHubAppError, match="jwt_signing_failed") as caught:
        GitHubAppCredentials("123", SecretStr(KEY)).create_jwt()
    assert_safe(caught.value)


async def test_token_acquisition_cache_and_close(signer):
    h = Harness()
    async with h.client as client:
        first = await client.get_repository("7", "pluto", "lab")
        second = await client.get_repository("7", "pluto", "lab")
        assert first == second
        assert first.id == "42"
        assert h.exchanges == 1
        exchange, read, _ = h.requests
        assert exchange.url.path == "/app/installations/7/access_tokens"
        assert exchange.headers["authorization"] == f"Bearer {APP_JWT}"
        assert json.loads(exchange.content) == {
            "permissions": {"contents": "read", "pull_requests": "read"}
        }
        assert read.headers["authorization"] == f"Bearer {TOKEN}"
        assert read.headers["x-github-api-version"] == "2022-11-28"
        assert read.headers["accept"] == "application/vnd.github+json"
        assert TOKEN not in repr(client._tokens)
    assert h.client._tokens == {}
    assert h.client._http.is_closed


@pytest.mark.parametrize("lifetime,refresh_at", [(3600, 300), (120, 60)])
async def test_cache_refresh_boundary(lifetime, refresh_at, signer):
    h = Harness(
        lambda request: h.token_response(expires_in=lifetime) if request.method == "POST" else None
    )
    async with h.client as client:
        await client.get_repository("7", "pluto", "lab")
        h.now = NOW + refresh_at - 1
        await client.get_repository("7", "pluto", "lab")
        assert h.exchanges == 1
        h.now += 1
        await client.get_repository("7", "pluto", "lab")
        assert h.exchanges == 2


async def test_installation_isolation_invalidation_and_concurrent_acquisition(signer):
    h = Harness()
    async with h.client as client:
        results = await asyncio.gather(
            *(client.get_repository("7", "pluto", "lab") for _ in range(8))
        )
        assert len(results) == 8
        assert h.exchanges == 1
        await client.get_repository("8", "pluto", "lab")
        assert h.exchanges == 2
        client.invalidate_installation("7")
        await client.get_repository("7", "pluto", "lab")
        await client.get_repository("8", "pluto", "lab")
        assert h.exchanges == 3


async def test_pr_metadata_and_diff_ignore_payload_urls(signer):
    def handler(request):
        if request.method == "POST":
            return None
        if request.headers["accept"] == "application/vnd.github.diff":
            return httpx.Response(200, text="diff --git a/a.py b/a.py\n+hello\n")
        return httpx.Response(200, json=PR)

    h = Harness(handler)
    async with h.client as client:
        pr = await client.get_pull_request("7", "pluto", "lab", 3)
        diff = await client.get_pull_request_diff("7", "pluto", "lab", 3)
        assert pr.head.sha == "a" * 40
        assert pr.number == 3
        assert "diff_url" not in pr.model_dump()
        assert diff == "diff --git a/a.py b/a.py\n+hello\n"
        assert [r.url.path for r in h.requests[1:]] == ["/repos/pluto/lab/pulls/3"] * 2


async def test_repository_pagination_never_follows_link(signer):
    h = Harness(
        lambda request: (
            httpx.Response(
                200,
                json={"total_count": 2, "repositories": [REPO]},
                headers={"Link": '<https://evil.invalid/steal>; rel="next"'},
            )
            if request.method == "GET"
            else None
        )
    )
    async with h.client as client:
        page = await client.list_repositories("7", page=2, per_page=1)
        assert page.total_count == 2
        assert page.repositories[0].id == "42"
        assert h.requests[-1].url.path == "/installation/repositories"
        assert dict(h.requests[-1].url.params) == {"page": "2", "per_page": "1"}
        assert len(h.requests) == 2


@pytest.mark.parametrize(
    "owner,repo",
    [
        ("https://evil.invalid", "lab"),
        ("..", "lab"),
        ("pluto", "a/b"),
        ("pluto", "%2f"),
        ("pluto", "a?token=x"),
    ],
)
async def test_unsafe_repository_paths_fail_before_io(owner, repo, signer):
    h = Harness()
    async with h.client as client:
        with pytest.raises(GitHubAppError, match="invalid_repository"):
            await client.get_repository("7", owner, repo)
        assert h.requests == []


@pytest.mark.parametrize("installation_id", ["0", "../7", "7?x=y", "https://evil.invalid", "７"])
async def test_invalid_installation_fails_before_io(installation_id, signer):
    h = Harness()
    async with h.client as client:
        with pytest.raises(GitHubAppError, match="invalid_installation_id"):
            await client.get_repository(installation_id, "pluto", "lab")
        assert h.requests == []


@pytest.mark.parametrize("number", [0, -1, True, "3"])
async def test_invalid_pr_number(number, signer):
    h = Harness()
    async with h.client as client:
        with pytest.raises(GitHubAppError, match="invalid_pr_number"):
            await client.get_pull_request("7", "pluto", "lab", number)
        assert h.requests == []


@pytest.mark.parametrize("page,per_page", [(0, 10), (1, 101), (True, 10), (1, 0)])
async def test_invalid_pagination(page, per_page, signer):
    h = Harness()
    async with h.client as client:
        with pytest.raises(GitHubAppError, match="invalid_pagination"):
            await client.list_repositories("7", page=page, per_page=per_page)
        assert h.requests == []


@pytest.mark.parametrize(
    "status,code",
    [(403, "forbidden"), (404, "not_found"), (422, "upstream_error"), (302, "upstream_error")],
)
async def test_terminal_errors_and_redirects_are_safe(status, code, signer, caplog):
    caplog.set_level("DEBUG")
    h = Harness(
        lambda request: (
            httpx.Response(
                status,
                text=TOKEN + KEY + "raw-sensitive-body",
                headers={"Location": "https://evil.invalid/" + TOKEN},
            )
            if request.method == "GET"
            else None
        )
    )
    async with h.client as client:
        with pytest.raises(GitHubAppError) as caught:
            await client.get_repository("7", "pluto", "lab")
        assert caught.value.code == code
        assert caught.value.status_code == status
        assert not caught.value.retryable
        assert len(h.requests) == 2
        assert h.sleeps == []
        assert_safe(caught.value)
        for secret in (TOKEN, KEY, APP_JWT, "raw-sensitive-body"):
            assert secret not in caplog.text


@pytest.mark.parametrize("always_unauthorized", [False, True])
async def test_401_refreshes_once_and_evicts_rejected_token(always_unauthorized, signer):
    reads = 0

    def handler(request):
        nonlocal reads
        if request.method == "POST":
            return h.token_response(token=f"{TOKEN}-{h.exchanges}")
        reads += 1
        if reads == 1 or always_unauthorized:
            return httpx.Response(401, text=TOKEN)
        return None

    h = Harness(handler)
    async with h.client as client:
        if always_unauthorized:
            with pytest.raises(GitHubAppError, match="unauthorized") as caught:
                await client.get_repository("7", "pluto", "lab")
            assert_safe(caught.value)
            assert client._tokens == {}
        else:
            assert (await client.get_repository("7", "pluto", "lab")).id == "42"
        assert h.exchanges == 2
        assert reads == 2
        assert h.requests[-1].headers["authorization"] == f"Bearer {TOKEN}-2"


async def test_exchange_401_is_not_retried(signer):
    h = Harness(lambda request: httpx.Response(401, text=APP_JWT))
    async with h.client as client:
        with pytest.raises(GitHubAppError, match="unauthorized") as caught:
            await client.get_repository("7", "pluto", "lab")
        assert h.exchanges == 1
        assert client._tokens == {}
        assert_safe(caught.value)


@pytest.mark.parametrize(
    "status,headers,expected",
    [
        (429, {"Retry-After": "3"}, 3),
        (403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(NOW + 4)}, 4),
        (403, {"Retry-After": "2"}, 2),
        (429, {"Retry-After": format_datetime(datetime.fromtimestamp(NOW + 5, UTC))}, 5),
        (503, {}, 1),
    ],
)
async def test_retry_backoff_then_success(status, headers, expected, signer):
    reads = 0

    def handler(request):
        nonlocal reads
        if request.method == "GET":
            reads += 1
            if reads == 1:
                return httpx.Response(status, headers=headers, text=TOKEN)
        return None

    h = Harness(handler)
    async with h.client as client:
        assert (await client.get_repository("7", "pluto", "lab")).id == "42"
        assert h.sleeps == [expected]
        assert reads == 2
        assert h.exchanges == 1


async def test_long_rate_limit_returns_delay_without_retrying_early(signer):
    h = Harness(lambda request: httpx.Response(429, headers={"Retry-After": "120"}, text=TOKEN))
    async with h.client as client:
        with pytest.raises(GitHubAppError) as caught:
            await client.get_repository("7", "pluto", "lab")
        assert caught.value.code == "rate_limited"
        assert caught.value.retryable
        assert caught.value.retry_after_seconds == 120
        assert h.sleeps == []
        assert h.exchanges == 1
        assert_safe(caught.value)


@pytest.mark.parametrize("header", ["invalid", "nan", "inf", "-1"])
async def test_malformed_retry_headers_are_bounded(header, signer):
    h = Harness(lambda request: httpx.Response(429, headers={"Retry-After": header}))
    async with h.client as client:
        with pytest.raises(GitHubAppError, match="rate_limited"):
            await client.get_repository("7", "pluto", "lab")
        assert h.exchanges == 2
        assert h.sleeps == [60]


@pytest.mark.parametrize(
    "error_type,code", [(httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "transport_error")]
)
async def test_transport_failures_retry_and_redact(error_type, code, signer, caplog):
    caplog.set_level("DEBUG")

    def handler(request):
        raise error_type(TOKEN + KEY + APP_JWT, request=request)

    h = Harness(handler)
    async with h.client as client:
        with pytest.raises(GitHubAppError) as caught:
            await client.get_repository("7", "pluto", "lab")
        assert caught.value.code == code
        assert caught.value.retryable
        assert h.exchanges == 3
        assert h.sleeps == [1, 2]
        assert_safe(caught.value)
        for secret in (TOKEN, KEY, APP_JWT):
            assert secret not in caplog.text


@pytest.mark.parametrize(
    "payload",
    [
        {"token": TOKEN, "expires_at": "bad"},
        {"token": "", "expires_at": "2027-01-15T09:00:00Z"},
        {"token": TOKEN, "expires_at": datetime.fromtimestamp(NOW, UTC).isoformat()},
        {"token": TOKEN, "expires_at": datetime.fromtimestamp(NOW + 60, UTC).isoformat()},
        {
            "token": TOKEN,
            "expires_at": datetime.fromtimestamp(NOW + 3600, UTC).replace(tzinfo=None).isoformat(),
        },
    ],
)
async def test_invalid_token_responses_never_cache_or_leak(payload, signer):
    h = Harness(lambda request: httpx.Response(201, json=payload))
    async with h.client as client:
        with pytest.raises(GitHubAppError) as caught:
            await client.get_repository("7", "pluto", "lab")
        assert client._tokens == {}
        assert h.exchanges == 1
        assert_safe(caught.value)


@pytest.mark.parametrize(
    "body", [b"raw-sensitive-body", b'{"token": "ghs_fake-installation-token"}']
)
async def test_invalid_metadata_response_is_redacted(body, signer):
    h = Harness(
        lambda request: httpx.Response(200, content=body) if request.method == "GET" else None
    )
    async with h.client as client:
        with pytest.raises(GitHubAppError, match="invalid_response") as caught:
            await client.get_repository("7", "pluto", "lab")
        assert_safe(caught.value)


@pytest.mark.parametrize(
    "content,code",
    [(b"\xff", "invalid_diff_encoding"), (b"x" * (5 * 1024 * 1024 + 1), "response_too_large")],
)
async def test_diff_encoding_and_size_limits(content, code, signer):
    h = Harness(
        lambda request: httpx.Response(200, content=content) if request.method == "GET" else None
    )
    async with h.client as client:
        with pytest.raises(GitHubAppError, match=code):
            await client.get_pull_request_diff("7", "pluto", "lab", 3)
        assert len(h.requests) == 2


async def test_explicit_timeout_proxy_isolation_and_cancellation(signer, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://evil.invalid:1234")
    h = Harness(lambda request: (_ for _ in ()).throw(asyncio.CancelledError()))
    async with h.client as client:
        assert client._http.timeout == httpx.Timeout(10)
        assert not client._http.trust_env
        assert not client._http.follow_redirects
        with pytest.raises(asyncio.CancelledError):
            await client.get_repository("7", "pluto", "lab")
        assert h.sleeps == []
        assert client._tokens == {}


async def test_settings_timeout_wiring_and_disabled_credentials(signer):
    config = Settings(
        _env_file=None, github_app_id="", github_app_private_key="", github_app_timeout_seconds=4
    )
    async with GitHubAppClient.from_settings(config) as client:
        assert client._http.timeout == httpx.Timeout(4)
        with pytest.raises(GitHubAppError, match="app_not_configured"):
            await client.get_repository("7", "pluto", "lab")
        assert signer == []


@pytest.mark.parametrize("timeout", [0, -1, 61, float("nan"), float("inf")])
def test_invalid_timeout_rejected(timeout, signer):
    with pytest.raises(ValueError, match="timeout_seconds"):
        GitHubAppClient(GitHubAppCredentials("123", SecretStr(KEY)), timeout_seconds=timeout)


async def test_compressed_json_is_decoded_once(signer):
    h = Harness(
        lambda request: (
            httpx.Response(
                200,
                headers={"Content-Encoding": "gzip"},
                content=gzip.compress(json.dumps(REPO).encode()),
            )
            if request.method == "GET"
            else None
        )
    )
    async with h.client as client:
        assert (await client.get_repository("7", "pluto", "lab")).id == "42"
        assert h.sleeps == []


@pytest.mark.parametrize("token", [TOKEN + "\r\nInjected: value", " ", "非令牌"])
async def test_token_header_injection_rejected(token, signer):
    h = Harness(lambda request: h.token_response(token=token))
    async with h.client as client:
        with pytest.raises(GitHubAppError, match="invalid_response") as caught:
            await client.get_repository("7", "pluto", "lab")
        assert len(h.requests) == 1
        assert client._tokens == {}
        assert_safe(caught.value)


async def test_rate_limit_without_headers_uses_conservative_backoff(signer):
    h = Harness(lambda request: httpx.Response(429))
    async with h.client as client:
        with pytest.raises(GitHubAppError, match="rate_limited") as caught:
            await client.get_repository("7", "pluto", "lab")
        assert h.exchanges == 2
        assert h.sleeps == [60]
        assert caught.value.retry_after_seconds == 120


async def test_retry_exhaustion_for_server_errors(signer):
    h = Harness(lambda request: httpx.Response(503, text=TOKEN))
    async with h.client as client:
        with pytest.raises(GitHubAppError, match="upstream_error") as caught:
            await client.get_repository("7", "pluto", "lab")
        assert h.exchanges == 3
        assert h.sleeps == [1, 2]
        assert caught.value.status_code == 503
        assert caught.value.retryable
        assert_safe(caught.value)


async def test_failed_refresh_never_falls_back_to_stale_token(signer):
    h = Harness(
        lambda request: (
            httpx.Response(403) if request.method == "POST" and h.exchanges > 1 else None
        )
    )
    async with h.client as client:
        await client.get_repository("7", "pluto", "lab")
        h.now += 300
        with pytest.raises(GitHubAppError, match="forbidden"):
            await client.get_repository("7", "pluto", "lab")
        assert len(h.requests) == 3
        assert client._tokens == {}


async def test_bounded_cache_evicts_oldest_installation(signer):
    h = Harness()
    async with h.client as client:
        for installation_id in range(1, 258):
            await client.get_repository(str(installation_id), "pluto", "lab")
        assert len(client._tokens) == 256
        assert "1" not in client._tokens
        assert "257" in client._tokens


@pytest.mark.parametrize(
    "path", ["https://evil.invalid", "//evil.invalid", "/repos/a/b?token=x", "/repos/a\\b"]
)
async def test_internal_origin_guard_rejects_arbitrary_urls(path, signer):
    h = Harness()
    async with h.client as client:
        with pytest.raises(GitHubAppError, match="invalid_api_path"):
            await client._request("GET", path, SecretStr(TOKEN))
        assert h.requests == []
