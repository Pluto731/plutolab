"""Shared FastAPI dependencies for authenticated routes."""

from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.core.security import ACCESS_TOKEN, decode_token
from plutolab_api.db.deps import get_db
from plutolab_api.models.user import User

# auto_error=False so a missing header yields our own 401 (FastAPI defaults to 403).
_bearer = HTTPBearer(auto_error=False)

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if creds is None:
        raise _CREDENTIALS_ERROR
    try:
        payload = decode_token(creds.credentials)
        user_id = UUID(payload.sub)
    except (jwt.InvalidTokenError, ValueError):
        raise _CREDENTIALS_ERROR from None

    if payload.type != ACCESS_TOKEN:
        raise _CREDENTIALS_ERROR

    user = await db.get(User, user_id)
    if user is None:
        raise _CREDENTIALS_ERROR
    return user


CurrentUser = Annotated[User, Depends(current_user)]
