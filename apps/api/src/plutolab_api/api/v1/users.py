"""Authenticated user profile endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.api.deps import CurrentUser
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
