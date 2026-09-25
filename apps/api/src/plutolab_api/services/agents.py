"""Agent CRUD with owner scoping and atomic optimistic concurrency."""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.models.agent import Agent
from plutolab_api.schemas.agent import AgentCreate, AgentReplace


class AgentNotFoundError(Exception):
    pass


class AgentConflictError(Exception):
    pass


async def get_agent(db: AsyncSession, owner: UUID, agent_id: UUID) -> Agent:
    agent = await db.scalar(
        select(Agent).where(Agent.id == agent_id, Agent.user_id == owner, Agent.status == "active")
    )
    if agent is None:
        raise AgentNotFoundError
    return agent


async def list_agents(
    db: AsyncSession, owner: UUID, limit: int, offset: int
) -> tuple[list[Agent], int]:
    filters = (Agent.user_id == owner, Agent.status == "active")
    total = await db.scalar(select(func.count()).select_from(Agent).where(*filters))
    rows = await db.scalars(
        select(Agent)
        .where(*filters)
        .order_by(Agent.created_at.desc(), Agent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total or 0


async def create_agent(db: AsyncSession, owner: UUID, body: AgentCreate) -> Agent:
    agent = Agent(user_id=owner, **body.model_dump())
    db.add(agent)
    await db.flush()
    return agent


async def replace_agent(db: AsyncSession, owner: UUID, agent_id: UUID, body: AgentReplace) -> Agent:
    await get_agent(db, owner, agent_id)
    row = await db.scalar(
        update(Agent)
        .where(
            Agent.id == agent_id,
            Agent.user_id == owner,
            Agent.status == "active",
            Agent.version == body.expected_version,
            Agent.version < 2_147_483_647,
        )
        .values(
            **body.model_dump(exclude={"expected_version"}),
            version=Agent.version + 1,
            updated_at=func.now(),
        )
        .returning(Agent)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise AgentConflictError
    return row


async def archive_agent(
    db: AsyncSession, owner: UUID, agent_id: UUID, expected_version: int
) -> None:
    await get_agent(db, owner, agent_id)
    result = await db.scalar(
        update(Agent)
        .where(
            Agent.id == agent_id,
            Agent.user_id == owner,
            Agent.status == "active",
            Agent.version == expected_version,
            Agent.version < 2_147_483_647,
        )
        .values(status="archived", version=Agent.version + 1, updated_at=func.now())
        .returning(Agent.id)
    )
    if result is None:
        raise AgentConflictError
