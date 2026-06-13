"""Dashboard summary endpoint.

Adapts to login state:
  - Anonymous → demo data so the marketing/landing dashboard preview looks
    populated (HR / 访客 view).
  - Authenticated → real counts. Phase 3 / 4 / 7 are not built yet, so counts
    are all zero for now; real aggregation hooks in as those phases land.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel

from plutolab_api.api.deps import OptionalUser

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class ActivityItem(BaseModel):
    kind: str  # "note" | "task" | "rag" | "image" | "agent" | "chat"
    title: str
    timestamp: str  # ISO 8601


class DashboardSummary(BaseModel):
    is_authenticated: bool
    notes_count: int
    tasks_count: int
    rag_docs_count: int
    agents_count: int
    images_count: int
    tokens_this_month: int
    tokens_limit: int
    recent_activities: list[ActivityItem]


def _demo_summary() -> DashboardSummary:
    """Marketing-friendly demo payload for guest viewers."""
    now = datetime.now(UTC)
    return DashboardSummary(
        is_authenticated=False,
        notes_count=42,
        tasks_count=7,
        rag_docs_count=12,
        agents_count=3,
        images_count=24,
        tokens_this_month=18_400,
        tokens_limit=100_000,
        recent_activities=[
            ActivityItem(
                kind="note",
                title="LLM 微调实验笔记",
                timestamp=(now - timedelta(minutes=5)).isoformat(),
            ),
            ActivityItem(
                kind="rag",
                title="GPT-4 技术报告.pdf",
                timestamp=(now - timedelta(hours=1)).isoformat(),
            ),
            ActivityItem(
                kind="image",
                title="cyberpunk cat · 第 3 版",
                timestamp=(now - timedelta(hours=3)).isoformat(),
            ),
            ActivityItem(
                kind="agent",
                title="周报总结 Agent",
                timestamp=(now - timedelta(hours=8)).isoformat(),
            ),
        ],
    )


def _real_summary() -> DashboardSummary:
    """Authenticated payload. All zeros until Phase 3/4/7 land."""
    return DashboardSummary(
        is_authenticated=True,
        notes_count=0,
        tasks_count=0,
        rag_docs_count=0,
        agents_count=0,
        images_count=0,
        tokens_this_month=0,
        tokens_limit=100_000,
        recent_activities=[],
    )


@router.get("/summary", response_model=DashboardSummary)
async def summary(user: OptionalUser) -> DashboardSummary:
    return _real_summary() if user is not None else _demo_summary()
