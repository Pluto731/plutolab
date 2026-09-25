"""Owner-scoped Run history/cancellation and event replay API acceptance."""

from sqlalchemy.ext.asyncio import async_sessionmaker

from plutolab_api.api.v1.agent_runs import get_run_sessions
from plutolab_api.models.agent_run import AgentRun
from tests.test_agent_runs import setup_run
from tests.test_agents import agent_client as agent_client
from tests.test_agents import auth as auth
from tests.test_agents import local_only as local_only
from tests.test_review_domain import owners as owners
from tests.test_review_domain import review_db as review_db
from tests.test_review_domain import review_engine as review_engine


async def test_run_create_idempotency_history_cancel_and_sse_replay(
    agent_client, owners, review_db
):
    _seed, _agent, workflow = await setup_run(review_db, owners[0])
    await review_db.commit()
    headers = {**auth(owners[0]), "Idempotency-Key": "create-run-1"}
    path = f"/api/v1/workflows/{workflow.id}/runs"
    payload = {"workflow_version": 1, "text": "private-run-prompt"}
    created = await agent_client.post(path, json=payload, headers=headers)
    assert created.status_code == 202, created.text
    run_id = created.json()["id"]
    repeated = await agent_client.post(path, json=payload, headers=headers)
    assert repeated.status_code == 202 and repeated.json()["id"] == run_id
    changed = await agent_client.post(
        path,
        json={"workflow_version": 1, "text": "different"},
        headers=headers,
    )
    assert changed.status_code == 409
    assert (
        await agent_client.get(f"/api/v1/runs/{run_id}", headers=auth(owners[1]))
    ).status_code == 404

    cancelled = await agent_client.post(f"/api/v1/runs/{run_id}/cancel", headers=auth(owners[0]))
    assert cancelled.status_code == 200 and cancelled.json()["state"] == "cancelled"
    events = await agent_client.get(f"/api/v1/runs/{run_id}/events", headers=auth(owners[0]))
    assert events.status_code == 200
    event_rows = events.json()["items"]
    assert [event["sequence"] for event in event_rows] == list(range(1, len(event_rows) + 1))
    assert [event["event_type"] for event in event_rows][-2:] == [
        "run_cancel_requested",
        "run_finished",
    ]
    assert "private-run-prompt" not in events.text
    assert (
        await agent_client.get(f"/api/v1/runs/{run_id}/events", headers=auth(owners[1]))
    ).status_code == 404

    session_factory = async_sessionmaker(
        bind=review_db.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    agent_client._transport.app.dependency_overrides[get_run_sessions] = lambda: session_factory
    stream = await agent_client.get(
        f"/api/v1/runs/{run_id}/events/stream",
        headers={**auth(owners[0]), "Last-Event-ID": "0"},
    )
    assert stream.status_code == 200
    assert "event: run_cancel_requested" in stream.text and "id: 3" in stream.text
    resumed = await agent_client.get(
        f"/api/v1/runs/{run_id}/events?after=2", headers=auth(owners[0])
    )
    assert [row["sequence"] for row in resumed.json()["items"]] == [3]


async def test_rerun_snapshot_and_latest_are_new_idempotent_runs(agent_client, owners, review_db):
    source, _agent, workflow = await setup_run(review_db, owners[0])
    await review_db.commit()
    source_id, original_ciphertext = source.id, source.snapshot_ciphertext
    headers = {**auth(owners[0]), "Idempotency-Key": "rerun-snapshot-1"}
    path = f"/api/v1/runs/{source_id}/rerun"
    first = await agent_client.post(path, json={"mode": "snapshot"}, headers=headers)
    assert first.status_code == 202, first.text
    duplicate = await agent_client.post(path, json={"mode": "snapshot"}, headers=headers)
    assert duplicate.json()["id"] == first.json()["id"] != str(source_id)
    clone = await review_db.get(AgentRun, first.json()["id"])
    assert clone.snapshot_ciphertext == original_ciphertext
    await agent_client.put(
        f"/api/v1/workflows/{workflow.id}",
        json={
            "name": "flow-v2",
            "description": workflow.description,
            "graph": workflow.graph.model_dump(mode="json"),
            "expected_version": 1,
        },
        headers=auth(owners[0]),
    )
    latest = await agent_client.post(
        path,
        json={"mode": "latest"},
        headers={**auth(owners[0]), "Idempotency-Key": "rerun-latest-1"},
    )
    assert latest.status_code == 202, latest.text
    assert latest.json()["id"] != first.json()["id"]
    assert latest.json()["workflow_version"] == 2
