"""Project management with real permission isolation (B12).

Permission model:
  * Global role (viewer/analyst/operator/admin) governs platform-level actions.
  * Project membership adds a project-scoped role on the same scale; a global
    analyst is NOT automatically a member of every project and cannot read a
    project's data unless listed in project_members (global admin excepted).
  * Membership changes take effect on the next request - there is no cached
    membership state in sessions.
  * Application roles never map to AgentGuard privileges.

Every write goes through the database audit log with an optional project scope.
"""

from __future__ import annotations

import dataclasses

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.data_mode import DataMode, effective_data_mode
from app.core.db import open_session
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.models.app import Project, ProjectInvestigation, ProjectMember
from app.services.demo_service import DemoService

PROJECT_ROLES = ["viewer", "analyst", "operator", "admin"]
PROJECT_STATUSES = {"active", "archived"}


class ProjectServiceError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(message)


@dataclasses.dataclass(frozen=True)
class ProjectContext:
    project: Project
    membership_role: str | None  # None when not a member (global admin path)


def _session(settings: Settings):
    session = open_session(settings)
    if session is None:
        raise ProjectServiceError(503, "PROJECTS_REQUIRE_DATABASE",
                                  "项目管理需要 DATABASE_URL（projects 表为业务数据，不能内存化）")
    return session


def require_project_access(
    settings: Settings,
    user,
    project_id: int,
    *,
    required_role: str,
) -> ProjectContext:
    """Load the project and enforce membership-or-global-admin access."""
    with _session(settings) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise ProjectServiceError(404, "PROJECT_NOT_FOUND", f"项目不存在：{project_id}")
        membership_role = session.scalar(
            select(ProjectMember.role).where(
                ProjectMember.project_id == project_id,
                ProjectMember.username == user.username,
            )
        )
        if user.role == "admin" and user.source in {"database", "demo", "dev"}:
            # Global admin: full access, still audited per action.
            return ProjectContext(project=project, membership_role=membership_role)
        if membership_role is None:
            # Uniform 404 for outsiders: do not reveal project existence.
            raise ProjectServiceError(404, "PROJECT_NOT_FOUND", f"项目不存在：{project_id}")
        if membership_role not in PROJECT_ROLES:
            raise ProjectServiceError(403, "PERMISSION_DENIED", "项目成员角色无效")
        from app.services.auth_service import has_role

        if not has_role(required_role, membership_role):
            raise ProjectServiceError(
                403, "PERMISSION_DENIED",
                f"项目内角色 {membership_role} 无权执行该操作（需要 {required_role} 及以上）")
        return ProjectContext(project=project, membership_role=membership_role)


def create_project(
    settings: Settings,
    *,
    actor,
    name: str,
    description: str | None,
) -> dict:
    with _session(settings) as session:
        existing = session.scalar(select(Project).where(Project.name == name))
        if existing is not None:
            raise ProjectServiceError(409, "PROJECT_EXISTS", f"项目名称已存在：{name}")
        project = Project(name=name, description=description, status="active",
                          created_by=actor.username)
        session.add(project)
        session.flush()
        session.add(ProjectMember(project_id=project.id, username=actor.username,
                                  role="admin", added_by=actor.username))
        session.commit()
        return _project_payload(session, project, include_members=True)


def list_projects(settings: Settings, user, *, limit: int, offset: int) -> tuple[list[dict], int]:
    with _session(settings) as session:
        total = session.scalar(select(func.count()).select_from(Project))
        query = select(Project).order_by(Project.id.desc()).limit(limit).offset(offset)
        if user.role != "admin":
            member_project_ids = select(ProjectMember.project_id).where(
                ProjectMember.username == user.username)
            query = query.where(Project.id.in_(member_project_ids))
        projects = session.scalars(query).all()
        return [_project_payload(session, project) for project in projects], int(total or 0)


def get_project(settings: Settings, context: ProjectContext, *, include_members: bool = True) -> dict:
    with _session(settings) as session:
        session.add(context.project)
        return _project_payload(session, context.project, include_members=include_members)


def update_project(
    settings: Settings,
    context: ProjectContext,
    *,
    actor,
    description: str | None = None,
    status: str | None = None,
) -> dict:
    if status is not None and status not in PROJECT_STATUSES:
        raise ProjectServiceError(422, "INVALID_STATUS", f"项目状态必须是 {sorted(PROJECT_STATUSES)}")
    with _session(settings) as session:
        project = session.merge(context.project)
        if description is not None:
            project.description = description
        if status is not None:
            project.status = status
        session.commit()
        return _project_payload(session, project, include_members=True)


def list_members(settings: Settings, context: ProjectContext) -> list[dict]:
    with _session(settings) as session:
        rows = session.scalars(
            select(ProjectMember).where(ProjectMember.project_id == context.project.id)
            .order_by(ProjectMember.created_at)
        ).all()
        return [
            {
                "username": row.username,
                "role": row.role,
                "added_by": row.added_by,
                "added_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]


def add_member(
    settings: Settings,
    context: ProjectContext,
    *,
    actor,
    username: str,
    role: str,
) -> dict:
    if role not in PROJECT_ROLES:
        raise ProjectServiceError(422, "INVALID_ROLE", f"项目成员角色必须是 {PROJECT_ROLES} 之一")
    with _session(settings) as session:
        project = session.merge(context.project)
        if project.status == "archived":
            raise ProjectServiceError(409, "PROJECT_ARCHIVED", "项目已归档，不能调整成员")
        existing = session.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id, ProjectMember.username == username)
        )
        if existing is not None:
            raise ProjectServiceError(409, "MEMBER_EXISTS", f"用户已是项目成员：{username}")
        member = ProjectMember(project_id=project.id, username=username, role=role,
                               added_by=actor.username)
        session.add(member)
        try:
            session.commit()
        except IntegrityError as exc:
            # The unique constraint is the concurrency authority: two parallel
            # adds must end with one membership and an explicit 409, never a 500.
            session.rollback()
            raise ProjectServiceError(409, "MEMBER_EXISTS",
                                      f"用户已是项目成员：{username}") from exc
        return {"username": member.username, "role": member.role,
                "added_by": member.added_by,
                "added_at": member.created_at.isoformat() if member.created_at else None}


def remove_member(settings: Settings, context: ProjectContext, *, actor, username: str) -> dict:
    with _session(settings) as session:
        project = session.merge(context.project)
        if project.status == "archived":
            raise ProjectServiceError(409, "PROJECT_ARCHIVED", "项目已归档，不能调整成员")
        member = session.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id, ProjectMember.username == username)
        )
        if member is None:
            raise ProjectServiceError(404, "MEMBER_NOT_FOUND", f"用户不是项目成员：{username}")
        admins = session.scalars(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id, ProjectMember.role == "admin")
        ).all()
        if member.role == "admin" and len(admins) <= 1:
            raise ProjectServiceError(409, "LAST_PROJECT_ADMIN",
                                      "不能移除最后一个项目管理员")
        session.delete(member)
        session.commit()
        return {"removed": username}


def link_investigation(
    settings: Settings,
    client: AgentGuardClient,
    demo: DemoService,
    context: ProjectContext,
    *,
    actor,
    agentguard_request_id: str,
    display_name: str | None,
    notes: str | None,
    mode_override: str | None,
) -> dict:
    """Reference an AgentGuard-stored investigation. The reference is only
    accepted when the investigation actually exists in the authoritative
    source for the current data mode; live mode verifies via the public API,
    demo modes via fixtures, and unavailable mode refuses (no fabricated links).
    """
    mode = effective_data_mode(mode_override, _reachable(client))
    if mode == DataMode.LIVE:
        try:
            client.get_investigation(agentguard_request_id)
            verification = "verified"
        except AgentGuardError as exc:
            if exc.status_code == 404:
                raise ProjectServiceError(
                    422, "INVESTIGATION_NOT_FOUND",
                    f"AgentGuard 中不存在该调查：{agentguard_request_id}") from exc
            raise ProjectServiceError(
                502, "VERIFICATION_FAILED",
                f"无法向上游验证调查（HTTP {exc.status_code} {exc.code}）；未建立关联") from exc
    elif mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        if demo.get_investigation(agentguard_request_id) is None:
            raise ProjectServiceError(422, "INVESTIGATION_NOT_FOUND",
                                      f"演示数据源中不存在该调查：{agentguard_request_id}")
        verification = "verified"
    else:
        raise ProjectServiceError(
            503, "VERIFICATION_UNAVAILABLE",
            "AgentGuard 不可达且未启用演示模式；无法验证调查存在，未建立关联")

    with _session(settings) as session:
        project = session.merge(context.project)
        if project.status == "archived":
            raise ProjectServiceError(409, "PROJECT_ARCHIVED", "项目已归档，不能关联调查")
        existing = session.scalar(
            select(ProjectInvestigation).where(
                ProjectInvestigation.project_id == project.id,
                ProjectInvestigation.agentguard_request_id == agentguard_request_id)
        )
        if existing is not None:
            raise ProjectServiceError(409, "INVESTIGATION_LINKED",
                                      f"该调查已关联到此项目：{agentguard_request_id}")
        row = ProjectInvestigation(
            project_id=project.id,
            agentguard_request_id=agentguard_request_id,
            created_by=actor.username,
            display_name=display_name,
            notes=notes,
            verification=verification,
            verification_source=mode.value,
        )
        session.add(row)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise ProjectServiceError(409, "INVESTIGATION_LINKED",
                                      f"该调查已关联到此项目：{agentguard_request_id}") from exc
        return _investigation_payload(row)


def list_investigations(settings: Settings, context: ProjectContext) -> list[dict]:
    with _session(settings) as session:
        rows = session.scalars(
            select(ProjectInvestigation)
            .where(ProjectInvestigation.project_id == context.project.id)
            .order_by(ProjectInvestigation.created_at.desc())
        ).all()
        return [_investigation_payload(row) for row in rows]


def unlink_investigation(
    settings: Settings, context: ProjectContext, *, agentguard_request_id: str
) -> dict:
    with _session(settings) as session:
        project = session.merge(context.project)
        row = session.scalar(
            select(ProjectInvestigation).where(
                ProjectInvestigation.project_id == project.id,
                ProjectInvestigation.agentguard_request_id == agentguard_request_id)
        )
        if row is None:
            raise ProjectServiceError(404, "INVESTIGATION_NOT_LINKED",
                                      f"该调查未关联到此项目：{agentguard_request_id}")
        session.delete(row)
        session.commit()
        return {"unlinked": agentguard_request_id}


def _reachable(client: AgentGuardClient) -> bool:
    try:
        client.health()
        return True
    except AgentGuardError:
        return False


def _project_payload(session, project: Project, *, include_members: bool = False) -> dict:
    payload = {
        "project_id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "created_by": project.created_by,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "investigation_count": int(session.scalar(
            select(func.count()).select_from(ProjectInvestigation)
            .where(ProjectInvestigation.project_id == project.id)) or 0),
    }
    if include_members:
        payload["members"] = [
            {"username": row.username, "role": row.role, "added_by": row.added_by}
            for row in session.scalars(
                select(ProjectMember).where(ProjectMember.project_id == project.id)
            ).all()
        ]
    return payload


def _investigation_payload(row: ProjectInvestigation) -> dict:
    return {
        "agentguard_request_id": row.agentguard_request_id,
        "display_name": row.display_name,
        "notes": row.notes,
        "verification": row.verification,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
