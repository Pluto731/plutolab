"""Async Redis client singleton + FastAPI dependency.

Tests override `get_redis` with a fakeredis instance via `app.dependency_overrides`.
"""

from redis.asyncio import Redis, from_url

from plutolab_api.core.config import settings

_client: Redis | None = None


def get_redis() -> Redis:
    """FastAPI dependency: return the process-wide async Redis client.

    Lazy-initialised; `decode_responses=True` so we get `str` back from `GET`
    instead of `bytes` (token payloads are always strings here).
    """
    global _client
    if _client is None:
        _client = from_url(settings.redis_url, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
