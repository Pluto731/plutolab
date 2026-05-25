"""Security primitives: password hashing (bcrypt) and JWT issuing/decoding.

Pure functions only — no DB, no request context. Endpoints and dependencies
build on these.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from plutolab_api.core.config import settings

ACCESS_TOKEN = "access"
REFRESH_TOKEN = "refresh"

_BCRYPT_ROUNDS = 12


@dataclass(frozen=True)
class TokenPayload:
    sub: str
    type: str


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _create_token(subject: str, token_type: str, ttl: timedelta) -> str:
    now = datetime.now(UTC)
    claims = {"sub": subject, "type": token_type, "iat": now, "exp": now + ttl}
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    ttl = expires_delta or timedelta(minutes=settings.jwt_access_ttl_min)
    return _create_token(subject, ACCESS_TOKEN, ttl)


def create_refresh_token(subject: str, expires_delta: timedelta | None = None) -> str:
    ttl = expires_delta or timedelta(days=settings.jwt_refresh_ttl_days)
    return _create_token(subject, REFRESH_TOKEN, ttl)


def decode_token(token: str) -> TokenPayload:
    """Decode and verify a JWT. Raises jwt.InvalidTokenError (or a subclass such as
    jwt.ExpiredSignatureError) when the token is invalid, expired, or tampered with."""
    claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return TokenPayload(sub=claims["sub"], type=claims.get("type", ""))
