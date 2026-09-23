"""Local signed webhook acceptance. Network is limited to disposable PostgreSQL."""

import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from starlette.requests import Request

from plutolab_api.api.v1.router import api_router
from plutolab_api.core.config import settings
from plutolab_api.db.base import Base
from plutolab_api.db.deps import get_db
from plutolab_api.models.review import (
    GitHubInstallation,
    ReviewDelivery,
    ReviewJob,
    ReviewOutbox,
    ReviewSettings,
)
from plutolab_api.models.user import User
from plutolab_api.services.review import webhook
from plutolab_api.services.review.jobs import enqueue_review
from plutolab_api.services.review.settings import (
    ReviewConflictError,
    ReviewRules,
    create_installation,
    create_settings,
)
from plutolab_api.services.review.webhook import MAX_BODY_BYTES, WebhookError, verify_request
from tests.test_review_domain import disposable_database, migrate
from tests.test_review_domain import owners as owners
from tests.test_review_domain import review_db as review_db
from tests.test_review_domain import review_engine as review_engine
from tests.test_review_installations_api import local_only as local_only
from tests.test_review_jobs import request as job_request

SECRET = SecretStr("local-webhook-signing-fixture-not-a-production-secret")


def signed_headers(body: bytes, *, event="ping", delivery=None):
    return {
        "x-hub-signature-256": "sha256="
        + hmac.new(SECRET.get_secret_value().encode(), body, hashlib.sha256).hexdigest(),
        "x-github-delivery": delivery or str(uuid4()),
        "x-github-event": event,
    }


def raw_request(chunks, headers):
    events = iter(chunks)
    reads = []

    async def receive():
        reads.append(True)
        item = next(events)
        if isinstance(item, dict):
            return item
        return {"type": "http.request", "body": item, "more_body": bool(item)}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/review/webhook",
            "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
        },
        receive,
    ), reads


async def test_chunked_body_verified_with_constant_time_comparison(monkeypatch):
    body = b'{"zen":"local"}'
    compare = Mock(wraps=hmac.compare_digest)
    monkeypatch.setattr(webhook.hmac, "compare_digest", compare)
    request, reads = raw_request([body[:4], body[4:], b""], signed_headers(body))
    event = await verify_request(request, SECRET)
    assert event.payload == {"zen": "local"}
    assert event.payload_sha256 == hashlib.sha256(body).hexdigest()
    assert len(reads) == 3
    compare.assert_called_once()
    assert all(isinstance(value, bytes) for value in compare.call_args.args)


@pytest.mark.parametrize(
    "signature", [None, "", "sha1=" + "0" * 40, "sha256=oops", "sha256=" + "0" * 64]
)
async def test_missing_malformed_or_mismatched_signature(signature):
    body = b"{}"
    headers = signed_headers(body)
    if signature is None:
        del headers["x-hub-signature-256"]
    else:
        headers["x-hub-signature-256"] = signature
    request, _ = raw_request([body, b""], headers)
    with pytest.raises(WebhookError) as caught:
        await verify_request(request, SECRET)
    assert caught.value.status == 403


async def test_declared_oversize_rejected_without_reading():
    headers = signed_headers(b"{}") | {"content-length": str(MAX_BODY_BYTES + 1)}
    request, reads = raw_request([], headers)
    with pytest.raises(WebhookError) as caught:
        await verify_request(request, SECRET)
    assert caught.value.status == 413
    assert not reads


async def test_stream_limit_checked_before_buffering_next_chunk():
    chunks = [b"x" * (MAX_BODY_BYTES - 1), b"xx", b"must-not-read"]
    request, reads = raw_request(chunks, signed_headers(b"{}"))
    with pytest.raises(WebhookError) as caught:
        await verify_request(request, SECRET)
    assert caught.value.status == 413
    assert len(reads) == 2


async def test_exact_body_limit_is_accepted():
    body = b'{"text":"' + b"x" * (MAX_BODY_BYTES - 11) + b'"}'
    assert len(body) == MAX_BODY_BYTES
    request, _ = raw_request([body, b""], signed_headers(body))
    assert (await verify_request(request, SECRET)).event_type == "ping"


@pytest.mark.parametrize(
    "body", [b"{", b"[]", b"\xff", b'{"a":1,"a":2}', b'{"a":NaN}', b"[" * 2000]
)
async def test_signed_malformed_json_is_rejected(body):
    request, _ = raw_request([body, b""], signed_headers(body))
    with pytest.raises(WebhookError) as caught:
        await verify_request(request, SECRET)
    assert caught.value.status == 400


@pytest.mark.parametrize(
    "headers,status",
    [
        ({"content-length": "-1"}, 400),
        ({"content-length": "1"}, 400),
        ({"content-encoding": "gzip"}, 415),
        ({"x-github-delivery": "bad"}, 400),
        ({"x-github-event": "../url"}, 400),
    ],
)
async def test_bad_transport_headers(headers, status):
    request, _ = raw_request([b"{}", b""], signed_headers(b"{}") | headers)
    with pytest.raises(WebhookError) as caught:
        await verify_request(request, SECRET)
    assert caught.value.status == status


async def test_unconfigured_secret_fails_closed_without_body_read():
    request, reads = raw_request([], signed_headers(b"{}"))
    with pytest.raises(WebhookError) as caught:
        await verify_request(request, SecretStr(""))
    assert caught.value.status == 503
    assert not reads


async def test_disconnect_never_acknowledged():
    request, _ = raw_request([b"{", {"type": "http.disconnect"}], signed_headers(b"{}"))
    with pytest.raises(WebhookError) as caught:
        await verify_request(request, SECRET)
    assert caught.value.status == 400


@pytest.mark.parametrize(
    "name", ["x-hub-signature-256", "x-github-delivery", "x-github-event", "content-length"]
)
async def test_duplicate_headers_rejected(name):
    body = b"{}"
    request, _ = raw_request([body, b""], signed_headers(body) | {"content-length": "2"})
    header = next(item for item in request.scope["headers"] if item[0] == name.encode())
    request.scope["headers"].append(header)
    with pytest.raises(WebhookError) as caught:
        await verify_request(request, SECRET)
    assert caught.value.status == (403 if name == "x-hub-signature-256" else 400)


async def test_raw_byte_tampering_rejected_even_when_json_equivalent():
    request, _ = raw_request([b'{ "a": 1 }', b""], signed_headers(b'{"a":1}'))
    with pytest.raises(WebhookError) as caught:
        await verify_request(request, SECRET)
    assert caught.value.status == 403


@pytest.mark.parametrize("action", [None, 1, "", "a" * 129, "../../secret"])
async def test_invalid_pr_action(action):
    body = json.dumps({"action": action}).encode()
    request, _ = raw_request([body, b""], signed_headers(body, event="pull_request"))
    with pytest.raises(WebhookError) as caught:
        await verify_request(request, SECRET)
    assert caught.value.status == 400


PREFIX = "/api/v1/review/webhook"


def pr_payload(action="opened", **changes):
    payload = {
        "action": action,
        "installation": {"id": 301},
        "repository": {"id": 401, "html_url": "https://untrusted.invalid/repo"},
        "number": 7,
        "pull_request": {
            "number": 7,
            "state": "open",
            "base": {"repo": {"id": 401}},
            "head": {"sha": "a" * 40},
            "diff_url": "https://untrusted.invalid/private",
            "body": "private PR text must not be persisted",
        },
        "sender": {"id": 999},
        "user_id": "not-authority",
    }
    payload.update(changes)
    return payload


async def post_event(client, payload=None, *, event="pull_request", delivery=None, headers=None):
    body = json.dumps(pr_payload() if payload is None else payload).encode()
    return await client.post(
        PREFIX,
        content=body,
        headers=signed_headers(body, event=event, delivery=delivery) | (headers or {}),
    )


async def seed_review(db, owner):
    await create_installation(db, owner.id, "301")
    await create_settings(db, owner.id, "301", "401", "owner/repo", rules=ReviewRules(enabled=True))


@pytest_asyncio.fixture
async def webhook_api(review_db, owners, monkeypatch):
    monkeypatch.setattr(settings, "github_app_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "review_webhook_model", "local-test-model")
    monkeypatch.setattr(settings, "review_webhook_budgets", job_request().policy.budgets)
    await seed_review(review_db, owners[0])
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")

    async def database():
        yield review_db

    app.dependency_overrides[get_db] = database
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def counts(db):
    return tuple(
        [
            await db.scalar(select(func.count()).select_from(model))
            for model in (ReviewDelivery, ReviewJob, ReviewOutbox)
        ]
    )


@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
async def test_accepted_pr_commits_delivery_job_and_outbox(webhook_api, review_db, owners, action):
    response = await post_event(webhook_api, pr_payload(action))
    assert response.status_code == 202, response.text
    assert response.json() == {"status": "accepted", "duplicate": False}
    assert response.headers["cache-control"] == "no-store"
    assert await counts(review_db) == (1, 1, 1)
    job = await review_db.scalar(select(ReviewJob))
    delivery = await review_db.scalar(select(ReviewDelivery))
    outbox = await review_db.scalar(select(ReviewOutbox))
    assert job.owner_id == owners[0].id
    assert delivery.job_id == outbox.job_id == job.id
    assert delivery.action == action and len(delivery.payload_sha256) == 64
    assert delivery.disposition == "accepted" and delivery.ignore_reason is None
    assert job.policy["publication_mode"] == "preview_only"
    assert "private PR" not in json.dumps(job.policy)
    assert job.head_sha == "a" * 40


@pytest.mark.parametrize(
    "event,action",
    [
        ("ping", None),
        ("star", "created"),
        ("issues", "opened"),
        ("unknown_event", None),
        ("pull_request", "closed"),
        ("pull_request", "edited"),
        ("pull_request", "auto_merge_enabled"),
    ],
)
async def test_irrelevant_events_persist_and_deduplicate(webhook_api, review_db, event, action):
    delivery = str(uuid4())
    payload = {} if action is None else {"action": action}
    first = await post_event(webhook_api, payload, event=event, delivery=delivery)
    second = await post_event(webhook_api, payload, event=event, delivery=delivery)
    assert first.status_code == second.status_code == 200
    assert first.json() == {"status": "ignored", "duplicate": False}
    assert second.json() == {"status": "ignored", "duplicate": True}
    assert await counts(review_db) == (1, 0, 0)
    row = await review_db.get(ReviewDelivery, delivery)
    assert row.job_id is None and row.owner_id is None and row.payload_sha256


async def test_delivery_and_job_suppression_are_independent(webhook_api, review_db):
    delivery = str(uuid4())
    first = await post_event(webhook_api, delivery=delivery)
    same = await post_event(webhook_api, delivery=delivery.upper())
    another = await post_event(webhook_api)
    assert first.status_code == same.status_code == another.status_code == 202
    assert same.json()["duplicate"] is True
    assert another.json()["duplicate"] is False
    assert await counts(review_db) == (2, 1, 1)


@pytest.mark.parametrize("change", ["payload", "event", "action"])
async def test_reused_guid_with_different_content_is_conflict(webhook_api, review_db, change):
    delivery = str(uuid4())
    assert (await post_event(webhook_api, delivery=delivery)).status_code == 202
    payload = pr_payload()
    event = "pull_request"
    if change == "payload":
        payload["number"] = 8
    elif change == "action":
        payload["action"] = "reopened"
    else:
        event = "ping"
    result = await post_event(webhook_api, payload, event=event, delivery=delivery)
    assert result.status_code == 409
    assert await counts(review_db) == (1, 1, 1)


@pytest.mark.parametrize(
    "mutation",
    ["missing_installation", "bool_id", "repo_mismatch", "pr_mismatch", "bad_sha", "closed_state"],
)
async def test_invalid_pr_identity_never_persists(webhook_api, review_db, mutation):
    payload = pr_payload()
    if mutation == "missing_installation":
        payload.pop("installation")
    elif mutation == "bool_id":
        payload["installation"]["id"] = True
    elif mutation == "repo_mismatch":
        payload["pull_request"]["base"]["repo"]["id"] = 402
    elif mutation == "pr_mismatch":
        payload["pull_request"]["number"] = 8
    elif mutation == "bad_sha":
        payload["pull_request"]["head"]["sha"] = "not-a-sha"
    else:
        payload["pull_request"]["state"] = "closed"
    response = await post_event(webhook_api, payload)
    assert response.status_code == 400
    assert await counts(review_db) == (0, 0, 0)


@pytest.mark.parametrize(
    "case", ["unknown_installation", "revoked", "disabled", "foreign_repository"]
)
async def test_only_active_authorized_repository_is_scheduled(webhook_api, review_db, owners, case):
    payload = pr_payload()
    if case == "unknown_installation":
        payload["installation"]["id"] = 999
    elif case == "revoked":
        row = await review_db.get(GitHubInstallation, "301")
        row.revoked_at = datetime.now(UTC)
    elif case == "disabled":
        row = await review_db.scalar(select(ReviewSettings))
        row.enabled = False
    else:
        await create_installation(review_db, owners[1].id, "302")
        payload["installation"]["id"] = 302
    await review_db.flush()
    response = await post_event(webhook_api, payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert await counts(review_db) == (1, 0, 0)


@pytest.mark.parametrize("config", ["secret", "model", "budgets", "inconsistent_budget"])
async def test_missing_or_invalid_configuration_fails_closed(
    webhook_api, review_db, monkeypatch, config
):
    if config == "secret":
        monkeypatch.setattr(settings, "github_app_webhook_secret", SecretStr(""))
    elif config == "model":
        monkeypatch.setattr(settings, "review_webhook_model", "")
    elif config == "budgets":
        monkeypatch.setattr(settings, "review_webhook_budgets", None)
    else:
        limits = settings.review_webhook_budgets.model_copy(update={"context_window_tokens": 1})
        monkeypatch.setattr(settings, "review_webhook_budgets", limits)
    response = await post_event(webhook_api)
    assert response.status_code == 503
    assert await counts(review_db) == (0, 0, 0)
    assert SECRET.get_secret_value() not in response.text


async def test_webhook_http_rejections_do_not_commit(webhook_api, review_db, monkeypatch):
    commit = AsyncMock(wraps=review_db.commit)
    monkeypatch.setattr(review_db, "commit", commit)
    for headers, expected in [
        ({"x-hub-signature-256": "bad"}, 403),
        ({"content-length": str(MAX_BODY_BYTES + 1)}, 413),
    ]:
        response = await post_event(webhook_api, headers=headers)
        assert response.status_code == expected
    commit.assert_not_called()
    assert await counts(review_db) == (0, 0, 0)


async def test_repo_rules_snapshot_and_cap_used(webhook_api, review_db):
    row = await review_db.scalar(select(ReviewSettings))
    row.rules_version = 4
    row.max_pr_lines = 500
    row.skip_paths = ["docs/**"]
    row.focus = ["security"]
    await review_db.flush()
    assert (await post_event(webhook_api)).status_code == 202
    job = await review_db.scalar(select(ReviewJob))
    assert job.rules_version == 4 and job.policy["skip_paths"] == ["docs/**"]
    assert job.policy["focus"] == ["security"]
    assert job.policy["budgets"]["max_changed_lines"] == 500


async def test_failure_after_outbox_flush_rolls_back_everything(
    webhook_api, review_db, monkeypatch
):
    original = webhook.enqueue_review

    async def fail_after_flush(*args, **kwargs):
        await original(*args, **kwargs)
        assert await counts(review_db) == (1, 1, 1)
        raise SQLAlchemyError("private-database-detail")

    monkeypatch.setattr(webhook, "enqueue_review", fail_after_flush)
    response = await post_event(webhook_api)
    assert response.status_code == 503
    assert "private-database-detail" not in response.text
    assert await counts(review_db) == (0, 0, 0)


@pytest_asyncio.fixture
async def durable_api(monkeypatch):
    """Separate committed sessions, not the rollback fixture's shared transaction."""
    monkeypatch.setattr(settings, "github_app_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "review_webhook_model", "local-test-model")
    monkeypatch.setattr(settings, "review_webhook_budgets", job_request().policy.budgets)
    async with disposable_database() as url:
        migrate(url, "upgrade", "head")
        engine = create_async_engine(url)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                owner = User(email=f"{uuid4()}@webhook.test")
                db.add(owner)
                await db.flush()
                await seed_review(db, owner)
                await db.commit()
            app = FastAPI()
            app.include_router(api_router, prefix="/api/v1")

            async def database():
                async with AsyncSession(engine, expire_on_commit=False) as db:
                    yield db

            app.dependency_overrides[get_db] = database
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                yield client, engine
        finally:
            await engine.dispose()


async def test_concurrent_duplicate_deliveries_commit_once(durable_api):
    client, engine = durable_api
    delivery = str(uuid4())
    responses = await asyncio.gather(*[post_event(client, delivery=delivery) for _ in range(4)])
    assert [response.status_code for response in responses] == [202] * 4
    assert sum(not response.json()["duplicate"] for response in responses) == 1
    async with AsyncSession(engine) as observer:
        assert await counts(observer) == (1, 1, 1)


@pytest.mark.parametrize("committed", [False, True])
async def test_commit_failure_never_acknowledges_and_retry_recovers(
    durable_api, monkeypatch, committed
):
    client, engine = durable_api
    original = AsyncSession.commit
    fail_once = True

    async def commit(db):
        nonlocal fail_once
        if fail_once:
            fail_once = False
            if committed:
                await original(db)
            raise SQLAlchemyError("private-connection-string")
        await original(db)

    monkeypatch.setattr(AsyncSession, "commit", commit)
    delivery = str(uuid4())
    response = await post_event(client, delivery=delivery)
    assert response.status_code == 503
    assert "private-connection-string" not in response.text
    async with AsyncSession(engine) as observer:
        assert await counts(observer) == ((1, 1, 1) if committed else (0, 0, 0))
    retry = await post_event(client, delivery=delivery)
    assert retry.status_code == 202
    assert retry.json()["duplicate"] is committed
    async with AsyncSession(engine) as observer:
        assert await counts(observer) == (1, 1, 1)


async def test_ignored_delivery_commit_is_visible_to_independent_session(durable_api):
    client, engine = durable_api
    response = await post_event(client, {}, event="ping")
    assert response.status_code == 200
    async with AsyncSession(engine) as observer:
        assert await counts(observer) == (1, 0, 0)


async def test_http_chunk_stream_stops_at_limit(webhook_api, review_db):
    reads = []

    async def content():
        for chunk in [b"x" * MAX_BODY_BYTES, b"x", b"must-not-read"]:
            reads.append(len(chunk))
            yield chunk

    response = await webhook_api.post(PREFIX, content=content(), headers=signed_headers(b"{}"))
    assert response.status_code == 413
    assert reads == [MAX_BODY_BYTES, 1]
    assert await counts(review_db) == (0, 0, 0)


async def test_job_api_cannot_reuse_ignored_delivery(webhook_api, review_db, owners):
    delivery = str(uuid4())
    assert (await post_event(webhook_api, {}, event="ping", delivery=delivery)).status_code == 200
    with pytest.raises(ReviewConflictError, match="ignored"):
        await enqueue_review(review_db, owners[0].id, job_request(delivery_id=delivery))
    assert await counts(review_db) == (1, 0, 0)


async def test_delivery_database_constraint_requires_ignored_reason(review_db):
    with pytest.raises(IntegrityError):
        async with review_db.begin_nested():
            review_db.add(
                ReviewDelivery(
                    delivery_id=str(uuid4()),
                    disposition="ignored",
                    event_type="ping",
                    action="",
                    payload_sha256="a" * 64,
                )
            )
            await review_db.flush()


async def test_migration_preserves_legacy_delivery_and_round_trips():
    async with disposable_database() as url:
        migrate(url, "upgrade", "0015")
        engine = create_async_engine(url)
        delivery_id = str(uuid4())
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                owner = User(email=f"{uuid4()}@migration.test")
                db.add(owner)
                await db.flush()
                await seed_review(db, owner)
                request = job_request()
                job_id = uuid4()
                await db.execute(
                    text(
                        "INSERT INTO review_jobs "
                        "(id,owner_id,installation_id,repo_id,pr_number,head_sha,"
                        "rules_version,provider,policy,max_attempts) "
                        "VALUES (:id,:owner,'301','401',7,:head,1,'anthropic',"
                        "CAST(:policy AS jsonb),1)"
                    ),
                    {
                        "id": job_id,
                        "owner": owner.id,
                        "head": "a" * 40,
                        "policy": json.dumps(request.policy.model_dump(mode="json")),
                    },
                )
                await db.execute(
                    text(
                        "INSERT INTO review_deliveries (delivery_id,job_id,owner_id,event_type,action) VALUES (:delivery,:job,:owner,'pull_request','opened')"
                    ),
                    {"delivery": delivery_id, "job": job_id, "owner": owner.id},
                )
                await db.commit()
            for operation, revision in [
                ("upgrade", "0016"),
                ("downgrade", "0015"),
                ("upgrade", "0016"),
            ]:
                await engine.dispose()  # Reconnect after out-of-process DDL.
                migrate(url, operation, revision)
                async with engine.connect() as conn:
                    row = (
                        await conn.execute(text("SELECT delivery_id,action FROM review_deliveries"))
                    ).one()
                    assert tuple(row) == (delivery_id, "opened")
                    columns = await conn.run_sync(
                        lambda sync: {
                            column["name"]
                            for column in inspect(sync).get_columns("review_deliveries")
                        }
                    )
                    assert ("disposition" in columns) is (revision == "0016")
            async with AsyncSession(engine) as db:
                row = await db.get(ReviewDelivery, delivery_id)
                assert row.disposition == "accepted" and row.payload_sha256 is None
                assert row.job_id == job_id and row.owner_id == owner.id
            async with engine.connect() as conn:
                diffs = await conn.run_sync(
                    lambda sync: compare_metadata(
                        MigrationContext.configure(
                            sync,
                            opts={
                                "include_object": lambda obj, name, kind, reflected, compare_to: (
                                    name == "review_deliveries"
                                    if kind == "table"
                                    else getattr(getattr(obj, "table", None), "name", None)
                                    == "review_deliveries"
                                )
                            },
                        ),
                        Base.metadata,
                    )
                )
                assert diffs == []
        finally:
            await engine.dispose()


async def test_migration_downgrade_refuses_to_delete_inbox_history():
    async with disposable_database() as url:
        migrate(url, "upgrade", "0016")
        engine = create_async_engine(url)
        try:
            async with AsyncSession(engine) as db:
                db.add(
                    ReviewDelivery(
                        delivery_id=str(uuid4()),
                        disposition="ignored",
                        event_type="ping",
                        action="",
                        ignore_reason="irrelevant_event",
                        payload_sha256="a" * 64,
                    )
                )
                await db.commit()
            with pytest.raises(pytest.fail.Exception, match="Cannot downgrade 0016"):
                migrate(url, "downgrade", "0015")
            async with engine.connect() as conn:
                assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == "0016"
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM review_deliveries WHERE disposition='ignored'")
                    )
                    == 1
                )
        finally:
            await engine.dispose()
