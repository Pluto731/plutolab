"""Integration tests for /api/v1/auth (register / login / me)."""

from httpx import AsyncClient

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


async def _register(client: AsyncClient, email: str = "alice@example.com", pw: str = "supersecret") -> dict:
    resp = await client.post(REGISTER, json={"email": email, "password": pw})
    return resp.json()


class TestRegister:
    async def test_register_creates_user_and_returns_tokens(self, client: AsyncClient) -> None:
        resp = await client.post(
            REGISTER, json={"email": "alice@example.com", "password": "supersecret"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["token_type"] == "bearer"
        assert data["access_token"] and data["refresh_token"]
        assert data["user"]["email"] == "alice@example.com"
        assert data["user"]["name"] == "alice"  # defaulted from email local part
        assert data["user"]["email_verified"] is False
        assert "password" not in data["user"]
        assert "password_hash" not in data["user"]

    async def test_register_duplicate_email_conflicts(self, client: AsyncClient) -> None:
        await client.post(REGISTER, json={"email": "dup@example.com", "password": "supersecret"})
        resp = await client.post(
            REGISTER, json={"email": "dup@example.com", "password": "anotherpw1"}
        )
        assert resp.status_code == 409

    async def test_register_rejects_short_password(self, client: AsyncClient) -> None:
        resp = await client.post(REGISTER, json={"email": "x@example.com", "password": "short"})
        assert resp.status_code == 422

    async def test_register_rejects_bad_email(self, client: AsyncClient) -> None:
        resp = await client.post(REGISTER, json={"email": "not-an-email", "password": "supersecret"})
        assert resp.status_code == 422


class TestLogin:
    async def test_login_success(self, client: AsyncClient) -> None:
        await _register(client, "bob@example.com", "mypassword")
        resp = await client.post(LOGIN, json={"email": "bob@example.com", "password": "mypassword"})
        assert resp.status_code == 200
        assert resp.json()["access_token"]

    async def test_login_wrong_password(self, client: AsyncClient) -> None:
        await _register(client, "carol@example.com", "rightpassword")
        resp = await client.post(
            LOGIN, json={"email": "carol@example.com", "password": "wrongpassword"}
        )
        assert resp.status_code == 401

    async def test_login_unknown_email(self, client: AsyncClient) -> None:
        resp = await client.post(LOGIN, json={"email": "ghost@example.com", "password": "whatever1"})
        assert resp.status_code == 401


class TestMe:
    async def test_me_with_valid_token(self, client: AsyncClient) -> None:
        tokens = await _register(client, "dave@example.com", "davepassword")
        resp = await client.get(ME, headers={"Authorization": f"Bearer {tokens['access_token']}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "dave@example.com"

    async def test_me_without_token(self, client: AsyncClient) -> None:
        resp = await client.get(ME)
        assert resp.status_code == 401

    async def test_me_with_invalid_token(self, client: AsyncClient) -> None:
        resp = await client.get(ME, headers={"Authorization": "Bearer not.a.jwt"})
        assert resp.status_code == 401

    async def test_me_rejects_refresh_token(self, client: AsyncClient) -> None:
        tokens = await _register(client, "erin@example.com", "erinpassword")
        resp = await client.get(ME, headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
        assert resp.status_code == 401
