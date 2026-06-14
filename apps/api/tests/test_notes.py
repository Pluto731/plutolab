"""Integration tests for /api/v1/notes (Phase 3.1)."""

from uuid import uuid4

from httpx import AsyncClient

from plutolab_api.core.config import settings
from plutolab_api.core.sample_note import SAMPLE_NOTE_TITLE

REGISTER = "/api/v1/auth/register"
NOTES = "/api/v1/notes"
SAMPLE = "/api/v1/notes/sample"


async def _register_and_token(client: AsyncClient, email: str) -> str:
    resp = await client.post(REGISTER, json={"email": email, "password": "supersecret"})
    assert resp.status_code == 201
    return resp.json()["access_token"]


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    token = await _register_and_token(client, email)
    return {"Authorization": f"Bearer {token}"}


class TestListAndCreate:
    async def test_list_empty(self, client: AsyncClient) -> None:
        h = await _auth(client, "alice@example.com")
        resp = await client.get(NOTES, headers=h)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_returns_full_content(self, client: AsyncClient) -> None:
        h = await _auth(client, "bob@example.com")
        resp = await client.post(
            NOTES, headers=h, json={"title": "想法", "content": "今天学了 FastAPI"}
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "想法"
        assert body["content"] == "今天学了 FastAPI"
        assert "id" in body
        assert "created_at" in body
        assert "updated_at" in body

    async def test_create_with_empty_content_defaults_to_blank(
        self, client: AsyncClient
    ) -> None:
        h = await _auth(client, "carol@example.com")
        resp = await client.post(NOTES, headers=h, json={"title": "TODO"})
        assert resp.status_code == 201
        assert resp.json()["content"] == ""

    async def test_created_note_appears_in_list_with_excerpt(
        self, client: AsyncClient
    ) -> None:
        h = await _auth(client, "dave@example.com")
        long_content = "a" * 500
        await client.post(NOTES, headers=h, json={"title": "长文", "content": long_content})
        resp = await client.get(NOTES, headers=h)
        items = resp.json()
        assert len(items) == 1
        assert items[0]["title"] == "长文"
        # 列表只返 excerpt (前 160 字), 不返 content
        assert items[0]["excerpt"] == "a" * 160
        assert "content" not in items[0]

    async def test_list_ordered_by_updated_at_desc(self, client: AsyncClient) -> None:
        """PATCH 一条老笔记后应浮到顶部 — 这是 updated_at desc 真正的语义."""
        import asyncio

        h = await _auth(client, "erin@example.com")
        first = await client.post(NOTES, headers=h, json={"title": "老的"})
        await asyncio.sleep(0.02)  # 让 NOW() 精度区分开
        await client.post(NOTES, headers=h, json={"title": "新的"})
        # 此时排序: ["新的", "老的"]
        items = (await client.get(NOTES, headers=h)).json()
        assert [i["title"] for i in items][0] == "新的"

        # PATCH 老的, 应浮到顶
        await asyncio.sleep(0.02)
        await client.patch(
            f"{NOTES}/{first.json()['id']}", headers=h, json={"content": "改一下"}
        )
        items = (await client.get(NOTES, headers=h)).json()
        assert [i["title"] for i in items] == ["老的", "新的"]

    async def test_empty_title_rejected(self, client: AsyncClient) -> None:
        h = await _auth(client, "frank@example.com")
        resp = await client.post(NOTES, headers=h, json={"title": "", "content": "x"})
        assert resp.status_code == 422

    async def test_too_long_title_rejected(self, client: AsyncClient) -> None:
        h = await _auth(client, "grace@example.com")
        resp = await client.post(NOTES, headers=h, json={"title": "x" * 201})
        assert resp.status_code == 422


class TestGet:
    async def test_get_own_note(self, client: AsyncClient) -> None:
        h = await _auth(client, "henry@example.com")
        created = await client.post(NOTES, headers=h, json={"title": "原文", "content": "正文"})
        note_id = created.json()["id"]
        resp = await client.get(f"{NOTES}/{note_id}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["content"] == "正文"

    async def test_get_nonexistent_returns_404(self, client: AsyncClient) -> None:
        h = await _auth(client, "iris@example.com")
        resp = await client.get(f"{NOTES}/{uuid4()}", headers=h)
        assert resp.status_code == 404


class TestUpdate:
    async def test_patch_title_only(self, client: AsyncClient) -> None:
        h = await _auth(client, "jack@example.com")
        created = await client.post(NOTES, headers=h, json={"title": "旧标题", "content": "正文"})
        note_id = created.json()["id"]
        resp = await client.patch(
            f"{NOTES}/{note_id}", headers=h, json={"title": "新标题"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "新标题"
        assert body["content"] == "正文"  # 没动

    async def test_patch_content_only(self, client: AsyncClient) -> None:
        h = await _auth(client, "kate@example.com")
        created = await client.post(NOTES, headers=h, json={"title": "标题", "content": "旧"})
        note_id = created.json()["id"]
        resp = await client.patch(
            f"{NOTES}/{note_id}", headers=h, json={"content": "新正文"}
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "新正文"

    async def test_patch_can_clear_content_with_empty_string(
        self, client: AsyncClient
    ) -> None:
        h = await _auth(client, "leo@example.com")
        created = await client.post(NOTES, headers=h, json={"title": "T", "content": "有内容"})
        note_id = created.json()["id"]
        resp = await client.patch(f"{NOTES}/{note_id}", headers=h, json={"content": ""})
        assert resp.status_code == 200
        assert resp.json()["content"] == ""

    async def test_patch_nonexistent_returns_404(self, client: AsyncClient) -> None:
        h = await _auth(client, "mia@example.com")
        resp = await client.patch(
            f"{NOTES}/{uuid4()}", headers=h, json={"title": "X"}
        )
        assert resp.status_code == 404


class TestDelete:
    async def test_delete_own_note(self, client: AsyncClient) -> None:
        h = await _auth(client, "nick@example.com")
        created = await client.post(NOTES, headers=h, json={"title": "删我"})
        note_id = created.json()["id"]
        resp = await client.delete(f"{NOTES}/{note_id}", headers=h)
        assert resp.status_code == 204
        assert (await client.get(NOTES, headers=h)).json() == []

    async def test_delete_nonexistent_returns_404(self, client: AsyncClient) -> None:
        h = await _auth(client, "olive@example.com")
        resp = await client.delete(f"{NOTES}/{uuid4()}", headers=h)
        assert resp.status_code == 404


class TestAuthAndIsolation:
    async def test_requires_authentication(self, client: AsyncClient) -> None:
        assert (await client.get(NOTES)).status_code == 401
        assert (await client.post(NOTES, json={"title": "x"})).status_code == 401
        assert (await client.get(f"{NOTES}/{uuid4()}")).status_code == 401
        assert (await client.patch(f"{NOTES}/{uuid4()}", json={"title": "x"})).status_code == 401
        assert (await client.delete(f"{NOTES}/{uuid4()}")).status_code == 401

    async def test_cannot_see_other_users_notes(self, client: AsyncClient) -> None:
        alice = await _auth(client, "alice-iso-note@example.com")
        bob = await _auth(client, "bob-iso-note@example.com")
        await client.post(NOTES, headers=alice, json={"title": "Alice 的笔记"})
        assert (await client.get(NOTES, headers=bob)).json() == []

    async def test_cannot_get_other_users_note(self, client: AsyncClient) -> None:
        alice = await _auth(client, "alice-get-note@example.com")
        bob = await _auth(client, "bob-get-note@example.com")
        created = await client.post(NOTES, headers=alice, json={"title": "Alice"})
        note_id = created.json()["id"]
        # Bob 拿 Alice 的 id 应该 404, 不返 403 (避免暴露 id 存在)
        resp = await client.get(f"{NOTES}/{note_id}", headers=bob)
        assert resp.status_code == 404

    async def test_cannot_update_other_users_note(self, client: AsyncClient) -> None:
        alice = await _auth(client, "alice-upd-note@example.com")
        bob = await _auth(client, "bob-upd-note@example.com")
        created = await client.post(NOTES, headers=alice, json={"title": "Alice"})
        note_id = created.json()["id"]
        resp = await client.patch(
            f"{NOTES}/{note_id}", headers=bob, json={"title": "Hacked"}
        )
        assert resp.status_code == 404

    async def test_cannot_delete_other_users_note(self, client: AsyncClient) -> None:
        alice = await _auth(client, "alice-del-note@example.com")
        bob = await _auth(client, "bob-del-note@example.com")
        created = await client.post(NOTES, headers=alice, json={"title": "Alice"})
        note_id = created.json()["id"]
        resp = await client.delete(f"{NOTES}/{note_id}", headers=bob)
        assert resp.status_code == 404


class TestSampleNote:
    async def test_sample_endpoint_creates_with_expected_title(
        self, client: AsyncClient
    ) -> None:
        h = await _auth(client, "sample-user@example.com")
        resp = await client.post(SAMPLE, headers=h)
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == SAMPLE_NOTE_TITLE
        assert "Markdown" in body["content"]

    async def test_sample_requires_auth(self, client: AsyncClient) -> None:
        assert (await client.post(SAMPLE)).status_code == 401

    async def test_register_seeds_sample_when_onboarding_enabled(
        self, client: AsyncClient, monkeypatch
    ) -> None:
        # 用 monkeypatch 重新打开 onboarding (conftest autouse 默认关掉)
        monkeypatch.setattr(settings, "onboarding_sample_note", True)
        h = await _auth(client, "onboarded@example.com")
        items = (await client.get(NOTES, headers=h)).json()
        assert len(items) == 1
        assert items[0]["title"] == SAMPLE_NOTE_TITLE
