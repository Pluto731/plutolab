"""Slice 9 persistence acceptance on disposable local PostgreSQL."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from plutolab_api.core.crypto import decrypt
from plutolab_api.db.base import Base
from plutolab_api.models.agent_run import AgentRunNode
from plutolab_api.models.user import User
from plutolab_api.schemas.agent import AgentCreate, AgentReplace, ExecutionBudget, ExecutionPolicy
from plutolab_api.schemas.agent_run import RunCreate
from plutolab_api.schemas.workflow import WorkflowCreate, WorkflowReplace
from plutolab_api.services.agent_runs import (
    RunConflictError,
    RunNotFoundError,
    create_run,
    get_run,
    purge_expired_runs,
    read_snapshot,
    start_run,
)
from plutolab_api.services.agents import create_agent, replace_agent
from plutolab_api.services.workflows import (
    WorkflowReferenceError,
    create_workflow,
    replace_workflow,
)
from tests.test_agents import local_only as local_only
from tests.test_review_domain import disposable_database, migrate
from tests.test_review_domain import owners as owners
from tests.test_review_domain import review_db as review_db
from tests.test_review_domain import review_engine as review_engine


async def setup_run(db, owner, *, tools=(), key=True, nodes=("a",), edges=(), budget=None):
    from plutolab_api.core.crypto import encrypt
    from plutolab_api.models.user_api_key import UserApiKey

    agent = await create_agent(
        db,
        owner.id,
        AgentCreate(
            name="researcher", model="gpt-4o-mini", role_prompt="PRIVATE_PROMPT", tools=list(tools)
        ),
    )
    graph = {
        "nodes": [{"id": n, "agent_id": str(agent.id), "agent_version": 1} for n in nodes],
        "edges": [{"source": a, "target": b} for a, b in edges],
    }
    workflow = await create_workflow(db, owner.id, WorkflowCreate(name="flow", graph=graph))
    if key:
        db.add(
            UserApiKey(
                user_id=owner.id,
                provider="openai",
                key_ciphertext=encrypt("fixture-provider-key-not-secret"),
                key_preview="test",
            )
        )
        await db.flush()
    run = await create_run(
        db,
        owner.id,
        workflow.id,
        RunCreate(
            workflow_version=1,
            text="PRIVATE_INPUT",
            policy=ExecutionPolicy(budget=budget or ExecutionBudget()),
        ),
    )
    return run, agent, workflow


async def test_snapshot_stable_after_definition_changes(review_db, owners):
    run, agent, workflow = await setup_run(review_db, owners[0])
    before = run.snapshot_ciphertext
    assert b"PRIVATE_PROMPT" not in before and b"PRIVATE_INPUT" not in before
    assert "fixture-provider-key" not in decrypt(before)
    await replace_agent(
        review_db,
        owners[0].id,
        agent.id,
        AgentReplace(
            name="changed", model="gpt-4o-mini", role_prompt="NEW_PROMPT", expected_version=1
        ),
    )
    with pytest.raises(WorkflowReferenceError):
        await create_run(
            review_db, owners[0].id, workflow.id, RunCreate(workflow_version=1, text="x")
        )
    graph = workflow.graph.model_dump(mode="json")
    graph["nodes"][0]["agent_version"] = 2
    await replace_workflow(
        review_db,
        owners[0].id,
        workflow.id,
        WorkflowReplace(name="changed", graph=graph, expected_version=1),
    )
    assert read_snapshot(run).agents["a"].role_prompt == "PRIVATE_PROMPT"
    assert run.snapshot_ciphertext == before
    assert read_snapshot(run).price.catalog == "openai-text-2026-09-24"
    with pytest.raises(RunConflictError):
        await create_run(
            review_db, owners[0].id, workflow.id, RunCreate(workflow_version=1, text="x")
        )


async def test_owner_scope_and_retention(review_db, owners):
    first, _, workflow = await setup_run(review_db, owners[0])
    second, _, _ = await setup_run(review_db, owners[1])
    with pytest.raises(RunNotFoundError):
        await get_run(review_db, owners[1].id, first.id)
    with pytest.raises(RunNotFoundError):
        await create_run(
            review_db, owners[1].id, workflow.id, RunCreate(workflow_version=1, text="x")
        )
    assert 29 <= (first.expires_at - datetime.now(UTC)).days <= 30
    assert await purge_expired_runs(review_db, owners[0].id) == 0
    assert (
        await purge_expired_runs(review_db, owners[0].id, datetime.now(UTC) + timedelta(days=31))
        == 1
    )
    assert (
        await review_db.scalar(select(AgentRunNode).where(AgentRunNode.run_id == first.id)) is None
    )
    assert (await get_run(review_db, owners[1].id, second.id)).id == second.id


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE agent_runs SET snapshot_ciphertext=decode('00','hex') WHERE id=:id",
        "UPDATE agent_runs SET state='succeeded', finished_at=NOW() WHERE id=:id",
        "UPDATE agent_runs SET charged_tokens=token_limit+1 WHERE id=:id",
        "UPDATE agent_run_nodes SET state='succeeded',finished_at=NOW() WHERE run_id=:id",
        "UPDATE agent_run_nodes SET error_code='SECRET_DATA' WHERE run_id=:id",
    ],
)
async def test_database_guards(review_db, owners, sql):
    run, _, _ = await setup_run(review_db, owners[0])
    with pytest.raises(DBAPIError):
        async with review_db.begin_nested():
            await review_db.execute(text(sql), {"id": run.id})


async def test_terminal_run_cannot_restart(review_db, owners):
    run, _, _ = await setup_run(review_db, owners[0])
    await start_run(review_db, owners[0].id, run.id)
    with pytest.raises(RunConflictError):
        await start_run(review_db, owners[0].id, run.id)
    await review_db.execute(
        text("UPDATE agent_runs SET state='cancelled',finished_at=NOW() WHERE id=:id"),
        {"id": run.id},
    )
    with pytest.raises(DBAPIError, match="terminal"):
        async with review_db.begin_nested():
            await review_db.execute(
                text("UPDATE agent_runs SET state='running',finished_at=NULL WHERE id=:id"),
                {"id": run.id},
            )


async def test_migration_roundtrip_and_metadata():
    async with disposable_database() as url:
        migrate(url, "upgrade", "0022")
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("INSERT INTO users(email) VALUES ('sentinel@run.test')"))
            migrate(url, "upgrade", "0025")

            def check(sync):
                ctx = MigrationContext.configure(
                    sync,
                    opts={
                        "include_object": lambda obj, name, kind, reflected, compare: (
                            kind != "table"
                            or name
                            in {
                                "agent_runs",
                                "agent_run_nodes",
                                "agent_run_outbox",
                                "agent_run_events",
                            }
                        ),
                        "compare_server_default": True,
                    },
                )
                assert compare_metadata(ctx, Base.metadata) == []

            async with engine.connect() as conn:
                await conn.run_sync(check)
            async with AsyncSession(engine, expire_on_commit=False) as db:
                owner = await db.scalar(select(User).where(User.email == "sentinel@run.test"))
                run, _, _ = await setup_run(db, owner)
                await db.commit()
                assert read_snapshot(run).text == "PRIVATE_INPUT"
            migrate(url, "downgrade", "0022")
            async with engine.connect() as conn:
                assert "agent_runs" not in await conn.run_sync(
                    lambda sync: inspect(sync).get_table_names()
                )
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM users WHERE email='sentinel@run.test'")
                    )
                    == 1
                )
            migrate(url, "upgrade", "0025")
            async with engine.connect() as conn:
                await conn.run_sync(check)
        finally:
            await engine.dispose()


def test_unknown_pricing_or_forged_owner_is_rejected():
    from pydantic import ValidationError

    from plutolab_api.schemas.agent_run import PriceCard

    with pytest.raises(ValidationError):
        PriceCard.model_validate({"catalog": "unknown-price-table"})
    with pytest.raises(ValidationError):
        RunCreate.model_validate({"workflow_version": 1, "text": "x", "user_id": str(uuid4())})
