"""Phase 6 contracts. Definitions only; no provider or tool execution."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AgentState = Literal["active", "archived"]
WorkflowState = Literal["draft", "ready", "archived"]
RunState = Literal["pending", "running", "succeeded", "partial", "failed", "cancelled"]
NodeState = Literal["pending", "running", "succeeded", "failed", "skipped", "cancelled"]
Version = Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
NodeId = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")]

# Local compatibility catalog, based on the existing chat adapter, not a live model listing.
MODEL_CATALOG: dict[str, tuple[str, ...]] = {"openai": ("gpt-4o-mini",)}
TOOL_IDS: frozenset[str] = frozenset({"search_notes"})


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentDefinition(Contract):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    role_prompt: str = Field(min_length=1, max_length=16000, repr=False)
    provider: Literal["openai"] = "openai"
    model: str = Field(min_length=1, max_length=100)
    tools: list[str] = Field(default_factory=list, max_length=16)

    @field_validator("name", "role_prompt")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("Must contain non-whitespace text without NUL")
        return value

    @field_validator("description")
    @classmethod
    def no_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("NUL is not permitted")
        return value

    @model_validator(mode="after")
    def allowed_configuration(self) -> "AgentDefinition":
        if self.model not in MODEL_CATALOG[self.provider]:
            raise ValueError("Model is not in the local compatibility catalog")
        if len(self.tools) != len(set(self.tools)) or not set(self.tools) <= TOOL_IDS:
            raise ValueError("Tools must be unique and explicitly registered")
        return self


class AgentCreate(AgentDefinition):
    pass


class AgentReplace(AgentDefinition):
    expected_version: Version


class AgentPublic(AgentDefinition):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    version: Version
    status: AgentState
    created_at: datetime
    updated_at: datetime


class AgentPage(Contract):
    items: list[AgentPublic]
    total: int = Field(ge=0)


class WorkflowNode(Contract):
    id: NodeId
    agent_id: UUID
    agent_version: Version
    label: str = Field(default="", max_length=100)


class WorkflowEdge(Contract):
    source: NodeId
    target: NodeId


class WorkflowGraph(Contract):
    nodes: list[WorkflowNode] = Field(min_length=1, max_length=32)
    edges: list[WorkflowEdge] = Field(default_factory=list, max_length=128)

    @model_validator(mode="after")
    def references(self) -> "WorkflowGraph":
        ids = {node.id for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("Node IDs must be unique")
        pairs = {(edge.source, edge.target) for edge in self.edges}
        if len(pairs) != len(self.edges):
            raise ValueError("Duplicate edges are not permitted")
        if any(a not in ids or b not in ids or a == b for a, b in pairs):
            raise ValueError("Edges must reference distinct existing nodes")
        return self


class ExecutionBudget(Contract):
    parallelism: int = Field(default=4, strict=True, ge=1, le=4)
    node_timeout_seconds: int = Field(default=60, strict=True, ge=1, le=120)
    run_timeout_seconds: int = Field(default=600, strict=True, ge=1, le=600)
    max_tokens: int = Field(default=32000, strict=True, ge=1, le=32000)
    max_cost_microusd: int = Field(default=1_000_000, strict=True, ge=1, le=1_000_000)
    retries: int = Field(default=0, strict=True, ge=0, le=2)


class NodeOutput(Contract):
    node_id: NodeId
    text: str = Field(max_length=32000, repr=False)


class NodeInput(Contract):
    text: str = Field(max_length=16000, repr=False)
    upstream: list[NodeOutput] = Field(default_factory=list, max_length=32, repr=False)

    @model_validator(mode="after")
    def bounded_context(self) -> "NodeInput":
        ids = [item.node_id for item in self.upstream]
        if len(ids) != len(set(ids)):
            raise ValueError("Upstream node IDs must be unique")
        if sum(len(item.text) for item in self.upstream) + len(self.text) > 64000:
            raise ValueError("Combined context exceeds 64000 characters")
        return self


class ExecutionPolicy(Contract):
    failure_policy: Literal["fail_fast"] = "fail_fast"
    rerun_policy: Literal["original_snapshot"] = "original_snapshot"
    budget: ExecutionBudget = Field(default_factory=ExecutionBudget)


class ExecutionStatus(Contract):
    workflow: WorkflowState
    run: RunState
    node: NodeState
