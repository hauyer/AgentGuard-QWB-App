"""Allow only one unresolved loop creation per project investigation."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

ACTIVE_STATUSES = "'PREPARED', 'SUBMITTING', 'SUBMISSION_AMBIGUOUS', 'LINK_PENDING'"


def upgrade() -> None:
    predicate = sa.text(f"status IN ({ACTIVE_STATUSES})")
    op.create_index(
        "uq_active_loop_submission_per_base",
        "investigation_loop_submissions",
        ["project_id", "base_request_id"],
        unique=True,
        sqlite_where=predicate,
        postgresql_where=predicate,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_active_loop_submission_per_base",
        table_name="investigation_loop_submissions",
    )
