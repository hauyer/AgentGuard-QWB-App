"""Verify the Alembic migration chain on a fresh SQLite or PostgreSQL database.

Runs upgrade to head, downgrade to base, and upgrade again, then checks that
every BFF business table (including B9 user credential columns) exists.

Usage (from backend/ with the project venv):
    python ../scripts/verify_migrations.py [--database-url sqlite:///...]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, inspect

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"

REQUIRED_TABLES = {
    "alembic_version", "users", "projects", "project_members",
    "project_investigations", "investigation_bookmarks", "report_exports",
    "project_investigation_loops", "investigation_loop_submissions",
    "demo_scenarios", "ui_preferences", "app_audit_events",
}
REQUIRED_USER_COLUMNS = {"password_hash", "is_active"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    if args.database_url:
        url = args.database_url
    else:
        db_path = Path(tempfile.mkdtemp()) / "migrate-check.db"
        url = f"sqlite:///{db_path.as_posix()}"

    env = {**os.environ, "DATABASE_URL": url}
    python = sys.executable

    def alembic(*cli_args: str) -> int:
        result = subprocess.run(
            [python, "-m", "alembic", *cli_args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, cwd=BACKEND_ROOT,
        )
        print(f"$ alembic {' '.join(cli_args)} -> rc={result.returncode}")
        if result.returncode != 0:
            print(result.stdout[-800:])
            print(result.stderr[-1200:])
        return result.returncode

    ok = True
    ok &= alembic("upgrade", "head") == 0
    ok &= alembic("current") == 0
    ok &= alembic("downgrade", "0001") == 0
    ok &= alembic("downgrade", "base") == 0
    ok &= alembic("upgrade", "head") == 0

    engine = create_engine(url)
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    user_cols = sorted(column["name"] for column in inspector.get_columns("users")) if "users" in tables else []
    print("tables:", tables)
    print("users columns:", user_cols)
    missing = REQUIRED_TABLES - set(tables)
    print("required tables missing:", sorted(missing) if missing else "NONE")
    cols_ok = REQUIRED_USER_COLUMNS <= set(user_cols)
    print("users B9 columns present:", cols_ok)
    indexes = inspector.get_indexes("investigation_loop_submissions") if "investigation_loop_submissions" in tables else []
    active_lock = next((index for index in indexes if index["name"] == "uq_active_loop_submission_per_base"), None)
    active_lock_ok = bool(
        active_lock
        and active_lock.get("unique")
        and active_lock.get("column_names") == ["project_id", "base_request_id"]
    )
    print("unique unresolved-submission lock present:", active_lock_ok)
    engine.dispose()
    return 0 if (ok and not missing and cols_ok and active_lock_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
