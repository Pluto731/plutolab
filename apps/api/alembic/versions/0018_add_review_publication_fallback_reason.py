"""Persist the exact inline-review 422 fallback reason."""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "review_jobs",
        sa.Column("publication_fallback_reason", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_review_jobs_publication_fallback_reason_valid"),
        "review_jobs",
        "publication_fallback_reason IS NULL OR "
        "publication_fallback_reason IN ('diff_position_mismatch')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_review_jobs_publication_fallback_reason_valid"),
        "review_jobs",
        type_="check",
    )
    op.drop_column("review_jobs", "publication_fallback_reason")
