"""B19: run_id authorization bridge for project-linked investigations."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_investigations") as batch:
        batch.add_column(sa.Column("last_known_run_id", sa.String(length=64), nullable=True))
    op.create_index("ix_project_investigations_last_known_run_id", "project_investigations",
                    ["last_known_run_id"])


def downgrade() -> None:
    op.drop_index("ix_project_investigations_last_known_run_id", table_name="project_investigations")
    with op.batch_alter_table("project_investigations") as batch:
        batch.drop_column("last_known_run_id")
