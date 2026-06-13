"""Integration tests for /api/v1/auth/forgot-password + /reset-password."""

import fakeredis.aioredis
from httpx import AsyncClient

from tests.conftest import FakeMailer

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
FORGOT = "/api/v1/auth/forgot-password"
RESET = "/api/v1/auth/reset-password"

_OK_MESSAGE = "如果该邮箱已注册，我们已发送重置链接，请查收。"


async def _register(client: AsyncClient, email: str, pw: str) -> None:
    resp = await client.post(REGISTER, json={"email": email, "password": pw})
    assert resp.status_code == 201, resp.text


def _token_from(reset_url: str) -> str:
    # reset_url 形如 http://.../reset-password?token=xxxx
    return reset_url.split("token=", 1)[1]


class TestForgotPassword:
    async def test_known_email_sends_mail_and_returns_generic_ok(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        await _register(client, "alice@example.com", "originalpw")
        resp = await client.post(FORGOT, json={"email": "alice@example.com"})
        assert resp.status_code == 200
        assert resp.json()["message"] == _OK_MESSAGE
        assert len(fake_mailer.reset_emails) == 1
        sent = fake_mailer.reset_emails[0]
        assert sent["to"] == "alice@example.com"
        assert "token=" in str(sent["reset_url"])

    async def test_unknown_email_returns_ok_but_does_not_send(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        resp = await client.post(FORGOT, json={"email": "ghost@example.com"})
        assert resp.status_code == 200
        assert resp.json()["message"] == _OK_MESSAGE
        assert fake_mailer.reset_emails == []

    async def test_oauth_only_user_returns_ok_but_does_not_send(
        self,
        client: AsyncClient,
        fake_mailer: FakeMailer,
        db_session,
    ) -> None:
        # 直接造一个只有 github_id、没有 password_hash 的用户
        from plutolab_api.models.user import User

        user = User(email="ghuser@example.com", github_id=999_999, name="gh")
        db_session.add(user)
        await db_session.commit()

        resp = await client.post(FORGOT, json={"email": "ghuser@example.com"})
        assert resp.status_code == 200
        assert fake_mailer.reset_emails == []

    async def test_throttled_second_call_does_not_send(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        await _register(client, "bob@example.com", "originalpw")
        first = await client.post(FORGOT, json={"email": "bob@example.com"})
        second = await client.post(FORGOT, json={"email": "bob@example.com"})
        assert first.status_code == 200
        assert second.status_code == 200
        # 第二次被静默限流, mailer 不会再收到
        assert len(fake_mailer.reset_emails) == 1

    async def test_rejects_bad_email_format(self, client: AsyncClient) -> None:
        resp = await client.post(FORGOT, json={"email": "not-an-email"})
        assert resp.status_code == 422


class TestResetPassword:
    async def test_valid_token_resets_password_and_allows_login(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        await _register(client, "carol@example.com", "oldpassword")
        await client.post(FORGOT, json={"email": "carol@example.com"})
        token = _token_from(str(fake_mailer.reset_emails[0]["reset_url"]))

        resp = await client.post(RESET, json={"token": token, "password": "newpassword1"})
        assert resp.status_code == 200

        # 旧密码失效
        old_login = await client.post(
            LOGIN, json={"email": "carol@example.com", "password": "oldpassword"}
        )
        assert old_login.status_code == 401
        # 新密码可用
        new_login = await client.post(
            LOGIN, json={"email": "carol@example.com", "password": "newpassword1"}
        )
        assert new_login.status_code == 200

    async def test_token_is_one_shot(self, client: AsyncClient, fake_mailer: FakeMailer) -> None:
        await _register(client, "dave@example.com", "oldpassword")
        await client.post(FORGOT, json={"email": "dave@example.com"})
        token = _token_from(str(fake_mailer.reset_emails[0]["reset_url"]))

        ok = await client.post(RESET, json={"token": token, "password": "newpassword1"})
        replay = await client.post(RESET, json={"token": token, "password": "thirdpassword1"})
        assert ok.status_code == 200
        assert replay.status_code == 400

    async def test_invalid_token_rejected(self, client: AsyncClient) -> None:
        resp = await client.post(
            RESET, json={"token": "nope-not-a-real-token", "password": "newpassword1"}
        )
        assert resp.status_code == 400

    async def test_rejects_short_password(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        await _register(client, "erin@example.com", "oldpassword")
        await client.post(FORGOT, json={"email": "erin@example.com"})
        token = _token_from(str(fake_mailer.reset_emails[0]["reset_url"]))

        resp = await client.post(RESET, json={"token": token, "password": "short"})
        assert resp.status_code == 422
        # token 未被消费 (校验失败发生在更早阶段) — 这里我们只断言返回码
        # 注意: pydantic 校验先于 consume, 所以 token 仍然有效


class TestForgotPasswordResetUrl:
    async def test_reset_url_uses_configured_base(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        from plutolab_api.core.config import settings

        await _register(client, "fiona@example.com", "originalpw")
        await client.post(FORGOT, json={"email": "fiona@example.com"})
        url = str(fake_mailer.reset_emails[0]["reset_url"])
        assert url.startswith(settings.app_base_url.rstrip("/") + "/reset-password?token=")


class TestTokenIsolation:
    async def test_token_stored_under_pwreset_purpose(
        self,
        client: AsyncClient,
        fake_mailer: FakeMailer,
        fake_redis: fakeredis.aioredis.FakeRedis,
    ) -> None:
        await _register(client, "grace@example.com", "originalpw")
        await client.post(FORGOT, json={"email": "grace@example.com"})
        token = _token_from(str(fake_mailer.reset_emails[0]["reset_url"]))
        # Redis key 必须带 purpose 前缀, 防止跨用途重放
        assert await fake_redis.exists(f"pwreset:{token}") == 1
