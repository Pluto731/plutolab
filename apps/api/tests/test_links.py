"""Integration tests for /api/v1/links — Phase 3.3."""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from plutolab_api.core.link_metadata import LinkMetadata

REGISTER = "/api/v1/auth/register"
LINKS = "/api/v1/links"


async def _register_and_token(client: AsyncClient, email: str) -> str:
    resp = await client.post(REGISTER, json={"email": email, "password": "supersecret"})
    assert resp.status_code == 201
    return resp.json()["access_token"]


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    token = await _register_and_token(client, email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _mock_fetch_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """禁止测试真去抓 URL — 全部 mock 成固定返回."""

    async def _fake(url: str) -> LinkMetadata:
        return LinkMetadata(
            title=f"Mocked title for {url}",
            description="Mocked description",
            image_url="https://example.com/og.png",
            favicon_url="https://example.com/favicon.ico",
        )

    monkeypatch.setattr(
        "plutolab_api.api.v1.links.fetch_url_metadata", _fake
    )


class TestListAndCreate:
    async def test_list_empty(self, client: AsyncClient) -> None:
        h = await _auth(client, "alice-link@example.com")
        resp = await client.get(LINKS, headers=h)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_returns_link_with_metadata(
        self, client: AsyncClient
    ) -> None:
        h = await _auth(client, "bob-link@example.com")
        resp = await client.post(
            LINKS, headers=h, json={"url": "https://anthropic.com/news/claude"}
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["url"] == "https://anthropic.com/news/claude"
        assert "Mocked title" in body["title"]
        assert body["description"] == "Mocked description"
        assert body["image_url"] == "https://example.com/og.png"
        assert body["favicon_url"] == "https://example.com/favicon.ico"

    async def test_create_invalid_url_rejected(self, client: AsyncClient) -> None:
        h = await _auth(client, "bad-url@example.com")
        resp = await client.post(LINKS, headers=h, json={"url": "not-a-url"})
        assert resp.status_code == 422

    async def test_create_requires_http_scheme(self, client: AsyncClient) -> None:
        h = await _auth(client, "no-scheme@example.com")
        # ftp / 缺 scheme 不接受
        resp = await client.post(LINKS, headers=h, json={"url": "example.com"})
        assert resp.status_code == 422

    async def test_created_appears_in_list(self, client: AsyncClient) -> None:
        h = await _auth(client, "carol-link@example.com")
        await client.post(LINKS, headers=h, json={"url": "https://example.com/1"})
        await client.post(LINKS, headers=h, json={"url": "https://example.com/2"})
        items = (await client.get(LINKS, headers=h)).json()
        assert len(items) == 2
        # 按 created_at desc, 第二个加的在前
        assert items[0]["url"] == "https://example.com/2"


class TestDelete:
    async def test_delete_own(self, client: AsyncClient) -> None:
        h = await _auth(client, "dave-link@example.com")
        created = await client.post(LINKS, headers=h, json={"url": "https://example.com"})
        link_id = created.json()["id"]
        resp = await client.delete(f"{LINKS}/{link_id}", headers=h)
        assert resp.status_code == 204
        assert (await client.get(LINKS, headers=h)).json() == []

    async def test_delete_nonexistent_returns_404(
        self, client: AsyncClient
    ) -> None:
        h = await _auth(client, "erin-link@example.com")
        resp = await client.delete(f"{LINKS}/{uuid4()}", headers=h)
        assert resp.status_code == 404


class TestAuthAndIsolation:
    async def test_requires_authentication(self, client: AsyncClient) -> None:
        assert (await client.get(LINKS)).status_code == 401
        assert (
            await client.post(LINKS, json={"url": "https://example.com"})
        ).status_code == 401
        assert (await client.delete(f"{LINKS}/{uuid4()}")).status_code == 401

    async def test_cannot_see_other_users_links(
        self, client: AsyncClient
    ) -> None:
        alice = await _auth(client, "alice-iso-link@example.com")
        bob = await _auth(client, "bob-iso-link@example.com")
        await client.post(LINKS, headers=alice, json={"url": "https://alice.example.com"})
        assert (await client.get(LINKS, headers=bob)).json() == []

    async def test_cannot_delete_other_users_link(
        self, client: AsyncClient
    ) -> None:
        alice = await _auth(client, "alice-del-link@example.com")
        bob = await _auth(client, "bob-del-link@example.com")
        created = await client.post(
            LINKS, headers=alice, json={"url": "https://alice.example.com"}
        )
        link_id = created.json()["id"]
        resp = await client.delete(f"{LINKS}/{link_id}", headers=bob)
        assert resp.status_code == 404
