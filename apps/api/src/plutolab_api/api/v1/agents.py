"""Owner-private definition API. No model calls, credentials or tool execution."""

from collections.abc import Callable, Coroutine
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.api.deps import CurrentUser
from plutolab_api.db.deps import get_db
from plutolab_api.schemas.agent import AgentCreate, AgentPage, AgentPublic, AgentReplace
from plutolab_api.services import agents


class DefinitionRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[None, None, Response]]:
        original = super().get_route_handler()

        async def handle(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError:
                # Never reflect a rejected prompt, API key or arbitrary field name/value.
                return JSONResponse(status_code=422, content={"detail": "Invalid Agent request"})
            except agents.AgentNotFoundError as exc:
                raise HTTPException(404, "Agent not found") from exc
            except agents.AgentConflictError as exc:
                raise HTTPException(409, "Agent version conflict; reload before retrying") from exc

        return handle


router = APIRouter(prefix="/agents", tags=["agents"], route_class=DefinitionRoute)
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=AgentPage)
async def list_agents(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> AgentPage:
    rows, total = await agents.list_agents(db, user.id, limit, offset)
    return AgentPage(items=[AgentPublic.model_validate(row) for row in rows], total=total)


@router.post("", response_model=AgentPublic, status_code=201)
async def create_agent(body: AgentCreate, user: CurrentUser, db: DbSession) -> AgentPublic:
    row = await agents.create_agent(db, user.id, body)
    result = AgentPublic.model_validate(row)
    await db.commit()
    return result


@router.get("/{agent_id}", response_model=AgentPublic)
async def get_agent(agent_id: UUID, user: CurrentUser, db: DbSession) -> AgentPublic:
    return AgentPublic.model_validate(await agents.get_agent(db, user.id, agent_id))


@router.put("/{agent_id}", response_model=AgentPublic)
async def replace_agent(
    agent_id: UUID,
    body: AgentReplace,
    user: CurrentUser,
    db: DbSession,
) -> AgentPublic:
    row = await agents.replace_agent(db, user.id, agent_id, body)
    result = AgentPublic.model_validate(row)
    await db.commit()
    return result


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: UUID,
    user: CurrentUser,
    db: DbSession,
    expected_version: Annotated[int, Query(ge=1, le=2_147_483_647)],
) -> Response:
    await agents.archive_agent(db, user.id, agent_id, expected_version)
    await db.commit()
    return Response(status_code=204)
