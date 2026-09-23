"""Validated payloads rendered for the GitHub review publication boundary."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PublicationComment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    path: str = Field(min_length=1, max_length=4096)
    line: int = Field(gt=0)
    side: Literal["LEFT", "RIGHT"]
    position: int = Field(gt=0)
    body: str = Field(min_length=1, max_length=6000)


class PublicationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    marker: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=60_000)
    comments: tuple[PublicationComment, ...] = Field(max_length=100)
    finding_count: int = Field(ge=0)
    inline_count: int = Field(ge=0)
    omitted_inline_count: int = Field(ge=0)
    status: Literal["published", "partially_published"]


class RemotePublication(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, strict=True)

    id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    body: str = ""
