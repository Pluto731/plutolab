"""Phase 6 local full flow through authenticated APIs, outbox, mock worker and SSE."""

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker

from plutolab_api.api.v1.agent_runs import get_run_sessions
from plutolab_api.core.crypto import encrypt
from plutolab_api.models.user_api_key import UserApiKey
from plutolab_api.services.agent_provider import OpenAITextProvider
from plutolab_api.services.agent_run_queue import (
    RunMessage,
    RunReceipt,
    dispatch_due,
    process_run_receipt,
)
from tests.test_agent_contracts import definition
from tests.test_agents import agent_client as agent_client
from tests.test_agents import auth as auth
from tests.test_agents import local_only as local_only
from tests.test_review_domain import owners as owners
from tests.test_review_domain import review_db as review_db
from tests.test_review_domain import review_engine as review_engine


class MemoryBroker:
    def __init__(self):
        self.messages = []
        self.acked = []

    async def publish(self, message):
        self.messages.append(message)
        return "1"

    async def receive(self):
        return None

    async def acknowledge(self, receipt):
        self.acked.append(receipt.receipt_id)


async def test_agent_workflow_run_worker_events_history_and_snapshot_rerun(
    agent_client, owners, review_db
):
    user = owners[0]
    headers = auth(user)
    other_headers = auth(owners[1])
    agent = await agent_client.post(
        "/api/v1/agents",
        json=definition(role_prompt="用证据总结输入，不编造来源。"),
        headers=headers,
    )
    assert agent.status_code == 201, agent.text
    workflow = await agent_client.post(
        "/api/v1/workflows",
        json={
            "name": "全链路验收",
            "graph": {
                "nodes": [
                    {
                        "id": "research",
                        "agent_id": agent.json()["id"],
                        "agent_version": 1,
                    }
                ],
                "edges": [],
            },
            "layout": {},
        },
        headers=headers,
    )
    assert workflow.status_code == 201, workflow.text
    review_db.add(
        UserApiKey(
            user_id=user.id,
            provider="openai",
            key_ciphertext=encrypt("fixture-e2e-key"),
            key_preview="test",
        )
    )
    await review_db.commit()
    created = await agent_client.post(
        f"/api/v1/workflows/{workflow.json()['id']}/runs",
        json={"workflow_version": 1, "text": "private e2e input"},
        headers={**headers, "Idempotency-Key": "phase6-e2e-run"},
    )
    assert created.status_code == 202, created.text
    run_id = created.json()["id"]

    sessions = async_sessionmaker(
        bind=review_db.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    broker = MemoryBroker()
    async with sessions() as db:
        assert await dispatch_due(db, broker) == 1
    assert broker.messages == [RunMessage(run_id=run_id)]

    def complete(_request):
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": "e2e safe result"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            },
        )

    receipt = RunReceipt("e2e-receipt", broker.messages[0])
    state = await process_run_receipt(
        sessions, broker, receipt, OpenAITextProvider(transport=httpx.MockTransport(complete))
    )
    assert state == "succeeded" and broker.acked == ["e2e-receipt"]
    review_db.expire_all()

    detail = await agent_client.get(f"/api/v1/runs/{run_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["state"] == "succeeded"
    assert detail.json()["nodes"][0]["output"] == "e2e safe result"
    assert "private e2e input" not in detail.text and "fixture-e2e-key" not in detail.text
    assert (await agent_client.get("/api/v1/runs", headers=headers)).json()["total"] == 1
    assert (
        await agent_client.get(f"/api/v1/runs/{run_id}", headers=other_headers)
    ).status_code == 404

    events = await agent_client.get(f"/api/v1/runs/{run_id}/events", headers=headers)
    assert [event["sequence"] for event in events.json()["items"]] == [1, 2, 3, 4]
    agent_client._transport.app.dependency_overrides[get_run_sessions] = lambda: sessions
    replay = await agent_client.get(
        f"/api/v1/runs/{run_id}/events/stream",
        headers={**headers, "Last-Event-ID": "2"},
    )
    assert replay.status_code == 200 and "id: 3" in replay.text and "id: 4" in replay.text
    assert "private e2e input" not in replay.text and "e2e safe result" not in replay.text

    rerun = await agent_client.post(
        f"/api/v1/runs/{run_id}/rerun",
        json={"mode": "snapshot"},
        headers={**headers, "Idempotency-Key": "phase6-e2e-rerun"},
    )
    assert rerun.status_code == 202 and rerun.json()["id"] != run_id
