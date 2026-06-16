"""Schemas for tasks — Phase 3.2.a + 3.2.b + 3.2.c-1."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["low", "normal", "high"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    priority: Priority = "normal"
    due_date: date | None = None
    parent_id: UUID | None = None  # C-2: 创建子任务时传父 id


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    done: bool | None = None
    priority: Priority | None = None
    # due_date=None 表示清空, key 缺失表示不动 (PATCH 区分用 exclude_unset)
    due_date: date | None = None


class TaskPublic(BaseModel):
    id: UUID
    parent_id: UUID | None
    title: str
    done: bool
    priority: Priority
    due_date: date | None
    sort_order: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskReorderRequest(BaseModel):
    """C-1 bulk reorder: 按数组顺序写 sort_order 0, 1, 2, ..."""

    ids: list[UUID] = Field(min_length=1, max_length=500)
