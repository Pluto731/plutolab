"""One-shot tokens backed by Redis (auto-expire via TTL, atomic consume).

Used for password-reset links and email-verification links. Tokens are
opaque random strings; the Redis key embeds the *purpose* so a reset token
can't be replayed as a verify token (or vice-versa).
"""

import secrets

from redis.asyncio import Redis


def _key(purpose: str, token: str) -> str:
    return f"{purpose}:{token}"


async def issue_token(redis: Redis, purpose: str, subject: str, ttl_seconds: int) -> str:
    """Mint a fresh opaque token bound to `subject` (usually user_id).

    Returned token is URL-safe and contains ~256 bits of entropy.
    """
    token = secrets.token_urlsafe(32)
    await redis.set(_key(purpose, token), subject, ex=ttl_seconds)
    return token


async def consume_token(redis: Redis, purpose: str, token: str) -> str | None:
    """Atomically read & delete a token. Returns the subject on success, else None.

    The delete-on-read guarantees one-shot semantics: a reused link fails even
    if the TTL hasn't expired yet.
    """
    key = _key(purpose, token)
    async with redis.pipeline(transaction=True) as pipe:
        pipe.get(key)
        pipe.delete(key)
        value, _ = await pipe.execute()
    return value


async def claim_rate_limit(redis: Redis, key: str, window_seconds: int) -> bool:
    """Allow at most one action per `window_seconds` for the given key.

    Returns True if the caller is allowed (first within the window), False if
    they should be silently throttled. Implemented as `SET NX EX` so the
    window starts from the first call and clears itself.
    """
    was_set = await redis.set(f"ratelimit:{key}", "1", nx=True, ex=window_seconds)
    return bool(was_set)
