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
from plutolab_api.models.pomodoro import PomodoroSession
from plutolab_api.models.task import Task

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

# 取 dashboard 显示的最近笔记 / 任务条数
RECENT_NOTES_LIMIT = 5
RECENT_TASKS_LIMIT = 5


class ActivityItem(BaseModel):
    kind: str  # "note" | "task" | "rag" | "image" | "agent" | "chat"
    title: str
    timestamp: str  # ISO 8601
    id: str | None = None  # 笔记/任务等可跳转的实体 id (展示性活动可缺省)


class RecentTaskItem(BaseModel):
    """Dashboard TasksCard 用 — 最近未完成任务."""

    id: str
    title: str


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
    pomodoros_today: int  # 3.4: 今天完成的专注番茄数 (短/长休不计)
    recent_activities: list[ActivityItem]
    recent_tasks: list[RecentTaskItem]  # 3.2.a: 最近未完成任务


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
        pomodoros_today=4,
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
        recent_tasks=[
            RecentTaskItem(id="demo-1", title="修 RAG 检索 bug"),
            RecentTaskItem(id="demo-2", title="写 Phase 3 设计文档"),
            RecentTaskItem(id="demo-3", title="整理 LLM 微调笔记"),
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

    # 任务: 未完成数 + 最近 N 条未完成任务
    tasks_count = await db.scalar(
        select(func.count())
        .select_from(Task)
        .where(Task.user_id == user_id, Task.done.is_(False))
    )
    tasks_count = int(tasks_count or 0)

    # 番茄钟: 今天完成的专注番茄数 (短/长休不计)
    today_start = datetime.combine(
        datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC
    )
    pomodoros_today = await db.scalar(
        select(func.count())
        .select_from(PomodoroSession)
        .where(
            PomodoroSession.user_id == user_id,
            PomodoroSession.kind == "focus",
            PomodoroSession.completed_at >= today_start,
        )
    )
    pomodoros_today = int(pomodoros_today or 0)
    # B C-2: dashboard 只展示顶层未完成任务, 避免显示子任务但父任务缺席
    recent_task_rows = await db.scalars(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.done.is_(False),
            Task.parent_id.is_(None),
        )
        .order_by(Task.sort_order.asc(), Task.created_at.desc())
        .limit(RECENT_TASKS_LIMIT)
    )
    recent_tasks = [
        RecentTaskItem(id=str(t.id), title=t.title) for t in recent_task_rows.all()
    ]

    return DashboardSummary(
        is_authenticated=True,
        notes_count=notes_count,
        tasks_count=tasks_count,
        rag_docs_count=0,
        agents_count=0,
        images_count=0,
        tokens_this_month=0,
        tokens_limit=100_000,
        today_words=today_words,
        writing_streak=writing_streak,
        pomodoros_today=pomodoros_today,
        recent_activities=recent_activities,
        recent_tasks=recent_tasks,
    )


@router.get("/summary", response_model=DashboardSummary)
async def summary(user: OptionalUser, db: DbSession) -> DashboardSummary:
    if user is None:
        return _demo_summary()
    return await _real_summary(db, str(user.id))
