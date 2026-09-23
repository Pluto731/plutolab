"""GitHub App credentials, separate from site OAuth. No credential persistence."""

import time
from collections.abc import Callable

import jwt
from pydantic import SecretStr

from plutolab_api.core.config import Settings


class GitHubAppError(Exception):
    """Only allowlisted diagnostics; never attach upstream bodies or exceptions."""

    def __init__(
        self,
        code: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(f"GitHub App request failed: {code}")
        self.code = code
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


class GitHubAppCredentials:
    """RS256 signer. Returned JWT and stored key have redacted string/repr output."""

    def __init__(
        self, app_id: str, private_key: SecretStr, *, clock: Callable[[], float] = time.time
    ) -> None:
        self._app_id = app_id
        self._private_key = private_key
        self._clock = clock

    @classmethod
    def from_settings(cls, config: Settings) -> "GitHubAppCredentials":
        return cls(config.github_app_id, config.github_app_private_key)

    def create_jwt(self) -> SecretStr:
        if (
            not self._app_id.isascii()
            or not self._app_id.isdecimal()
            or len(self._app_id) > 20
            or int(self._app_id) <= 0
        ):
            raise GitHubAppError("app_not_configured")
        if not self._private_key.get_secret_value().strip():
            raise GitHubAppError("app_not_configured")
        now = int(self._clock())
        # GitHub allows exp at most ten minutes ahead; reserve one minute for skew.
        claims = {"iss": self._app_id, "iat": now - 60, "exp": now + 540}
        try:
            return SecretStr(
                jwt.encode(claims, self._private_key.get_secret_value(), algorithm="RS256")
            )
        except (jwt.PyJWTError, ValueError, TypeError):
            # Raise outside except: even __context__ must not retain a raw key error.
            pass
        raise GitHubAppError("jwt_signing_failed")
