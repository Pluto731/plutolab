"""Deterministic bounded-concurrency execution of a persisted run DAG."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from plutolab_api.models.agent_run import AgentRun, AgentRunNode
from plutolab_api.services.agent_execution import execute_node
from plutolab_api.services.agent_provider import TextProvider
from plutolab_api.services.agent_runs import finish_run, get_run, read_snapshot, record_run_event
from plutolab_api.services.workflow_graph import plan_layers


async def _skip_pending(
    db: AsyncSession, run_id: UUID, node_ids: set[str], *, cancelled: bool = False
) -> None:
    if not node_ids:
        return
    run = await db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
    rows = list(
        await db.scalars(
            select(AgentRunNode)
            .where(
                AgentRunNode.run_id == run_id,
                AgentRunNode.node_id.in_(node_ids),
                AgentRunNode.state == "pending",
            )
            .with_for_update()
        )
    )
    for row in rows:
        row.state = "cancelled" if cancelled else "skipped"
        row.error_code = "cancelled" if cancelled else "dependency_failed"
        row.finished_at = datetime.now(UTC)
        if run:
            await record_run_event(
                db, run, "node_skipped", row.state, node_id=row.node_id, summary=row.error_code
            )
    await db.commit()


async def execute_run(
    sessions: async_sessionmaker[AsyncSession],
    owner: UUID,
    run_id: UUID,
    provider: TextProvider,
    *,
    concurrency: int = 4,
    fail_fast: bool = True,
) -> str:
    """Run independent nodes in parallel; failed layers suppress all descendants.

    Each node receives a fresh session because execute_node commits its own state.
    A failed provider result is terminal and is never retried at scheduler level.
    """
    if type(concurrency) is not int or not 1 <= concurrency <= 8:
        raise ValueError("Concurrency must be between 1 and 8")
    async with sessions() as db:
        run = await get_run(db, owner, run_id)
        snapshot = read_snapshot(run)
    semaphore = asyncio.Semaphore(concurrency)
    failed = False
    for layer in plan_layers(snapshot.graph):
        async with sessions() as db:
            current = await get_run(db, owner, run_id)
            cancelled = current.cancel_requested
        if cancelled or (failed and fail_fast):
            async with sessions() as db:
                pending = set(
                    await db.scalars(
                        select(AgentRunNode.node_id).where(
                            AgentRunNode.run_id == run_id, AgentRunNode.state == "pending"
                        )
                    )
                )
                await _skip_pending(db, run_id, pending, cancelled=cancelled)
            break

        async def run_one(node_id: str) -> bool:
            async with semaphore, sessions() as db:
                node = await execute_node(db, owner, run_id, node_id, provider)
                return node.state == "succeeded"

        results = await asyncio.gather(*(run_one(node_id) for node_id in layer))
        if not all(results):
            failed = True
    async with sessions() as db:
        run = await finish_run(db, owner, run_id)
        await db.commit()
        return run.state
