"""Schemas for links — Phase 3.3."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class LinkCreate(BaseModel):
    # HttpUrl 自动校验 (http:// 或 https:// + 合法域名)
    url: HttpUrl


class LinkPublic(BaseModel):
    id: UUID
    url: str
    title: str
    description: str | None
    image_url: str | None
    favicon_url: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
