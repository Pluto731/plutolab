"""Server-owned read-only tools. Caller supplies authenticated identity, never model arguments."""

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.models.note import Note


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("Invalid query")
        return value


class SearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    title: str = Field(max_length=200)
    excerpt: str = Field(max_length=160)


class SearchOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[SearchItem] = Field(max_length=20)


async def _notes(db: AsyncSession, user_id: UUID, arguments: SearchInput) -> SearchOutput:
    pattern = f"%{arguments.query.strip()}%"
    result = await db.scalars(
        select(Note)
        .where(
            Note.user_id == user_id,
            (Note.title.ilike(pattern)) | (Note.content.ilike(pattern)),
        )
        .order_by(Note.updated_at.desc())
        .limit(arguments.limit)
    )
    notes = result.all()
    return SearchOutput(
        items=[
            SearchItem(id=note.id, title=note.title, excerpt=note.content[:160]) for note in notes
        ]
    )


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    executor: Callable[[AsyncSession, UUID, SearchInput], Awaitable[SearchOutput]]
    permission: Literal["read"] = "read"
    timeout_seconds: float = 5
    max_result_bytes: int = 16_384
    input_model: type[SearchInput] = SearchInput
    output_model: type[SearchOutput] = SearchOutput


REGISTRY = MappingProxyType(
    {
        "search_notes": ToolDefinition("search_notes", "搜索本人的笔记，返回标题及短摘要", _notes),
    }
)
# Conservative fail-closed detection of common credential formats, not general DLP.
_SECRET = re.compile(
    r"sk-[a-zA-Z0-9_-]{12,}|gh[pousr]_[a-zA-Z0-9]{16,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|bearer\s+\S+|"
    r"(?:api[_ -]?key|password|secret|token|ciphertext)\s*[\"']?\s*[:=]",
    re.IGNORECASE,
)


def contains_sensitive_text(value: str) -> bool:
    return _SECRET.search(value) is not None


class ToolExecutionError(Exception):
    """Public error code only; provider/user text is never reflected."""


async def execute_tool(
    name: str,
    arguments: object,
    *,
    db: AsyncSession,
    user_id: UUID,
    enabled_tools: tuple[str, ...],
) -> SearchOutput:
    definition = REGISTRY.get(name)
    if definition is None or name not in enabled_tools:
        raise ToolExecutionError("tool_not_allowed")
    if not isinstance(user_id, UUID):
        raise ToolExecutionError("invalid_identity")
    try:
        parsed = definition.input_model.model_validate(arguments)
    except ValidationError as exc:
        raise ToolExecutionError("invalid_arguments") from exc
    try:
        async with asyncio.timeout(definition.timeout_seconds):
            result = await definition.executor(db, user_id, parsed)
        result = definition.output_model.model_validate(result.model_dump())
        raw = result.model_dump_json()
        if len(raw.encode()) > definition.max_result_bytes or contains_sensitive_text(raw):
            raise ToolExecutionError("unsafe_output")
        return result
    except ToolExecutionError:
        raise
    except TimeoutError as exc:
        raise ToolExecutionError("tool_timeout") from exc
    except Exception as exc:
        raise ToolExecutionError("tool_failed") from exc
