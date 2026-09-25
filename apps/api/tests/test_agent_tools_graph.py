"""Graph planning and adversarial tool execution boundaries."""

import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from plutolab_api.schemas.agent import WorkflowGraph
from plutolab_api.services import agent_tools as tools
from plutolab_api.services.workflow_graph import plan_layers


def graph(nodes, edges=()):
    return WorkflowGraph.model_validate(
        {
            "nodes": [{"id": n, "agent_id": uuid4(), "agent_version": 1} for n in nodes],
            "edges": [{"source": a, "target": b} for a, b in edges],
        }
    )


@pytest.mark.parametrize(
    ("nodes", "edges", "expected"),
    [
        (["a"], [], (("a",),)),
        (["z", "b", "a", "c"], [("a", "c"), ("b", "c")], (("a", "b", "z"), ("c",))),
        (["c", "b", "a"], [("a", "b"), ("b", "c")], (("a",), ("b",), ("c",))),
        ([str(i) for i in range(32)], [], (tuple(sorted(str(i) for i in range(32))),)),
    ],
)
def test_layers(nodes, edges, expected):
    assert plan_layers(graph(nodes, edges)) == expected
    assert plan_layers(graph(list(reversed(nodes)), list(reversed(edges)))) == expected


@pytest.mark.parametrize(
    ("nodes", "edges"),
    [
        ([], []),
        (["a", "a"], []),
        (["a"], [("a", "x")]),
        (["a"], [("a", "a")]),
        (["a", "b"], [("a", "b"), ("a", "b")]),
        ([str(i) for i in range(33)], []),
    ],
)
def test_bad_structure(nodes, edges):
    with pytest.raises(ValidationError):
        graph(nodes, edges)


def test_cycle_and_mutation():
    with pytest.raises(ValueError, match="acyclic"):
        plan_layers(graph(["a", "b", "z"], [("a", "b"), ("b", "a")]))
    value = graph(["a"])
    value.nodes.clear()
    with pytest.raises(ValidationError):
        plan_layers(value)


@pytest.mark.parametrize(
    "arguments",
    [
        {"query": "x", "user_id": str(uuid4())},
        {"query": "x", "owner": "fake"},
        {"query": " "},
        {"query": "x", "limit": 21},
        {"query": "x", "limit": True},
        {"query": "x", "limit": "2"},
        {"query": "x" * 201},
    ],
)
async def test_invalid_arguments(arguments):
    with pytest.raises(tools.ToolExecutionError, match=r"^invalid_arguments$"):
        await tools.execute_tool(
            "search_notes", arguments, db=None, user_id=uuid4(), enabled_tools=("search_notes",)
        )


@pytest.mark.parametrize(("name", "enabled"), [("shell", ("shell",)), ("search_notes", ())])
async def test_not_allowed(name, enabled):
    with pytest.raises(tools.ToolExecutionError, match="tool_not_allowed"):
        await tools.execute_tool(
            name, {"query": "x"}, db=None, user_id=uuid4(), enabled_tools=enabled
        )


@pytest.mark.parametrize("mode", ["ok", "secret", "error", "timeout", "size"])
async def test_execution(monkeypatch, mode):
    owner = uuid4()

    async def handler(db, user_id, arguments):
        assert user_id == owner
        assert arguments.query == "x"
        if mode == "error":
            raise RuntimeError("PRIVATE_PROVIDER_KEY")
        if mode == "timeout":
            await asyncio.sleep(1)
        return tools.SearchOutput(
            items=[
                tools.SearchItem(
                    id=uuid4(), title="t", excerpt="api_key=secret" if mode == "secret" else "safe"
                )
            ]
        )

    definition = replace(
        tools.REGISTRY["search_notes"],
        executor=handler,
        timeout_seconds=0.01,
        max_result_bytes=1 if mode == "size" else 16384,
    )
    monkeypatch.setattr(tools, "REGISTRY", {"search_notes": definition})
    if mode == "ok":
        result = await tools.execute_tool(
            "search_notes", {"query": "x"}, db=None, user_id=owner, enabled_tools=("search_notes",)
        )
        assert result.items[0].excerpt == "safe"
    else:
        code = {
            "secret": "unsafe_output",
            "error": "tool_failed",
            "timeout": "tool_timeout",
            "size": "unsafe_output",
        }[mode]
        with pytest.raises(tools.ToolExecutionError, match=f"^{code}$"):
            await tools.execute_tool(
                "search_notes",
                {"query": "x"},
                db=None,
                user_id=owner,
                enabled_tools=("search_notes",),
            )


def test_edge_budget_boundary():
    nodes = [str(i) for i in range(32)]
    edges = [(str(a), str(b)) for a in range(32) for b in range(a + 1, 32)]
    assert sum(map(len, plan_layers(graph(nodes, edges[:128])))) == 32
    with pytest.raises(ValidationError):
        graph(nodes, edges[:129])
