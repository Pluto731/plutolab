"""User notes — Phase 3.1.

最朴素的 markdown 文本 (列表 + 编辑). 标签 / 全文搜索 / AI 总结
推到 3.1.polish.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from plutolab_api.db.base import Base


class Note(Base):
    __tablename__ = "notes"

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
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
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
        return f"<Note id={self.id} title={self.title!r}>"
