"""add notes.tags array column

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notes",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    # GIN 索引让 ?tag= 过滤 (Note.tags.any(t)) 走索引
    op.create_index(
        "ix_notes_tags_gin", "notes", ["tags"], postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_notes_tags_gin", table_name="notes")
    op.drop_column("notes", "tags")
