"""Schemas for pomodoro sessions — Phase 3.4."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PomodoroKind = Literal["focus", "short_break", "long_break"]


class PomodoroCreate(BaseModel):
    """记录一次已完成的番茄会话."""

    kind: PomodoroKind
    planned_seconds: int = Field(ge=60, le=2 * 60 * 60)  # 1 分 ~ 2 小时
    task_id: UUID | None = None


class PomodoroPublic(BaseModel):
    id: UUID
    kind: PomodoroKind
    planned_seconds: int
    task_id: UUID | None
    completed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PomodoroWithTask(PomodoroPublic):
    """列表 / 历史展示用 — 带上关联任务的标题 (任务被删后 task_title=null)."""

    task_title: str | None = None
