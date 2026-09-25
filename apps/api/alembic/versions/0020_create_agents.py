"""Create owner-private Agent definitions (Phase 6 Slice 2)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column(
            "id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("role_prompt", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column(
            "tools",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'active'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("version >= 1", name="version_positive"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="valid_status"),
        sa.CheckConstraint("length(btrim(name)) BETWEEN 1 AND 100", name="name_length"),
        sa.CheckConstraint("length(description) <= 2000", name="description_length"),
        sa.CheckConstraint(
            "length(role_prompt) BETWEEN 1 AND 16000 AND length(btrim(role_prompt)) > 0",
            name="prompt_length",
        ),
        sa.CheckConstraint("provider = 'openai' AND model = 'gpt-4o-mini'", name="model_catalog"),
        sa.CheckConstraint("tools = '[]'::jsonb", name="registered_tools"),
    )
    op.create_index("ix_agents_user_id", "agents", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_agents_user_id", table_name="agents")
    op.drop_table("agents")
