"""Integration tests for /api/v1/users/me/api-keys (Phase 2.5)."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.core.crypto import decrypt
from plutolab_api.models.user_api_key import UserApiKey

REGISTER = "/api/v1/auth/register"
KEYS = "/api/v1/users/me/api-keys"


async def _register_and_token(client: AsyncClient, email: str) -> str:
    resp = await client.post(REGISTER, json={"email": email, "password": "supersecret"})
    assert resp.status_code == 201
    return resp.json()["access_token"]


class TestListAndCreate:
    async def test_list_empty(self, client: AsyncClient) -> None:
        token = await _register_and_token(client, "alice@example.com")
        resp = await client.get(KEYS, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_returns_preview_not_ciphertext(
        self, client: AsyncClient
    ) -> None:
        token = await _register_and_token(client, "bob@example.com")
        resp = await client.post(
            KEYS,
            headers={"Authorization": f"Bearer {token}"},
            json={"provider": "anthropic", "key": "sk-ant-test-key-AB12CD34", "label": "dev"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["provider"] == "anthropic"
        assert body["key_preview"] == "CD34"
        assert body["label"] == "dev"
        # 不应回明文或 ciphertext
        assert "key" not in body
        assert "key_ciphertext" not in body

    async def test_created_key_appears_in_list(self, client: AsyncClient) -> None:
        token = await _register_and_token(client, "carol@example.com")
        h = {"Authorization": f"Bearer {token}"}
        await client.post(
            KEYS, headers=h, json={"provider": "openai", "key": "sk-test-AAAA1234"}
        )
        resp = await client.get(KEYS, headers=h)
        items = resp.json()
        assert len(items) == 1
        assert items[0]["provider"] == "openai"
        assert items[0]["key_preview"] == "1234"

    async def test_invalid_provider_rejected(self, client: AsyncClient) -> None:
        token = await _register_and_token(client, "dave@example.com")
        resp = await client.post(
            KEYS,
            headers={"Authorization": f"Bearer {token}"},
            json={"provider": "azure", "key": "sk-test-abcdef"},
        )
        assert resp.status_code == 422

    async def test_short_key_rejected(self, client: AsyncClient) -> None:
        token = await _register_and_token(client, "erin@example.com")
        resp = await client.post(
            KEYS,
            headers={"Authorization": f"Bearer {token}"},
            json={"provider": "anthropic", "key": "short"},
        )
        assert resp.status_code == 422

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        list_resp = await client.get(KEYS)
        post_resp = await client.post(
            KEYS, json={"provider": "anthropic", "key": "sk-ant-test-key"}
        )
        assert list_resp.status_code == 401
        assert post_resp.status_code == 401


class TestEncryption:
    async def test_plaintext_actually_encrypted_in_db(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        token = await _register_and_token(client, "fiona@example.com")
        plain = "sk-ant-secret-very-long-key-XYZW9876"
        await client.post(
            KEYS,
            headers={"Authorization": f"Bearer {token}"},
            json={"provider": "anthropic", "key": plain},
        )
        # DB 里直接读, 必须看不到明文
        row = await db_session.scalar(select(UserApiKey).limit(1))
        assert row is not None
        assert plain.encode() not in row.key_ciphertext
        # 但能 Fernet 解回原文
        assert decrypt(row.key_ciphertext) == plain


class TestIsolationAndDelete:
    async def test_cannot_see_other_users_keys(self, client: AsyncClient) -> None:
        alice_token = await _register_and_token(client, "alice-iso@example.com")
        bob_token = await _register_and_token(client, "bob-iso@example.com")
        await client.post(
            KEYS,
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"provider": "anthropic", "key": "sk-alice-12345"},
        )
        # Bob 看自己的 keys 列表应该是空
        bob_list = await client.get(KEYS, headers={"Authorization": f"Bearer {bob_token}"})
        assert bob_list.json() == []

    async def test_delete_own_key(self, client: AsyncClient) -> None:
        token = await _register_and_token(client, "grace@example.com")
        h = {"Authorization": f"Bearer {token}"}
        created = await client.post(
            KEYS, headers=h, json={"provider": "anthropic", "key": "sk-grace-12345"}
        )
        key_id = created.json()["id"]
        resp = await client.delete(f"{KEYS}/{key_id}", headers=h)
        assert resp.status_code == 204
        # 删完列表为空
        assert (await client.get(KEYS, headers=h)).json() == []

    async def test_cannot_delete_other_users_key(self, client: AsyncClient) -> None:
        alice_token = await _register_and_token(client, "alice-del@example.com")
        bob_token = await _register_and_token(client, "bob-del@example.com")
        created = await client.post(
            KEYS,
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"provider": "anthropic", "key": "sk-alice-12345"},
        )
        key_id = created.json()["id"]
        # Bob 拿 Alice 的 key_id 尝试删
        resp = await client.delete(
            f"{KEYS}/{key_id}", headers={"Authorization": f"Bearer {bob_token}"}
        )
        assert resp.status_code == 404
