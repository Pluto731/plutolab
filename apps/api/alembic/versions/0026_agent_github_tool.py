"""Allow the bounded public GitHub search tool on private Agents."""

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_agents_registered_tools"), "agents", type_="check")
    op.create_check_constraint(
        op.f("ck_agents_registered_tools"),
        "agents",
        "tools IN ('[]'::jsonb, '[\"search_notes\"]'::jsonb, '[\"search_github\"]'::jsonb, "
        '\'["search_notes", "search_github"]\'::jsonb, '
        '\'["search_github", "search_notes"]\'::jsonb)',
    )


def downgrade() -> None:
    # Fail transactionally if Agents still use GitHub; never silently strip permissions.
    op.drop_constraint(op.f("ck_agents_registered_tools"), "agents", type_="check")
    op.create_check_constraint(
        op.f("ck_agents_registered_tools"),
        "agents",
        "tools IN ('[]'::jsonb, '[\"search_notes\"]'::jsonb)",
    )
