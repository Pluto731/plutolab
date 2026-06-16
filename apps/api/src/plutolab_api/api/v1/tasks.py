"""Tasks CRUD endpoints (Phase 3.2.a).

用户隔离: 所有 query 强制 `Task.user_id == current_user.id`.
不存在 / 不属于当前用户一律返 404.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.api.deps import CurrentUser
from plutolab_api.core.logging import get_logger
from plutolab_api.db.deps import get_db
from plutolab_api.models.task import Task
from plutolab_api.schemas.task import TaskCreate, TaskPublic, TaskReorderRequest, TaskUpdate

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
    """所有任务按 sort_order asc 然后 created_at desc 返回. 前端按 done 分组."""
    result = await db.scalars(
        select(Task)
        .where(Task.user_id == user.id)
        .order_by(Task.sort_order.asc(), Task.created_at.desc())
    )
    return list(result.all())


@router.post("", response_model=TaskPublic, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate, user: CurrentUser, db: DbSession
) -> Task:
    # 新任务 sort_order = MIN(existing) - 1 让它在顶部 (Things / Todoist 直觉)
    min_so = await db.scalar(
        select(func.min(Task.sort_order)).where(Task.user_id == user.id)
    )
    new_order = (min_so - 1.0) if min_so is not None else 0.0
    task = Task(
        user_id=user.id,
        title=body.title,
        priority=body.priority,
        due_date=body.due_date,
        sort_order=new_order,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    logger.info("plutolab.task.created", user_id=str(user.id), task_id=str(task.id))
    return task


@router.post("/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_tasks(
    body: TaskReorderRequest, user: CurrentUser, db: DbSession
) -> None:
    """按 ids 数组顺序重写 sort_order = 0, 1, 2, ... 仅本人任务可改, 未列出的任务 sort_order 不动."""
    # 校验所有 id 都属于当前用户 — 防越权
    rows = await db.scalars(
        select(Task).where(
            Task.user_id == user.id,
            Task.id.in_(body.ids),
        )
    )
    owned = {t.id: t for t in rows.all()}
    if len(owned) != len(set(body.ids)):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="One or more task ids not found"
        )
    for idx, tid in enumerate(body.ids):
        owned[tid].sort_order = float(idx)
    await db.commit()
    logger.info(
        "plutolab.task.reordered", user_id=str(user.id), count=len(body.ids)
    )


@router.patch("/{task_id}", response_model=TaskPublic)
async def update_task(
    task_id: UUID, body: TaskUpdate, user: CurrentUser, db: DbSession
) -> Task:
    task = await _get_owned(db, task_id, user.id)
    # Pydantic exclude_unset 区分 "未传" 与 "传 null". 业务: 未传保持原值,
    # 传 null 清空 (仅 due_date 适用 — title/done/priority 不接受 null).
    fields = body.model_dump(exclude_unset=True)
    if "title" in fields and fields["title"] is not None:
        task.title = fields["title"]
    if "done" in fields and fields["done"] is not None:
        task.done = fields["done"]
    if "priority" in fields and fields["priority"] is not None:
        task.priority = fields["priority"]
    if "due_date" in fields:
        task.due_date = fields["due_date"]  # 允许 None 清空
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, user: CurrentUser, db: DbSession) -> None:
    task = await _get_owned(db, task_id, user.id)
    await db.delete(task)
    await db.commit()
    logger.info("plutolab.task.deleted", user_id=str(user.id), task_id=str(task_id))
