"""Pure definition and future execution contracts, with no execution implementation."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from plutolab_api.schemas.agent import (
    AgentCreate,
    AgentReplace,
    ExecutionBudget,
    ExecutionPolicy,
    ExecutionStatus,
    NodeInput,
    WorkflowGraph,
)


def definition(**changes: object) -> dict[str, object]:
    return {"name": "研究员", "role_prompt": "只总结输入资料", "model": "gpt-4o-mini", **changes}


def test_valid_definition_and_sensitive_repr():
    body = AgentCreate.model_validate(definition())
    assert body.tools == []
    assert body.provider == "openai"
    assert body.role_prompt not in repr(body)
    assert ExecutionPolicy().failure_policy == "fail_fast"


@pytest.mark.parametrize(
    "changes",
    [
        {"name": " "},
        {"name": "a" * 101},
        {"role_prompt": "\n"},
        {"role_prompt": "x" * 16001},
        {"role_prompt": "bad\x00text"},
        {"description": "x" * 2001},
        {"description": "\x00"},
        {"model": "unregistered"},
        {"provider": "anthropic"},
        {"tools": ["shell"]},
        {"tools": ["search_notes", "search_notes"]},
        {"tools": ["a", "a"]},
        {"api_key": "SECRET"},
        {"owner_id": str(uuid4())},
        {"key_ciphertext": "SECRET"},
        {"status": "archived"},
        {"version": 1},
        {"name": 42},
        {"tools": None},
    ],
)
def test_invalid_definition(changes):
    with pytest.raises(ValidationError):
        AgentCreate.model_validate(definition(**changes))


@pytest.mark.parametrize("version", [0, -1, True, "1", 1.5, 2_147_483_648])
def test_version_is_strict_and_bounded(version):
    with pytest.raises(ValidationError):
        AgentReplace.model_validate(definition(expected_version=version))


@pytest.mark.parametrize(
    "changes",
    [
        {"parallelism": 5},
        {"parallelism": True},
        {"max_tokens": 32001},
        {"max_cost_microusd": 1_000_001},
        {"retries": 3},
        {"node_timeout_seconds": 121},
        {"run_timeout_seconds": 601},
        {"max_tokens": 0},
    ],
)
def test_budget_limits(changes):
    with pytest.raises(ValidationError):
        ExecutionBudget.model_validate(changes)


@pytest.mark.parametrize("field", ["workflow", "run", "node"])
def test_invalid_status(field):
    value = {"workflow": "draft", "run": "pending", "node": "pending", field: "invalid"}
    with pytest.raises(ValidationError):
        ExecutionStatus.model_validate(value)


def test_graph_contract_rejects_invalid_references_and_size():
    node = {"id": "a", "agent_id": str(uuid4()), "agent_version": 1}
    assert WorkflowGraph.model_validate({"nodes": [node]}).nodes[0].id == "a"
    invalid = [
        {"nodes": []},
        {"nodes": [node, node]},
        {"nodes": [node], "edges": [{"source": "a", "target": "missing"}]},
        {"nodes": [node], "edges": [{"source": "a", "target": "a"}]},
        {"nodes": [{**node, "id": str(i)} for i in range(33)]},
        {"nodes": [node], "edges": [{"source": "a", "target": "b"}] * 129},
    ]
    for value in invalid:
        with pytest.raises(ValidationError):
            WorkflowGraph.model_validate(value)


def test_context_is_bounded_and_unique():
    assert NodeInput(text="输入").upstream == []
    for upstream in [
        [{"node_id": "a", "text": "x"}] * 2,
        [{"node_id": str(i), "text": "x" * 32000} for i in range(3)],
    ]:
        with pytest.raises(ValidationError):
            NodeInput(text="input", upstream=upstream)
    with pytest.raises(ValidationError):
        ExecutionPolicy(failure_policy="continue")
