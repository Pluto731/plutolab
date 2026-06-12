"""Unit tests for plutolab_api.core.tokens (one-shot tokens + rate limiting)."""

import fakeredis.aioredis
import pytest

from plutolab_api.core.tokens import claim_rate_limit, consume_token, issue_token


@pytest.fixture
def redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


class TestIssueAndConsume:
    async def test_issue_then_consume_returns_subject(
        self, redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        token = await issue_token(redis, "pwreset", "user-1", ttl_seconds=60)
        assert token and len(token) >= 32

        subject = await consume_token(redis, "pwreset", token)
        assert subject == "user-1"

    async def test_consume_is_one_shot(self, redis: fakeredis.aioredis.FakeRedis) -> None:
        token = await issue_token(redis, "pwreset", "user-1", ttl_seconds=60)
        first = await consume_token(redis, "pwreset", token)
        second = await consume_token(redis, "pwreset", token)
        assert first == "user-1"
        assert second is None

    async def test_consume_unknown_token_returns_none(
        self, redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        assert await consume_token(redis, "pwreset", "nope-not-a-token") is None

    async def test_purposes_are_isolated(self, redis: fakeredis.aioredis.FakeRedis) -> None:
        token = await issue_token(redis, "pwreset", "user-1", ttl_seconds=60)
        # 用别的 purpose 去 consume 同一个 token 必须失败
        assert await consume_token(redis, "emailverify", token) is None
        # 原 purpose 仍可消费 (一次性还没被花掉)
        assert await consume_token(redis, "pwreset", token) == "user-1"

    async def test_issued_token_expires(self, redis: fakeredis.aioredis.FakeRedis) -> None:
        token = await issue_token(redis, "pwreset", "user-1", ttl_seconds=60)
        ttl = await redis.ttl(f"pwreset:{token}")
        assert 0 < ttl <= 60


class TestRateLimit:
    async def test_first_call_allowed(self, redis: fakeredis.aioredis.FakeRedis) -> None:
        assert await claim_rate_limit(redis, "forgot:alice@example.com", 60) is True

    async def test_second_call_within_window_denied(
        self, redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        await claim_rate_limit(redis, "forgot:alice@example.com", 60)
        assert await claim_rate_limit(redis, "forgot:alice@example.com", 60) is False

    async def test_different_keys_independent(self, redis: fakeredis.aioredis.FakeRedis) -> None:
        assert await claim_rate_limit(redis, "forgot:alice@example.com", 60) is True
        assert await claim_rate_limit(redis, "forgot:bob@example.com", 60) is True
