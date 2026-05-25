"""Unit tests for the security primitives (password hashing + JWT).

These are pure functions with no DB / network, so they form the fast TDD core.
"""

from datetime import timedelta

import jwt
import pytest

from plutolab_api.core.security import (
    TokenPayload,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self) -> None:
        hashed = hash_password("correct horse battery")
        assert hashed != "correct horse battery"
        assert hashed.startswith("$2")  # bcrypt prefix

    def test_verify_accepts_correct_password(self) -> None:
        hashed = hash_password("s3cret-pw")
        assert verify_password("s3cret-pw", hashed) is True

    def test_verify_rejects_wrong_password(self) -> None:
        hashed = hash_password("s3cret-pw")
        assert verify_password("wrong-pw", hashed) is False

    def test_same_password_gets_distinct_salts(self) -> None:
        a = hash_password("same-pw")
        b = hash_password("same-pw")
        assert a != b
        assert verify_password("same-pw", a)
        assert verify_password("same-pw", b)

    def test_verify_handles_unicode(self) -> None:
        hashed = hash_password("密码-π-🔒")
        assert verify_password("密码-π-🔒", hashed) is True
        assert verify_password("密码-π", hashed) is False


class TestJwt:
    def test_access_token_roundtrips(self) -> None:
        token = create_access_token("user-123")
        payload = decode_token(token)
        assert isinstance(payload, TokenPayload)
        assert payload.sub == "user-123"
        assert payload.type == "access"

    def test_refresh_token_has_refresh_type(self) -> None:
        token = create_refresh_token("user-123")
        payload = decode_token(token)
        assert payload.sub == "user-123"
        assert payload.type == "refresh"

    def test_expired_token_is_rejected(self) -> None:
        token = create_access_token("user-123", expires_delta=timedelta(seconds=-1))
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(token)

    def test_tampered_token_is_rejected(self) -> None:
        token = create_access_token("user-123")
        tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(tampered)

    def test_token_signed_with_other_secret_is_rejected(self) -> None:
        forged = jwt.encode({"sub": "x", "type": "access"}, "other-secret", algorithm="HS256")
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(forged)
