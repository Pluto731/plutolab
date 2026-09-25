"""Owner-private Workflow heads and append-only revisions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column(
            "id", postgresql.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'ready'")),
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
        sa.CheckConstraint("status IN ('ready', 'archived')", name="valid_status"),
    )
    op.create_index("ix_workflows_user_id", "workflows", ["user_id"])
    op.create_table(
        "workflow_revisions",
        sa.Column(
            "workflow_id",
            postgresql.UUID(),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("graph", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("layout", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("version >= 1", name="version_positive"),
        sa.CheckConstraint(
            "length(name) BETWEEN 1 AND 100 AND length(btrim(name)) > 0", name="name_length"
        ),
        sa.CheckConstraint("length(description) <= 2000", name="description_length"),
        sa.CheckConstraint("status IN ('ready', 'archived')", name="valid_status"),
        sa.CheckConstraint(
            "jsonb_typeof(graph) = 'object' AND jsonb_typeof(layout) = 'object'",
            name="json_objects",
        ),
    )
    op.execute("""
        CREATE FUNCTION reject_workflow_revision_update() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Workflow revisions are immutable'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER workflow_revision_immutable BEFORE UPDATE ON workflow_revisions
        FOR EACH ROW EXECUTE FUNCTION reject_workflow_revision_update()
    """)


def downgrade() -> None:
    op.drop_table("workflow_revisions")
    op.execute("DROP FUNCTION reject_workflow_revision_update()")
    op.drop_index("ix_workflows_user_id", table_name="workflows")
    op.drop_table("workflows")
