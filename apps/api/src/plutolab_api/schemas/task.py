"""Schemas for tasks — Phase 3.2.a + 3.2.b."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["low", "normal", "high"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    priority: Priority = "normal"
    due_date: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    done: bool | None = None
    priority: Priority | None = None
    # 用 Field 区分 "未传" 与 "传 null 清空 due_date" 不行 (Pydantic 默认 None=未传).
    # 业务采用: due_date=None 表示清空, key 缺失表示不动. 客户端用 PATCH 不带 due_date 即可保留.
    due_date: date | None = None


class TaskPublic(BaseModel):
    id: UUID
    title: str
    done: bool
    priority: Priority
    due_date: date | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
