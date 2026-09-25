"""Versioned Workflow definitions; layout is presentation data, never executable."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from plutolab_api.schemas.agent import Contract, NodeId, Version, WorkflowGraph
from plutolab_api.services.workflow_graph import plan_layers


class Position(Contract):
    x: float = Field(ge=-10000, le=10000, allow_inf_nan=False)
    y: float = Field(ge=-10000, le=10000, allow_inf_nan=False)


class WorkflowCreate(Contract):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    graph: WorkflowGraph
    layout: dict[NodeId, Position] = Field(default_factory=dict, max_length=32)

    @field_validator("name", "description")
    @classmethod
    def text_fields(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("NUL is forbidden")
        return value

    @model_validator(mode="after")
    def valid_graph(self) -> "WorkflowCreate":
        if not self.name.strip():
            raise ValueError("Name must not be blank")
        plan_layers(self.graph)
        if not self.layout.keys() <= {node.id for node in self.graph.nodes}:
            raise ValueError("Layout must reference graph nodes")
        return self


class WorkflowReplace(WorkflowCreate):
    expected_version: Version


class WorkflowPublic(WorkflowCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    version: Version
    status: Literal["ready", "archived"]
    created_at: datetime
    updated_at: datetime


class WorkflowPage(Contract):
    items: list[WorkflowPublic]
    total: int


class WorkflowTemplateSummary(Contract):
    slug: str = Field(pattern=r"^[a-z0-9-]{1,64}$")
    version: Version
    name: str = Field(max_length=100)
    description: str = Field(max_length=500)
    required_tools: list[str] = Field(max_length=16)


class WorkflowTemplatePage(Contract):
    items: list[WorkflowTemplateSummary] = Field(max_length=20)


class WorkflowTemplateImport(Contract):
    name: str | None = Field(default=None, min_length=1, max_length=100)
