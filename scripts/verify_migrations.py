"""Verify the Alembic migration chain on a fresh SQLite database.

Runs upgrade to head, downgrade to base, and upgrade again, then checks that
every BFF business table (including B9 user credential columns) exists.

Usage (from backend/ with the project venv):
    python ../scripts/verify_migrations.py [--database-url sqlite:///...]
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"

REQUIRED_TABLES = {
    "alembic_version", "users", "projects", "project_members",
    "investigation_bookmarks", "report_exports", "demo_scenarios",
    "ui_preferences", "app_audit_events",
}
REQUIRED_USER_COLUMNS = {"password_hash", "is_active"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    if args.database_url:
        url = args.database_url
        db_path = None
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

    if db_path is None:
        print("table presence check only supported for SQLite; skipping schema inspection")
        return 0 if ok else 1

    conn = sqlite3.connect(db_path)
    tables = sorted(row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"))
    user_cols = sorted(row[1] for row in conn.execute("PRAGMA table_info(users)"))
    conn.close()
    print("tables:", tables)
    print("users columns:", user_cols)
    missing = REQUIRED_TABLES - set(tables)
    print("required tables missing:", sorted(missing) if missing else "NONE")
    cols_ok = REQUIRED_USER_COLUMNS <= set(user_cols)
    print("users B9 columns present:", cols_ok)
    return 0 if (ok and not missing and cols_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
