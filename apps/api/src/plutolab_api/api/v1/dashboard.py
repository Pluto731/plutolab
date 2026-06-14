"""Dashboard summary endpoint.

Adapts to login state:
  - Anonymous → demo data so the marketing/landing dashboard preview looks
    populated (HR / 访客 view).
  - Authenticated → real counts. Phase 3 笔记 已接真数据, Phase 4 / 7 仍为 0
    占位; 真实聚合 (RAG/Agent/图像) 等对应 Phase 落地后接入.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.api.deps import OptionalUser
from plutolab_api.db.deps import get_db
from plutolab_api.models.note import Note

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

# 取 dashboard 显示的最近笔记条数
RECENT_NOTES_LIMIT = 5


class ActivityItem(BaseModel):
    kind: str  # "note" | "task" | "rag" | "image" | "agent" | "chat"
    title: str
    timestamp: str  # ISO 8601
    id: str | None = None  # 笔记/任务等可跳转的实体 id (展示性活动可缺省)


class DashboardSummary(BaseModel):
    is_authenticated: bool
    notes_count: int
    tasks_count: int
    rag_docs_count: int
    agents_count: int
    images_count: int
    tokens_this_month: int
    tokens_limit: int
    today_words: int  # 今天编辑/创建过的笔记 content 字符合计
    writing_streak: int  # 从今天往前推, 连续有笔记 updated 的天数
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
        today_words=1_240,
        writing_streak=5,
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


def _compute_streak(updated_dates: list[datetime]) -> int:
    """从最新一条 updated_at 往前推, 连续 (按日历日) 有笔记的天数.

    规则: 如果最新一条不是今天/昨天 → streak = 0 (链条断了, 不算).
    如果最新一条是今天 → 起点 = 今天, 否则 = 昨天 (允许"今天还没写但昨天写过").
    依次往前找连续每天都有笔记.
    """
    if not updated_dates:
        return 0
    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    days = {d.date() for d in updated_dates}
    if today in days:
        cursor = today
    elif yesterday in days:
        cursor = yesterday
    else:
        return 0
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


async def _real_summary(db: AsyncSession, user_id: str) -> DashboardSummary:
    """已登录: 笔记接真表数据, 其他 Phase 未落地保持 0 占位."""
    # 笔记总数
    notes_count = await db.scalar(
        select(func.count()).select_from(Note).where(Note.user_id == user_id)
    )
    notes_count = int(notes_count or 0)

    # 最近 N 条笔记 (按 updated_at desc) → recent_activities
    recent_rows = await db.scalars(
        select(Note)
        .where(Note.user_id == user_id)
        .order_by(Note.updated_at.desc())
        .limit(RECENT_NOTES_LIMIT)
    )
    recent_notes = list(recent_rows.all())
    recent_activities = [
        ActivityItem(
            kind="note",
            id=str(n.id),
            title=n.title,
            timestamp=n.updated_at.isoformat(),
        )
        for n in recent_notes
    ]

    # 今日字数: 今天 updated 过的笔记 content 长度合计
    today_start = datetime.combine(
        datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC
    )
    today_rows = await db.scalars(
        select(Note)
        .where(Note.user_id == user_id, Note.updated_at >= today_start)
    )
    today_words = sum(len(n.content or "") for n in today_rows.all())

    # 连续写作天数: 取所有 updated_at 算
    all_rows = await db.scalars(
        select(Note.updated_at).where(Note.user_id == user_id)
    )
    writing_streak = _compute_streak(list(all_rows.all()))

    return DashboardSummary(
        is_authenticated=True,
        notes_count=notes_count,
        tasks_count=0,
        rag_docs_count=0,
        agents_count=0,
        images_count=0,
        tokens_this_month=0,
        tokens_limit=100_000,
        today_words=today_words,
        writing_streak=writing_streak,
        recent_activities=recent_activities,
    )


@router.get("/summary", response_model=DashboardSummary)
async def summary(user: OptionalUser, db: DbSession) -> DashboardSummary:
    if user is None:
        return _demo_summary()
    return await _real_summary(db, str(user.id))
