"""Persist BFF loop submission intent and reconciliation status.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investigation_loop_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("base_request_id", sa.String(length=256), nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("request_payload", sa.Text(), nullable=False),
        sa.Column("baseline_loop_ids", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("loop_id", sa.String(length=256), nullable=True),
        sa.Column("response_payload", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_status_code", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "submission_id", name="uq_project_loop_submission"),
        sa.UniqueConstraint("idempotency_key", name="uq_loop_submission_idempotency_key"),
    )
    op.create_index("ix_investigation_loop_submissions_project_id", "investigation_loop_submissions", ["project_id"])
    op.create_index(
        "ix_investigation_loop_submissions_base_request_id",
        "investigation_loop_submissions",
        ["base_request_id"],
    )
    op.create_index(
        "ix_investigation_loop_submissions_idempotency_key",
        "investigation_loop_submissions",
        ["idempotency_key"],
    )
    op.create_index("ix_investigation_loop_submissions_status", "investigation_loop_submissions", ["status"])
    op.create_index("ix_investigation_loop_submissions_loop_id", "investigation_loop_submissions", ["loop_id"])


def downgrade() -> None:
    op.drop_index("ix_investigation_loop_submissions_loop_id", table_name="investigation_loop_submissions")
    op.drop_index("ix_investigation_loop_submissions_status", table_name="investigation_loop_submissions")
    op.drop_index("ix_investigation_loop_submissions_idempotency_key", table_name="investigation_loop_submissions")
    op.drop_index("ix_investigation_loop_submissions_base_request_id", table_name="investigation_loop_submissions")
    op.drop_index("ix_investigation_loop_submissions_project_id", table_name="investigation_loop_submissions")
    op.drop_table("investigation_loop_submissions")
