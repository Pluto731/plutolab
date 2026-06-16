"""add tasks.sort_order column

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "sort_order",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    # 给现有任务一个初始 sort_order: 按 created_at desc 排, 最新的 sort_order 最小 (顶部)
    # PG 不能在 ALTER 后直接 UPDATE 使用 ROW_NUMBER 简洁, 用 CTE.
    op.execute(
        """
        WITH ordered AS (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY user_id ORDER BY created_at DESC
            ) AS rn
            FROM tasks
        )
        UPDATE tasks SET sort_order = ordered.rn::float
        FROM ordered
        WHERE tasks.id = ordered.id
        """
    )


def downgrade() -> None:
    op.drop_column("tasks", "sort_order")
