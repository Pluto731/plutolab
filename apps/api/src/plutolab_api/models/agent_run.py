"""Owner-private execution records; sensitive payloads are authenticated ciphertext."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from plutolab_api.db.base import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_id", "workflow_version"],
            ["workflow_revisions.workflow_id", "workflow_revisions.version"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "state IN ('pending','running','succeeded','partial','failed','cancelled')",
            name="valid_state",
        ),
        CheckConstraint(
            "token_limit BETWEEN 1 AND 32000 AND cost_limit BETWEEN 1 AND 1000000",
            name="budget_limits",
        ),
        CheckConstraint(
            "charged_tokens >= 0 AND reserved_tokens >= 0 AND charged_tokens + reserved_tokens <= token_limit AND charged_cost >= 0 AND reserved_cost >= 0 AND charged_cost + reserved_cost <= cost_limit",
            name="budget_usage",
        ),
        CheckConstraint(
            "checkpoint_version >= 0 AND jsonb_typeof(checkpoint) = 'object' AND octet_length(checkpoint::text) <= 4096",
            name="checkpoint_bounds",
        ),
        CheckConstraint("event_sequence >= 0", name="event_sequence_bounds"),
        CheckConstraint(
            "idempotency_key IS NULL OR length(idempotency_key) BETWEEN 1 AND 128",
            name="idempotency_key_bounds",
        ),
        CheckConstraint(
            "request_fingerprint IS NULL OR length(request_fingerprint) = 64",
            name="request_fingerprint_bounds",
        ),
        UniqueConstraint("user_id", "idempotency_key", name="uq_agent_runs_user_idempotency"),
        CheckConstraint(
            "octet_length(snapshot_ciphertext) BETWEEN 1 AND 4000000", name="snapshot_size"
        ),
        CheckConstraint("expires_at > created_at", name="retention"),
        CheckConstraint(
            "(state IN ('pending','running') AND finished_at IS NULL) OR (state NOT IN ('pending','running') AND finished_at IS NOT NULL)",
            name="terminal_time",
        ),
    )
    id: Mapped[UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    workflow_id: Mapped[UUID] = mapped_column(PG_UUID, nullable=False)
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    token_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    charged_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    charged_cost: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    reserved_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    reserved_cost: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    checkpoint: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    checkpoint_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    event_sequence: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_fingerprint: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class AgentRunNode(Base):
    __tablename__ = "agent_run_nodes"
    __table_args__ = (
        CheckConstraint(
            "state IN ('pending','running','succeeded','failed','skipped','cancelled')",
            name="valid_state",
        ),
        CheckConstraint(
            "attempts BETWEEN 0 AND 9 AND retries BETWEEN 0 AND 2", name="attempt_bounds"
        ),
        CheckConstraint("reserved_tokens >= 0 AND reserved_cost >= 0", name="reservation_positive"),
        CheckConstraint(
            "output_ciphertext IS NULL OR octet_length(output_ciphertext) <= 200000",
            name="output_size",
        ),
        CheckConstraint(
            "input_ciphertext IS NULL OR octet_length(input_ciphertext) <= 500000",
            name="input_size",
        ),
        CheckConstraint(
            "error_code IS NULL OR error_code IN ('missing_key','invalid_key','unsupported_model','budget_exceeded','provider_timeout','provider_rate_limit','provider_unavailable','provider_auth','provider_invalid','unsafe_output','tool_failed','tool_limit','cancelled','dependency_failed','internal_error')",
            name="error_code",
        ),
        CheckConstraint(
            "(state IN ('pending','running') AND finished_at IS NULL) OR (state NOT IN ('pending','running') AND finished_at IS NOT NULL)",
            name="terminal_time",
        ),
    )
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID, ForeignKey("agent_runs.id", ondelete="CASCADE"), primary_key=True
    )
    node_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    input_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    output_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    error_code: Mapped[str | None] = mapped_column(String(40))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    retries: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    usage_uncertain: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    reserved_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    reserved_cost: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRunOutbox(Base):
    """Transactional dispatch intent; broker payloads carry only this stable run id."""

    __tablename__ = "agent_run_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','claimed','queued','running','completed','failed')",
            name="valid_status",
        ),
        CheckConstraint("attempts BETWEEN 0 AND 100", name="attempt_bounds"),
        CheckConstraint("(claim_token IS NULL) = (claim_until IS NULL)", name="claim_pair"),
        CheckConstraint("(status = 'running') = (run_lease_until IS NOT NULL)", name="run_lease"),
        Index("ix_agent_run_outbox_dispatch", "status", "available_at"),
    )
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID, ForeignKey("agent_runs.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'pending'")
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    claim_token: Mapped[UUID | None] = mapped_column(PG_UUID)
    claim_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class AgentRunEvent(Base):
    __tablename__ = "agent_run_events"
    __table_args__ = (
        CheckConstraint("sequence > 0", name="sequence_positive"),
        CheckConstraint(
            "event_type IN ('run_started','run_cancel_requested','run_finished','node_started','node_finished','node_skipped')",
            name="event_type",
        ),
        CheckConstraint("summary IS NULL OR length(summary) <= 256", name="summary_bounds"),
    )
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID, ForeignKey("agent_runs.id", ondelete="CASCADE"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    node_id: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
