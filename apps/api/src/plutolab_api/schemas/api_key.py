"""Schemas for user-owned API keys (Phase 2.5)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# 当前支持的 provider 白名单 (容易扩展)
ApiKeyProvider = Literal["anthropic", "openai", "deepseek", "replicate"]


class CreateApiKeyRequest(BaseModel):
    provider: ApiKeyProvider
    key: str = Field(min_length=10, max_length=200, description="明文 API key, 服务端立即加密")
    label: str | None = Field(default=None, max_length=50)


class ApiKeyPublic(BaseModel):
    """对外永远不含明文 / ciphertext, 只暴露元信息和末 4 位 preview."""

    id: UUID
    provider: ApiKeyProvider
    key_preview: str
    label: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
