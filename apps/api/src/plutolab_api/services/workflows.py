"""Transactional Workflow versions; validate and lock referenced Agent definitions."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.models.agent import Agent
from plutolab_api.models.workflow import Workflow, WorkflowRevision
from plutolab_api.schemas.workflow import WorkflowCreate, WorkflowPublic, WorkflowReplace


class WorkflowNotFoundError(Exception):
    pass


class WorkflowConflictError(Exception):
    pass


class WorkflowReferenceError(Exception):
    pass


async def _head(
    db: AsyncSession, owner: UUID, workflow_id: UUID, *, lock: bool = False, archived: bool = False
) -> Workflow:
    stmt = select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == owner)
    if not archived:
        stmt = stmt.where(Workflow.status == "ready")
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    head = await db.scalar(stmt)
    if head is None:
        raise WorkflowNotFoundError
    return head


async def validate_references(db: AsyncSession, owner: UUID, body: WorkflowCreate) -> None:
    ids = {node.agent_id for node in body.graph.nodes}
    # SHARE locks serialize with concurrent Agent replacement/archive until commit.
    rows = await db.scalars(
        select(Agent)
        .where(Agent.id.in_(ids), Agent.user_id == owner, Agent.status == "active")
        .order_by(Agent.id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    versions = {row.id: row.version for row in rows}
    if any(versions.get(node.agent_id) != node.agent_version for node in body.graph.nodes):
        raise WorkflowReferenceError


def public(head: Workflow, revision: WorkflowRevision) -> WorkflowPublic:
    return WorkflowPublic(
        id=head.id,
        version=revision.version,
        status=revision.status,
        name=revision.name,
        description=revision.description,
        graph=revision.graph,
        layout=revision.layout,
        created_at=head.created_at,
        updated_at=revision.created_at,
    )


async def get_workflow(
    db: AsyncSession, owner: UUID, workflow_id: UUID, version: int | None = None
) -> WorkflowPublic:
    head = await _head(db, owner, workflow_id, archived=version is not None)
    revision = await db.get(
        WorkflowRevision, (workflow_id, version if version is not None else head.version)
    )
    if revision is None:
        raise WorkflowNotFoundError
    return public(head, revision)


async def list_workflows(
    db: AsyncSession, owner: UUID, limit: int, offset: int
) -> tuple[list[WorkflowPublic], int]:
    filters = (Workflow.user_id == owner, Workflow.status == "ready")
    total = await db.scalar(select(func.count()).select_from(Workflow).where(*filters))
    rows = await db.execute(
        select(Workflow, WorkflowRevision)
        .join(
            WorkflowRevision,
            (WorkflowRevision.workflow_id == Workflow.id)
            & (WorkflowRevision.version == Workflow.version),
        )
        .where(*filters)
        .order_by(Workflow.created_at.desc(), Workflow.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [public(head, revision) for head, revision in rows], total or 0


async def _append(db: AsyncSession, head: Workflow, body: WorkflowCreate) -> WorkflowPublic:
    revision = WorkflowRevision(
        workflow_id=head.id,
        version=head.version,
        status=head.status,
        **body.model_dump(mode="json"),
    )
    db.add(revision)
    await db.flush()
    return public(head, revision)


async def create_workflow(db: AsyncSession, owner: UUID, body: WorkflowCreate) -> WorkflowPublic:
    body = WorkflowCreate.model_validate(body.model_dump())
    await validate_references(db, owner, body)
    head = Workflow(user_id=owner)
    db.add(head)
    await db.flush()
    return await _append(db, head, body)


async def replace_workflow(
    db: AsyncSession, owner: UUID, workflow_id: UUID, body: WorkflowReplace
) -> WorkflowPublic:
    body = WorkflowReplace.model_validate(body.model_dump())
    head = await _head(db, owner, workflow_id, lock=True)
    if head.version != body.expected_version or head.version == 2_147_483_647:
        raise WorkflowConflictError
    definition = WorkflowCreate.model_validate(body.model_dump(exclude={"expected_version"}))
    await validate_references(db, owner, definition)
    head.version += 1
    head.updated_at = func.now()
    return await _append(db, head, definition)


async def archive_workflow(
    db: AsyncSession, owner: UUID, workflow_id: UUID, expected_version: int
) -> None:
    head = await _head(db, owner, workflow_id, lock=True)
    if head.version != expected_version or head.version == 2_147_483_647:
        raise WorkflowConflictError
    previous = await db.get(WorkflowRevision, (workflow_id, head.version))
    if previous is None:
        raise WorkflowNotFoundError
    body = WorkflowCreate(
        name=previous.name,
        description=previous.description,
        graph=previous.graph,
        layout=previous.layout,
    )
    head.version += 1
    head.status = "archived"
    head.updated_at = func.now()
    # Archiving does not require currently-valid Agent refs; it preserves history.
    await _append(db, head, body)
