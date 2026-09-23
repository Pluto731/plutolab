"""Expand delivery inbox for signed ignored events and reopened PRs."""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_review_deliveries_event_valid"), "review_deliveries", type_="check")
    op.drop_constraint(
        op.f("ck_review_deliveries_action_valid"), "review_deliveries", type_="check"
    )
    op.alter_column("review_deliveries", "job_id", existing_type=sa.UUID(), nullable=True)
    op.alter_column("review_deliveries", "owner_id", existing_type=sa.UUID(), nullable=True)
    op.alter_column(
        "review_deliveries", "action", existing_type=sa.String(16), type_=sa.String(128)
    )
    op.add_column("review_deliveries", sa.Column("payload_sha256", sa.String(64), nullable=True))
    op.add_column("review_deliveries", sa.Column("ignore_reason", sa.String(32), nullable=True))
    op.add_column(
        "review_deliveries",
        sa.Column(
            "disposition", sa.String(16), nullable=False, server_default=sa.text("'accepted'")
        ),
    )
    for name, condition in (
        ("event_valid", "event_type ~ '^[a-z_]{1,32}$'"),
        ("action_valid", "action ~ '^[a-z_]{0,128}$'"),
        ("payload_hash_valid", "payload_sha256 IS NULL OR payload_sha256 ~ '^[0-9a-f]{64}$'"),
        (
            "disposition_valid",
            "(disposition = 'accepted' AND job_id IS NOT NULL AND owner_id IS NOT NULL AND event_type = 'pull_request' AND action IN ('opened','synchronize','reopened') AND ignore_reason IS NULL) OR (disposition = 'ignored' AND job_id IS NULL AND payload_sha256 IS NOT NULL AND ignore_reason IS NOT NULL AND ignore_reason IN ('irrelevant_event','irrelevant_action','inactive_installation','repository_not_enabled'))",
        ),
    ):
        op.create_check_constraint(
            op.f("ck_review_deliveries_" + name), "review_deliveries", condition
        )


def downgrade() -> None:
    # No automatic deletion of durable inbox rows to make an old schema fit.
    incompatible = op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM review_deliveries WHERE disposition <> 'accepted' OR action = 'reopened')"
        )
    )
    if incompatible:
        raise RuntimeError("Cannot downgrade 0016 while ignored or reopened deliveries exist")
    for name in ("disposition_valid", "payload_hash_valid", "action_valid", "event_valid"):
        op.drop_constraint(op.f("ck_review_deliveries_" + name), "review_deliveries", type_="check")
    for name in ("disposition", "ignore_reason", "payload_sha256"):
        op.drop_column("review_deliveries", name)
    op.alter_column(
        "review_deliveries", "action", existing_type=sa.String(128), type_=sa.String(16)
    )
    op.alter_column("review_deliveries", "job_id", existing_type=sa.UUID(), nullable=False)
    op.alter_column("review_deliveries", "owner_id", existing_type=sa.UUID(), nullable=False)
    op.create_check_constraint(
        op.f("ck_review_deliveries_event_valid"), "review_deliveries", "event_type = 'pull_request'"
    )
    op.create_check_constraint(
        op.f("ck_review_deliveries_action_valid"),
        "review_deliveries",
        "action IN ('opened','synchronize')",
    )
