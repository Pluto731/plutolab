"""Tasks CRUD endpoints (Phase 3.2.a).

用户隔离: 所有 query 强制 `Task.user_id == current_user.id`.
不存在 / 不属于当前用户一律返 404.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.api.deps import CurrentUser
from plutolab_api.core.logging import get_logger
from plutolab_api.db.deps import get_db
from plutolab_api.models.task import Task
from plutolab_api.schemas.task import TaskCreate, TaskPublic, TaskUpdate

logger = get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _get_owned(db: AsyncSession, task_id: UUID, user_id: UUID) -> Task:
    task = await db.get(Task, task_id)
    if task is None or task.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("", response_model=list[TaskPublic])
async def list_tasks(user: CurrentUser, db: DbSession) -> list[Task]:
    """所有任务按 created_at desc 返回. 前端按 done 分组渲染."""
    result = await db.scalars(
        select(Task)
        .where(Task.user_id == user.id)
        .order_by(Task.created_at.desc())
    )
    return list(result.all())


@router.post("", response_model=TaskPublic, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate, user: CurrentUser, db: DbSession
) -> Task:
    task = Task(user_id=user.id, title=body.title)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    logger.info("plutolab.task.created", user_id=str(user.id), task_id=str(task.id))
    return task


@router.patch("/{task_id}", response_model=TaskPublic)
async def update_task(
    task_id: UUID, body: TaskUpdate, user: CurrentUser, db: DbSession
) -> Task:
    task = await _get_owned(db, task_id, user.id)
    if body.title is not None:
        task.title = body.title
    if body.done is not None:
        task.done = body.done
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, user: CurrentUser, db: DbSession) -> None:
    task = await _get_owned(db, task_id, user.id)
    await db.delete(task)
    await db.commit()
    logger.info("plutolab.task.deleted", user_id=str(user.id), task_id=str(task_id))
