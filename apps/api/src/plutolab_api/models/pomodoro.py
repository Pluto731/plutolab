"""PomodoroSession model — Phase 3.4 番茄钟.

只记录"已完成"的会话 — 中途取消的不入库. 字段:
  - kind: focus(专注) / short_break(短休) / long_break(长休)
  - planned_seconds: 计划时长 (25*60 / 5*60 / 15*60)
  - completed_at: 完成时刻 (server clock_timestamp)
  - task_id: 可选关联到任务 (NULL 表示无关联). 任务删除时 SET NULL,
    保留番茄历史 (而非 CASCADE 删历史).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from plutolab_api.db.base import Base


class PomodoroSession(Base):
    __tablename__ = "pomodoro_sessions"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    planned_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("clock_timestamp()"),
    )

    def __repr__(self) -> str:
        return f"<PomodoroSession id={self.id} kind={self.kind}>"
