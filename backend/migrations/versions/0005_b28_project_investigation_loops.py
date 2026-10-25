"""B28: project-scoped investigation loop mapping (B29 migration)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_investigation_loops",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("base_request_id", sa.String(length=64), nullable=False),
        sa.Column("loop_id", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("verified_source", sa.String(length=16), nullable=False, server_default="unverified"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "loop_id", name="uq_project_loop"),
        sa.UniqueConstraint("loop_id", name="uq_loop_id_unique"),
    )
    op.create_index("ix_project_investigation_loops_project_id", "project_investigation_loops", ["project_id"])
    op.create_index(
        "ix_project_investigation_loops_base_request_id",
        "project_investigation_loops", ["base_request_id"])
    op.create_index("ix_project_investigation_loops_loop_id", "project_investigation_loops", ["loop_id"])


def downgrade() -> None:
    op.drop_index("ix_project_investigation_loops_loop_id", table_name="project_investigation_loops")
    op.drop_index(
        "ix_project_investigation_loops_base_request_id",
        table_name="project_investigation_loops")
    op.drop_index("ix_project_investigation_loops_project_id", table_name="project_investigation_loops")
    op.drop_table("project_investigation_loops")
