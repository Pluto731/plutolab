"""Owner-private Agent definitions; credentials are resolved only at execution time."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from plutolab_api.db.base import Base


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("status IN ('active', 'archived')", name="valid_status"),
        CheckConstraint("length(btrim(name)) BETWEEN 1 AND 100", name="name_length"),
        CheckConstraint("length(description) <= 2000", name="description_length"),
        CheckConstraint(
            "length(role_prompt) BETWEEN 1 AND 16000 AND length(btrim(role_prompt)) > 0",
            name="prompt_length",
        ),
        CheckConstraint("provider = 'openai' AND model = 'gpt-4o-mini'", name="model_catalog"),
        CheckConstraint(
            "tools IN ('[]'::jsonb, '[\"search_notes\"]'::jsonb, '[\"search_github\"]'::jsonb, "
            '\'["search_notes", "search_github"]\'::jsonb, '
            '\'["search_github", "search_notes"]\'::jsonb)',
            name="registered_tools",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    role_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tools: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=text("NOW()"),
    )
