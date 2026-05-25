"""Authenticated user profile endpoints."""

import io
import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.api.deps import CurrentUser
from plutolab_api.core.config import settings
from plutolab_api.core.security import hash_password, verify_password
from plutolab_api.db.deps import get_db
from plutolab_api.models.user import User
from plutolab_api.schemas.user import (
    ChangePasswordRequest,
    UpdateProfileRequest,
    UserPublic,
)

router = APIRouter(prefix="/users", tags=["users"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_AVATAR_SIZE = 256


@router.patch("/me", response_model=UserPublic)
async def update_me(body: UpdateProfileRequest, user: CurrentUser, db: DbSession) -> User:
    user.name = body.name
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(body: ChangePasswordRequest, user: CurrentUser, db: DbSession) -> None:
    if user.password_hash is None or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="当前密码不正确")
    user.password_hash = hash_password(body.new_password)
    await db.commit()


def _process_avatar(raw: bytes) -> bytes:
    """Re-encode an uploaded image to a square webp thumbnail.

    Re-encoding (rather than storing the raw upload) neutralizes malicious
    payloads disguised as images and normalizes format/size.
    """
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()  # detect truncated / non-image data
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="无法识别的图片文件") from e

    # 居中裁剪成正方形再缩放, 避免拉伸变形
    side = min(img.size)
    left = (img.width - side) // 2
    top = (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize(
        (_AVATAR_SIZE, _AVATAR_SIZE), Image.LANCZOS
    )

    out = io.BytesIO()
    img.save(out, format="WEBP", quality=85)
    return out.getvalue()


@router.post("/me/avatar", response_model=UserPublic)
async def upload_avatar(
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File()],
) -> User:
    if file.content_type is None or not file.content_type.startswith("image/"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="只接受图片文件")

    raw = await file.read()
    if len(raw) > settings.avatar_max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="图片不能超过 2MB")

    webp = _process_avatar(raw)

    dest_dir = Path(settings.avatar_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / f"{user.id}.webp").write_bytes(webp)

    # 文件名固定 (覆盖旧图), 用时间戳查询参数破浏览器缓存
    user.avatar = f"/api/v1/avatars/{user.id}.webp?v={int(time.time())}"
    await db.commit()
    await db.refresh(user)
    return user
