"""Bounded public repository discovery; no user tokens or arbitrary URL fetching."""

import json
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from urllib.parse import urlencode
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession


class GitHubSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    month: str | None = Field(
        default=None,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="YYYY-MM; omitted means the previous calendar month in UTC",
    )
    keyword: str = Field(default="", max_length=80, pattern=r"^[\w .+#-]*$")
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("month")
    @classmethod
    def valid_month(cls, value: str | None) -> str | None:
        if value is not None:
            date.fromisoformat(f"{value}-01")
        return value


class GitHubRepository(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    full_name: str = Field(max_length=201, pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    url: str = Field(max_length=240)
    description: str = Field(max_length=160)
    stars: int = Field(ge=0)
    created_at: str = Field(max_length=40)


class GitHubSearchOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    month: str
    observed_at: str
    source: str
    metric: Literal[
        "Repositories created in the selected month, ranked by current total stars; not historical Trending or monthly star growth."
    ] = "Repositories created in the selected month, ranked by current total stars; not historical Trending or monthly star growth."
    incomplete_results: bool
    items: list[GitHubRepository] = Field(max_length=10)


async def search_github(
    db: AsyncSession,
    user_id: UUID,
    arguments: GitHubSearchInput,
) -> GitHubSearchOutput:
    now = datetime.now(UTC)
    month = arguments.month or (now.date().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    first = date.fromisoformat(f"{month}-01")
    following = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    last = following - timedelta(days=1)
    # Model input cannot inject search qualifiers, origins, credentials or pagination.
    query = f"created:{first.isoformat()}..{last.isoformat()} fork:false archived:false"
    if arguments.keyword.strip():
        query += f' "{arguments.keyword.strip()}" in:name,description'
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": arguments.limit}
    async with (
        httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False) as client,
        client.stream(
            "GET",
            "https://api.github.com/search/repositories",
            params=params,
            headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        ) as response,
    ):
        response.raise_for_status()
        raw = bytearray()
        async for chunk in response.aiter_bytes(chunk_size=16_384):
            raw.extend(chunk)
            if len(raw) > 262_144:
                raise ValueError("GitHub response exceeds size limit")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("Invalid GitHub response")
    if len(payload["items"]) > arguments.limit:
        raise ValueError("GitHub response exceeds item limit")
    items = []
    for item in payload["items"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid GitHub repository")
        full_name = item.get("full_name")
        description = item.get("description")
        if description is not None and not isinstance(description, str):
            raise ValueError("Invalid repository description")
        items.append(
            GitHubRepository(
                full_name=full_name,
                url=f"https://github.com/{full_name}",
                description=(description or "")[:160],
                stars=item.get("stargazers_count"),
                created_at=item.get("created_at"),
            )
        )
    return GitHubSearchOutput(
        month=month,
        observed_at=now.isoformat(),
        source="https://github.com/search?"
        + urlencode({"q": query, "type": "repositories", "s": "stars", "o": "desc"}),
        incomplete_results=payload.get("incomplete_results"),
        items=items,
    )
