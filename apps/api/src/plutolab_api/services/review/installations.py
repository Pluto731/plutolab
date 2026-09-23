"""Verified installation binding and owner-bound one-time CSRF state.

Only linked personal GitHub accounts can prove ownership with the current account
model. Organization membership requires a separate user-authorization flow.
"""

import hashlib
import secrets
from datetime import datetime
from typing import Literal, TypeVar
from urllib.parse import urlencode
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.core.github_app import GitHubAppError
from plutolab_api.models.review import GitHubInstallation
from plutolab_api.services.review.github_client import GitHubAppClient
from plutolab_api.services.review.settings import (
    ReviewAccessDeniedError,
    ReviewConflictError,
    create_installation,
    get_installation,
    revoke_installation,
)

STATE_TTL_SECONDS = 300


class InstallationStateError(ValueError):
    """Missing, mismatched, already consumed or expired state; no token in diagnostic."""


class InstallationStateUnavailableError(RuntimeError):
    """Fail closed when the shared state store cannot guarantee one-time consumption."""


class AppIdentity(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    id: int = Field(gt=0)
    slug: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,99}$")


class InstallationAccount(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    id: int = Field(gt=0)
    type: Literal["User", "Organization"]


class InstallationEvidence(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    id: int = Field(gt=0)
    app_id: int = Field(gt=0)
    account: InstallationAccount
    suspended_at: datetime | None
    permissions: dict[str, str]


_Evidence = TypeVar("_Evidence", bound=BaseModel)


class InstallationGitHubClient(GitHubAppClient):
    """App-authenticated metadata reads; extends Slice 4 without changing it."""

    async def _metadata(self, path: str, model: type[_Evidence]) -> _Evidence:
        response = await self._request("GET", path, self._credentials.create_jwt())
        try:
            return model.model_validate_json(response.content)
        except ValidationError:
            pass
        raise GitHubAppError("invalid_response")

    async def app_identity(self) -> AppIdentity:
        return await self._metadata("/app", AppIdentity)

    async def installation(self, installation_id: str) -> InstallationEvidence:
        if (
            not installation_id.isascii()
            or not installation_id.isdecimal()
            or not 0 < len(installation_id) <= 20
            or installation_id.startswith("0")
        ):
            raise ReviewAccessDeniedError("Installation unavailable")
        return await self._metadata(f"/app/installations/{installation_id}", InstallationEvidence)


class _StateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    owner_id: UUID
    github_id: int = Field(gt=0)
    app_id: int = Field(gt=0)


class InstallationStart(BaseModel):
    installation_url: str
    expires_in_seconds: int = STATE_TTL_SECONDS


def _state_key(owner_id: UUID, state: str) -> str:
    # Neither Redis keys nor values persist the raw bearer state.
    digest = hashlib.sha256(state.encode()).hexdigest()
    return f"review:installation-state:{owner_id}:{digest}"


def _linked_github_id(github_id: int | None) -> int:
    if github_id is None or github_id <= 0:
        raise ReviewAccessDeniedError("A linked GitHub account is required")
    return github_id


async def initiate_installation(
    store: Redis,
    github: InstallationGitHubClient,
    owner_id: UUID,
    github_id: int | None,
) -> InstallationStart:
    github_id = _linked_github_id(github_id)
    app = await github.app_identity()
    record = _StateRecord(owner_id=owner_id, github_id=github_id, app_id=app.id)
    for _ in range(3):
        state = secrets.token_urlsafe(32)
        try:
            stored = await store.set(
                _state_key(owner_id, state), record.model_dump_json(), ex=STATE_TTL_SECONDS, nx=True
            )
        except RedisError:
            break
        if stored:
            return InstallationStart(
                installation_url=f"https://github.com/apps/{app.slug}/installations/new?{urlencode({'state': state})}"
            )
    raise InstallationStateUnavailableError("Installation state unavailable")


async def _consume_state(
    store: Redis, owner_id: UUID, github_id: int | None, state: str
) -> _StateRecord:
    github_id = _linked_github_id(github_id)
    if len(state) != 43 or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in state
    ):
        raise InstallationStateError("Invalid installation state")
    failed = False
    try:
        raw = await store.getdel(_state_key(owner_id, state))
    except RedisError:
        failed = True
        raw = None
    if failed:
        raise InstallationStateUnavailableError("Installation state unavailable")
    if raw is not None:
        try:
            record = _StateRecord.model_validate_json(raw)
        except ValidationError:
            record = None
        if record is not None and record.owner_id == owner_id and record.github_id == github_id:
            return record
    raise InstallationStateError("Invalid installation state")


def _verify_evidence(
    evidence: InstallationEvidence, installation_id: str, record: _StateRecord
) -> None:
    allowed_permissions = {
        "metadata": {"read"},
        "contents": {"read"},
        "pull_requests": {"read", "write"},
    }
    if (
        str(evidence.id) != installation_id
        or evidence.app_id != record.app_id
        or evidence.suspended_at is not None
        or evidence.account.type != "User"
        or evidence.account.id != record.github_id
        or evidence.permissions.get("contents") != "read"
        or evidence.permissions.get("pull_requests") not in {"read", "write"}
        or any(
            value not in allowed_permissions.get(key, set())
            for key, value in evidence.permissions.items()
        )
    ):
        raise ReviewAccessDeniedError("Installation ownership or permissions could not be verified")


async def bind_installation(
    db: AsyncSession,
    store: Redis,
    github: InstallationGitHubClient,
    owner_id: UUID,
    github_id: int | None,
    *,
    state: str,
    installation_id: str,
) -> GitHubInstallation:
    # Burn state before verification; failures require starting a fresh flow.
    record = await _consume_state(store, owner_id, github_id, state)
    evidence = await github.installation(installation_id)
    _verify_evidence(evidence, installation_id, record)
    # No row locks are held during remote IO. The primary key arbitrates first-bind races.
    existing = await db.scalar(
        select(GitHubInstallation)
        .where(GitHubInstallation.installation_id == installation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if existing is not None:
        if existing.owner_id != owner_id:
            raise ReviewAccessDeniedError("Installation unavailable")
        if existing.revoked_at is not None:
            raise ReviewConflictError("Revoked installation cannot be rebound by callback")
        return existing
    return await create_installation(db, owner_id, installation_id)


async def installation_status(
    db: AsyncSession, owner_id: UUID, installation_id: str
) -> GitHubInstallation:
    return await get_installation(db, owner_id, installation_id)


async def unbind_installation(
    db: AsyncSession, owner_id: UUID, installation_id: str
) -> GitHubInstallation:
    """Local soft revocation; retain ownership and history, disable rules atomically.

    Existing Slice 3 entry points check active installation under the same lock.
    No remote uninstall, token revocation or claim that an in-flight remote write was undone.
    """
    async with db.begin_nested():
        return await revoke_installation(db, owner_id, installation_id)
