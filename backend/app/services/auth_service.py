"""Application-layer identity (B8 minimal model).

Roles: viewer (read-only), analyst (create investigations, view evidence),
operator (manage authorised operation requests), admin (system settings).
The application role never maps to AgentGuard privileges automatically -
AgentGuard still enforces its own authorization on every upstream call.

When auth is disabled (dev default) an implicit local admin session is used,
clearly labelled; production must set AUTH_ENABLED=true.
"""

from __future__ import annotations

import dataclasses

from app.core.config import Settings

ROLE_ORDER = ["viewer", "analyst", "operator", "admin"]


@dataclasses.dataclass(frozen=True)
class AppUser:
    username: str
    display_name: str
    role: str
    password: str  # demo-only credentials; production auth is out of scope for MVP

    def to_public(self) -> dict:
        return {"username": self.username, "display_name": self.display_name, "role": self.role}


DEMO_USERS: dict[str, AppUser] = {
    user.username: user
    for user in [
        AppUser("viewer", "演示查看者", "viewer", "viewer-demo"),
        AppUser("analyst", "演示分析员", "analyst", "analyst-demo"),
        AppUser("operator", "演示操作员", "operator", "operator-demo"),
        AppUser("admin", "演示管理员", "admin", "admin-demo"),
    ]
}


def verify_credentials(username: str, password: str) -> AppUser | None:
    user = DEMO_USERS.get(username)
    if user is None or user.password != password:
        return None
    return user


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
        password="",
    )
