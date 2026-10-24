"""Initial application-layer tables.

Revision ID: 0001
Revises:
Create Date: 2026-10-23

BFF-owned business tables only (see app/models/app.py). AgentGuard-owned data
is never duplicated here.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _now() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        _now(),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        _now(),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "project_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        _now(),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )
    op.create_index("ix_project_members_project_id", "project_members", ["project_id"])
    op.create_index("ix_project_members_user_id", "project_members", ["user_id"])

    op.create_table(
        "investigation_bookmarks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        _now(),
        sa.UniqueConstraint("user_id", "request_id", name="uq_user_bookmark"),
    )
    op.create_index("ix_investigation_bookmarks_user_id", "investigation_bookmarks", ["user_id"])
    op.create_index("ix_investigation_bookmarks_request_id", "investigation_bookmarks", ["request_id"])

    op.create_table(
        "report_exports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("format", sa.String(length=8), nullable=False),
        sa.Column("exported_by", sa.String(length=64), nullable=False),
        _now(),
    )
    op.create_index("ix_report_exports_run_id", "report_exports", ["run_id"])

    op.create_table(
        "demo_scenarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scenario_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("data_mode", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _now(),
        sa.UniqueConstraint("scenario_id"),
    )
    op.create_index("ix_demo_scenarios_scenario_id", "demo_scenarios", ["scenario_id"])

    op.create_table(
        "ui_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pref_key", sa.String(length=64), nullable=False),
        sa.Column("pref_value", sa.Text(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.UniqueConstraint("user_id", "pref_key", name="uq_user_pref"),
    )
    op.create_index("ix_ui_preferences_user_id", "ui_preferences", ["user_id"])

    op.create_table(
        "app_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target", sa.String(length=128), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        _now(),
    )
    op.create_index("ix_app_audit_events_actor", "app_audit_events", ["actor"])
    op.create_index("ix_app_audit_events_action", "app_audit_events", ["action"])
    op.create_index("ix_app_audit_events_created_at", "app_audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("app_audit_events")
    op.drop_table("ui_preferences")
    op.drop_table("demo_scenarios")
    op.drop_table("report_exports")
    op.drop_table("investigation_bookmarks")
    op.drop_table("project_members")
    op.drop_table("projects")
    op.drop_table("users")
