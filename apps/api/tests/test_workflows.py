"""Real owner-scoped Workflow API, history, locking and migration acceptance."""

import asyncio
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from plutolab_api.db.base import Base
from plutolab_api.models.user import User
from plutolab_api.models.workflow import WorkflowRevision
from plutolab_api.schemas.agent import AgentCreate
from plutolab_api.schemas.workflow import WorkflowCreate, WorkflowReplace
from plutolab_api.services.agents import create_agent
from plutolab_api.services.workflows import WorkflowConflictError, create_workflow, replace_workflow
from tests.test_agent_contracts import definition
from tests.test_agents import agent_client as agent_client
from tests.test_agents import auth
from tests.test_agents import local_only as local_only
from tests.test_review_domain import disposable_database, migrate
from tests.test_review_domain import owners as owners
from tests.test_review_domain import review_db as review_db
from tests.test_review_domain import review_engine as review_engine


def body(agent_id, **changes):
    value = {
        "name": "研究流程",
        "graph": {
            "nodes": [{"id": "a", "agent_id": str(agent_id), "agent_version": 1}],
            "edges": [],
        },
        "layout": {"a": {"x": 10, "y": 20}},
    }
    value.update(changes)
    return value


async def seed(db, owner):
    return await create_agent(db, owner.id, AgentCreate.model_validate(definition()))


async def test_crud_history_archive(agent_client, owners, review_db):
    agent = await seed(review_db, owners[0])
    headers = auth(owners[0])
    r = await agent_client.post("/api/v1/workflows", json=body(agent.id), headers=headers)
    assert r.status_code == 201, r.text
    first = r.json()
    assert "user_id" not in first and first["version"] == 1
    path = f"/api/v1/workflows/{first['id']}"
    r = await agent_client.put(
        path, json=body(agent.id, expected_version=1, name="新版"), headers=headers
    )
    assert r.status_code == 200 and r.json()["version"] == 2
    assert (await agent_client.get(path + "/versions/1", headers=headers)).json() == first
    assert (
        await agent_client.put(path, json=body(agent.id, expected_version=1), headers=headers)
    ).status_code == 409
    page = (await agent_client.get("/api/v1/workflows?limit=1&offset=0", headers=headers)).json()
    assert page["total"] == 1 and page["items"][0]["name"] == "新版"
    assert (await agent_client.get("/api/v1/workflows?offset=1", headers=headers)).json()[
        "items"
    ] == []
    assert (
        await agent_client.delete(path + "?expected_version=1", headers=headers)
    ).status_code == 409
    assert (
        await agent_client.delete(path + "?expected_version=2", headers=headers)
    ).status_code == 204
    assert (await agent_client.get(path, headers=headers)).status_code == 404
    assert (await agent_client.get(path + "/versions/1", headers=headers)).json() == first
    assert (await agent_client.get(path + "/versions/3", headers=headers)).json()[
        "status"
    ] == "archived"
    assert (
        await agent_client.put(path, json=body(agent.id, expected_version=3), headers=headers)
    ).status_code == 404


async def test_owner_scope(agent_client, owners, review_db):
    agent = await seed(review_db, owners[0])
    r = await agent_client.post("/api/v1/workflows", json=body(agent.id), headers=auth(owners[0]))
    path = f"/api/v1/workflows/{r.json()['id']}"
    headers = auth(owners[1])
    for suffix in ("", "/versions/1"):
        assert (await agent_client.get(path + suffix, headers=headers)).status_code == 404
    assert (
        await agent_client.put(path, json=body(agent.id, expected_version=1), headers=headers)
    ).status_code == 404
    assert (
        await agent_client.delete(path + "?expected_version=1", headers=headers)
    ).status_code == 404
    assert (await agent_client.get("/api/v1/workflows", headers=headers)).json()["total"] == 0
    assert (
        await agent_client.post("/api/v1/workflows", json=body(agent.id), headers=headers)
    ).status_code == 422
    assert (await agent_client.get(path)).status_code == 401


@pytest.mark.parametrize("mode", ["missing", "stale", "archived"])
async def test_references(agent_client, owners, review_db, mode):
    agent = await seed(review_db, owners[0])
    headers = auth(owners[0])
    created = await agent_client.post("/api/v1/workflows", json=body(agent.id), headers=headers)
    path = f"/api/v1/workflows/{created.json()['id']}"
    if mode == "missing":
        agent_id = uuid4()
    else:
        agent_id = agent.id
        if mode == "archived":
            await agent_client.delete(
                f"/api/v1/agents/{agent.id}?expected_version=1", headers=headers
            )
        else:
            await agent_client.put(
                f"/api/v1/agents/{agent.id}", json=definition(expected_version=1), headers=headers
            )
    assert (
        await agent_client.post("/api/v1/workflows", json=body(agent_id), headers=headers)
    ).status_code == 422
    assert (
        await agent_client.put(path, json=body(agent_id, expected_version=1), headers=headers)
    ).status_code == 422
    history = (await agent_client.get(path + "/versions/1", headers=headers)).json()
    assert history["graph"]["nodes"][0]["agent_version"] == 1
    assert (
        await agent_client.delete(path + "?expected_version=1", headers=headers)
    ).status_code == 204


@pytest.mark.parametrize("mode", ["empty", "cycle", "layout", "secret", "version", "large_layout"])
async def test_invalid_requests(agent_client, owners, review_db, mode):
    agent = await seed(review_db, owners[0])
    value = body(agent.id)
    if mode == "empty":
        value["graph"]["nodes"] = []
    if mode == "cycle":
        value["graph"]["nodes"].append({"id": "b", "agent_id": str(agent.id), "agent_version": 1})
        value["graph"]["edges"] = [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]
    if mode == "layout":
        value["layout"]["unknown"] = {"x": 0, "y": 0}
    if mode == "secret":
        value["DO_NOT_REFLECT"] = "DO_NOT_REFLECT"
    if mode == "version":
        value["graph"]["nodes"][0]["agent_version"] = True
    if mode == "large_layout":
        value["layout"]["a"]["x"] = 10001
    r = await agent_client.post("/api/v1/workflows", json=value, headers=auth(owners[0]))
    assert r.status_code == 422
    assert "DO_NOT_REFLECT" not in r.text


async def test_concurrent_updates(review_engine):
    async with AsyncSession(review_engine, expire_on_commit=False) as db:
        owner = User(email=f"{uuid4()}@workflow.test")
        db.add(owner)
        await db.flush()
        agent = await seed(db, owner)
        workflow = await create_workflow(
            db, owner.id, WorkflowCreate.model_validate(body(agent.id))
        )
        owner_id, agent_id, workflow_id = owner.id, agent.id, workflow.id
        await db.commit()

    async def change(name):
        async with AsyncSession(review_engine, expire_on_commit=False) as db:
            try:
                await replace_workflow(
                    db,
                    owner_id,
                    workflow_id,
                    WorkflowReplace.model_validate(body(agent_id, expected_version=1, name=name)),
                )
                await db.commit()
                return "ok"
            except WorkflowConflictError:
                await db.rollback()
                return "conflict"

    assert sorted(await asyncio.gather(change("one"), change("two"))) == ["conflict", "ok"]
    async with AsyncSession(review_engine) as db:
        versions = await db.scalars(
            select(WorkflowRevision.version)
            .where(WorkflowRevision.workflow_id == workflow_id)
            .order_by(WorkflowRevision.version)
        )
        assert list(versions) == [1, 2]


async def test_migration_metadata_and_immutability():
    async with disposable_database() as url:
        migrate(url, "upgrade", "0021")
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("INSERT INTO users(email) VALUES ('sentinel@workflow.test')")
                )
            migrate(url, "upgrade", "0022")

            def check(sync):
                ctx = MigrationContext.configure(
                    sync,
                    opts={
                        "include_object": lambda obj, name, kind, reflected, compare: (
                            kind != "table" or name in {"workflows", "workflow_revisions"}
                        ),
                        "compare_server_default": True,
                    },
                )
                assert compare_metadata(ctx, Base.metadata) == []

            async with engine.connect() as conn:
                await conn.run_sync(check)
            async with AsyncSession(engine, expire_on_commit=False) as db:
                owner = await db.scalar(select(User).where(User.email == "sentinel@workflow.test"))
                agent = await seed(db, owner)
                workflow = await create_workflow(
                    db, owner.id, WorkflowCreate.model_validate(body(agent.id))
                )
                await db.commit()
                with pytest.raises(DBAPIError, match="immutable"):
                    async with db.begin_nested():
                        await db.execute(
                            text(
                                "UPDATE workflow_revisions SET name='tampered' WHERE workflow_id=:id"
                            ),
                            {"id": workflow.id},
                        )
            migrate(url, "downgrade", "0021")
            async with engine.connect() as conn:
                assert "workflows" not in await conn.run_sync(
                    lambda sync: inspect(sync).get_table_names()
                )
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM users WHERE email='sentinel@workflow.test'")
                    )
                    == 1
                )
            migrate(url, "upgrade", "0022")
            async with engine.connect() as conn:
                await conn.run_sync(check)
        finally:
            await engine.dispose()


async def test_save_locks_agent_until_commit(review_engine):
    from plutolab_api.services.agents import archive_agent

    async with AsyncSession(review_engine, expire_on_commit=False) as setup:
        owner = User(email=f"{uuid4()}@workflow-lock.test")
        setup.add(owner)
        await setup.flush()
        agent = await seed(setup, owner)
        owner_id, agent_id = owner.id, agent.id
        await setup.commit()
    async with AsyncSession(review_engine, expire_on_commit=False) as saving:
        await create_workflow(saving, owner_id, WorkflowCreate.model_validate(body(agent_id)))
        async with AsyncSession(review_engine, expire_on_commit=False) as archiving:
            await archiving.execute(text("SET LOCAL lock_timeout = '100ms'"))
            with pytest.raises(DBAPIError, match="lock timeout"):
                await archive_agent(archiving, owner_id, agent_id, 1)
            await archiving.rollback()
        await saving.commit()
    async with AsyncSession(review_engine, expire_on_commit=False) as archiving:
        await archive_agent(archiving, owner_id, agent_id, 1)
        await archiving.commit()


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "offset=10001"])
async def test_pagination_bounds(agent_client, owners, query):
    response = await agent_client.get(f"/api/v1/workflows?{query}", headers=auth(owners[0]))
    assert response.status_code == 422


async def test_missing_history_and_version_overflow(agent_client, owners, review_db):
    agent = await seed(review_db, owners[0])
    headers = auth(owners[0])
    response = await agent_client.post("/api/v1/workflows", json=body(agent.id), headers=headers)
    workflow_id = response.json()["id"]
    path = f"/api/v1/workflows/{workflow_id}"
    assert (await agent_client.get(path + "/versions/99", headers=headers)).status_code == 404
    assert (await agent_client.get(path + "/versions/0", headers=headers)).status_code == 422
    await review_db.execute(
        text("UPDATE workflows SET version=2147483647 WHERE id=:id"), {"id": workflow_id}
    )
    assert (
        await agent_client.put(
            path, json=body(agent.id, expected_version=2147483647), headers=headers
        )
    ).status_code == 409
    assert (
        await agent_client.delete(path + "?expected_version=2147483647", headers=headers)
    ).status_code == 409
