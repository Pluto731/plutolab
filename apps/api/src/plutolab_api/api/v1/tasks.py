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
    # 子任务: 校验 parent 存在 + 属于本人 + parent 本身不是子任务 (限制单层嵌套, 避 cycle).
    parent_id = body.parent_id
    if parent_id is not None:
        parent = await db.get(Task, parent_id)
        if parent is None or parent.user_id != user.id:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Parent task not found"
            )
        if parent.parent_id is not None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="子任务不能再有子任务 (仅支持单层嵌套)",
            )

    # 顶层任务 sort_order = MIN(existing 顶层) - 1; 子任务 sort_order = MAX(siblings) + 1
    if parent_id is None:
        min_so = await db.scalar(
            select(func.min(Task.sort_order)).where(
                Task.user_id == user.id, Task.parent_id.is_(None)
            )
        )
        new_order = (min_so - 1.0) if min_so is not None else 0.0
    else:
        max_so = await db.scalar(
            select(func.max(Task.sort_order)).where(Task.parent_id == parent_id)
        )
        new_order = (max_so + 1.0) if max_so is not None else 0.0

    task = Task(
        user_id=user.id,
        parent_id=parent_id,
        title=body.title,
        priority=body.priority,
        due_date=body.due_date,
        sort_order=new_order,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    logger.info(
        "plutolab.task.created",
        user_id=str(user.id),
        task_id=str(task.id),
        parent_id=str(parent_id) if parent_id else None,
    )
    return task


@router.post("/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_tasks(
    body: TaskReorderRequest, user: CurrentUser, db: DbSession
) -> None:
    """按 ids 数组顺序重写 sort_order = 0, 1, 2, ... 仅本人任务可改, 未列出的任务 sort_order 不动.

    一次只 reorder 同级 (全部顶层 或 同父下的子任务). 前端控制顺序合法性, 后端只做
    用户隔离 + bulk 写.
    """
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
