"""add tasks.parent_id self FK CASCADE (subtasks)

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_tasks_parent_id", "tasks", ["parent_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_parent_id", table_name="tasks")
    op.drop_column("tasks", "parent_id")
