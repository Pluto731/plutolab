"""Schemas for notes (Phase 3.1 + 3.1.polish B.1)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=200_000)


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, max_length=200_000)


class NotePublic(BaseModel):
    """完整笔记 — 编辑页 / 创建返回."""

    id: UUID
    title: str
    content: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NoteSummary(BaseModel):
    """列表项 — 不返回正文, 用首 160 字符当 excerpt 节省带宽."""

    id: UUID
    title: str
    excerpt: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TagWithCount(BaseModel):
    """B.1 列表页左栏 tag 筛选 chip — 标签名 + 该用户带此标签的笔记数."""

    name: str
    count: int
