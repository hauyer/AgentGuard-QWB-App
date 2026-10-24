"""Application-layer identity (B8 minimal model, hardened in B9).

Roles: viewer (read-only), analyst (create investigations, view evidence),
operator (manage authorised operation requests), admin (system settings).
The application role never maps to AgentGuard privileges automatically -
AgentGuard still enforces its own authorization on every upstream call.

B9 rules:
  * When auth is disabled (dev default) an implicit local admin session is
    used, clearly labelled; production is rejected at config validation.
  * Database users (users table, PBKDF2 password hashes) are the production
    identity source; sessions of deactivated users are rejected.
  * The hardcoded demo accounts are available only in development/demo
    environments (settings.demo_users_enabled); production always refuses
    them even if the flag is set.
"""

from __future__ import annotations

import dataclasses
import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.core.db import open_session
from app.core.passwords import verify_password
from app.models.app import User

logger = logging.getLogger(__name__)

ROLE_ORDER = ["viewer", "analyst", "operator", "admin"]


@dataclasses.dataclass(frozen=True)
class AppUser:
    username: str
    display_name: str
    role: str
    source: str = "database"  # database | demo | dev

    def to_public(self) -> dict:
        return {
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "source": self.source,
        }


DEMO_USERS: dict[str, AppUser] = {
    user.username: user
    for user in [
        AppUser("viewer", "演示查看者", "viewer", "demo"),
        AppUser("analyst", "演示分析员", "analyst", "demo"),
        AppUser("operator", "演示操作员", "operator", "demo"),
        AppUser("admin", "演示管理员", "admin", "demo"),
    ]
}
DEMO_PASSWORDS: dict[str, str] = {
    # Demo-only credentials; rejected outside development/demo environments.
    "viewer": "viewer-demo",
    "analyst": "analyst-demo",
    "operator": "operator-demo",
    "admin": "admin-demo",
}


def _db_user(settings: Settings, username: str) -> AppUser | None:
    session = open_session(settings)
    if session is None:
        return None
    try:
        with session:
            row = session.scalar(select(User).where(User.username == username))
            if row is None or not row.is_active or row.role not in ROLE_ORDER:
                return None
            return AppUser(
                username=row.username,
                display_name=row.display_name or row.username,
                role=row.role,
                source="database",
            )
    except SQLAlchemyError:
        # Fail closed: an unavailable/mis-migrated database must not fall back
        # to any other identity source.
        logger.error("user lookup failed; denying session (database unavailable)")
        return None


def find_user(settings: Settings, username: str) -> AppUser | None:
    """Resolve a live user by username (database first, then gated demo list).

    Used by request dependencies so deactivating a database user or disabling
    demo accounts invalidates existing sessions on the next request.
    """
    user = _db_user(settings, username)
    if user is not None:
        return user
    if settings.demo_users_enabled:
        return DEMO_USERS.get(username)
    return None


def verify_credentials(settings: Settings, username: str, password: str) -> AppUser | None:
    """Authenticate against database users; demo users only in dev/demo envs.

    Database errors fail closed (no fallback authentication).
    """
    session = open_session(settings)
    if session is not None:
        try:
            with session:
                row = session.scalar(select(User).where(User.username == username))
                if row is not None:
                    if not row.is_active or not verify_password(password, row.password_hash):
                        return None
                    return AppUser(
                        username=row.username,
                        display_name=row.display_name or row.username,
                        role=row.role,
                        source="database",
                    )
        except SQLAlchemyError:
            logger.error("credential lookup failed; denying login (database unavailable)")
            return None
    if settings.demo_users_enabled and DEMO_PASSWORDS.get(username) == password:
        return DEMO_USERS[username]
    return None


def has_role(required: str, current: str | None) -> bool:
    if not current:
        return False
    if required not in ROLE_ORDER or current not in ROLE_ORDER:
        return False
    return ROLE_ORDER.index(current) >= ROLE_ORDER.index(required)


def local_dev_user(settings: Settings) -> AppUser:
    return AppUser(
        username="local",
        display_name="本地开发用户（认证未启用）",
        role="admin",
        source="dev",
    )
