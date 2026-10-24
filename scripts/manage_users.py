"""Manage database-backed application users (B9).

Usage (from backend/, with DATABASE_URL configured and migrations applied):

    python ../scripts/manage_users.py create <username> --role analyst [--display-name NAME]
    python ../scripts/manage_users.py set-password <username>
    python ../scripts/manage_users.py deactivate <username>
    python ../scripts/manage_users.py activate <username>
    python ../scripts/manage_users.py list

Passwords are read interactively (getpass) or from --password-stdin. Stored as
PBKDF2-SHA256 hashes (app.core.passwords) - never plaintext. Demo accounts in
app/services/auth_service.py are only honoured in development/demo APP_ENV.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.db import get_engine, upgrade_database  # noqa: E402
from app.core.passwords import hash_password, is_hashed_password  # noqa: E402
from app.models.app import User  # noqa: E402
from app.services.auth_service import ROLE_ORDER  # noqa: E402


def _read_password(*, confirm: bool = True) -> str:
    if sys.stdin.isatty():
        first = getpass.getpass("Password: ")
        if not first:
            raise SystemExit("Password must not be empty")
        if confirm:
            second = getpass.getpass("Confirm password: ")
            if first != second:
                raise SystemExit("Passwords do not match")
        return first
    value = sys.stdin.readline().rstrip("\r\n")
    if not value:
        raise SystemExit("Password must not be empty")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["create", "set-password", "deactivate", "activate", "list"])
    parser.add_argument("username", nargs="?")
    parser.add_argument("--role", choices=ROLE_ORDER, default="viewer")
    parser.add_argument("--display-name", default=None)
    parser.add_argument("--password-stdin", action="store_true", help="read the password from stdin (no prompt)")
    args = parser.parse_args()

    if args.command in {"create", "set-password", "deactivate", "activate"} and not args.username:
        parser.error(f"{args.command} requires a username")

    settings = Settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not configured; database users require a database")
    upgrade_database(settings)
    engine = get_engine(settings)
    assert engine is not None

    from sqlalchemy.orm import Session

    with Session(engine) as session:
        if args.command == "list":
            rows = session.scalars(select(User).order_by(User.username)).all()
            for row in rows:
                kind = "password" if is_hashed_password(row.password_hash) else "no-login"
                print(f"{row.username:24} role={row.role:9} active={row.is_active} auth={kind}")
            return 0

        user = session.scalar(select(User).where(User.username == args.username))
        if args.command == "create":
            if user is not None:
                raise SystemExit(f"user already exists: {args.username}")
            password = _read_password(confirm=not args.password_stdin)
            session.add(
                User(
                    username=args.username,
                    role=args.role,
                    display_name=args.display_name or args.username,
                    password_hash=hash_password(password),
                    is_active=True,
                )
            )
            session.commit()
            print(f"created user {args.username} (role={args.role}, PBKDF2 hash stored)")
            return 0

        if user is None:
            raise SystemExit(f"unknown user: {args.username}")
        if args.command == "set-password":
            user.password_hash = hash_password(_read_password(confirm=not args.password_stdin))
        elif args.command == "deactivate":
            user.is_active = False
        elif args.command == "activate":
            user.is_active = True
        session.commit()
        print(f"updated user {args.username}: {args.command}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
