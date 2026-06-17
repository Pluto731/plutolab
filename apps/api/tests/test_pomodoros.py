"""Integration tests for /api/v1/pomodoros — Phase 3.4."""

from uuid import uuid4

from httpx import AsyncClient

REGISTER = "/api/v1/auth/register"
POMODOROS = "/api/v1/pomodoros"
TASKS = "/api/v1/tasks"


async def _register_and_token(client: AsyncClient, email: str) -> str:
    resp = await client.post(REGISTER, json={"email": email, "password": "supersecret"})
    assert resp.status_code == 201
    return resp.json()["access_token"]


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    token = await _register_and_token(client, email)
    return {"Authorization": f"Bearer {token}"}


class TestCreate:
    async def test_create_focus_session(self, client: AsyncClient) -> None:
        h = await _auth(client, "alice-pomo@example.com")
        resp = await client.post(
            POMODOROS,
            headers=h,
            json={"kind": "focus", "planned_seconds": 1500},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["kind"] == "focus"
        assert body["planned_seconds"] == 1500
        assert body["task_id"] is None

    async def test_create_short_break(self, client: AsyncClient) -> None:
        h = await _auth(client, "bob-pomo@example.com")
        resp = await client.post(
            POMODOROS,
            headers=h,
            json={"kind": "short_break", "planned_seconds": 300},
        )
        assert resp.json()["kind"] == "short_break"

    async def test_create_with_task(self, client: AsyncClient) -> None:
        h = await _auth(client, "carol-pomo@example.com")
        task = await client.post(TASKS, headers=h, json={"title": "学 LLM"})
        task_id = task.json()["id"]
        resp = await client.post(
            POMODOROS,
            headers=h,
            json={"kind": "focus", "planned_seconds": 1500, "task_id": task_id},
        )
        assert resp.json()["task_id"] == task_id

    async def test_invalid_kind_rejected(self, client: AsyncClient) -> None:
        h = await _auth(client, "bad-kind@example.com")
        resp = await client.post(
            POMODOROS,
            headers=h,
            json={"kind": "lunch_break", "planned_seconds": 600},
        )
        assert resp.status_code == 422

    async def test_seconds_too_short_rejected(self, client: AsyncClient) -> None:
        h = await _auth(client, "short-secs@example.com")
        resp = await client.post(
            POMODOROS, headers=h, json={"kind": "focus", "planned_seconds": 10}
        )
        assert resp.status_code == 422

    async def test_seconds_too_long_rejected(self, client: AsyncClient) -> None:
        h = await _auth(client, "long-secs@example.com")
        resp = await client.post(
            POMODOROS,
            headers=h,
            json={"kind": "focus", "planned_seconds": 100_000},
        )
        assert resp.status_code == 422

    async def test_cannot_use_other_user_task(
        self, client: AsyncClient
    ) -> None:
        alice = await _auth(client, "alice-task-pomo@example.com")
        bob = await _auth(client, "bob-task-pomo@example.com")
        a_task = await client.post(TASKS, headers=alice, json={"title": "A"})
        resp = await client.post(
            POMODOROS,
            headers=bob,
            json={
                "kind": "focus",
                "planned_seconds": 1500,
                "task_id": a_task.json()["id"],
            },
        )
        assert resp.status_code == 404


class TestList:
    async def test_list_empty(self, client: AsyncClient) -> None:
        h = await _auth(client, "list-empty@example.com")
        resp = await client.get(POMODOROS, headers=h)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_returns_today_sessions(
        self, client: AsyncClient
    ) -> None:
        h = await _auth(client, "list-today@example.com")
        for _ in range(3):
            await client.post(
                POMODOROS, headers=h, json={"kind": "focus", "planned_seconds": 1500}
            )
        body = (await client.get(POMODOROS, headers=h)).json()
        assert len(body) == 3
        # 按 completed_at desc, 都是 focus
        assert all(s["kind"] == "focus" for s in body)

    async def test_list_includes_task_title(
        self, client: AsyncClient
    ) -> None:
        h = await _auth(client, "list-title@example.com")
        task = await client.post(TASKS, headers=h, json={"title": "做题"})
        task_id = task.json()["id"]
        await client.post(
            POMODOROS,
            headers=h,
            json={"kind": "focus", "planned_seconds": 1500, "task_id": task_id},
        )
        body = (await client.get(POMODOROS, headers=h)).json()
        assert body[0]["task_title"] == "做题"

    async def test_list_isolated_per_user(self, client: AsyncClient) -> None:
        alice = await _auth(client, "alice-list-pomo@example.com")
        bob = await _auth(client, "bob-list-pomo@example.com")
        await client.post(
            POMODOROS,
            headers=alice,
            json={"kind": "focus", "planned_seconds": 1500},
        )
        assert (await client.get(POMODOROS, headers=bob)).json() == []


class TestAuth:
    async def test_create_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            POMODOROS, json={"kind": "focus", "planned_seconds": 1500}
        )
        assert resp.status_code == 401

    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        assert (await client.get(POMODOROS)).status_code == 401
