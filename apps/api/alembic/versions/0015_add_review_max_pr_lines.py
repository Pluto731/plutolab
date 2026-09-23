"""Persist optional per-repository PR line cap; preserve legacy uncapped rules."""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("review_settings", sa.Column("max_pr_lines", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f("ck_review_settings_max_pr_lines_valid"),
        "review_settings",
        "max_pr_lines IS NULL OR max_pr_lines >= min_pr_lines",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_review_settings_max_pr_lines_valid"), "review_settings", type_="check"
    )
    op.drop_column("review_settings", "max_pr_lines")
