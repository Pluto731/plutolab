"""Owner-scoped snapshot creation and lifecycle primitives, no public run API yet."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.core.crypto import decrypt, encrypt
from plutolab_api.models.agent import Agent
from plutolab_api.models.agent_run import AgentRun, AgentRunEvent, AgentRunNode, AgentRunOutbox
from plutolab_api.models.workflow import Workflow, WorkflowRevision
from plutolab_api.schemas.agent_run import AgentSnapshot, RunCreate, RunSnapshot
from plutolab_api.schemas.workflow import WorkflowCreate
from plutolab_api.services.workflows import validate_references


class RunNotFoundError(Exception):
    pass


class RunConflictError(Exception):
    pass


async def get_run(db: AsyncSession, owner: UUID, run_id: UUID, *, lock: bool = False) -> AgentRun:
    stmt = select(AgentRun).where(
        AgentRun.id == run_id, AgentRun.user_id == owner, AgentRun.expires_at > datetime.now(UTC)
    )
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    result = await db.scalar(stmt)
    if result is None:
        raise RunNotFoundError
    return result


def read_snapshot(run: AgentRun) -> RunSnapshot:
    return RunSnapshot.model_validate_json(decrypt(run.snapshot_ciphertext))


async def create_run(
    db: AsyncSession,
    owner: UUID,
    workflow_id: UUID,
    body: RunCreate,
    *,
    idempotency_key: str | None = None,
) -> AgentRun:
    body = RunCreate.model_validate(body.model_dump())
    if idempotency_key is not None:
        if not 1 <= len(idempotency_key) <= 128:
            raise RunConflictError
        await db.scalar(
            select(
                func.pg_advisory_xact_lock(func.hashtextextended(f"{owner}:{idempotency_key}", 0))
            )
        )
        fingerprint = sha256(f"{workflow_id}:{body.model_dump_json()}".encode()).hexdigest()
        existing = await db.scalar(
            select(AgentRun).where(
                AgentRun.user_id == owner, AgentRun.idempotency_key == idempotency_key
            )
        )
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise RunConflictError
            return existing
    else:
        fingerprint = None
    head = await db.scalar(
        select(Workflow)
        .where(Workflow.id == workflow_id, Workflow.user_id == owner, Workflow.status == "ready")
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    if head is None:
        raise RunNotFoundError
    if head.version != body.workflow_version:
        raise RunConflictError
    revision = await db.get(WorkflowRevision, (workflow_id, head.version))
    if revision is None:
        raise RunNotFoundError
    definition = WorkflowCreate(
        name=revision.name,
        description=revision.description,
        graph=revision.graph,
        layout=revision.layout,
    )
    await validate_references(db, owner, definition)
    rows = await db.scalars(
        select(Agent).where(
            Agent.user_id == owner, Agent.id.in_({n.agent_id for n in definition.graph.nodes})
        )
    )
    agents = {
        row.id: AgentSnapshot(
            id=row.id,
            version=row.version,
            name=row.name,
            description=row.description,
            role_prompt=row.role_prompt,
            provider=row.provider,
            model=row.model,
            tools=row.tools,
        )
        for row in rows
    }
    snapshot = RunSnapshot(
        graph=definition.graph,
        agents={n.id: agents[n.agent_id] for n in definition.graph.nodes},
        text=body.text,
        policy=body.policy,
    )
    run = AgentRun(
        user_id=owner,
        workflow_id=workflow_id,
        workflow_version=head.version,
        snapshot_ciphertext=encrypt(snapshot.model_dump_json()),
        token_limit=body.policy.budget.max_tokens,
        cost_limit=body.policy.budget.max_cost_microusd,
        expires_at=datetime.now(UTC) + timedelta(days=30),
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    db.add(run)
    await db.flush()
    db.add(AgentRunOutbox(run_id=run.id))
    db.add_all(AgentRunNode(run_id=run.id, node_id=node.id) for node in snapshot.graph.nodes)
    await db.flush()
    return run


async def start_run(db: AsyncSession, owner: UUID, run_id: UUID) -> AgentRun:
    run = await get_run(db, owner, run_id, lock=True)
    if run.state != "pending":
        raise RunConflictError
    run.state = "running"
    run.started_at = datetime.now(UTC)
    await record_run_event(db, run, "run_started", "running")
    await db.flush()
    return run


async def finish_run(db: AsyncSession, owner: UUID, run_id: UUID) -> AgentRun:
    run = await get_run(db, owner, run_id, lock=True)
    if run.state != "running" or run.reserved_tokens or run.reserved_cost:
        raise RunConflictError
    nodes = list(await db.scalars(select(AgentRunNode).where(AgentRunNode.run_id == run.id)))
    if not nodes or any(n.state in {"pending", "running"} for n in nodes):
        raise RunConflictError
    successes = sum(n.state == "succeeded" for n in nodes)
    run.state = (
        "cancelled"
        if run.cancel_requested
        else "succeeded"
        if successes == len(nodes)
        else "partial"
        if successes
        else "failed"
    )
    run.finished_at = datetime.now(UTC)
    run.checkpoint = {"completed_node_ids": sorted(n.node_id for n in nodes)}
    run.checkpoint_version += 1
    await record_run_event(db, run, "run_finished", run.state)
    await db.flush()
    return run


async def record_run_event(
    db: AsyncSession,
    run: AgentRun,
    event_type: str,
    state: str,
    *,
    node_id: str | None = None,
    summary: str | None = None,
) -> AgentRunEvent:
    run.event_sequence += 1
    event = AgentRunEvent(
        run_id=run.id,
        sequence=run.event_sequence,
        event_type=event_type,
        node_id=node_id,
        state=state,
        summary=summary,
    )
    db.add(event)
    # A graph has at most 32 nodes; 512 events is ample while keeping replay storage bounded.
    if run.event_sequence > 512:
        await db.execute(
            delete(AgentRunEvent).where(
                AgentRunEvent.run_id == run.id,
                AgentRunEvent.sequence <= run.event_sequence - 512,
            )
        )
    await db.flush()
    return event


async def cancel_run(db: AsyncSession, owner: UUID, run_id: UUID) -> AgentRun:
    run = await get_run(db, owner, run_id, lock=True)
    if run.state not in {"pending", "running"}:
        return run
    if run.state == "running":
        if not run.cancel_requested:
            run.cancel_requested = True
            await record_run_event(db, run, "run_cancel_requested", "running")
        await db.flush()
        return run
    now = datetime.now(UTC)
    nodes = list(
        await db.scalars(
            select(AgentRunNode)
            .where(AgentRunNode.run_id == run.id, AgentRunNode.state == "pending")
            .with_for_update()
        )
    )
    for node in nodes:
        node.state, node.error_code, node.finished_at = "cancelled", "cancelled", now
        await record_run_event(db, run, "node_skipped", "cancelled", node_id=node.node_id)
    run.cancel_requested = True
    await record_run_event(db, run, "run_cancel_requested", "cancelled")
    outbox = await db.get(AgentRunOutbox, run.id, with_for_update=True)
    if outbox and outbox.status != "running":
        outbox.status, outbox.claim_token, outbox.claim_until = "failed", None, None
        outbox.updated_at = now
    await record_run_event(db, run, "run_finished", "cancelled")
    run.state, run.finished_at = "cancelled", now
    await db.flush()
    return run


async def rerun_snapshot(
    db: AsyncSession,
    owner: UUID,
    run_id: UUID,
    *,
    idempotency_key: str | None = None,
) -> AgentRun:
    source = await get_run(db, owner, run_id)
    fingerprint = sha256(f"snapshot:{run_id}".encode()).hexdigest()
    if idempotency_key:
        await db.scalar(
            select(
                func.pg_advisory_xact_lock(func.hashtextextended(f"{owner}:{idempotency_key}", 0))
            )
        )
        existing = await db.scalar(
            select(AgentRun).where(
                AgentRun.user_id == owner, AgentRun.idempotency_key == idempotency_key
            )
        )
        if existing:
            if existing.request_fingerprint != fingerprint:
                raise RunConflictError
            return existing
    snapshot = read_snapshot(source)
    run = AgentRun(
        user_id=owner,
        workflow_id=source.workflow_id,
        workflow_version=source.workflow_version,
        snapshot_ciphertext=source.snapshot_ciphertext,
        token_limit=source.token_limit,
        cost_limit=source.cost_limit,
        expires_at=datetime.now(UTC) + timedelta(days=30),
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint if idempotency_key else None,
    )
    db.add(run)
    await db.flush()
    db.add(AgentRunOutbox(run_id=run.id))
    db.add_all(AgentRunNode(run_id=run.id, node_id=node.id) for node in snapshot.graph.nodes)
    await db.flush()
    return run


async def rerun_latest(
    db: AsyncSession, owner: UUID, run_id: UUID, *, idempotency_key: str | None = None
) -> AgentRun:
    source = await get_run(db, owner, run_id)
    snapshot = read_snapshot(source)
    head = await db.scalar(
        select(Workflow).where(
            Workflow.id == source.workflow_id,
            Workflow.user_id == owner,
            Workflow.status == "ready",
        )
    )
    if head is None:
        raise RunNotFoundError
    derived_key = (
        sha256(f"latest:{run_id}:{idempotency_key}".encode()).hexdigest()
        if idempotency_key
        else None
    )
    return await create_run(
        db,
        owner,
        source.workflow_id,
        RunCreate(workflow_version=head.version, text=snapshot.text, policy=snapshot.policy),
        idempotency_key=derived_key,
    )


async def list_runs(
    db: AsyncSession, owner: UUID, *, limit: int = 20, offset: int = 0
) -> tuple[list[AgentRun], int]:
    condition = (AgentRun.user_id == owner) & (AgentRun.expires_at > datetime.now(UTC))
    total = await db.scalar(select(func.count()).select_from(AgentRun).where(condition)) or 0
    rows = list(
        await db.scalars(
            select(AgentRun)
            .where(condition)
            .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return rows, total


async def read_run_events(
    db: AsyncSession, owner: UUID, run_id: UUID, *, after: int = 0, limit: int = 64
) -> tuple[AgentRun, list[AgentRunEvent], int]:
    run = await get_run(db, owner, run_id)
    oldest = await db.scalar(
        select(func.min(AgentRunEvent.sequence)).where(AgentRunEvent.run_id == run.id)
    )
    rows = list(
        await db.scalars(
            select(AgentRunEvent)
            .where(AgentRunEvent.run_id == run.id, AgentRunEvent.sequence > after)
            .order_by(AgentRunEvent.sequence)
            .limit(limit)
        )
    )
    return run, rows, oldest or run.event_sequence + 1


async def purge_expired_runs(db: AsyncSession, owner: UUID, now: datetime | None = None) -> int:
    # Internal retention primitive only; no scheduler or cleanup endpoint in this slice.
    result = await db.execute(
        delete(AgentRun).where(
            AgentRun.user_id == owner, AgentRun.expires_at <= (now or datetime.now(UTC))
        )
    )
    return result.rowcount
