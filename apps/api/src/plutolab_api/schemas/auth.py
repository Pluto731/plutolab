"""Auth request/response schemas."""

from pydantic import BaseModel, EmailStr, Field

from plutolab_api.schemas.user import UserPublic

# bcrypt only hashes the first 72 bytes, so cap password length here.
_PW = Field(min_length=8, max_length=72)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = _PW
    name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic


class GitHubLoginRequest(BaseModel):
    code: str
    redirect_uri: str


class GitHubConfigResponse(BaseModel):
    client_id: str
    configured: bool


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = _PW


class RequestPasswordCodeRequest(BaseModel):
    """新流程: 本地直接输新密码 + 邮箱; 系统发验证码到邮箱."""

    email: EmailStr
    password: str = _PW


class VerifyPasswordCodeRequest(BaseModel):
    """凭邮件里的 6 位验证码确认改密码."""

    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class MessageResponse(BaseModel):
    message: str
