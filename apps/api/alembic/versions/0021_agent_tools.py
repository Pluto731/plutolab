"""Enable reviewed read-only note search tool."""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_agents_registered_tools"), "agents", type_="check")
    op.create_check_constraint(
        "registered_tools", "agents", "tools IN ('[]'::jsonb, '[\"search_notes\"]'::jsonb)"
    )


def downgrade() -> None:
    # Refuse downgrade if configured tools exist; never silently discard configuration.
    op.drop_constraint(op.f("ck_agents_registered_tools"), "agents", type_="check")
    op.create_check_constraint("registered_tools", "agents", "tools = '[]'::jsonb")
