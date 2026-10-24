"""B12: project business management.

- projects: status (active|archived) + created_by
- project_members: rebuilt on username identity (demo and DB users share the
  identity namespace; removing a row revokes access immediately)
- project_investigations: references to AgentGuard-stored investigations
- app_audit_events: optional project_id scope for per-project audit queries

The B8 project_members table was never populated by the application, so it is
rebuilt (not migrated row-by-row); downgrade recreates the 0001 shape.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("status", sa.String(length=16), nullable=False,
                                   server_default="active"))
        batch.add_column(sa.Column("created_by", sa.String(length=64), nullable=True))
    op.create_index("ix_projects_status", "projects", ["status"])

    op.drop_table("project_members")
    op.create_table(
        "project_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("username", sa.String(length=64), nullable=False, index=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("added_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "username", name="uq_project_member"),
    )

    op.create_table(
        "project_investigations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("agentguard_request_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("display_name", sa.String(length=256), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("verification", sa.String(length=16), nullable=False, server_default="unverified"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "agentguard_request_id", name="uq_project_investigation"),
    )

    with op.batch_alter_table("app_audit_events") as batch:
        batch.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_index("ix_app_audit_events_project_id", "app_audit_events", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_app_audit_events_project_id", table_name="app_audit_events")
    with op.batch_alter_table("app_audit_events") as batch:
        batch.drop_column("project_id")

    op.drop_table("project_investigations")
    op.drop_table("project_members")
    op.create_table(
        "project_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    op.drop_index("ix_projects_status", table_name="projects")
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("created_by")
        batch.drop_column("status")
