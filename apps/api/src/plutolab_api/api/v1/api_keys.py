"""User-owned API key endpoints (Phase 2.5).

Users add their own Anthropic / OpenAI / Replicate keys. Server encrypts with
Fernet on write, stores last-4-char preview for UI. Plaintext never leaves
the request that wrote it.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.api.deps import CurrentUser
from plutolab_api.core.crypto import encrypt
from plutolab_api.core.logging import get_logger
from plutolab_api.db.deps import get_db
from plutolab_api.models.user_api_key import UserApiKey
from plutolab_api.schemas.api_key import ApiKeyPublic, CreateApiKeyRequest

logger = get_logger(__name__)

router = APIRouter(prefix="/users/me/api-keys", tags=["api-keys"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _preview(key: str) -> str:
    """末 4 位; key 短于 4 位直接返回整段 (理论上不会, 但兜底)."""
    return key[-4:] if len(key) >= 4 else key


@router.get("", response_model=list[ApiKeyPublic])
async def list_keys(user: CurrentUser, db: DbSession) -> list[UserApiKey]:
    result = await db.scalars(
        select(UserApiKey)
        .where(UserApiKey.user_id == user.id)
        .order_by(UserApiKey.created_at.desc())
    )
    return list(result.all())


@router.post("", response_model=ApiKeyPublic, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: CreateApiKeyRequest, user: CurrentUser, db: DbSession
) -> UserApiKey:
    api_key = UserApiKey(
        user_id=user.id,
        provider=body.provider,
        key_ciphertext=encrypt(body.key),
        key_preview=_preview(body.key),
        label=body.label,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    logger.info(
        "plutolab.api_key.created",
        user_id=str(user.id),
        provider=body.provider,
        key_id=str(api_key.id),
    )
    return api_key


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(key_id: UUID, user: CurrentUser, db: DbSession) -> None:
    api_key = await db.get(UserApiKey, key_id)
    # 同时校验存在 + 属于当前用户 (避免别人猜 UUID 删你的)
    if api_key is None or api_key.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="API key not found")
    await db.delete(api_key)
    await db.commit()
    logger.info(
        "plutolab.api_key.deleted", user_id=str(user.id), key_id=str(key_id)
    )
