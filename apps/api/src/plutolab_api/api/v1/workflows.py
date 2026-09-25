"""Owner-private Workflow API with sanitized validation errors."""

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
from plutolab_api.schemas.workflow import (
    WorkflowCreate,
    WorkflowPage,
    WorkflowPublic,
    WorkflowReplace,
    WorkflowTemplateImport,
    WorkflowTemplatePage,
)
from plutolab_api.services import workflow_templates, workflows


class WorkflowRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[None, None, Response]]:
        original = super().get_route_handler()

        async def handle(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError:
                return JSONResponse(status_code=422, content={"detail": "Invalid Workflow request"})
            except workflows.WorkflowNotFoundError as exc:
                raise HTTPException(404, "Workflow not found") from exc
            except workflows.WorkflowConflictError as exc:
                raise HTTPException(409, "Workflow version conflict") from exc
            except workflows.WorkflowReferenceError as exc:
                raise HTTPException(422, "Agent references unavailable or outdated") from exc

        return handle


router = APIRouter(prefix="/workflows", tags=["workflows"], route_class=WorkflowRoute)
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=WorkflowPage)
async def list_workflows(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> WorkflowPage:
    items, total = await workflows.list_workflows(db, user.id, limit, offset)
    return WorkflowPage(items=items, total=total)


@router.post("", response_model=WorkflowPublic, status_code=201)
async def create_workflow(body: WorkflowCreate, user: CurrentUser, db: DbSession) -> WorkflowPublic:
    result = await workflows.create_workflow(db, user.id, body)
    await db.commit()
    return result


@router.get("/templates", response_model=WorkflowTemplatePage)
async def list_templates(user: CurrentUser) -> WorkflowTemplatePage:
    return WorkflowTemplatePage(items=workflow_templates.list_templates())


@router.post(
    "/templates/{slug}/versions/{version}/import",
    response_model=WorkflowPublic,
    status_code=201,
)
async def import_template(
    slug: str,
    version: int,
    body: WorkflowTemplateImport,
    user: CurrentUser,
    db: DbSession,
) -> WorkflowPublic:
    if not 1 <= version <= 2_147_483_647:
        raise HTTPException(404, "Workflow template not found")
    try:
        result = await workflow_templates.import_template(db, user.id, slug, version, body)
    except workflow_templates.TemplateNotFoundError as exc:
        raise HTTPException(404, "Workflow template not found") from exc
    except workflow_templates.TemplateToolsUnavailableError as exc:
        raise HTTPException(422, "Workflow template requires unavailable tools") from exc
    await db.commit()
    return result


@router.get("/{workflow_id}", response_model=WorkflowPublic)
async def get_workflow(workflow_id: UUID, user: CurrentUser, db: DbSession) -> WorkflowPublic:
    return await workflows.get_workflow(db, user.id, workflow_id)


@router.get("/{workflow_id}/versions/{version}", response_model=WorkflowPublic)
async def get_version(
    workflow_id: UUID, version: int, user: CurrentUser, db: DbSession
) -> WorkflowPublic:
    if version < 1 or version > 2_147_483_647:
        raise HTTPException(422, "Invalid version")
    return await workflows.get_workflow(db, user.id, workflow_id, version)


@router.put("/{workflow_id}", response_model=WorkflowPublic)
async def replace_workflow(
    workflow_id: UUID, body: WorkflowReplace, user: CurrentUser, db: DbSession
) -> WorkflowPublic:
    result = await workflows.replace_workflow(db, user.id, workflow_id, body)
    await db.commit()
    return result


@router.delete("/{workflow_id}", status_code=204)
async def archive_workflow(
    workflow_id: UUID,
    user: CurrentUser,
    db: DbSession,
    expected_version: Annotated[int, Query(ge=1, le=2_147_483_647)],
) -> Response:
    await workflows.archive_workflow(db, user.id, workflow_id, expected_version)
    await db.commit()
    return Response(status_code=204)
