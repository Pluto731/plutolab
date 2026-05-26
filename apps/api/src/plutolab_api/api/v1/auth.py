"""Authentication endpoints: register, login, current user."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.api.deps import CurrentUser
from plutolab_api.core.config import settings
from plutolab_api.core.github_oauth import exchange_code
from plutolab_api.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from plutolab_api.db.deps import get_db
from plutolab_api.models.user import User
from plutolab_api.schemas.auth import (
    GitHubConfigResponse,
    GitHubLoginRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from plutolab_api.schemas.user import UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _tokens_for(user: User) -> TokenResponse:
    subject = str(user.id)
    return TokenResponse(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
        user=UserPublic.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: DbSession) -> TokenResponse:
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        name=body.name or body.email.split("@", 1)[0],
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _tokens_for(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None or user.password_hash is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return _tokens_for(user)


@router.get("/me", response_model=UserPublic)
async def me(user: CurrentUser) -> User:
    return user


@router.get("/github/config", response_model=GitHubConfigResponse)
async def github_config() -> GitHubConfigResponse:
    configured = bool(settings.github_client_id and settings.github_client_secret)
    return GitHubConfigResponse(client_id=settings.github_client_id, configured=configured)


@router.post("/github", response_model=TokenResponse)
async def github_login(body: GitHubLoginRequest, db: DbSession) -> TokenResponse:
    if not (settings.github_client_id and settings.github_client_secret):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="GitHub 登录未配置")

    gh = await exchange_code(body.code, body.redirect_uri)

    user = await db.scalar(select(User).where(User.github_id == gh.id))
    if user is None and gh.email:
        # 邮箱已存在 → 关联该 GitHub 账号 (账号合并)
        user = await db.scalar(select(User).where(User.email == gh.email))
        if user is not None:
            user.github_id = gh.id
            if not user.avatar:
                user.avatar = gh.avatar
    if user is None:
        user = User(
            email=gh.email or f"gh_{gh.id}@users.noreply.github.com",
            github_id=gh.id,
            name=gh.name or gh.login,
            avatar=gh.avatar,
            email_verified=True,  # GitHub 已验证主邮箱
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)
    return _tokens_for(user)
