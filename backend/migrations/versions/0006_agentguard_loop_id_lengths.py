"""Align investigation identity and verification with public data sources.

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # AgentGuard's public loop contract permits request and loop IDs up to 256
    # characters. Keep this forward-only so already-applied migrations remain
    # immutable and existing references survive the column expansion.
    with op.batch_alter_table("project_investigations") as batch:
        batch.alter_column(
            "agentguard_request_id",
            existing_type=sa.String(length=64),
            type_=sa.String(length=256),
            existing_nullable=False,
        )
    with op.batch_alter_table("project_investigation_loops") as batch:
        batch.alter_column(
            "base_request_id",
            existing_type=sa.String(length=64),
            type_=sa.String(length=256),
            existing_nullable=False,
        )
        batch.alter_column(
            "loop_id",
            existing_type=sa.String(length=64),
            type_=sa.String(length=256),
            existing_nullable=False,
        )
    with op.batch_alter_table("project_investigations") as batch:
        # Historical "verified" rows may have been checked against demo data;
        # keep them, but never silently treat them as AgentGuard Live links.
        batch.add_column(
            sa.Column("verification_source", sa.String(length=16), nullable=False,
                      server_default="unknown")
        )


def downgrade() -> None:
    # Downgrade can only be safe if no IDs exceed the previous 64-character
    # limit. Fail rather than truncate or silently lose ownership references.
    bind = op.get_bind()
    for table_name, column_name in (
        ("project_investigations", "agentguard_request_id"),
        ("project_investigation_loops", "base_request_id"),
        ("project_investigation_loops", "loop_id"),
    ):
        table = sa.table(table_name, sa.column(column_name))
        too_long = bind.scalar(
            sa.select(sa.literal(1))
            .select_from(table)
            .where(sa.func.length(table.c[column_name]) > 64)
            .limit(1)
        )
        if too_long:
            raise RuntimeError(
                f"Cannot downgrade {table_name}.{column_name}: "
                "an identifier exceeds 64 characters"
            )
    with op.batch_alter_table("project_investigation_loops") as batch:
        batch.alter_column(
            "loop_id",
            existing_type=sa.String(length=256),
            type_=sa.String(length=64),
            existing_nullable=False,
        )
        batch.alter_column(
            "base_request_id",
            existing_type=sa.String(length=256),
            type_=sa.String(length=64),
            existing_nullable=False,
        )
    with op.batch_alter_table("project_investigations") as batch:
        batch.drop_column("verification_source")
        batch.alter_column(
            "agentguard_request_id",
            existing_type=sa.String(length=256),
            type_=sa.String(length=64),
            existing_nullable=False,
        )
