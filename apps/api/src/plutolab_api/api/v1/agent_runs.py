"""Owner-scoped Agent Run lifecycle, history and bounded SSE replay."""

import asyncio
import re
import time
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRoute
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from plutolab_api.api.deps import CurrentUser
from plutolab_api.core.crypto import decrypt
from plutolab_api.db.deps import get_db
from plutolab_api.db.session import AsyncSessionLocal
from plutolab_api.models.agent_run import AgentRun, AgentRunNode
from plutolab_api.schemas.agent_run import (
    NodeResult,
    RunCreate,
    RunDetail,
    RunEventPage,
    RunEventView,
    RunNodeView,
    RunPage,
    RunRerun,
    RunSummary,
)
from plutolab_api.services import agent_runs


class RunRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handle(request: Request):
            try:
                return await original(request)
            except RequestValidationError as exc:
                raise HTTPException(422, "Invalid Run request") from exc

        return handle


router = APIRouter(tags=["agent-runs"], route_class=RunRoute)
DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_run_sessions() -> async_sessionmaker[AsyncSession]:
    return AsyncSessionLocal


RunSessions = Annotated[async_sessionmaker[AsyncSession], Depends(get_run_sessions)]
IdempotencyHeader = Annotated[
    str | None,
    Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"),
]


def _summary(run: AgentRun) -> RunSummary:
    return RunSummary(
        id=run.id,
        workflow_id=run.workflow_id,
        workflow_version=run.workflow_version,
        state=run.state,
        created_at=run.created_at,
        finished_at=run.finished_at,
    )


def _event_view(event) -> RunEventView:
    return RunEventView(
        sequence=event.sequence,
        event_type=event.event_type,
        node_id=event.node_id,
        state=event.state,
        summary=event.summary,
        created_at=event.created_at,
    )


async def _detail(db: AsyncSession, run: AgentRun) -> RunDetail:
    nodes = list(
        await db.scalars(
            select(AgentRunNode).where(AgentRunNode.run_id == run.id).order_by(AgentRunNode.node_id)
        )
    )
    return RunDetail(
        id=run.id,
        workflow_id=run.workflow_id,
        workflow_version=run.workflow_version,
        state=run.state,
        created_at=run.created_at,
        finished_at=run.finished_at,
        cancel_requested=run.cancel_requested,
        event_sequence=run.event_sequence,
        checkpoint=run.checkpoint,
        charged_tokens=run.charged_tokens,
        charged_cost_microusd=run.charged_cost,
        graph=agent_runs.read_snapshot(run).graph,
        nodes=[
            RunNodeView(
                node_id=node.node_id,
                state=node.state,
                error_code=node.error_code,
                output=NodeResult.model_validate_json(decrypt(node.output_ciphertext)).text
                if node.output_ciphertext
                else None,
                attempts=node.attempts,
                retries=node.retries,
            )
            for node in nodes
        ],
    )


def _not_found(exc: agent_runs.RunNotFoundError) -> HTTPException:
    return HTTPException(404, "Run not found")


def _conflict(exc: agent_runs.RunConflictError) -> HTTPException:
    return HTTPException(409, "Run state or idempotency conflict")


@router.post("/workflows/{workflow_id}/runs", response_model=RunSummary, status_code=202)
async def create_run(
    workflow_id: UUID,
    body: RunCreate,
    user: CurrentUser,
    db: DbSession,
    idempotency_key: IdempotencyHeader = None,
) -> RunSummary:
    try:
        run = await agent_runs.create_run(
            db, user.id, workflow_id, body, idempotency_key=idempotency_key
        )
    except agent_runs.RunNotFoundError as exc:
        raise _not_found(exc) from exc
    except agent_runs.RunConflictError as exc:
        raise _conflict(exc) from exc
    result = _summary(run)
    await db.commit()
    return result


@router.get("/runs", response_model=RunPage)
async def list_runs(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> RunPage:
    rows, total = await agent_runs.list_runs(db, user.id, limit=limit, offset=offset)
    return RunPage(items=[_summary(run) for run in rows], total=total)


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: UUID, user: CurrentUser, db: DbSession) -> RunDetail:
    try:
        run = await agent_runs.get_run(db, user.id, run_id)
    except agent_runs.RunNotFoundError as exc:
        raise _not_found(exc) from exc
    return await _detail(db, run)


@router.post("/runs/{run_id}/cancel", response_model=RunDetail)
async def cancel_run(run_id: UUID, user: CurrentUser, db: DbSession) -> RunDetail:
    try:
        run = await agent_runs.cancel_run(db, user.id, run_id)
    except agent_runs.RunNotFoundError as exc:
        raise _not_found(exc) from exc
    await db.commit()
    return await _detail(db, run)


@router.post("/runs/{run_id}/rerun", response_model=RunSummary, status_code=202)
async def rerun(
    run_id: UUID,
    body: RunRerun,
    user: CurrentUser,
    db: DbSession,
    idempotency_key: IdempotencyHeader = None,
) -> RunSummary:
    try:
        run = (
            await agent_runs.rerun_snapshot(db, user.id, run_id, idempotency_key=idempotency_key)
            if body.mode == "snapshot"
            else await agent_runs.rerun_latest(db, user.id, run_id, idempotency_key=idempotency_key)
        )
    except agent_runs.RunNotFoundError as exc:
        raise _not_found(exc) from exc
    except agent_runs.RunConflictError as exc:
        raise _conflict(exc) from exc
    result = _summary(run)
    await db.commit()
    return result


@router.get("/runs/{run_id}/events", response_model=RunEventPage)
async def get_events(
    run_id: UUID,
    user: CurrentUser,
    db: DbSession,
    after: Annotated[int, Query(ge=0, le=2**63 - 1)] = 0,
    limit: Annotated[int, Query(ge=1, le=128)] = 64,
) -> RunEventPage:
    try:
        run, rows, oldest = await agent_runs.read_run_events(
            db, user.id, run_id, after=after, limit=limit
        )
    except agent_runs.RunNotFoundError as exc:
        raise _not_found(exc) from exc
    if after > run.event_sequence:
        raise HTTPException(416, "Event cursor is ahead of the Run")
    if after < oldest - 1:
        raise HTTPException(410, "Event cursor has expired; request a fresh Run snapshot")
    return RunEventPage(
        items=[_event_view(event) for event in rows],
        oldest_sequence=oldest,
        latest_sequence=run.event_sequence,
    )


@router.get("/runs/{run_id}/events/stream")
async def stream_events(
    run_id: UUID,
    user: CurrentUser,
    request: Request,
    sessions: RunSessions,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    if last_event_id is not None and not re.fullmatch(r"0|[1-9][0-9]{0,18}", last_event_id):
        raise HTTPException(400, "Invalid event cursor")
    cursor = int(last_event_id or "0")
    try:
        async with sessions() as db:
            run, _rows, _oldest = await agent_runs.read_run_events(
                db, user.id, run_id, after=0, limit=1
            )
            if cursor > run.event_sequence:
                raise HTTPException(416, "Event cursor is ahead of the Run")
    except agent_runs.RunNotFoundError as exc:
        raise _not_found(exc) from exc

    async def packets() -> AsyncIterator[str]:
        nonlocal cursor
        started = time.monotonic()
        keepalive = started
        while time.monotonic() - started < 900:
            if await request.is_disconnected():
                return
            try:
                async with sessions() as db:
                    run, rows, oldest = await agent_runs.read_run_events(
                        db, user.id, run_id, after=cursor, limit=64
                    )
            except agent_runs.RunNotFoundError:
                yield "event: run_expired\ndata: {}\n\n"
                return
            if cursor < oldest - 1:
                cursor = oldest - 1
                yield f'event: cursor_expired\ndata: {{"oldest_sequence":{oldest}}}\n\n'
            for row in rows:
                event = _event_view(row)
                cursor = row.sequence
                yield f"id: {row.sequence}\nevent: {row.event_type}\ndata: {event.model_dump_json()}\n\n"
            if run.state not in {"pending", "running"} and not rows:
                return
            now = time.monotonic()
            if now - keepalive >= 15:
                yield ": keepalive\n\n"
                keepalive = now
            await asyncio.sleep(0.5)
        yield "event: stream_timeout\ndata: {}\n\n"

    return StreamingResponse(
        packets(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
