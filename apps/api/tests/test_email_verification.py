"""Integration tests for email verification (register auto-send + send-verification + verify-email)."""

import fakeredis.aioredis
from httpx import AsyncClient

from tests.conftest import FakeMailer

REGISTER = "/api/v1/auth/register"
SEND_VERIFY = "/api/v1/auth/send-verification"
VERIFY = "/api/v1/auth/verify-email"
ME = "/api/v1/auth/me"


async def _register(
    client: AsyncClient, email: str = "alice@example.com", pw: str = "supersecret"
) -> dict:
    resp = await client.post(REGISTER, json={"email": email, "password": pw})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _token_from(verify_url: str) -> str:
    return verify_url.split("token=", 1)[1]


class TestRegisterSendsVerificationEmail:
    async def test_register_triggers_verification_email(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        await _register(client, "alice@example.com")
        assert len(fake_mailer.verify_emails) == 1
        sent = fake_mailer.verify_emails[0]
        assert sent["to"] == "alice@example.com"
        assert "token=" in str(sent["verify_url"])
        assert sent["ttl_hours"] == 24

    async def test_verify_url_uses_configured_base(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        from plutolab_api.core.config import settings

        await _register(client, "bob@example.com")
        url = str(fake_mailer.verify_emails[0]["verify_url"])
        assert url.startswith(settings.app_base_url.rstrip("/") + "/verify-email?token=")

    async def test_new_user_is_unverified(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        tokens = await _register(client, "carol@example.com")
        assert tokens["user"]["email_verified"] is False


class TestVerifyEmail:
    async def test_valid_token_verifies_user(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        tokens = await _register(client, "dave@example.com")
        token = _token_from(str(fake_mailer.verify_emails[0]["verify_url"]))

        resp = await client.post(VERIFY, json={"token": token})
        assert resp.status_code == 200
        assert "成功" in resp.json()["message"]

        # 再调 /me 应见到 email_verified=True
        me = await client.get(
            ME, headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        assert me.json()["email_verified"] is True

    async def test_token_is_one_shot(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        await _register(client, "erin@example.com")
        token = _token_from(str(fake_mailer.verify_emails[0]["verify_url"]))

        ok = await client.post(VERIFY, json={"token": token})
        replay = await client.post(VERIFY, json={"token": token})
        assert ok.status_code == 200
        assert replay.status_code == 400

    async def test_invalid_token_rejected(self, client: AsyncClient) -> None:
        resp = await client.post(VERIFY, json={"token": "not-a-valid-token"})
        assert resp.status_code == 400

    async def test_reset_token_cannot_verify_email(
        self,
        client: AsyncClient,
        fake_mailer: FakeMailer,
        fake_redis: fakeredis.aioredis.FakeRedis,
    ) -> None:
        # 用 forgot-password 拿一个 reset token, 不能用它来 verify-email (purpose 隔离)
        await _register(client, "fiona@example.com")
        await client.post("/api/v1/auth/forgot-password", json={"email": "fiona@example.com"})
        reset_token = str(fake_mailer.reset_emails[0]["reset_url"]).split("token=", 1)[1]

        resp = await client.post(VERIFY, json={"token": reset_token})
        assert resp.status_code == 400


class TestSendVerification:
    async def test_unverified_user_can_resend(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        tokens = await _register(client, "grace@example.com")
        before = len(fake_mailer.verify_emails)

        resp = await client.post(
            SEND_VERIFY,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 200
        assert len(fake_mailer.verify_emails) == before + 1

    async def test_throttled_resend_returns_429(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        tokens = await _register(client, "henry@example.com")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        first = await client.post(SEND_VERIFY, headers=headers)
        second = await client.post(SEND_VERIFY, headers=headers)
        assert first.status_code == 200
        assert second.status_code == 429

    async def test_already_verified_user_gets_message(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        tokens = await _register(client, "ivy@example.com")
        # 先把它验证掉
        token = _token_from(str(fake_mailer.verify_emails[0]["verify_url"]))
        await client.post(VERIFY, json={"token": token})

        # 再调 send-verification 不应发新邮件
        before = len(fake_mailer.verify_emails)
        resp = await client.post(
            SEND_VERIFY,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 200
        assert "已经验证" in resp.json()["message"]
        assert len(fake_mailer.verify_emails) == before

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        resp = await client.post(SEND_VERIFY)
        assert resp.status_code == 401


class TestTokenStorage:
    async def test_verify_token_stored_under_emailverify_purpose(
        self,
        client: AsyncClient,
        fake_mailer: FakeMailer,
        fake_redis: fakeredis.aioredis.FakeRedis,
    ) -> None:
        await _register(client, "jane@example.com")
        token = _token_from(str(fake_mailer.verify_emails[0]["verify_url"]))
        # 必须带 emailverify 前缀, 不能和 pwreset 撞
        assert await fake_redis.exists(f"emailverify:{token}") == 1
        assert await fake_redis.exists(f"pwreset:{token}") == 0
