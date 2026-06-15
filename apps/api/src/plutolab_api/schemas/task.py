"""Schemas for tasks — Phase 3.2.a."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    done: bool | None = None


class TaskPublic(BaseModel):
    id: UUID
    title: str
    done: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
