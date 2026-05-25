"""Integration tests for /api/v1/users (profile + password)."""

from httpx import AsyncClient

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/users/me"
PASSWORD = "/api/v1/users/me/password"


async def _auth_headers(client: AsyncClient, email: str, password: str = "supersecret") -> dict:
    resp = await client.post(REGISTER, json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestUpdateProfile:
    async def test_update_name(self, client: AsyncClient) -> None:
        headers = await _auth_headers(client, "u1@example.com")
        resp = await client.patch(ME, json={"name": "新昵称"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "新昵称"

    async def test_update_name_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.patch(ME, json={"name": "x"})
        assert resp.status_code == 401

    async def test_update_name_rejects_empty(self, client: AsyncClient) -> None:
        headers = await _auth_headers(client, "u2@example.com")
        resp = await client.patch(ME, json={"name": ""}, headers=headers)
        assert resp.status_code == 422


class TestChangePassword:
    async def test_change_password_success(self, client: AsyncClient) -> None:
        headers = await _auth_headers(client, "p1@example.com", "oldpassword")
        resp = await client.post(
            PASSWORD,
            json={"current_password": "oldpassword", "new_password": "newpassword1"},
            headers=headers,
        )
        assert resp.status_code == 204

        old = await client.post(LOGIN, json={"email": "p1@example.com", "password": "oldpassword"})
        assert old.status_code == 401
        new = await client.post(LOGIN, json={"email": "p1@example.com", "password": "newpassword1"})
        assert new.status_code == 200

    async def test_change_password_wrong_current(self, client: AsyncClient) -> None:
        headers = await _auth_headers(client, "p2@example.com", "rightpassword")
        resp = await client.post(
            PASSWORD,
            json={"current_password": "wrongpassword", "new_password": "newpassword1"},
            headers=headers,
        )
        assert resp.status_code == 400

    async def test_change_password_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            PASSWORD, json={"current_password": "a", "new_password": "newpassword1"}
        )
        assert resp.status_code == 401

    async def test_change_password_rejects_short(self, client: AsyncClient) -> None:
        headers = await _auth_headers(client, "p3@example.com")
        resp = await client.post(
            PASSWORD,
            json={"current_password": "supersecret", "new_password": "short"},
            headers=headers,
        )
        assert resp.status_code == 422
