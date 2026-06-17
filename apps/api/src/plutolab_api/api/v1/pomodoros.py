"""Pomodoro sessions — Phase 3.4 番茄钟.

只记录"已完成"会话. 中途取消的不入库 (前端控制).
用户隔离 + task_id 可选关联 (任务删除时 SET NULL).
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.api.deps import CurrentUser
from plutolab_api.core.logging import get_logger
from plutolab_api.db.deps import get_db
from plutolab_api.models.pomodoro import PomodoroSession
from plutolab_api.models.task import Task
from plutolab_api.schemas.pomodoro import (
    PomodoroCreate,
    PomodoroPublic,
    PomodoroWithTask,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/pomodoros", tags=["pomodoros"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _today_start_utc() -> datetime:
    return datetime.combine(datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC)


@router.get("", response_model=list[PomodoroWithTask])
async def list_today(
    user: CurrentUser,
    db: DbSession,
    days: Annotated[int, Query(ge=1, le=30)] = 1,
) -> list[PomodoroWithTask]:
    """默认返回当天 (UTC 日历日) 已完成会话. days>1 时往前推 N 天."""
    since = _today_start_utc() - timedelta(days=days - 1)
    stmt = (
        select(PomodoroSession)
        .where(
            PomodoroSession.user_id == user.id,
            PomodoroSession.completed_at >= since,
        )
        .order_by(PomodoroSession.completed_at.desc())
    )
    sessions = (await db.scalars(stmt)).all()

    # 一次性 join task title 避 N+1
    task_ids = {s.task_id for s in sessions if s.task_id is not None}
    titles: dict[UUID, str] = {}
    if task_ids:
        rows = await db.execute(
            select(Task.id, Task.title).where(Task.id.in_(task_ids))
        )
        for tid, ttitle in rows.all():
            titles[tid] = ttitle

    return [
        PomodoroWithTask(
            id=s.id,
            kind=s.kind,  # type: ignore[arg-type]
            planned_seconds=s.planned_seconds,
            task_id=s.task_id,
            completed_at=s.completed_at,
            task_title=titles.get(s.task_id) if s.task_id else None,
        )
        for s in sessions
    ]


@router.post(
    "", response_model=PomodoroPublic, status_code=status.HTTP_201_CREATED
)
async def create_session(
    body: PomodoroCreate, user: CurrentUser, db: DbSession
) -> PomodoroSession:
    # 校验 task_id 属于本人 (避越权)
    if body.task_id is not None:
        task = await db.get(Task, body.task_id)
        if task is None or task.user_id != user.id:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Task not found"
            )
    session = PomodoroSession(
        user_id=user.id,
        kind=body.kind,
        planned_seconds=body.planned_seconds,
        task_id=body.task_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    logger.info(
        "plutolab.pomodoro.completed",
        user_id=str(user.id),
        kind=body.kind,
        planned_seconds=body.planned_seconds,
        task_id=str(body.task_id) if body.task_id else None,
    )
    return session
