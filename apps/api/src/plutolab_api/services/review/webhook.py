"""Bounded signed GitHub events; no remote URLs, credentials, or provider calls."""

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import ClientDisconnect, Request

from plutolab_api.models.review import GitHubInstallation, ReviewDelivery, ReviewSettings
from plutolab_api.schemas.review import ReviewBudgets, ReviewPolicy
from plutolab_api.services.review.jobs import EnqueueReview, enqueue_review

MAX_BODY_BYTES = 1024 * 1024
ACTIONS = frozenset({"opened", "synchronize", "reopened"})


class WebhookError(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class VerifiedEvent:
    delivery_id: str
    event_type: str
    action: str
    payload_sha256: str
    payload: dict[str, object]


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("Non-finite JSON number")


def _header(request: Request, name: str, *, required: bool = True) -> str | None:
    values = request.headers.getlist(name)
    if len(values) > 1 or (required and not values):
        raise WebhookError(400, "Missing or repeated webhook header")
    return values[0] if values else None


async def verify_request(request: Request, secret: SecretStr) -> VerifiedEvent:
    """Cap accumulated raw bytes before each append; never call request.body/json."""
    length = _header(request, "content-length", required=False)
    if length is not None:
        if not re.fullmatch(r"[0-9]{1,20}", length):
            raise WebhookError(400, "Invalid Content-Length")
        if int(length) > MAX_BODY_BYTES:
            raise WebhookError(413, "Webhook body exceeds 1 MiB")
    encoding = _header(request, "content-encoding", required=False)
    if encoding not in (None, "identity"):
        raise WebhookError(415, "Encoded webhook bodies are unsupported")
    if not secret.get_secret_value():
        raise WebhookError(503, "Webhook signing is not configured")
    signatures = request.headers.getlist("x-hub-signature-256")
    if len(signatures) != 1 or not re.fullmatch(r"sha256=[0-9a-fA-F]{64}", signatures[0]):
        raise WebhookError(403, "Invalid webhook signature")
    body = bytearray()
    try:
        async for chunk in request.stream():
            if len(chunk) > MAX_BODY_BYTES - len(body):
                raise WebhookError(413, "Webhook body exceeds 1 MiB")
            body.extend(chunk)
    except ClientDisconnect:
        raise WebhookError(400, "Incomplete webhook body") from None
    if length is not None and len(body) != int(length):
        raise WebhookError(400, "Content-Length does not match body")
    expected = hmac.digest(secret.get_secret_value().encode("utf-8"), body, "sha256")
    if not hmac.compare_digest(expected, bytes.fromhex(signatures[0][7:])):
        raise WebhookError(403, "Invalid webhook signature")
    delivery = _header(request, "x-github-delivery")
    event_type = _header(request, "x-github-event")
    if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", delivery or ""):
        raise WebhookError(400, "Invalid delivery GUID")
    if not re.fullmatch(r"[a-z_]{1,32}", event_type or ""):
        raise WebhookError(400, "Invalid event type")
    try:
        payload = json.loads(
            body.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_invalid_constant
        )
    except (ValueError, RecursionError):
        raise WebhookError(400, "Invalid webhook JSON") from None
    if not isinstance(payload, dict):
        raise WebhookError(400, "Webhook JSON must be an object")
    action = payload.get("action", "")
    if event_type == "pull_request" and (
        not isinstance(action, str) or not re.fullmatch(r"[a-z_]{1,128}", action)
    ):
        raise WebhookError(400, "Invalid pull request action")
    # Ignored event payloads need no action schema and are never retained as raw JSON.
    if event_type != "pull_request":
        action = ""
    assert delivery is not None and event_type is not None
    return VerifiedEvent(
        str(UUID(delivery)), event_type, action, hashlib.sha256(body).hexdigest(), payload
    )


ClaimId = Annotated[int, Field(strict=True, gt=0, le=99_999_999_999_999_999_999)]


class _Claim(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)


class _IdClaim(_Claim):
    id: ClaimId


class _BaseClaim(_Claim):
    repo: _IdClaim


class _HeadClaim(_Claim):
    sha: str = Field(pattern=r"^[0-9a-f]{40}$")


class _PRClaim(_Claim):
    number: int = Field(gt=0, le=2_147_483_647)
    state: str = Field(pattern=r"^open$")
    base: _BaseClaim
    head: _HeadClaim


class PullRequestClaim(_Claim):
    installation: _IdClaim
    repository: _IdClaim
    number: int = Field(gt=0, le=2_147_483_647)
    pull_request: _PRClaim


def validate_pull_request(event: VerifiedEvent) -> PullRequestClaim:
    try:
        claim = PullRequestClaim.model_validate(event.payload)
    except ValidationError:
        raise WebhookError(400, "Invalid pull request identity") from None
    if (
        claim.number != claim.pull_request.number
        or claim.repository.id != claim.pull_request.base.repo.id
    ):
        raise WebhookError(400, "Inconsistent pull request identity")
    return claim


@dataclass(frozen=True)
class InboxResult:
    disposition: str
    duplicate: bool


async def ingest_event(
    db: AsyncSession,
    event: VerifiedEvent,
    *,
    model: str,
    budgets: ReviewBudgets | None,
    max_attempts: int,
) -> InboxResult:
    """Caller commits before acknowledgment. Delivery -> installation lock order.

    The digest and event/action tuple fence reused delivery IDs. No payload URLs,
    sender identities, source code, or PR text are stored or acted upon.
    """
    lock_key = int.from_bytes(hashlib.sha256(event.delivery_id.encode()).digest()[:8], signed=True)
    await db.execute(select(func.pg_advisory_xact_lock(lock_key)))
    existing = await db.get(ReviewDelivery, event.delivery_id)
    if existing is not None:
        if (
            existing.payload_sha256 != event.payload_sha256
            or existing.event_type != event.event_type
            or existing.action != event.action
        ):
            raise WebhookError(409, "Delivery GUID conflicts with stored event")
        return InboxResult(existing.disposition, True)

    async def ignore(reason: str) -> InboxResult:
        db.add(
            ReviewDelivery(
                delivery_id=event.delivery_id,
                event_type=event.event_type,
                action=event.action,
                payload_sha256=event.payload_sha256,
                disposition="ignored",
                ignore_reason=reason,
            )
        )
        await db.flush()
        return InboxResult("ignored", False)

    if event.event_type != "pull_request":
        return await ignore("irrelevant_event")
    if event.action not in ACTIONS:
        return await ignore("irrelevant_action")
    claim = validate_pull_request(event)
    installation = await db.scalar(
        select(GitHubInstallation)
        .where(GitHubInstallation.installation_id == str(claim.installation.id))
        .with_for_update()
    )
    if installation is None or installation.revoked_at is not None:
        return await ignore("inactive_installation")
    rules = await db.scalar(
        select(ReviewSettings).where(
            ReviewSettings.owner_id == installation.owner_id,
            ReviewSettings.installation_id == installation.installation_id,
            ReviewSettings.repo_id == str(claim.repository.id),
        )
    )
    if rules is None or not rules.enabled:
        return await ignore("repository_not_enabled")
    if not model.strip() or budgets is None:
        raise WebhookError(503, "Review execution policy is not configured")
    limits = budgets.model_dump()
    limits["min_changed_lines"] = rules.min_pr_lines
    if rules.max_pr_lines is not None:
        limits["max_changed_lines"] = min(budgets.max_changed_lines, rules.max_pr_lines)
    policy = ReviewPolicy(
        rules_version=rules.rules_version,
        enabled=True,
        focus=rules.focus,
        skip_paths=rules.skip_paths,
        provider="anthropic",
        model=model,
        budgets=ReviewBudgets.model_validate(limits),
        publication_mode="preview_only",
    )
    await enqueue_review(
        db,
        installation.owner_id,
        EnqueueReview(
            installation_id=installation.installation_id,
            repo_id=rules.repo_id,
            pr_number=claim.number,
            head_sha=claim.pull_request.head.sha,
            delivery_id=event.delivery_id,
            action=event.action,
            policy=policy,
            max_attempts=max_attempts,
        ),
    )
    delivery = await db.get(ReviewDelivery, event.delivery_id)
    assert delivery is not None
    delivery.payload_sha256 = event.payload_sha256
    await db.flush()
    return InboxResult("accepted", False)
