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
