"""Slices 2–3: real disposable PostgreSQL, ASGI requests, no external transports."""

import asyncio
import socket
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi import FastAPI
from sqlalchemy import inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from plutolab_api.api.v1.router import api_router
from plutolab_api.core.security import create_access_token
from plutolab_api.db.base import Base
from plutolab_api.db.deps import get_db
from plutolab_api.models.agent import Agent
from plutolab_api.models.user import User
from plutolab_api.schemas.agent import AgentCreate, AgentReplace
from plutolab_api.services.agents import AgentConflictError, create_agent, replace_agent
from tests.test_agent_contracts import definition
from tests.test_review_domain import disposable_database, migrate
from tests.test_review_domain import owners as owners
from tests.test_review_domain import review_db as review_db
from tests.test_review_domain import review_engine as review_engine


@pytest.fixture(autouse=True)
def local_only(monkeypatch):
    original = socket.socket.connect

    def connect(sock, address):
        if (
            not isinstance(address, tuple)
            or address[0] not in {"127.0.0.1", "::1"}
            or address[1] != 5432
        ):
            raise AssertionError("Only loopback PostgreSQL is allowed")
        return original(sock, address)

    async def deny_http(*args, **kwargs):
        raise AssertionError("External HTTP forbidden in definition tests")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", deny_http)


@pytest_asyncio.fixture
async def agent_client(review_db: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")

    async def session():
        yield review_db

    app.dependency_overrides[get_db] = session
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


async def test_crud_versions_archive_and_private_response(agent_client, owners, review_db):
    headers = auth(owners[0])
    created = await agent_client.post("/api/v1/agents", json=definition(), headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["version"] == 1 and body["status"] == "active"
    assert not {"user_id", "owner_id", "api_key", "key_ciphertext"} & body.keys()
    path = f"/api/v1/agents/{body['id']}"
    assert (await agent_client.get(path, headers=headers)).json() == body
    updated = await agent_client.put(
        path, json=definition(name="编辑", expected_version=1), headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    stale = await agent_client.put(path, json=definition(expected_version=1), headers=headers)
    assert stale.status_code == 409
    assert (
        await agent_client.delete(path, params={"expected_version": 1}, headers=headers)
    ).status_code == 409
    assert (
        await agent_client.delete(path, params={"expected_version": 2}, headers=headers)
    ).status_code == 204
    assert (await agent_client.get(path, headers=headers)).status_code == 404
    assert (await agent_client.get("/api/v1/agents", headers=headers)).json() == {
        "items": [],
        "total": 0,
    }
    row = await review_db.scalar(select(Agent).where(Agent.user_id == owners[0].id))
    await review_db.refresh(row)
    assert row.status == "archived" and row.version == 3
    assert (
        await agent_client.put(path, json=definition(expected_version=3), headers=headers)
    ).status_code == 404


async def test_owner_isolation_and_missing_id(agent_client, owners):
    created = await agent_client.post("/api/v1/agents", json=definition(), headers=auth(owners[0]))
    assert created.status_code == 201
    for agent_id in [created.json()["id"], str(uuid4())]:
        path = f"/api/v1/agents/{agent_id}"
        headers = auth(owners[1])
        assert (await agent_client.get(path, headers=headers)).status_code == 404
        assert (
            await agent_client.put(path, json=definition(expected_version=1), headers=headers)
        ).status_code == 404
        assert (
            await agent_client.delete(path, params={"expected_version": 1}, headers=headers)
        ).status_code == 404
    assert (await agent_client.get("/api/v1/agents", headers=auth(owners[1]))).json()["total"] == 0


async def test_pagination(agent_client, owners):
    headers = auth(owners[0])
    for name in ["one", "two", "three"]:
        assert (
            await agent_client.post("/api/v1/agents", json=definition(name=name), headers=headers)
        ).status_code == 201
    first = (await agent_client.get("/api/v1/agents?limit=2", headers=headers)).json()
    last = (await agent_client.get("/api/v1/agents?limit=2&offset=2", headers=headers)).json()
    assert first["total"] == last["total"] == 3
    assert len(first["items"]) == 2 and len(last["items"]) == 1
    assert len({item["id"] for item in first["items"] + last["items"]}) == 3
    assert (await agent_client.get("/api/v1/agents?limit=101", headers=headers)).status_code == 422


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/api/v1/agents", None),
        ("POST", "/api/v1/agents", definition()),
        ("GET", f"/api/v1/agents/{uuid4()}", None),
        ("PUT", f"/api/v1/agents/{uuid4()}", definition(expected_version=1)),
        ("DELETE", f"/api/v1/agents/{uuid4()}?expected_version=1", None),
    ],
)
async def test_authentication_required(agent_client, method, path, body):
    response = await agent_client.request(method, path, json=body)
    assert response.status_code == 401


@pytest.mark.parametrize(
    "changes",
    [
        {"api_key": "DO_NOT_REFLECT"},
        {"owner_id": "DO_NOT_REFLECT"},
        {"model": "DO_NOT_REFLECT"},
        {"role_prompt": "DO_NOT_REFLECT" * 2000},
        {"tools": ["DO_NOT_REFLECT"]},
        {"provider": "DO_NOT_REFLECT"},
        {"DO_NOT_REFLECT": "value"},
    ],
)
async def test_invalid_requests_never_reflect_secrets(agent_client, owners, changes):
    response = await agent_client.post(
        "/api/v1/agents", json=definition(**changes), headers=auth(owners[0])
    )
    assert response.status_code == 422
    assert "DO_NOT_REFLECT" not in response.text


@pytest.mark.parametrize(
    "changes",
    [
        {"version": 0},
        {"status": "unknown"},
        {"name": ""},
        {"role_prompt": "x" * 16001},
        {"role_prompt": " " + "x" * 16000},
        {"provider": "other"},
        {"model": "other"},
        {"tools": ["shell"]},
        {"user_id": uuid4()},
    ],
)
async def test_database_constraints(review_db, owners, changes):
    row = Agent(user_id=owners[0].id, **AgentCreate.model_validate(definition()).model_dump())
    for key, value in changes.items():
        setattr(row, key, value)
    with pytest.raises(IntegrityError):
        async with review_db.begin_nested():
            review_db.add(row)
            await review_db.flush()


async def test_concurrent_replacements_only_one_wins(review_engine):
    async with AsyncSession(review_engine, expire_on_commit=False) as db:
        user = User(email=f"{uuid4()}@agent.test")
        db.add(user)
        await db.flush()
        row = await create_agent(db, user.id, AgentCreate.model_validate(definition()))
        agent_id, owner_id = row.id, user.id
        await db.commit()

    async def replace(name):
        async with AsyncSession(review_engine, expire_on_commit=False) as db:
            try:
                await replace_agent(
                    db,
                    owner_id,
                    agent_id,
                    AgentReplace.model_validate(definition(name=name, expected_version=1)),
                )
                await db.commit()
                return "success"
            except AgentConflictError:
                await db.rollback()
                return "conflict"

    assert sorted(await asyncio.gather(replace("first"), replace("second"))) == [
        "conflict",
        "success",
    ]
    async with AsyncSession(review_engine) as db:
        assert (await db.get(Agent, agent_id)).version == 2


async def test_version_overflow_rejected(agent_client, owners, review_db):
    row = await create_agent(review_db, owners[0].id, AgentCreate.model_validate(definition()))
    await review_db.execute(update(Agent).where(Agent.id == row.id).values(version=2_147_483_647))
    path = f"/api/v1/agents/{row.id}"
    response = await agent_client.put(
        path, json=definition(expected_version=2_147_483_647), headers=auth(owners[0])
    )
    assert response.status_code == 409


async def test_migration_round_trip_and_metadata():
    async with disposable_database() as url:
        migrate(url, "upgrade", "0019")
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("INSERT INTO users (email) VALUES ('sentinel@agent.test')"))
            migrate(url, "upgrade", "0021")

            def check(sync):
                assert "agents" in inspect(sync).get_table_names()
                ctx = MigrationContext.configure(
                    sync,
                    opts={
                        "include_object": lambda obj, name, kind, reflected, compare: (
                            kind != "table" or name == "agents"
                        ),
                        "compare_server_default": True,
                    },
                )
                assert compare_metadata(ctx, Base.metadata) == []
                assert {c["name"] for c in inspect(sync).get_check_constraints("agents")} == {
                    f"ck_agents_{name}"
                    for name in [
                        "version_positive",
                        "valid_status",
                        "name_length",
                        "description_length",
                        "prompt_length",
                        "model_catalog",
                        "registered_tools",
                    ]
                }

            async with engine.connect() as conn:
                await conn.run_sync(check)
            migrate(url, "downgrade", "0019")
            async with engine.connect() as conn:
                assert "agents" not in await conn.run_sync(
                    lambda sync: inspect(sync).get_table_names()
                )
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM users WHERE email='sentinel@agent.test'")
                    )
                    == 1
                )
            migrate(url, "upgrade", "0021")
            async with engine.connect() as conn:
                await conn.run_sync(check)
        finally:
            await engine.dispose()


async def test_registered_tool_owner_scope_and_storage(agent_client, owners, review_db):
    from plutolab_api.models.note import Note
    from plutolab_api.services.agent_tools import execute_tool

    review_db.add_all(
        [
            Note(user_id=owners[0].id, title="shared own", content="safe"),
            Note(user_id=owners[1].id, title="shared foreign", content="private"),
        ]
    )
    await review_db.flush()
    result = await execute_tool(
        "search_notes",
        {"query": "shared"},
        db=review_db,
        user_id=owners[0].id,
        enabled_tools=("search_notes",),
    )
    assert [item.title for item in result.items] == ["shared own"]
    response = await agent_client.post(
        "/api/v1/agents", json=definition(tools=["search_notes"]), headers=auth(owners[0])
    )
    assert response.status_code == 201
    assert response.json()["tools"] == ["search_notes"]


async def test_tool_migration_downgrade_protects_configuration():
    async with disposable_database() as url:
        migrate(url, "upgrade", "0020")
        migrate(url, "upgrade", "0021")
        migrate(url, "downgrade", "0020")
        migrate(url, "upgrade", "0021")
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                owner = await conn.scalar(
                    text("INSERT INTO users (email) VALUES ('tool@agent.test') RETURNING id")
                )
                await conn.execute(
                    text(
                        "INSERT INTO agents(user_id,name,role_prompt,provider,model,tools) VALUES (:owner,'n','r','openai','gpt-4o-mini','[\"search_notes\"]')"
                    ),
                    {"owner": owner},
                )
            with pytest.raises(pytest.fail.Exception, match="CheckViolationError"):
                migrate(url, "downgrade", "0020")
            async with engine.connect() as conn:
                assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == "0021"
                assert await conn.scalar(text("SELECT tools FROM agents")) == ["search_notes"]
        finally:
            await engine.dispose()
