"""Persist project-scoped AgentGuard Study registration intents and links."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_study_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("study_id", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("track", sa.String(length=32), nullable=True),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("request_payload", sa.Text(), nullable=False),
        sa.Column("response_payload", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("source_commit", sa.String(length=40), nullable=False),
        sa.Column("source_mode", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("registration_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "project_id", "created_by", "idempotency_key_hash",
            name="uq_project_study_idempotency",
        ),
        sa.UniqueConstraint("study_id", name="uq_project_study_upstream_id"),
    )
    op.create_index("ix_project_study_submissions_project_id", "project_study_submissions", ["project_id"])
    op.create_index("ix_project_study_submissions_study_id", "project_study_submissions", ["study_id"])
    op.create_index("ix_project_study_submissions_track", "project_study_submissions", ["track"])
    op.create_index("ix_project_study_submissions_status", "project_study_submissions", ["status"])
    op.create_index("ix_project_study_submissions_request_id", "project_study_submissions", ["request_id"])
    op.create_index("ix_project_study_submissions_created_by", "project_study_submissions", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_project_study_submissions_created_by", table_name="project_study_submissions")
    op.drop_index("ix_project_study_submissions_request_id", table_name="project_study_submissions")
    op.drop_index("ix_project_study_submissions_status", table_name="project_study_submissions")
    op.drop_index("ix_project_study_submissions_study_id", table_name="project_study_submissions")
    op.drop_index("ix_project_study_submissions_track", table_name="project_study_submissions")
    op.drop_index("ix_project_study_submissions_project_id", table_name="project_study_submissions")
    op.drop_table("project_study_submissions")
