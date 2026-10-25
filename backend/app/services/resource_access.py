"""Unified resource authorization (B19).

LIVE data is project data: every live-mode business object addressed by a
request_id or run_id must resolve to a project the caller is a member of
before any upstream call with the shared service credentials is made.

Rules:
  * request_id → project_investigations rows → member of ≥1 owning project.
  * run_id → last_known_run_id bridge (refreshed on authorized reads).
  * Objects linked to no project: visible to global admin only (audited);
    everyone else gets 404 - existence is never revealed.
  * Demo namespace (recorded/synthetic): login-gated, project-free, isolated.
  * Global admin bypass is explicit and audited by the calling route.
"""

from __future__ import annotations

import dataclasses

from sqlalchemy import select

from app.core.config import Settings
from app.core.data_mode import DataMode, effective_data_mode
from app.core.db import open_session
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.models.app import Project, ProjectInvestigation, ProjectInvestigationLoop, ProjectMember
from app.services.auth_service import AppUser


class AccessDenied(RuntimeError):
    """Denial without existence leakage: 404 for object reads (existence is
    never revealed), 403 for scope restrictions with an explicit reason."""

    def __init__(self, code: str = "INVESTIGATION_NOT_ACCESSIBLE",
                 message: str = "对象不存在或不可访问", *, status_code: int = 404) -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(message)


@dataclasses.dataclass(frozen=True)
class AccessGrant:
    data_mode: DataMode
    request_id: str
    # project ids in project_investigations that own this request_id
    project_ids: tuple[int, ...]
    membership_role: str | None  # highest project role across owning projects
    is_global_admin: bool


def effective_mode(settings: Settings, client: AgentGuardClient, mode_override: str | None) -> DataMode:
    reachable = False
    try:
        client.health()
        reachable = True
    except AgentGuardError:
        reachable = False
    return effective_data_mode(mode_override, reachable)


def _membership_role(settings: Settings, user: AppUser, project_ids: tuple[int, ...]) -> str | None:
    if not project_ids:
        return None
    session = open_session(settings)
    if session is None:
        return None  # no DB: only the global-admin path can proceed
    with session:
        rows = session.scalars(
            select(ProjectMember.role).where(
                ProjectMember.username == user.username,
                ProjectMember.project_id.in_(project_ids),
            )
        ).all()
    if not rows:
        return None
    order = ["viewer", "analyst", "operator", "admin"]
    return max((role for role in rows if role in order), key=order.index, default=None)


def _linked_project_ids(settings: Settings, request_id: str) -> tuple[int, ...]:
    session = open_session(settings)
    if session is None:
        # No authorization storage: nothing can be project-linked, so the only
        # path forward is the audited global-admin bypass (fail closed for
        # everyone else).
        return ()
    with session:
        rows = session.scalars(
            select(ProjectInvestigation.project_id).where(
                ProjectInvestigation.agentguard_request_id == request_id)
        ).all()
    return tuple(rows)


def require_investigation_access(
    settings: Settings,
    client: AgentGuardClient,
    user: AppUser,
    request_id: str,
    *,
    mode_override: str | None,
) -> AccessGrant:
    mode = effective_mode(settings, client, mode_override)
    if mode is not DataMode.LIVE:
        # Demo namespace: login-gated, project-free; a missing request_id is
        # fine (graph samples are browsable without one).
        return AccessGrant(data_mode=mode, request_id=request_id, project_ids=(),
                           membership_role=None, is_global_admin=user.role == "admin")
    if not request_id:
        raise AccessDenied("REQUEST_ID_REQUIRED", "缺少 request_id", status_code=422)
    project_ids = _linked_project_ids(settings, request_id)
    is_admin = user.role == "admin"
    role = _membership_role(settings, user, project_ids)
    if not project_ids:
        # Unlinked live object: admin-only, audited by the route.
        if not is_admin:
            raise AccessDenied()
        return AccessGrant(data_mode=mode, request_id=request_id, project_ids=(),
                           membership_role=None, is_global_admin=True)
    if role is None and not is_admin:
        raise AccessDenied()
    return AccessGrant(data_mode=mode, request_id=request_id, project_ids=project_ids,
                       membership_role=role, is_global_admin=is_admin)


def require_run_access(
    settings: Settings,
    client: AgentGuardClient,
    user: AppUser,
    run_id: str,
    *,
    mode_override: str | None,
) -> AccessGrant:
    """run_id-addressed resources (reports). Authorization resolves through the
    local run bridge; unknown run_ids are denied for non-admins (existence is
    not revealed even though AgentGuard would answer 200)."""
    mode = effective_mode(settings, client, mode_override)
    if mode is not DataMode.LIVE:
        return AccessGrant(data_mode=mode, request_id="", project_ids=(),
                           membership_role=None, is_global_admin=user.role == "admin")
    is_admin = user.role == "admin"
    session = open_session(settings)
    if session is None:
        # No authorization storage: run cannot be project-linked; admin-only.
        if not is_admin:
            raise AccessDenied("REPORT_NOT_ACCESSIBLE", "报告不存在或不可访问")
        return AccessGrant(data_mode=mode, request_id="", project_ids=(),
                           membership_role=None, is_global_admin=True)
    with session:
        rows = session.scalars(
            select(ProjectInvestigation).where(ProjectInvestigation.last_known_run_id == run_id)
        ).all()
    project_ids = tuple(row.project_id for row in rows)
    request_ids = tuple(row.agentguard_request_id for row in rows)
    if not project_ids:
        if not is_admin:
            raise AccessDenied("REPORT_NOT_ACCESSIBLE", "报告不存在或不可访问")
        return AccessGrant(data_mode=mode, request_id="", project_ids=(),
                           membership_role=None, is_global_admin=True)
    role = _membership_role(settings, user, project_ids)
    if role is None and not is_admin:
        raise AccessDenied("REPORT_NOT_ACCESSIBLE", "报告不存在或不可访问")
    return AccessGrant(data_mode=mode, request_id=request_ids[0] if request_ids else "",
                       project_ids=project_ids, membership_role=role, is_global_admin=is_admin)


def require_admin_scope(user: AppUser, *, code: str, message: str) -> None:
    """Upstream-wide collections (experiment index, experiences) expose records
    that cannot be attributed to projects: global admin only in live mode."""
    if user.role != "admin":
        raise AccessDenied(code, message, status_code=403)


def require_loop_access(
    settings: Settings,
    client: AgentGuardClient,
    user: AppUser,
    loop_id: str,
    *,
    mode_override: str | None,
) -> AccessGrant:
    """loop_id-addressed resources (E6 loops). Authorization resolves through the
    local loop→project mapping; unknown loop_ids are denied for non-admins."""
    mode = effective_mode(settings, client, mode_override)
    if mode is not DataMode.LIVE:
        return AccessGrant(data_mode=mode, request_id="", project_ids=(),
                           membership_role=None, is_global_admin=user.role == "admin")
    is_admin = user.role == "admin"
    session = open_session(settings)
    if session is None:
        if not is_admin:
            raise AccessDenied("LOOP_NOT_ACCESSIBLE", "调查循环不存在或不可访问")
        return AccessGrant(data_mode=mode, request_id="", project_ids=(),
                           membership_role=None, is_global_admin=True)
    with session:
        rows = session.scalars(
            select(ProjectInvestigationLoop).where(ProjectInvestigationLoop.loop_id == loop_id)
        ).all()
    if not rows:
        if not is_admin:
            raise AccessDenied("LOOP_NOT_ACCESSIBLE", "调查循环不存在或不可访问")
        return AccessGrant(data_mode=mode, request_id="", project_ids=(),
                           membership_role=None, is_global_admin=True)
    project_ids = tuple(row.project_id for row in rows)
    request_ids = tuple(row.base_request_id for row in rows)
    role = _membership_role(settings, user, project_ids)
    if role is None and not is_admin:
        raise AccessDenied("LOOP_NOT_ACCESSIBLE", "调查循环不存在或不可访问")
    return AccessGrant(data_mode=mode, request_id=request_ids[0] if request_ids else "",
                       project_ids=project_ids, membership_role=role, is_global_admin=is_admin)


def refresh_run_bridge(settings: Settings, request_id: str, run_id: str | None) -> None:
    """Best-effort bridge refresh after an authorized investigation read."""
    if not run_id:
        return
    session = open_session(settings)
    if session is None:
        return
    with session:
        rows = session.scalars(
            select(ProjectInvestigation).where(
                ProjectInvestigation.agentguard_request_id == request_id)
        ).all()
        for row in rows:
            if row.last_known_run_id != run_id:
                row.last_known_run_id = run_id
        session.commit()


def link_investigation_after_creation(settings: Settings, project_id: int, request_id: str,
                                      created_by: str) -> bool:
    """Persist the local project link after a successful upstream submission.

    Returns True when persisted; False when the write failed (the route must
    then surface link_pending instead of pretending the link exists).
    """
    session = open_session(settings)
    if session is None:
        return False
    try:
        with session:
            project = session.get(Project, project_id)
            if project is None:
                return False
            session.add(ProjectInvestigation(
                project_id=project_id,
                agentguard_request_id=request_id,
                created_by=created_by,
                verification="verified",
            ))
            session.commit()
        return True
    except Exception:  # noqa: BLE001 - link failure must not fail the creation response path silently
        return False
