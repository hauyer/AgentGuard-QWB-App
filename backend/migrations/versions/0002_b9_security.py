"""B9: database-backed user credentials.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-24

- users.password_hash (PBKDF2, app.core.passwords) for real accounts
- users.is_active so disabling an account also invalidates future sessions
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("password_hash", sa.String(length=256), nullable=True))
        batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_active")
        batch.drop_column("password_hash")
