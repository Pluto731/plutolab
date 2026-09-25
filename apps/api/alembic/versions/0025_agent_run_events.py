"""Run idempotency, cancellation and durable bounded event replay."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column("event_sequence", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "cancel_requested", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column("agent_runs", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.add_column(
        "agent_runs", sa.Column("request_fingerprint", sa.String(length=64), nullable=True)
    )
    op.create_check_constraint(
        "ck_agent_runs_event_sequence_bounds", "agent_runs", "event_sequence >= 0"
    )
    op.create_check_constraint(
        "ck_agent_runs_idempotency_key_bounds",
        "agent_runs",
        "idempotency_key IS NULL OR length(idempotency_key) BETWEEN 1 AND 128",
    )
    op.create_check_constraint(
        "ck_agent_runs_request_fingerprint_bounds",
        "agent_runs",
        "request_fingerprint IS NULL OR length(request_fingerprint) = 64",
    )
    op.create_unique_constraint(
        "uq_agent_runs_user_idempotency", "agent_runs", ["user_id", "idempotency_key"]
    )
    op.create_table(
        "agent_run_events",
        sa.Column(
            "run_id",
            postgresql.UUID(),
            sa.ForeignKey("agent_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("sequence", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("node_id", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint("sequence > 0", name="sequence_positive"),
        sa.CheckConstraint(
            "event_type IN ('run_started','run_cancel_requested','run_finished','node_started','node_finished','node_skipped')",
            name="event_type",
        ),
        sa.CheckConstraint("summary IS NULL OR length(summary) <= 256", name="summary_bounds"),
    )


def downgrade() -> None:
    op.drop_table("agent_run_events")
    op.drop_constraint("uq_agent_runs_user_idempotency", "agent_runs", type_="unique")
    op.drop_constraint("ck_agent_runs_request_fingerprint_bounds", "agent_runs", type_="check")
    op.drop_constraint("ck_agent_runs_idempotency_key_bounds", "agent_runs", type_="check")
    op.drop_constraint("ck_agent_runs_event_sequence_bounds", "agent_runs", type_="check")
    op.drop_column("agent_runs", "request_fingerprint")
    op.drop_column("agent_runs", "idempotency_key")
    op.drop_column("agent_runs", "cancel_requested")
    op.drop_column("agent_runs", "event_sequence")
