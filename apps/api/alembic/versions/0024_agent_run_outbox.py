"""Transactional dispatch outbox for Agent runs."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_run_outbox",
        sa.Column(
            "run_id",
            postgresql.UUID(),
            sa.ForeignKey("agent_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("claim_token", postgresql.UUID(), nullable=True),
        sa.Column("claim_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','claimed','queued','running','completed','failed')",
            name="valid_status",
        ),
        sa.CheckConstraint("attempts BETWEEN 0 AND 100", name="attempt_bounds"),
        sa.CheckConstraint("(claim_token IS NULL) = (claim_until IS NULL)", name="claim_pair"),
        sa.CheckConstraint(
            "(status = 'running') = (run_lease_until IS NOT NULL)", name="run_lease"
        ),
    )
    op.create_index("ix_agent_run_outbox_dispatch", "agent_run_outbox", ["status", "available_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_run_outbox_dispatch", table_name="agent_run_outbox")
    op.drop_table("agent_run_outbox")
