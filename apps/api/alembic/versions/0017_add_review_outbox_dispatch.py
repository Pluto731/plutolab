"""Persist bounded outbox dispatch retries and fenced relay claims."""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "review_outbox",
        sa.Column("dispatch_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "review_outbox",
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.add_column("review_outbox", sa.Column("claim_token", sa.UUID(), nullable=True))
    op.add_column(
        "review_outbox", sa.Column("claim_until", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("review_outbox", sa.Column("last_error", sa.String(64), nullable=True))
    op.drop_constraint(op.f("ck_review_outbox_status_valid"), "review_outbox", type_="check")
    op.create_check_constraint(
        op.f("ck_review_outbox_status_valid"),
        "review_outbox",
        "status IN ('pending','dispatched','cancelled','failed')",
    )
    op.create_check_constraint(
        op.f("ck_review_outbox_dispatch_attempts_valid"),
        "review_outbox",
        "dispatch_attempts >= 0 AND dispatch_attempts <= 100",
    )
    op.create_check_constraint(
        op.f("ck_review_outbox_claim_pair_valid"),
        "review_outbox",
        "(claim_token IS NULL) = (claim_until IS NULL)",
    )
    op.create_index("ix_review_outbox_dispatch_due", "review_outbox", ["status", "available_at"])


def downgrade() -> None:
    blocked = op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM review_outbox WHERE status = 'failed' OR claim_token IS NOT NULL)"
        )
    )
    if blocked:
        raise RuntimeError("Cannot downgrade 0017 while failed or claimed outbox entries exist")
    op.drop_index("ix_review_outbox_dispatch_due", table_name="review_outbox")
    for name in ("claim_pair_valid", "dispatch_attempts_valid", "status_valid"):
        op.drop_constraint(op.f("ck_review_outbox_" + name), "review_outbox", type_="check")
    for name in ("last_error", "claim_until", "claim_token", "available_at", "dispatch_attempts"):
        op.drop_column("review_outbox", name)
    op.create_check_constraint(
        op.f("ck_review_outbox_status_valid"),
        "review_outbox",
        "status IN ('pending','dispatched','cancelled')",
    )
