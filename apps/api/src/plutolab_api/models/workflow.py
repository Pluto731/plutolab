"""Owner-private Workflow heads and immutable definition revisions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from plutolab_api.db.base import Base


class Workflow(Base):
    __tablename__ = "workflows"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("status IN ('ready', 'archived')", name="valid_status"),
    )
    id: Mapped[UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ready'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class WorkflowRevision(Base):
    __tablename__ = "workflow_revisions"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "length(name) BETWEEN 1 AND 100 AND length(btrim(name)) > 0", name="name_length"
        ),
        CheckConstraint("length(description) <= 2000", name="description_length"),
        CheckConstraint("status IN ('ready', 'archived')", name="valid_status"),
        CheckConstraint(
            "jsonb_typeof(graph) = 'object' AND jsonb_typeof(layout) = 'object'",
            name="json_objects",
        ),
    )
    workflow_id: Mapped[UUID] = mapped_column(
        PG_UUID, ForeignKey("workflows.id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    graph: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    layout: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
