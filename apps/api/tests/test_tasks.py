"""Integration tests for /api/v1/tasks (Phase 3.2.a)."""

from uuid import uuid4

from httpx import AsyncClient

REGISTER = "/api/v1/auth/register"
TASKS = "/api/v1/tasks"


async def _register_and_token(client: AsyncClient, email: str) -> str:
    resp = await client.post(REGISTER, json={"email": email, "password": "supersecret"})
    assert resp.status_code == 201
    return resp.json()["access_token"]


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    token = await _register_and_token(client, email)
    return {"Authorization": f"Bearer {token}"}


class TestListAndCreate:
    async def test_list_empty(self, client: AsyncClient) -> None:
        h = await _auth(client, "alice-task@example.com")
        resp = await client.get(TASKS, headers=h)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_returns_task(self, client: AsyncClient) -> None:
        h = await _auth(client, "bob-task@example.com")
        resp = await client.post(TASKS, headers=h, json={"title": "买菜"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "买菜"
        assert body["done"] is False
        assert "id" in body
        assert "created_at" in body

    async def test_created_appears_in_list(self, client: AsyncClient) -> None:
        h = await _auth(client, "carol-task@example.com")
        await client.post(TASKS, headers=h, json={"title": "做饭"})
        items = (await client.get(TASKS, headers=h)).json()
        assert len(items) == 1
        assert items[0]["title"] == "做饭"

    async def test_empty_title_rejected(self, client: AsyncClient) -> None:
        h = await _auth(client, "dave-task@example.com")
        resp = await client.post(TASKS, headers=h, json={"title": ""})
        assert resp.status_code == 422

    async def test_too_long_title_rejected(self, client: AsyncClient) -> None:
        h = await _auth(client, "erin-task@example.com")
        resp = await client.post(TASKS, headers=h, json={"title": "x" * 201})
        assert resp.status_code == 422


class TestUpdate:
    async def test_toggle_done(self, client: AsyncClient) -> None:
        h = await _auth(client, "frank-task@example.com")
        created = await client.post(TASKS, headers=h, json={"title": "T"})
        task_id = created.json()["id"]
        resp = await client.patch(f"{TASKS}/{task_id}", headers=h, json={"done": True})
        assert resp.status_code == 200
        assert resp.json()["done"] is True
        # toggle 回
        resp2 = await client.patch(f"{TASKS}/{task_id}", headers=h, json={"done": False})
        assert resp2.json()["done"] is False

    async def test_rename_title(self, client: AsyncClient) -> None:
        h = await _auth(client, "grace-task@example.com")
        created = await client.post(TASKS, headers=h, json={"title": "旧"})
        task_id = created.json()["id"]
        resp = await client.patch(
            f"{TASKS}/{task_id}", headers=h, json={"title": "新"}
        )
        assert resp.json()["title"] == "新"
        # done 未传, 保持原值
        assert resp.json()["done"] is False

    async def test_patch_nonexistent_returns_404(self, client: AsyncClient) -> None:
        h = await _auth(client, "henry-task@example.com")
        resp = await client.patch(
            f"{TASKS}/{uuid4()}", headers=h, json={"done": True}
        )
        assert resp.status_code == 404


class TestDelete:
    async def test_delete_own_task(self, client: AsyncClient) -> None:
        h = await _auth(client, "iris-task@example.com")
        created = await client.post(TASKS, headers=h, json={"title": "删我"})
        task_id = created.json()["id"]
        resp = await client.delete(f"{TASKS}/{task_id}", headers=h)
        assert resp.status_code == 204
        assert (await client.get(TASKS, headers=h)).json() == []

    async def test_delete_nonexistent_returns_404(self, client: AsyncClient) -> None:
        h = await _auth(client, "jack-task@example.com")
        resp = await client.delete(f"{TASKS}/{uuid4()}", headers=h)
        assert resp.status_code == 404


class TestPriorityAndDueDate:
    async def test_create_default_priority_normal(self, client: AsyncClient) -> None:
        h = await _auth(client, "prio-default@example.com")
        resp = await client.post(TASKS, headers=h, json={"title": "T"})
        body = resp.json()
        assert body["priority"] == "normal"
        assert body["due_date"] is None

    async def test_create_with_priority_high(self, client: AsyncClient) -> None:
        h = await _auth(client, "prio-high@example.com")
        resp = await client.post(
            TASKS, headers=h, json={"title": "T", "priority": "high"}
        )
        assert resp.json()["priority"] == "high"

    async def test_create_invalid_priority_rejected(self, client: AsyncClient) -> None:
        h = await _auth(client, "prio-bad@example.com")
        resp = await client.post(
            TASKS, headers=h, json={"title": "T", "priority": "urgent"}
        )
        assert resp.status_code == 422

    async def test_create_with_due_date(self, client: AsyncClient) -> None:
        h = await _auth(client, "due-create@example.com")
        resp = await client.post(
            TASKS, headers=h, json={"title": "T", "due_date": "2026-12-31"}
        )
        assert resp.json()["due_date"] == "2026-12-31"

    async def test_patch_priority(self, client: AsyncClient) -> None:
        h = await _auth(client, "prio-patch@example.com")
        created = await client.post(TASKS, headers=h, json={"title": "T"})
        task_id = created.json()["id"]
        resp = await client.patch(
            f"{TASKS}/{task_id}", headers=h, json={"priority": "low"}
        )
        assert resp.json()["priority"] == "low"

    async def test_patch_due_date_set(self, client: AsyncClient) -> None:
        h = await _auth(client, "due-patch@example.com")
        created = await client.post(TASKS, headers=h, json={"title": "T"})
        task_id = created.json()["id"]
        resp = await client.patch(
            f"{TASKS}/{task_id}", headers=h, json={"due_date": "2026-07-01"}
        )
        assert resp.json()["due_date"] == "2026-07-01"

    async def test_patch_due_date_clear(self, client: AsyncClient) -> None:
        h = await _auth(client, "due-clear@example.com")
        created = await client.post(
            TASKS, headers=h, json={"title": "T", "due_date": "2026-12-31"}
        )
        task_id = created.json()["id"]
        # 显式传 null 清空
        resp = await client.patch(
            f"{TASKS}/{task_id}", headers=h, json={"due_date": None}
        )
        assert resp.json()["due_date"] is None

    async def test_patch_done_keeps_priority(self, client: AsyncClient) -> None:
        h = await _auth(client, "patch-partial@example.com")
        created = await client.post(
            TASKS, headers=h, json={"title": "T", "priority": "high"}
        )
        task_id = created.json()["id"]
        # 只 PATCH done, priority 应保留
        resp = await client.patch(
            f"{TASKS}/{task_id}", headers=h, json={"done": True}
        )
        body = resp.json()
        assert body["done"] is True
        assert body["priority"] == "high"


class TestAuthAndIsolation:
    async def test_requires_authentication(self, client: AsyncClient) -> None:
        assert (await client.get(TASKS)).status_code == 401
        assert (await client.post(TASKS, json={"title": "x"})).status_code == 401
        assert (await client.patch(f"{TASKS}/{uuid4()}", json={"done": True})).status_code == 401
        assert (await client.delete(f"{TASKS}/{uuid4()}")).status_code == 401

    async def test_cannot_see_other_users_tasks(self, client: AsyncClient) -> None:
        alice = await _auth(client, "alice-iso-task@example.com")
        bob = await _auth(client, "bob-iso-task@example.com")
        await client.post(TASKS, headers=alice, json={"title": "Alice"})
        assert (await client.get(TASKS, headers=bob)).json() == []

    async def test_cannot_update_other_users_task(self, client: AsyncClient) -> None:
        alice = await _auth(client, "alice-upd-task@example.com")
        bob = await _auth(client, "bob-upd-task@example.com")
        created = await client.post(TASKS, headers=alice, json={"title": "A"})
        task_id = created.json()["id"]
        resp = await client.patch(
            f"{TASKS}/{task_id}", headers=bob, json={"done": True}
        )
        assert resp.status_code == 404

    async def test_cannot_delete_other_users_task(self, client: AsyncClient) -> None:
        alice = await _auth(client, "alice-del-task@example.com")
        bob = await _auth(client, "bob-del-task@example.com")
        created = await client.post(TASKS, headers=alice, json={"title": "A"})
        task_id = created.json()["id"]
        resp = await client.delete(f"{TASKS}/{task_id}", headers=bob)
        assert resp.status_code == 404
