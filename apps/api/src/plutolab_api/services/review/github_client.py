"""Bounded GitHub App HTTP adapter. No OAuth, webhook URLs, DB or publication IO.

Callers must authorize owner/installation access before using this adapter.
REST contract baseline: 2022-11-28. Pagination uses local page numbers, not Link URLs.
"""

import asyncio
import math
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from types import TracebackType
from typing import Self, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from plutolab_api.core.config import Settings
from plutolab_api.core.github_app import GitHubAppCredentials, GitHubAppError

API_ORIGIN = "https://api.github.com"
API_VERSION = "2022-11-28"
_JSON_ACCEPT = "application/vnd.github+json"
_DIFF_ACCEPT = "application/vnd.github.diff"
_NAME = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")
_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
_CACHE_TTL_SECONDS = 300
_REFRESH_BUFFER_SECONDS = 60
_MAX_RETRIES = 2
_MAX_BACKOFF_SECONDS = 60


class Repository(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    full_name: str
    private: bool
    default_branch: str | None = None

    @field_validator("id", mode="before")
    @classmethod
    def decimal_id(cls, value: object) -> object:
        return str(value) if type(value) is int else value


class PullRequestHead(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    sha: str = Field(pattern=r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")
    ref: str


class PullRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    number: int = Field(gt=0)
    state: str = Field(pattern=r"^(open|closed)$")
    title: str
    head: PullRequestHead
    base: PullRequestHead
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)
    changed_files: int = Field(ge=0)


class RepositoryPage(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    total_count: int = Field(ge=0)
    repositories: list[Repository]


class _TokenResponse(BaseModel):
    token: SecretStr = Field(min_length=1)
    expires_at: datetime

    @field_validator("token")
    @classmethod
    def header_safe_token(cls, value: SecretStr) -> SecretStr:
        if not all(33 <= ord(char) <= 126 for char in value.get_secret_value()):
            raise ValueError("invalid token characters")
        return value


@dataclass(frozen=True)
class _CachedToken:
    token: SecretStr
    refresh_at: float


_DTO = TypeVar("_DTO", bound=BaseModel)


def _decode(response: httpx.Response, model: type[_DTO]) -> _DTO:
    try:
        return model.model_validate_json(response.content)
    except ValidationError:
        pass
    raise GitHubAppError("invalid_response")


def _installation_id(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise GitHubAppError("invalid_installation_id")
    return value


def _repository_path(owner: str, repo: str) -> str:
    if any(not _NAME.fullmatch(value) or value in {".", ".."} for value in (owner, repo)):
        raise GitHubAppError("invalid_repository")
    return f"/repos/{owner}/{repo}"


def _pr_path(owner: str, repo: str, number: int) -> str:
    if type(number) is not int or number <= 0:
        raise GitHubAppError("invalid_pr_number")
    return f"{_repository_path(owner, repo)}/pulls/{number}"


class GitHubAppClient:
    """Use one long-lived instance per App; async context manager closes and clears it.

    Inject only a transport for tests, not a client with arbitrary defaults/auth/hooks.
    Tokens stay in memory for at most five minutes, never within 60s of expiry.
    A lock coalesces token exchanges. Cache holds at most 256 installations.
    """

    def __init__(
        self,
        credentials: GitHubAppCredentials,
        *,
        timeout_seconds: float = 10,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 60:
            raise ValueError("timeout_seconds must be between 0 and 60")
        self._credentials = credentials
        self._clock = clock
        self._sleep = sleep
        self._tokens: dict[str, _CachedToken] = {}
        self._token_lock = asyncio.Lock()
        self._http = httpx.AsyncClient(
            transport=transport,
            timeout=timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        )

    @classmethod
    def from_settings(cls, config: Settings) -> Self:
        return cls(
            GitHubAppCredentials.from_settings(config),
            timeout_seconds=config.github_app_timeout_seconds,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        self._tokens.clear()
        await self._http.aclose()

    def invalidate_installation(self, installation_id: str) -> None:
        """Drop local cached credentials after caller verifies revocation/permission changes."""
        self._tokens.pop(_installation_id(installation_id), None)

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        delay = float(2**attempt)
        fallback = 60.0 * 2**attempt if response.status_code in {403, 429} else delay
        raw = response.headers.get("retry-after")
        has_wait_hint = False
        if raw is not None:
            try:
                wait = float(raw)
            except ValueError:
                try:
                    wait = parsedate_to_datetime(raw).timestamp() - self._clock()
                except (ValueError, TypeError, OverflowError):
                    wait = fallback
            if math.isfinite(wait) and wait >= 0:
                delay = max(delay, wait)
                has_wait_hint = True
        if response.headers.get("x-ratelimit-remaining") == "0":
            try:
                reset = float(response.headers.get("x-ratelimit-reset", ""))
                if math.isfinite(reset):
                    delay = max(delay, reset - self._clock())
                    has_wait_hint = True
            except ValueError:
                pass
        return delay if has_wait_hint else fallback

    async def _request(
        self,
        method: str,
        path: str,
        token: SecretStr,
        *,
        accept: str = _JSON_ACCEPT,
        params: dict[str, int] | None = None,
    ) -> httpx.Response:
        # Every path is built internally. This guard also protects future call sites.
        if not path.startswith("/") or path.startswith("//") or any(c in path for c in "?#\\"):
            raise GitHubAppError("invalid_api_path")
        headers = {
            "Authorization": f"Bearer {token.get_secret_value()}",
            "Accept": accept,
            "X-GitHub-Api-Version": API_VERSION,
        }
        for attempt in range(_MAX_RETRIES + 1):
            response = None
            error = None
            try:
                async with self._http.stream(
                    method,
                    API_ORIGIN + path,
                    headers=headers,
                    params=params,
                    json={"permissions": {"contents": "read", "pull_requests": "read"}}
                    if method == "POST"
                    else None,
                ) as upstream:
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in upstream.aiter_bytes():
                        size += len(chunk)
                        if size > _MAX_RESPONSE_BYTES:
                            raise GitHubAppError("response_too_large")
                        chunks.append(chunk)
                    # No request/auth object escapes this boundary.
                    response = httpx.Response(
                        upstream.status_code,
                        # aiter_bytes already decoded content; do not decompress it twice.
                        headers={
                            key: value
                            for key, value in upstream.headers.items()
                            if key not in {"content-encoding", "content-length"}
                        },
                        content=b"".join(chunks),
                    )
            except httpx.TimeoutException:
                error = GitHubAppError("timeout", retryable=True)
            except httpx.HTTPError:
                error = GitHubAppError("transport_error", retryable=True)
            if error is not None:
                if attempt < _MAX_RETRIES:
                    await self._sleep(float(2**attempt))
                    continue
                raise error
            assert response is not None
            status = response.status_code
            if 200 <= status < 300:
                return response
            limited = status == 429 or (
                status == 403
                and (
                    "retry-after" in response.headers
                    or response.headers.get("x-ratelimit-remaining") == "0"
                )
            )
            retryable = limited or 500 <= status < 600
            delay = self._retry_delay(response, attempt) if retryable else None
            if retryable and attempt < _MAX_RETRIES and delay <= _MAX_BACKOFF_SECONDS:
                await self._sleep(delay)
                continue
            code = (
                "rate_limited"
                if limited
                else {
                    401: "unauthorized",
                    403: "forbidden",
                    404: "not_found",
                }.get(status, "upstream_error")
            )
            raise GitHubAppError(
                code, status_code=status, retryable=retryable, retry_after_seconds=delay
            )
        raise AssertionError("unreachable")

    async def _installation_token(self, installation_id: str) -> SecretStr:
        installation_id = _installation_id(installation_id)
        async with self._token_lock:
            cached = self._tokens.get(installation_id)
            if cached is not None and self._clock() < cached.refresh_at:
                return cached.token
            self._tokens.pop(installation_id, None)
            response = await self._request(
                "POST",
                f"/app/installations/{installation_id}/access_tokens",
                self._credentials.create_jwt(),
            )
            result = _decode(response, _TokenResponse)
            if result.expires_at.tzinfo is None:
                raise GitHubAppError("invalid_token_expiry")
            now = self._clock()
            expires = result.expires_at.astimezone(UTC).timestamp()
            if expires <= now + _REFRESH_BUFFER_SECONDS:
                raise GitHubAppError("invalid_token_expiry")
            if len(self._tokens) >= 256:
                self._tokens.pop(next(iter(self._tokens)))
            self._tokens[installation_id] = _CachedToken(
                result.token, min(expires - _REFRESH_BUFFER_SECONDS, now + _CACHE_TTL_SECONDS)
            )
            return result.token

    async def _get(
        self,
        installation_id: str,
        path: str,
        *,
        accept: str = _JSON_ACCEPT,
        params: dict[str, int] | None = None,
    ) -> httpx.Response:
        for attempt in range(2):
            token = await self._installation_token(installation_id)
            try:
                return await self._request("GET", path, token, accept=accept, params=params)
            except GitHubAppError as error:
                if error.status_code != 401:
                    raise
                cached = self._tokens.get(installation_id)
                if cached is not None and cached.token == token:
                    self._tokens.pop(installation_id, None)
                if attempt:
                    raise
        raise AssertionError("unreachable")

    async def get_repository(self, installation_id: str, owner: str, repo: str) -> Repository:
        return _decode(await self._get(installation_id, _repository_path(owner, repo)), Repository)

    async def get_pull_request(
        self, installation_id: str, owner: str, repo: str, number: int
    ) -> PullRequest:
        return _decode(await self._get(installation_id, _pr_path(owner, repo, number)), PullRequest)

    async def get_pull_request_diff(
        self, installation_id: str, owner: str, repo: str, number: int
    ) -> str:
        response = await self._get(
            installation_id, _pr_path(owner, repo, number), accept=_DIFF_ACCEPT
        )
        try:
            return response.content.decode("utf-8")
        except UnicodeDecodeError:
            pass
        raise GitHubAppError("invalid_diff_encoding")

    async def list_repositories(
        self, installation_id: str, *, page: int = 1, per_page: int = 100
    ) -> RepositoryPage:
        if (
            type(page) is not int
            or page < 1
            or type(per_page) is not int
            or not 1 <= per_page <= 100
        ):
            raise GitHubAppError("invalid_pagination")
        return _decode(
            await self._get(
                installation_id,
                "/installation/repositories",
                params={"page": page, "per_page": per_page},
            ),
            RepositoryPage,
        )
