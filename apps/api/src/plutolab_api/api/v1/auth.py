"""Authentication endpoints: register, login, current user, password reset."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.api.deps import CurrentUser
from plutolab_api.core.config import settings
from plutolab_api.core.email import Mailer, get_mailer
from plutolab_api.core.github_oauth import exchange_code
from plutolab_api.core.logging import get_logger
from plutolab_api.core.redis import get_redis
from plutolab_api.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from plutolab_api.core.tokens import claim_rate_limit, consume_token, issue_token
from plutolab_api.db.deps import get_db
from plutolab_api.models.user import User
from plutolab_api.schemas.auth import (
    ForgotPasswordRequest,
    GitHubConfigResponse,
    GitHubLoginRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from plutolab_api.schemas.user import UserPublic

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[Redis, Depends(get_redis)]
MailerDep = Annotated[Mailer, Depends(get_mailer)]

PASSWORD_RESET_PURPOSE = "pwreset"
EMAIL_VERIFY_PURPOSE = "emailverify"
# 无论邮箱是否注册，统一返回这段文案，避免暴露账号存在性。
_FORGOT_OK = "如果该邮箱已注册，我们已发送重置链接，请查收。"


async def _send_verification_email(redis: Redis, mailer: Mailer, user: User) -> None:
    """Issue a one-shot verify token + send the verification email.

    Raises on failure; caller decides whether to swallow (e.g. register flow
    must not fail just because SMTP is down)."""
    token = await issue_token(
        redis, EMAIL_VERIFY_PURPOSE, str(user.id), settings.email_verify_ttl_seconds
    )
    verify_url = f"{settings.app_base_url.rstrip('/')}/verify-email?token={token}"
    ttl_hours = max(1, settings.email_verify_ttl_seconds // 3600)
    await mailer.send_email_verification(to=user.email, verify_url=verify_url, ttl_hours=ttl_hours)


def _tokens_for(user: User) -> TokenResponse:
    subject = str(user.id)
    return TokenResponse(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
        user=UserPublic.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: DbSession,
    redis: RedisDep,
    mailer: MailerDep,
) -> TokenResponse:
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

    # 发验证邮件 — 失败不挡注册 (SMTP 抖动 / 模板渲染异常都只 warn, 用户可在设置页重发)
    try:
        await _send_verification_email(redis, mailer, user)
    except Exception as e:
        logger.warning(
            "plutolab.auth.register.verify_email_failed",
            user_id=str(user.id),
            error=str(e),
        )

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


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: DbSession,
    redis: RedisDep,
    mailer: MailerDep,
) -> MessageResponse:
    """Send a password-reset link to the given email.

    Always returns 200 with the same message — we don't reveal whether the
    email is registered. Silently throttled per-email to prevent mailbox
    flooding by an attacker.
    """
    email = body.email
    # 同邮箱 N 秒内只发一次. 命中限流静默丢弃, 响应不变 (不暴露邮箱状态).
    allowed = await claim_rate_limit(
        redis, f"forgot:{email}", settings.password_reset_rate_limit_seconds
    )
    if not allowed:
        logger.info("plutolab.auth.forgot_password.throttled", email=email)
        return MessageResponse(message=_FORGOT_OK)

    user = await db.scalar(select(User).where(User.email == email))
    # 邮箱未注册或仅 GitHub 登录 (无 password_hash) → 不发, 也返回相同文案
    if user is None or user.password_hash is None:
        logger.info(
            "plutolab.auth.forgot_password.no_user",
            email=email,
            reason="not_found" if user is None else "oauth_only",
        )
        return MessageResponse(message=_FORGOT_OK)

    token = await issue_token(
        redis, PASSWORD_RESET_PURPOSE, str(user.id), settings.password_reset_ttl_seconds
    )
    reset_url = f"{settings.app_base_url.rstrip('/')}/reset-password?token={token}"
    ttl_min = max(1, settings.password_reset_ttl_seconds // 60)
    await mailer.send_password_reset(to=email, reset_url=reset_url, ttl_minutes=ttl_min)
    return MessageResponse(message=_FORGOT_OK)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest, db: DbSession, redis: RedisDep
) -> MessageResponse:
    """Consume a reset token and set a new password.

    Tokens are one-shot (deleted on consume), so a leaked link can't be
    replayed after use.
    """
    user_id = await consume_token(redis, PASSWORD_RESET_PURPOSE, body.token)
    if user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="重置链接无效或已过期")

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="重置链接无效或已过期")

    user.password_hash = hash_password(body.password)
    await db.commit()
    logger.info("plutolab.auth.password_reset.success", user_id=user_id)
    return MessageResponse(message="密码已重置，请用新密码登录。")


@router.post("/send-verification", response_model=MessageResponse)
async def send_verification(
    user: CurrentUser, redis: RedisDep, mailer: MailerDep
) -> MessageResponse:
    """Resend the email-verification link to the current user."""
    if user.email_verified:
        return MessageResponse(message="邮箱已经验证过了。")

    allowed = await claim_rate_limit(
        redis, f"emailverify:{user.id}", settings.email_verify_rate_limit_seconds
    )
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请稍后再试 (1 分钟内只能重发一次)。",
        )

    await _send_verification_email(redis, mailer, user)
    return MessageResponse(message="验证邮件已发送，请查收。")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    body: VerifyEmailRequest, db: DbSession, redis: RedisDep
) -> MessageResponse:
    """Consume an email-verification token and mark the user as verified."""
    user_id = await consume_token(redis, EMAIL_VERIFY_PURPOSE, body.token)
    if user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="验证链接无效或已过期")

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="验证链接无效或已过期")

    if user.email_verified:
        return MessageResponse(message="邮箱已经验证过了。")

    user.email_verified = True
    await db.commit()
    logger.info("plutolab.auth.email_verified", user_id=user_id)
    return MessageResponse(message="邮箱验证成功！")
