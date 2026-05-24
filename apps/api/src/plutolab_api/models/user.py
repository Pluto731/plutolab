"""User model — minimum viable placeholder for Phase 0.3.b.

Real auth fields land in Phase 2 (account system). For now this exists so we can
verify ORM mapping, migrations, and DB connectivity end-to-end.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from plutolab_api.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(500), nullable=True)
    plan: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'free'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=text("NOW()"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
