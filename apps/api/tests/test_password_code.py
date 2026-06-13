"""Integration tests for the code-based password reset flow.

POST /auth/request-password-code  → emails 6-digit code
POST /auth/verify-password-code   → applies the new password if code matches
"""

import fakeredis.aioredis
from httpx import AsyncClient

from tests.conftest import FakeMailer

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
REQUEST_CODE = "/api/v1/auth/request-password-code"
VERIFY_CODE = "/api/v1/auth/verify-password-code"


async def _register(client: AsyncClient, email: str, pw: str) -> None:
    resp = await client.post(REGISTER, json={"email": email, "password": pw})
    assert resp.status_code == 201, resp.text


class TestRequestPasswordCode:
    async def test_known_email_sends_6_digit_code(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        await _register(client, "alice@example.com", "oldpassword")
        resp = await client.post(
            REQUEST_CODE,
            json={"email": "alice@example.com", "password": "newpassword1"},
        )
        assert resp.status_code == 200
        assert len(fake_mailer.code_emails) == 1
        sent = fake_mailer.code_emails[0]
        assert sent["to"] == "alice@example.com"
        code = str(sent["code"])
        assert code.isdigit() and len(code) == 6

    async def test_unknown_email_returns_ok_without_sending(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        resp = await client.post(
            REQUEST_CODE,
            json={"email": "ghost@example.com", "password": "newpassword1"},
        )
        assert resp.status_code == 200
        assert fake_mailer.code_emails == []

    async def test_throttled_second_call_does_not_send(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        await _register(client, "bob@example.com", "oldpassword")
        body = {"email": "bob@example.com", "password": "newpassword1"}
        first = await client.post(REQUEST_CODE, json=body)
        second = await client.post(REQUEST_CODE, json=body)
        assert first.status_code == 200
        assert second.status_code == 200
        assert len(fake_mailer.code_emails) == 1

    async def test_rejects_short_password(self, client: AsyncClient) -> None:
        resp = await client.post(
            REQUEST_CODE, json={"email": "carol@example.com", "password": "short"}
        )
        assert resp.status_code == 422

    async def test_rejects_bad_email(self, client: AsyncClient) -> None:
        resp = await client.post(
            REQUEST_CODE, json={"email": "not-an-email", "password": "newpassword1"}
        )
        assert resp.status_code == 422


class TestVerifyPasswordCode:
    async def test_valid_code_changes_password(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        await _register(client, "dave@example.com", "oldpassword")
        await client.post(
            REQUEST_CODE,
            json={"email": "dave@example.com", "password": "newpassword1"},
        )
        code = str(fake_mailer.code_emails[0]["code"])

        resp = await client.post(
            VERIFY_CODE, json={"email": "dave@example.com", "code": code}
        )
        assert resp.status_code == 200

        # 旧密码失效
        old = await client.post(
            LOGIN, json={"email": "dave@example.com", "password": "oldpassword"}
        )
        assert old.status_code == 401
        # 新密码可用
        new = await client.post(
            LOGIN, json={"email": "dave@example.com", "password": "newpassword1"}
        )
        assert new.status_code == 200

    async def test_wrong_code_returns_400(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        await _register(client, "erin@example.com", "oldpassword")
        await client.post(
            REQUEST_CODE,
            json={"email": "erin@example.com", "password": "newpassword1"},
        )
        resp = await client.post(
            VERIFY_CODE, json={"email": "erin@example.com", "code": "000000"}
        )
        assert resp.status_code == 400

    async def test_too_many_wrong_attempts_invalidates(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        await _register(client, "fiona@example.com", "oldpassword")
        await client.post(
            REQUEST_CODE,
            json={"email": "fiona@example.com", "password": "newpassword1"},
        )
        # 错 3 次, 第 4 次连正确码都失败
        for _ in range(3):
            await client.post(
                VERIFY_CODE, json={"email": "fiona@example.com", "code": "000000"}
            )
        good_code = str(fake_mailer.code_emails[0]["code"])
        resp = await client.post(
            VERIFY_CODE, json={"email": "fiona@example.com", "code": good_code}
        )
        assert resp.status_code == 400
        assert "次数过多" in resp.json()["detail"]

    async def test_code_is_one_shot(
        self, client: AsyncClient, fake_mailer: FakeMailer
    ) -> None:
        await _register(client, "grace@example.com", "oldpassword")
        await client.post(
            REQUEST_CODE,
            json={"email": "grace@example.com", "password": "newpassword1"},
        )
        code = str(fake_mailer.code_emails[0]["code"])
        first = await client.post(
            VERIFY_CODE, json={"email": "grace@example.com", "code": code}
        )
        second = await client.post(
            VERIFY_CODE, json={"email": "grace@example.com", "code": code}
        )
        assert first.status_code == 200
        assert second.status_code == 400

    async def test_rejects_non_digit_code(self, client: AsyncClient) -> None:
        resp = await client.post(
            VERIFY_CODE, json={"email": "x@example.com", "code": "abcdef"}
        )
        assert resp.status_code == 422

    async def test_no_request_yet_returns_400(self, client: AsyncClient) -> None:
        resp = await client.post(
            VERIFY_CODE, json={"email": "nobody@example.com", "code": "123456"}
        )
        assert resp.status_code == 400


class TestStorage:
    async def test_redis_key_uses_correct_prefix(
        self,
        client: AsyncClient,
        fake_mailer: FakeMailer,
        fake_redis: fakeredis.aioredis.FakeRedis,
    ) -> None:
        await _register(client, "henry@example.com", "oldpassword")
        await client.post(
            REQUEST_CODE,
            json={"email": "henry@example.com", "password": "newpassword1"},
        )
        # 凭证存在 pwresetcode:{email} 下
        assert await fake_redis.exists("pwresetcode:henry@example.com") == 1
