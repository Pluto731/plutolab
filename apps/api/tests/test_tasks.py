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


class TestSortOrder:
    async def test_new_task_goes_to_top(self, client: AsyncClient) -> None:
        h = await _auth(client, "sort-top@example.com")
        # 创建 3 个任务, 依次按时间顺序
        for title in ["第一", "第二", "第三"]:
            await client.post(TASKS, headers=h, json={"title": title})
        items = (await client.get(TASKS, headers=h)).json()
        # 最新建的 "第三" 在顶 (sort_order 最小)
        titles = [t["title"] for t in items]
        assert titles == ["第三", "第二", "第一"]
        # sort_order 严格递增
        orders = [t["sort_order"] for t in items]
        assert orders == sorted(orders)

    async def test_reorder_bulk(self, client: AsyncClient) -> None:
        h = await _auth(client, "sort-bulk@example.com")
        created_ids = []
        for title in ["A", "B", "C"]:
            r = await client.post(TASKS, headers=h, json={"title": title})
            created_ids.append(r.json()["id"])
        # 当前顺序: C, B, A (新的在顶). 反转成 A, B, C.
        reordered = [created_ids[0], created_ids[1], created_ids[2]]  # A, B, C
        resp = await client.post(
            f"{TASKS}/reorder", headers=h, json={"ids": reordered}
        )
        assert resp.status_code == 204
        items = (await client.get(TASKS, headers=h)).json()
        assert [t["title"] for t in items] == ["A", "B", "C"]

    async def test_reorder_rejects_other_user_id(self, client: AsyncClient) -> None:
        alice = await _auth(client, "alice-reorder@example.com")
        bob = await _auth(client, "bob-reorder@example.com")
        a_task = (await client.post(TASKS, headers=alice, json={"title": "A"})).json()
        b_task = (await client.post(TASKS, headers=bob, json={"title": "B"})).json()
        # bob 试图 reorder 中混 alice 的 id 应 404
        resp = await client.post(
            f"{TASKS}/reorder",
            headers=bob,
            json={"ids": [b_task["id"], a_task["id"]]},
        )
        assert resp.status_code == 404

    async def test_reorder_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(f"{TASKS}/reorder", json={"ids": [str(uuid4())]})
        assert resp.status_code == 401


class TestSubtasks:
    async def test_create_subtask(self, client: AsyncClient) -> None:
        h = await _auth(client, "sub-create@example.com")
        parent = await client.post(TASKS, headers=h, json={"title": "父"})
        parent_id = parent.json()["id"]
        sub = await client.post(
            TASKS,
            headers=h,
            json={"title": "子", "parent_id": parent_id},
        )
        assert sub.status_code == 201
        assert sub.json()["parent_id"] == parent_id

    async def test_top_task_parent_id_is_null(self, client: AsyncClient) -> None:
        h = await _auth(client, "top-null@example.com")
        resp = await client.post(TASKS, headers=h, json={"title": "顶层"})
        assert resp.json()["parent_id"] is None

    async def test_subtask_cannot_have_subtask(self, client: AsyncClient) -> None:
        h = await _auth(client, "sub-nested@example.com")
        parent = await client.post(TASKS, headers=h, json={"title": "父"})
        parent_id = parent.json()["id"]
        sub = await client.post(
            TASKS, headers=h, json={"title": "子", "parent_id": parent_id}
        )
        sub_id = sub.json()["id"]
        # 子任务再加子 应 400
        resp = await client.post(
            TASKS, headers=h, json={"title": "孙", "parent_id": sub_id}
        )
        assert resp.status_code == 400

    async def test_cannot_use_other_user_parent_id(
        self, client: AsyncClient
    ) -> None:
        alice = await _auth(client, "alice-parent@example.com")
        bob = await _auth(client, "bob-parent@example.com")
        a_parent = await client.post(TASKS, headers=alice, json={"title": "Alice 父"})
        resp = await client.post(
            TASKS,
            headers=bob,
            json={"title": "Bob 子", "parent_id": a_parent.json()["id"]},
        )
        assert resp.status_code == 404

    async def test_delete_parent_cascades_subtasks(
        self, client: AsyncClient
    ) -> None:
        h = await _auth(client, "sub-cascade@example.com")
        parent = await client.post(TASKS, headers=h, json={"title": "父"})
        parent_id = parent.json()["id"]
        await client.post(
            TASKS, headers=h, json={"title": "子 1", "parent_id": parent_id}
        )
        await client.post(
            TASKS, headers=h, json={"title": "子 2", "parent_id": parent_id}
        )
        before = (await client.get(TASKS, headers=h)).json()
        assert len(before) == 3  # 父 + 2 子
        await client.delete(f"{TASKS}/{parent_id}", headers=h)
        after = (await client.get(TASKS, headers=h)).json()
        assert after == []  # CASCADE 删了子任务

    async def test_subtask_sort_order_appends_to_end(
        self, client: AsyncClient
    ) -> None:
        h = await _auth(client, "sub-sort@example.com")
        parent = await client.post(TASKS, headers=h, json={"title": "父"})
        parent_id = parent.json()["id"]
        for title in ["子A", "子B", "子C"]:
            await client.post(
                TASKS,
                headers=h,
                json={"title": title, "parent_id": parent_id},
            )
        items = (await client.get(TASKS, headers=h)).json()
        subs = sorted(
            (t for t in items if t["parent_id"] == parent_id),
            key=lambda t: t["sort_order"],
        )
        assert [t["title"] for t in subs] == ["子A", "子B", "子C"]


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
