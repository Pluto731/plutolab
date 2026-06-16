"""Task model — Phase 3.2.a 任务 MVP.

最朴素的 todo: title + done. 优先级 / 截止日期 / 子任务推到 3.2.b/c.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, Date, Float, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from plutolab_api.db.base import Base


class Task(Base):
    __tablename__ = "tasks"

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
    # C-2: 父任务 id (子任务嵌套). 父删时 CASCADE 删子. 顶层任务 parent_id = NULL.
    parent_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    done: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # B: low / normal / high (用 String 不用 Enum, migration 简单)
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'normal'")
    )
    # B: 截止日期 (可空)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # C-1: 手动排序权重. 新建时取 MIN(existing) - 1 让新任务在顶部.
    # reorder API bulk 写时按数组顺序 0, 1, 2, ...
    sort_order: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("clock_timestamp()"),
        onupdate=text("clock_timestamp()"),
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id} done={self.done} title={self.title!r}>"
