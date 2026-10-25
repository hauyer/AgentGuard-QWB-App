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
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

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


class LoopOwnershipError(RuntimeError):
    """A verified project-to-loop mapping could not be established safely."""

    def __init__(self, code: str, message: str, *, status_code: int = 409) -> None:
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


def _explicit_non_live_mode(mode_override: str | None) -> DataMode | None:
    if not mode_override:
        return None
    try:
        mode = DataMode(mode_override.strip().lower())
    except ValueError:
        return None
    return mode if mode is not DataMode.LIVE else None


def _membership_role(settings: Settings, user: AppUser, project_ids: tuple[int, ...]) -> str | None:
    if not project_ids:
        return None
    session = open_session(settings)
    if session is None:
        return None  # no DB: only the global-admin path can proceed
    try:
        with session:
            rows = session.scalars(
                select(ProjectMember.role).where(
                    ProjectMember.username == user.username,
                    ProjectMember.project_id.in_(project_ids),
                )
            ).all()
    except SQLAlchemyError as exc:
        raise AccessDenied(
            "AUTHORIZATION_STORAGE_UNAVAILABLE", "项目权限存储暂不可用", status_code=503
        ) from exc
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
    try:
        with session:
            rows = session.scalars(
                select(ProjectInvestigation.project_id).where(
                    ProjectInvestigation.agentguard_request_id == request_id)
            ).all()
    except SQLAlchemyError as exc:
        raise AccessDenied(
            "AUTHORIZATION_STORAGE_UNAVAILABLE", "项目权限存储暂不可用", status_code=503
        ) from exc
    return tuple(rows)


def require_investigation_access(
    settings: Settings,
    client: AgentGuardClient,
    user: AppUser,
    request_id: str,
    *,
    mode_override: str | None,
) -> AccessGrant:
    non_live_mode = _explicit_non_live_mode(mode_override)
    if non_live_mode is not None:
        # Demo namespace: login-gated, project-free; a missing request_id is
        # fine (graph samples are browsable without one).
        return AccessGrant(data_mode=non_live_mode, request_id=request_id, project_ids=(),
                           membership_role=None, is_global_admin=user.role == "admin")
    if not request_id:
        # Without an object ID there is no project scope to check. Preserve
        # the existing degraded-mode response when AgentGuard is unavailable;
        # a reachable Live source still requires a concrete request ID.
        mode = effective_mode(settings, client, mode_override)
        if mode is not DataMode.LIVE:
            return AccessGrant(data_mode=mode, request_id=request_id, project_ids=(),
                               membership_role=None, is_global_admin=user.role == "admin")
        raise AccessDenied("REQUEST_ID_REQUIRED", "缺少 request_id", status_code=422)
    project_ids = _linked_project_ids(settings, request_id)
    is_admin = user.role == "admin"
    role = _membership_role(settings, user, project_ids)
    if not project_ids:
        # Unlinked live object: admin-only, audited by the route.
        if not is_admin:
            raise AccessDenied()
        mode = effective_mode(settings, client, mode_override)
        return AccessGrant(data_mode=mode, request_id=request_id, project_ids=(),
                           membership_role=None, is_global_admin=True)
    if role is None and not is_admin:
        raise AccessDenied()
    # Check local authorization before probing AgentGuard. In particular, an
    # unauthorized request must not trigger even a health check against the
    # shared upstream credentials.
    mode = effective_mode(settings, client, mode_override)
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
    non_live_mode = _explicit_non_live_mode(mode_override)
    if non_live_mode is not None:
        return AccessGrant(data_mode=non_live_mode, request_id="", project_ids=(),
                           membership_role=None, is_global_admin=user.role == "admin")
    is_admin = user.role == "admin"
    session = open_session(settings)
    if session is None:
        if not is_admin:
            raise AccessDenied("LOOP_NOT_ACCESSIBLE", "调查循环不存在或不可访问")
        mode = effective_mode(settings, client, mode_override)
        return AccessGrant(data_mode=mode, request_id="", project_ids=(),
                           membership_role=None, is_global_admin=True)
    try:
        with session:
            rows = session.scalars(
                select(ProjectInvestigationLoop).where(ProjectInvestigationLoop.loop_id == loop_id)
            ).all()
    except SQLAlchemyError as exc:
        raise AccessDenied(
            "AUTHORIZATION_STORAGE_UNAVAILABLE", "项目权限存储暂不可用", status_code=503
        ) from exc
    if not rows:
        if not is_admin:
            raise AccessDenied("LOOP_NOT_ACCESSIBLE", "调查循环不存在或不可访问")
        mode = effective_mode(settings, client, mode_override)
        return AccessGrant(data_mode=mode, request_id="", project_ids=(),
                           membership_role=None, is_global_admin=True)
    project_ids = tuple(row.project_id for row in rows)
    request_ids = tuple(row.base_request_id for row in rows)
    role = _membership_role(settings, user, project_ids)
    if role is None and not is_admin:
        raise AccessDenied("LOOP_NOT_ACCESSIBLE", "调查循环不存在或不可访问")
    # Deny unknown or cross-project loop IDs before contacting AgentGuard.
    mode = effective_mode(settings, client, mode_override)
    return AccessGrant(data_mode=mode, request_id=request_ids[0] if request_ids else "",
                       project_ids=project_ids, membership_role=role, is_global_admin=is_admin)


def require_trusted_investigation_project(
    settings: Settings,
    request_id: str,
    grant: AccessGrant,
) -> int:
    """Return the only trusted project owner for a verified base investigation."""
    if grant.data_mode is not DataMode.LIVE:
        raise LoopOwnershipError(
            "LIVE_SOURCE_REQUIRED", "Loop 归属只能根据实时 AgentGuard 数据建立", status_code=503
        )
    session = open_session(settings)
    if session is None:
        raise LoopOwnershipError(
            "OWNERSHIP_STORAGE_UNAVAILABLE", "项目归属存储暂不可用", status_code=503
        )
    try:
        with session:
            rows = session.scalars(
                select(ProjectInvestigation).where(
                    ProjectInvestigation.agentguard_request_id == request_id
                )
            ).all()
            project_ids = {row.project_id for row in rows}
            if len(rows) != 1 or len(project_ids) != 1:
                raise LoopOwnershipError(
                    "INVESTIGATION_OWNERSHIP_CONFLICT",
                    "基础调查没有唯一的本地项目归属，Loop 列表未开放",
                )
            row = rows[0]
            if row.verification != "verified" or row.verification_source != DataMode.LIVE.value:
                raise LoopOwnershipError(
                    "INVESTIGATION_OWNERSHIP_UNVERIFIED",
                    "基础调查不是由 AgentGuard Live 验证，Loop 列表未开放",
                )
            project_id = row.project_id
            if session.get(Project, project_id) is None:
                raise LoopOwnershipError(
                    "INVESTIGATION_PROJECT_MISSING", "基础调查关联的项目不存在"
                )
    except LoopOwnershipError:
        raise
    except SQLAlchemyError as exc:
        raise LoopOwnershipError(
            "OWNERSHIP_STORAGE_UNAVAILABLE", "项目归属存储暂不可用", status_code=503
        ) from exc
    if project_id not in grant.project_ids:
        raise LoopOwnershipError(
            "INVESTIGATION_NOT_ACCESSIBLE", "基础调查不存在或不可访问", status_code=404
        )
    return project_id


def register_verified_investigation_loops(
    settings: Settings,
    *,
    request_id: str,
    project_id: int,
    loop_items: list[dict],
    created_by: str,
) -> None:
    """Atomically persist only upstream-verified loop ownership mappings.

    Repeated list reads are idempotent. A loop already assigned to another
    project or base investigation fails the whole transaction.
    """
    session = open_session(settings)
    if session is None:
        raise LoopOwnershipError(
            "OWNERSHIP_STORAGE_UNAVAILABLE", "项目归属存储暂不可用", status_code=503
        )
    try:
        with session.begin():
            base_rows = session.scalars(
                select(ProjectInvestigation).where(
                    ProjectInvestigation.agentguard_request_id == request_id
                )
            ).all()
            project_ids = {row.project_id for row in base_rows}
            if (len(base_rows) != 1 or project_ids != {project_id}
                    or base_rows[0].verification != "verified"
                    or base_rows[0].verification_source != DataMode.LIVE.value):
                raise LoopOwnershipError(
                    "INVESTIGATION_OWNERSHIP_CONFLICT",
                    "基础调查项目归属已变化或存在冲突，Loop 映射未写入",
                )
            if session.get(Project, project_id) is None:
                raise LoopOwnershipError(
                    "INVESTIGATION_PROJECT_MISSING", "基础调查关联的项目不存在"
                )

            for item in loop_items:
                loop_id = item["loop_id"]
                existing = session.scalar(
                    select(ProjectInvestigationLoop).where(
                        ProjectInvestigationLoop.loop_id == loop_id
                    )
                )
                if existing is None:
                    session.add(ProjectInvestigationLoop(
                        project_id=project_id,
                        base_request_id=request_id,
                        loop_id=loop_id,
                        created_by=created_by,
                        verified_source="agentguard",
                    ))
                    continue
                if existing.project_id != project_id or existing.base_request_id != request_id:
                    raise LoopOwnershipError(
                        "LOOP_OWNERSHIP_CONFLICT",
                        "Loop 已关联到其他项目或基础调查，映射未写入",
                    )
                if existing.verified_source not in {"unverified", "agentguard"}:
                    raise LoopOwnershipError(
                        "LOOP_OWNERSHIP_CONFLICT",
                        "Loop 的本地归属来源不匹配，映射未写入",
                    )
                existing.verified_source = "agentguard"
    except LoopOwnershipError:
        raise
    except IntegrityError as exc:
        raise LoopOwnershipError(
            "LOOP_OWNERSHIP_CONFLICT", "Loop 项目归属发生并发冲突，映射未写入"
        ) from exc
    except SQLAlchemyError as exc:
        raise LoopOwnershipError(
            "OWNERSHIP_STORAGE_UNAVAILABLE", "Loop 项目归属写入失败", status_code=503
        ) from exc


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
                verification_source=DataMode.LIVE.value,
            ))
            session.commit()
        return True
    except Exception:  # noqa: BLE001 - link failure must not fail the creation response path silently
        return False
