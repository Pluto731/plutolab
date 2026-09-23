"""GitHub ownership, versioned rules and durable review state; no credentials or raw PRs."""

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
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from plutolab_api.db.base import Base


class GitHubInstallation(Base):
    __tablename__ = "github_installations"
    __table_args__ = (
        UniqueConstraint("installation_id", "owner_id", name="uq_installation_owner"),
        CheckConstraint("installation_id ~ '^[1-9][0-9]{0,31}$'", name="installation_id_decimal"),
    )

    installation_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class ReviewSettings(Base):
    __tablename__ = "review_settings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["installation_id", "owner_id"],
            ["github_installations.installation_id", "github_installations.owner_id"],
            ondelete="CASCADE",
            name="fk_review_settings_installation_owner",
        ),
        UniqueConstraint("installation_id", "repo_id", name="uq_review_settings_installation_repo"),
        CheckConstraint("repo_id ~ '^[1-9][0-9]{0,31}$'", name="repo_id_decimal"),
        CheckConstraint("min_pr_lines > 0", name="min_pr_lines_positive"),
        CheckConstraint(
            "max_pr_lines IS NULL OR max_pr_lines >= min_pr_lines", name="max_pr_lines_valid"
        ),
        CheckConstraint("rules_version > 0", name="rules_version_positive"),
        CheckConstraint(
            "jsonb_typeof(skip_paths) = 'array' AND jsonb_array_length(skip_paths) <= 100",
            name="skip_paths_bounded",
        ),
        CheckConstraint(
            "jsonb_typeof(focus) = 'array' AND jsonb_array_length(focus) BETWEEN 1 AND 3 "
            'AND focus <@ \'["security","performance","quality"]\'::jsonb',
            name="focus_valid",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    installation_id: Mapped[str] = mapped_column(String(32))
    owner_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), index=True)
    repo_id: Mapped[str] = mapped_column(String(32))
    repo_name: Mapped[str] = mapped_column(String(201))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    min_pr_lines: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    max_pr_lines: Mapped[int | None] = mapped_column(Integer)
    skip_paths: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    focus: Mapped[list[str]] = mapped_column(
        JSONB,
        default=lambda: ["security", "performance", "quality"],
        server_default=text('\'["security","performance","quality"]\'::jsonb'),
    )
    rules_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), onupdate=text("NOW()")
    )


class ReviewJob(Base):
    """Immutable identity/policy snapshot and independent analysis/publication state."""

    __tablename__ = "review_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["installation_id", "owner_id"],
            ["github_installations.installation_id", "github_installations.owner_id"],
            ondelete="CASCADE",
            name="fk_review_jobs_installation_owner",
        ),
        UniqueConstraint("id", "owner_id", name="uq_review_jobs_id_owner"),
        UniqueConstraint(
            "owner_id",
            "installation_id",
            "repo_id",
            "pr_number",
            "head_sha",
            "rules_version",
            "provider",
            name="uq_review_jobs_identity",
        ),
        CheckConstraint("repo_id ~ '^[1-9][0-9]{0,31}$'", name="repo_id_decimal"),
        CheckConstraint("head_sha ~ '^([0-9a-f]{40}|[0-9a-f]{64})$'", name="head_sha_valid"),
        CheckConstraint("pr_number > 0 AND rules_version > 0", name="identity_positive"),
        CheckConstraint("max_attempts > 0 AND dispatch_version > 0", name="limits_positive"),
        CheckConstraint("provider = 'anthropic'", name="provider_valid"),
        CheckConstraint(
            "analysis_status IN ('draft','queued','processing','analyzed','partial',"
            "'failed','skipped','superseded','cancelled')",
            name="analysis_status_valid",
        ),
        CheckConstraint(
            "publication_status IN ('not_requested','preview_ready','publishing','published',"
            "'partially_published','publish_unknown','failed','blocked')",
            name="publication_status_valid",
        ),
        CheckConstraint(
            "publication_fallback_reason IS NULL OR publication_fallback_reason IN "
            "('diff_position_mismatch')",
            name="publication_fallback_reason_valid",
        ),
        CheckConstraint("jsonb_typeof(findings) = 'array'", name="findings_array"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    owner_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), index=True)
    installation_id: Mapped[str] = mapped_column(String(32))
    repo_id: Mapped[str] = mapped_column(String(32))
    pr_number: Mapped[int] = mapped_column(Integer)
    head_sha: Mapped[str] = mapped_column(String(64))
    rules_version: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(32))
    policy: Mapped[dict[str, object]] = mapped_column(JSONB)
    analysis_status: Mapped[str] = mapped_column(String(16), server_default=text("'queued'"))
    publication_status: Mapped[str] = mapped_column(
        String(24), server_default=text("'not_requested'")
    )
    publication: Mapped[dict[str, object]] = mapped_column(
        JSONB, server_default=text('\'{"status":"not_requested"}\'::jsonb')
    )
    publication_fallback_reason: Mapped[str | None] = mapped_column(String(64))
    verified_diff: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    findings: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    coverage: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    usage: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    summary: Mapped[str | None] = mapped_column(Text)
    error: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    max_attempts: Mapped[int] = mapped_column(Integer)
    dispatch_version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), onupdate=text("NOW()")
    )


class ReviewDelivery(Base):
    """Durable inbox identity; never stores the raw webhook body."""

    __tablename__ = "review_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "owner_id"], ["review_jobs.id", "review_jobs.owner_id"], ondelete="CASCADE"
        ),
        CheckConstraint("event_type ~ '^[a-z_]{1,32}$'", name="event_valid"),
        CheckConstraint("action ~ '^[a-z_]{0,128}$'", name="action_valid"),
        CheckConstraint(
            "payload_sha256 IS NULL OR payload_sha256 ~ '^[0-9a-f]{64}$'", name="payload_hash_valid"
        ),
        CheckConstraint(
            "(disposition = 'accepted' AND job_id IS NOT NULL AND owner_id IS NOT NULL "
            "AND event_type = 'pull_request' AND action IN ('opened','synchronize','reopened') "
            "AND ignore_reason IS NULL) OR (disposition = 'ignored' AND job_id IS NULL "
            "AND payload_sha256 IS NOT NULL AND ignore_reason IS NOT NULL AND ignore_reason IN "
            "('irrelevant_event','irrelevant_action','inactive_installation','repository_not_enabled'))",
            name="disposition_valid",
        ),
    )

    delivery_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    job_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), index=True)
    owner_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(128))
    payload_sha256: Mapped[str | None] = mapped_column(String(64))
    ignore_reason: Mapped[str | None] = mapped_column(String(32))
    disposition: Mapped[str] = mapped_column(String(16), server_default=text("'accepted'"))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class ReviewAttempt(Base):
    """Lease-fenced attempt; late workers cannot overwrite a recovered attempt."""

    __tablename__ = "review_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "owner_id"], ["review_jobs.id", "review_jobs.owner_id"], ondelete="CASCADE"
        ),
        UniqueConstraint("job_id", "kind", "number", name="uq_review_attempt_number"),
        CheckConstraint("kind IN ('analysis','publication')", name="kind_valid"),
        CheckConstraint(
            "status IN ('running','succeeded','failed','abandoned','unknown')", name="status_valid"
        ),
        CheckConstraint("number > 0", name="number_positive"),
        CheckConstraint("lease_until > started_at", name="lease_valid"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), index=True)
    owner_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(16))
    number: Mapped[int] = mapped_column(Integer)
    head_sha: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'running'"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict[str, object] | None] = mapped_column(JSONB)


class ReviewOutbox(Base):
    """Durable dispatch intent with bounded retries and fenced relay claims."""

    __tablename__ = "review_outbox"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "owner_id"], ["review_jobs.id", "review_jobs.owner_id"], ondelete="CASCADE"
        ),
        UniqueConstraint("job_id", "version", name="uq_review_outbox_job_version"),
        CheckConstraint("kind IN ('analyze','reconcile_publication')", name="kind_valid"),
        CheckConstraint(
            "status IN ('pending','dispatched','cancelled','failed')", name="status_valid"
        ),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "dispatch_attempts >= 0 AND dispatch_attempts <= 100", name="dispatch_attempts_valid"
        ),
        CheckConstraint("(claim_token IS NULL) = (claim_until IS NULL)", name="claim_pair_valid"),
        Index("ix_review_outbox_dispatch_due", "status", "available_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), index=True)
    owner_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'pending'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    dispatch_attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    claim_token: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    claim_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(64))
