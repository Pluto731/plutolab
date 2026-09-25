"""Single-node acceptance: real DB + mock HTTP, no external Provider calls."""

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.core.crypto import decrypt
from plutolab_api.models.agent_run import AgentRunNode
from plutolab_api.models.note import Note
from plutolab_api.models.user import User
from plutolab_api.models.user_api_key import UserApiKey
from plutolab_api.schemas.agent import ExecutionBudget
from plutolab_api.schemas.agent_run import NodeResult
from plutolab_api.services.agent_execution import execute_node
from plutolab_api.services.agent_provider import OpenAITextProvider, ProviderReply
from plutolab_api.services.agent_runs import (
    RunConflictError,
    RunNotFoundError,
    finish_run,
    get_run,
    start_run,
)
from tests.test_agent_runs import setup_run
from tests.test_agents import local_only as local_only
from tests.test_review_domain import review_engine as review_engine


@pytest_asyncio.fixture
async def review_db(review_engine):
    # The execution service owns real commits/rollbacks; no outer savepoint wrapper.
    async with AsyncSession(review_engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def owners(review_db):
    # Execution owns transactions; retain scalar identities across rollback expiration.
    rows = [User(email=f"{uuid4()}@execution.test") for _ in range(2)]
    review_db.add_all(rows)
    await review_db.flush()
    return tuple(SimpleNamespace(id=row.id) for row in rows)


def completion(text="safe result", *, tool=None, inputs=100, outputs=20):
    message = {"content": text}
    if tool:
        message["tool_calls"] = [{"id": "call_1", "type": "function", "function": tool}]
    return {
        "choices": [{"finish_reason": "tool_calls" if tool else "stop", "message": message}],
        "usage": {"prompt_tokens": inputs, "completion_tokens": outputs},
    }


def provider(handler):
    return OpenAITextProvider(transport=httpx.MockTransport(handler))


async def running(db, owner, **kwargs):
    run, _agent, _workflow = await setup_run(db, owner, **kwargs)
    await start_run(db, owner.id, run.id)
    await db.commit()
    return SimpleNamespace(id=run.id)


async def test_success_encrypts_output_and_prevents_duplicate(review_db, owners, caplog):
    run = await running(review_db, owners[0])
    from plutolab_api.schemas.agent import AgentReplace
    from plutolab_api.services.agent_runs import read_snapshot
    from plutolab_api.services.agents import replace_agent

    original = read_snapshot(await get_run(review_db, owners[0].id, run.id)).agents["a"]
    await replace_agent(
        review_db,
        owners[0].id,
        original.id,
        AgentReplace(
            name="new name",
            role_prompt="CHANGED_AFTER_SNAPSHOT",
            model="gpt-4o-mini",
            expected_version=1,
        ),
    )
    await review_db.commit()
    calls = []

    def handler(req):
        calls.append(req)
        assert str(req.url) == "https://api.openai.com/v1/chat/completions"
        assert req.headers["authorization"] == "Bearer fixture-provider-key-not-secret"
        payload = json.loads(req.content)
        assert payload["store"] is False and payload["max_completion_tokens"] == 2048
        assert payload["messages"][0]["content"] == "PRIVATE_PROMPT"
        return httpx.Response(200, json=completion())

    adapter = provider(handler)
    node = await execute_node(review_db, owners[0].id, run.id, "a", adapter)
    assert node.state == "succeeded" and node.attempts == 1
    assert b"safe result" not in node.output_ciphertext
    assert NodeResult.model_validate_json(decrypt(node.output_ciphertext)).text == "safe result"
    persisted = await get_run(review_db, owners[0].id, run.id)
    assert persisted.charged_tokens == 120 and persisted.charged_cost == 27
    assert persisted.reserved_tokens == 0 and persisted.reserved_cost == 0
    with pytest.raises(RunConflictError):
        await execute_node(review_db, owners[0].id, run.id, "a", adapter)
    assert len(calls) == 1
    assert (await finish_run(review_db, owners[0].id, run.id)).state == "succeeded"
    for secret in (
        "PRIVATE_PROMPT",
        "PRIVATE_INPUT",
        "fixture-provider-key-not-secret",
        "safe result",
    ):
        assert secret not in caplog.text


@pytest.mark.parametrize("mode", ["missing", "wrong_provider", "foreign", "invalid"])
async def test_key_is_owner_scoped_no_fallback(review_db, owners, mode):
    run = await running(review_db, owners[0], key=False)
    if mode != "missing":
        from plutolab_api.core.crypto import encrypt

        review_db.add(
            UserApiKey(
                user_id=owners[1].id if mode == "foreign" else owners[0].id,
                provider="anthropic" if mode == "wrong_provider" else "openai",
                key_ciphertext=b"broken" if mode == "invalid" else encrypt("fake-key"),
                key_preview="fake",
            )
        )
        await review_db.commit()

    def never(req):
        pytest.fail("Missing or wrong credentials must not issue a request")

    node = await execute_node(review_db, owners[0].id, run.id, "a", provider(never))
    assert node.error_code == ("invalid_key" if mode == "invalid" else "missing_key")
    assert node.attempts == 0


async def test_explicit_mock_provider_needs_no_stored_api_key(review_db, owners):
    run = await running(review_db, owners[0], key=False)

    class MockProvider:
        requires_api_key = False

        async def complete(self, request):
            return ProviderReply("本地模拟结果", None, 1, 1)

    node = await execute_node(review_db, owners[0].id, run.id, "a", MockProvider())

    assert node.state == "succeeded"
    assert NodeResult.model_validate_json(decrypt(node.output_ciphertext)).text == "本地模拟结果"


@pytest.mark.parametrize(
    "budget", [ExecutionBudget(max_tokens=1), ExecutionBudget(max_cost_microusd=1)]
)
async def test_budget_preflight_sends_nothing(review_db, owners, budget):
    run = await running(review_db, owners[0], budget=budget)

    def never(req):
        pytest.fail("Budget rejected calls must not leave the process")

    node = await execute_node(review_db, owners[0].id, run.id, "a", provider(never))
    assert node.error_code == "budget_exceeded" and node.attempts == 0
    assert (await get_run(review_db, owners[0].id, run.id)).charged_tokens == 0


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (429, "provider_rate_limit"),
        (503, "provider_unavailable"),
        (401, "provider_auth"),
        (302, "provider_invalid"),
        (400, "provider_invalid"),
    ],
)
async def test_http_failures_are_fixed_codes_and_conservatively_charged(
    review_db, owners, status, code, caplog
):
    run = await running(review_db, owners[0])
    node = await execute_node(
        review_db,
        owners[0].id,
        run.id,
        "a",
        provider(
            lambda req: httpx.Response(
                status,
                text="SECRET_PROVIDER_ERROR",
                headers={"location": "https://example.invalid"},
            )
        ),
    )
    assert node.error_code == code and node.usage_uncertain
    assert node.output_ciphertext is None
    assert (await get_run(review_db, owners[0].id, run.id)).charged_tokens > 2048
    assert "SECRET_PROVIDER_ERROR" not in caplog.text


async def test_transient_retry_is_bounded_and_reserved_again(review_db, owners):
    run = await running(review_db, owners[0], budget=ExecutionBudget(retries=1))
    calls = 0

    def handler(req):
        nonlocal calls
        calls += 1
        return (
            httpx.Response(429, text="error")
            if calls == 1
            else httpx.Response(200, json=completion())
        )

    node = await execute_node(review_db, owners[0].id, run.id, "a", provider(handler))
    assert node.state == "succeeded" and node.attempts == 2 and node.retries == 1
    assert node.usage_uncertain and calls == 2
    assert (await get_run(review_db, owners[0].id, run.id)).charged_tokens > 2048 + 120


@pytest.mark.parametrize(
    "mode",
    [
        "invalid_json",
        "missing_usage",
        "negative_usage",
        "excess_usage",
        "oversize",
        "secret",
        "key",
        "timeout",
    ],
)
async def test_malformed_sensitive_and_timeout_results(review_db, owners, mode):
    run = await running(review_db, owners[0])

    def handler(req):
        if mode == "timeout":
            raise httpx.ReadTimeout("SECRET_TIMEOUT", request=req)
        if mode == "invalid_json":
            return httpx.Response(200, text="not json")
        if mode == "oversize":
            return httpx.Response(200, text="x" * 262145)
        value = completion()
        if mode == "missing_usage":
            del value["usage"]
        if mode == "negative_usage":
            value["usage"]["prompt_tokens"] = -1
        if mode == "excess_usage":
            value["usage"]["completion_tokens"] = 2049
        if mode == "secret":
            value = completion("api_key=must-not-persist")
        if mode == "key":
            value = completion("fixture-provider-key-not-secret")
        return httpx.Response(200, json=value)

    node = await execute_node(review_db, owners[0].id, run.id, "a", provider(handler))
    expected = (
        "provider_timeout"
        if mode == "timeout"
        else "unsafe_output"
        if mode in {"secret", "key"}
        else "budget_exceeded"
        if mode == "excess_usage"
        else "provider_invalid"
    )
    assert node.error_code == expected and node.output_ciphertext is None
    assert node.reserved_tokens == 0


async def test_deadline_and_cancellation_persist_terminal_node(review_db, owners):
    run = await running(review_db, owners[0], budget=ExecutionBudget(node_timeout_seconds=1))

    class Slow:
        async def complete(self, request):
            await asyncio.sleep(5)
            return ProviderReply("late", None, 1, 1)

    node = await execute_node(review_db, owners[0].id, run.id, "a", Slow())
    assert node.error_code == "provider_timeout" and node.usage_uncertain
    run2 = await running(review_db, owners[0])
    entered = asyncio.Event()

    class Wait:
        async def complete(self, request):
            entered.set()
            await asyncio.Event().wait()
            return ProviderReply("never", None, 1, 1)

    task = asyncio.create_task(execute_node(review_db, owners[0].id, run2.id, "a", Wait()))
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    node2 = await review_db.get(AgentRunNode, (run2.id, "a"))
    assert node2.state == "cancelled" and node2.usage_uncertain and node2.reserved_tokens == 0


async def test_direct_predecessor_context_and_owner_denial(review_db, owners):
    run = await running(review_db, owners[0], nodes=("z", "a", "b"), edges=(("z", "b"), ("a", "b")))
    seen = []

    def handler(req):
        seen.append(json.loads(req.content))
        return httpx.Response(200, json=completion(f"output{len(seen)}"))

    adapter = provider(handler)
    with pytest.raises(RunNotFoundError):
        await execute_node(review_db, owners[1].id, run.id, "a", adapter)
    with pytest.raises(RunConflictError):
        await execute_node(review_db, owners[0].id, run.id, "b", adapter)
    for node in ("z", "a", "b"):
        assert (
            await execute_node(review_db, owners[0].id, run.id, node, adapter)
        ).state == "succeeded"
    data = json.loads(seen[-1]["messages"][1]["content"].split("\n", 1)[1])
    assert [item["node_id"] for item in data["upstream"]] == ["a", "z"]
    assert data["text"] == "PRIVATE_INPUT"


@pytest.mark.parametrize("mode", ["success", "unknown", "owner", "loop"])
async def test_read_only_tools(review_db, owners, mode):
    run = await running(review_db, owners[0], tools=("search_notes",))
    review_db.add_all(
        [
            Note(user_id=owners[0].id, title="visible own", content="own data"),
            Note(user_id=owners[1].id, title="visible foreign", content="FOREIGN_DATA"),
        ]
    )
    await review_db.commit()
    calls = []

    def handler(req):
        value = json.loads(req.content)
        calls.append(value)
        if len(calls) == 1 or mode == "loop":
            args = {"query": "visible"}
            if mode == "owner":
                args["user_id"] = str(owners[1].id)
            return httpx.Response(
                200,
                json=completion(
                    None,
                    tool={
                        "name": "shell" if mode == "unknown" else "search_notes",
                        "arguments": json.dumps(args),
                    },
                ),
            )
        return httpx.Response(200, json=completion("done"))

    node = await execute_node(review_db, owners[0].id, run.id, "a", provider(handler))
    if mode == "success":
        assert node.state == "succeeded" and len(calls) == 2
        assert "own data" in calls[1]["messages"][-1]["content"]
        assert "FOREIGN_DATA" not in calls[1]["messages"][-1]["content"]
    else:
        assert node.error_code == ("tool_limit" if mode == "loop" else "tool_failed")
        assert len(calls) == (3 if mode == "loop" else 1)


async def test_parallel_reservations_cannot_overspend(review_engine):
    async with AsyncSession(review_engine, expire_on_commit=False) as db:
        owner = User(email=f"{uuid4()}@budget.test")
        db.add(owner)
        await db.flush()
        run = await running(db, owner, nodes=("a", "b"), budget=ExecutionBudget(max_tokens=4500))
        run_id, owner_id = run.id, owner.id
    entered, release = asyncio.Event(), asyncio.Event()

    class Hold:
        async def complete(self, request):
            entered.set()
            await release.wait()
            return ProviderReply("safe", None, 100, 20)

    async def first():
        async with AsyncSession(review_engine, expire_on_commit=False) as db:
            return await execute_node(db, owner_id, run_id, "a", Hold())

    task = asyncio.create_task(first())
    try:
        await asyncio.wait_for(entered.wait(), 3)
        async with AsyncSession(review_engine, expire_on_commit=False) as db:

            def never(req):
                pytest.fail("Second reservation must fail")

            second = await execute_node(db, owner_id, run_id, "b", provider(never))
            assert second.error_code == "budget_exceeded" and second.attempts == 0
    finally:
        release.set()
        first_node = await task
    assert first_node.state == "succeeded"
    async with AsyncSession(review_engine, expire_on_commit=False) as db:
        run = await finish_run(db, owner_id, run_id)
        assert run.state == "partial" and run.charged_tokens == 120
        await db.commit()


async def test_run_deadline_stops_request_before_network(review_db, owners):
    from datetime import UTC, datetime, timedelta

    run = await running(review_db, owners[0], budget=ExecutionBudget(run_timeout_seconds=1))
    row = await get_run(review_db, owners[0].id, run.id)
    row.started_at = datetime.now(UTC) - timedelta(seconds=2)
    await review_db.commit()

    def never(request):
        pytest.fail("Expired run deadline must not issue a request")

    node = await execute_node(review_db, owners[0].id, run.id, "a", provider(never))
    assert node.error_code == "provider_timeout" and node.attempts == 0


async def test_retry_cannot_exceed_total_budget(review_db, owners):
    run = await running(review_db, owners[0], budget=ExecutionBudget(max_tokens=4500, retries=2))
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(503, text="unavailable")

    node = await execute_node(review_db, owners[0].id, run.id, "a", provider(handler))
    assert calls == 1 and node.attempts == 1
    assert node.error_code == "budget_exceeded" and node.usage_uncertain


async def test_unconfigured_tool_is_never_run(review_db, owners):
    run = await running(review_db, owners[0])

    def handler(request):
        assert "tools" not in json.loads(request.content)
        return httpx.Response(
            200, json=completion(None, tool={"name": "search_notes", "arguments": '{"query":"x"}'})
        )

    node = await execute_node(review_db, owners[0].id, run.id, "a", provider(handler))
    assert node.error_code == "tool_failed"


async def test_unexpected_provider_exception_is_persisted_and_propagated(review_db, owners):
    from plutolab_api.services.agent_provider import ProviderError

    run = await running(review_db, owners[0])

    class Broken:
        async def complete(self, request):
            raise RuntimeError("PRIVATE_INTERNAL_DETAIL")

    with pytest.raises(ProviderError, match=r"^internal_error$") as caught:
        await execute_node(review_db, owners[0].id, run.id, "a", Broken())
    assert isinstance(caught.value.__cause__, RuntimeError)
    row = await review_db.get(AgentRunNode, (run.id, "a"))
    assert row.error_code == "internal_error" and row.usage_uncertain


@pytest.mark.parametrize("mode", ["model", "zero", "too_large", "boolean"])
async def test_adapter_rejects_unapproved_model_or_output_bound(mode):
    from pydantic import SecretStr

    from plutolab_api.services.agent_provider import ProviderError, ProviderRequest

    request = ProviderRequest(
        key=SecretStr("fake"),
        messages=[],
        model="other" if mode == "model" else "gpt-4o-mini",
        max_output_tokens={"zero": 0, "too_large": 16385, "boolean": True}.get(mode, 20),
    )

    def never(req):
        pytest.fail("Invalid requests must be rejected before transport")

    with pytest.raises(ProviderError):
        await provider(never).complete(request)
