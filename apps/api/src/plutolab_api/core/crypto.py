"""Symmetric encryption for user-stored secrets (API keys).

Wraps `cryptography.fernet.Fernet` — AES128-CBC + HMAC, authenticated.
Key is read from `settings.fernet_key` (env `FERNET_KEY`). Generate a fresh
production key with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from cryptography.fernet import Fernet, InvalidToken

from plutolab_api.core.config import settings
from plutolab_api.core.logging import get_logger

logger = get_logger(__name__)

_DEV_DEFAULT_KEY = "cGx1dG9sYWJfZGV2X2luc2VjdXJlX2tleV94eF8xMjM="


def _fernet() -> Fernet:
    key = settings.fernet_key
    if key == _DEV_DEFAULT_KEY:
        logger.warning(
            "plutolab.crypto.dev_key",
            msg="FERNET_KEY is the dev default; set a real key in production",
        )
    return Fernet(key.encode("utf-8"))


def encrypt(plaintext: str) -> bytes:
    """Encrypt a string, return ciphertext bytes (safe to store in `bytea`)."""
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    """Decrypt ciphertext bytes back to original string.

    Raises `cryptography.fernet.InvalidToken` if tampered or wrong key."""
    return _fernet().decrypt(ciphertext).decode("utf-8")


__all__ = ["InvalidToken", "decrypt", "encrypt"]
