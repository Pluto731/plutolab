"""User-owned API keys (Anthropic / OpenAI / Replicate) — Phase 2.5.

Encrypted with Fernet (`core/crypto.py`). `key_preview` stores last 4 chars
of plaintext for UI display — never store plaintext.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, LargeBinary, String, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from plutolab_api.db.base import Base


class UserApiKey(Base):
    __tablename__ = "user_api_keys"

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
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    key_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_preview: Mapped[str] = mapped_column(String(8), nullable=False)
    label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    def __repr__(self) -> str:
        return f"<UserApiKey id={self.id} provider={self.provider} preview={self.key_preview}>"
