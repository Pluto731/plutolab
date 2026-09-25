"""Private encrypted run payloads and bounded execution contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from plutolab_api.schemas.agent import (
    AgentCreate,
    Contract,
    ExecutionPolicy,
    NodeId,
    RunState,
    Version,
    WorkflowGraph,
)
from plutolab_api.services.workflow_graph import plan_layers

ErrorCode = Literal[
    "missing_key",
    "invalid_key",
    "unsupported_model",
    "budget_exceeded",
    "provider_timeout",
    "provider_rate_limit",
    "provider_unavailable",
    "provider_auth",
    "provider_invalid",
    "unsafe_output",
    "tool_failed",
    "tool_limit",
    "cancelled",
    "dependency_failed",
    "internal_error",
]


class PriceCard(Contract):
    catalog: Literal["openai-text-2026-09-24"] = "openai-text-2026-09-24"
    input_microusd_per_million: Literal[150000] = 150000
    output_microusd_per_million: Literal[600000] = 600000


class AgentSnapshot(AgentCreate):
    id: UUID
    version: Version


class RunSnapshot(Contract):
    graph: WorkflowGraph
    agents: dict[NodeId, AgentSnapshot] = Field(max_length=32, repr=False)
    text: str = Field(max_length=16000, repr=False)
    policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    price: PriceCard = Field(default_factory=PriceCard)

    @model_validator(mode="after")
    def consistent(self) -> "RunSnapshot":
        plan_layers(self.graph)
        if self.agents.keys() != {n.id for n in self.graph.nodes}:
            raise ValueError("Snapshot must cover exactly the graph nodes")
        if any(
            self.agents[n.id].id != n.agent_id or self.agents[n.id].version != n.agent_version
            for n in self.graph.nodes
        ):
            raise ValueError("Agent snapshot reference mismatch")
        return self


class RunCreate(Contract):
    workflow_version: Version
    text: str = Field(max_length=16000, repr=False)
    policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)


class RunRerun(Contract):
    mode: Literal["snapshot", "latest"]


class RunCheckpoint(Contract):
    completed_node_ids: list[NodeId] = Field(default_factory=list, max_length=32)


class NodeResult(Contract):
    text: str = Field(max_length=32000, repr=False)


class RunSummary(Contract):
    id: UUID
    workflow_id: UUID
    workflow_version: int
    state: RunState
    created_at: datetime
    finished_at: datetime | None = None


class RunNodeView(Contract):
    node_id: NodeId
    state: Literal["pending", "running", "succeeded", "failed", "skipped", "cancelled"]
    error_code: ErrorCode | None = None
    output: str | None = Field(default=None, repr=False)
    attempts: int
    retries: int


class RunDetail(RunSummary):
    cancel_requested: bool
    event_sequence: int
    checkpoint: RunCheckpoint
    charged_tokens: int
    charged_cost_microusd: int
    graph: WorkflowGraph
    nodes: list[RunNodeView] = Field(max_length=32)


class RunPage(Contract):
    items: list[RunSummary] = Field(max_length=100)
    total: int


class RunEventView(Contract):
    sequence: int
    event_type: Literal[
        "run_started",
        "run_cancel_requested",
        "run_finished",
        "node_started",
        "node_finished",
        "node_skipped",
    ]
    node_id: NodeId | None = None
    state: Literal["pending", "running", "succeeded", "partial", "failed", "cancelled", "skipped"]
    summary: str | None = Field(default=None, max_length=256)
    created_at: datetime


class RunEventPage(Contract):
    items: list[RunEventView] = Field(max_length=128)
    oldest_sequence: int
    latest_sequence: int
