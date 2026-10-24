"""Project management routes (B12).

Consistent API contract:
  GET    /api/projects
  POST   /api/projects
  GET    /api/projects/{project_id}
  PATCH  /api/projects/{project_id}
  GET    /api/projects/{project_id}/members
  POST   /api/projects/{project_id}/members
  DELETE /api/projects/{project_id}/members/{username}
  GET    /api/projects/{project_id}/investigations
  POST   /api/projects/{project_id}/investigations
  DELETE /api/projects/{project_id}/investigations/{agentguard_request_id}

Every mutating route is CSRF-protected, role-gated, project-membership-gated
and writes to the persisted audit log with a project scope.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import require_role, require_role_csrf
from app.services import project_service
from app.services.project_service import ProjectServiceError

router = APIRouter()

AnalystCsrf = Annotated[object, Depends(require_role_csrf("analyst"))]


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=4000)


class UpdateProjectRequest(BaseModel):
    description: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(default=None, pattern="^(active|archived)$")


class AddMemberRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    role: str = Field(pattern="^(viewer|analyst|operator|admin)$")


class LinkInvestigationRequest(BaseModel):
    agentguard_request_id: str = Field(min_length=1, max_length=64)
    display_name: str | None = Field(default=None, max_length=256)
    notes: str | None = Field(default=None, max_length=4000)


def _error_response(exc: ProjectServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": {"error": exc.code, "message": str(exc)}})


def _mode_override(request: Request) -> str | None:
    return request.app.state.settings.app_data_mode or None


@router.get("/projects")
def projects_list(
    request: Request,
    user: Annotated[object, Depends(require_role("viewer"))],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    try:
        items, total = project_service.list_projects(
            request.app.state.settings, user, limit=limit, offset=offset)
    except ProjectServiceError as exc:
        return _error_response(exc)
    return {"count": len(items), "total": total, "offset": offset, "limit": limit, "items": items}


@router.post("/projects", status_code=201)
def projects_create(
    request: Request,
    body: CreateProjectRequest,
    user: AnalystCsrf,
) -> dict:
    try:
        payload = project_service.create_project(
            request.app.state.settings, actor=user, name=body.name, description=body.description)
    except ProjectServiceError as exc:
        return _error_response(exc)
    request.app.state.audit_service.record(
        actor=user.username, role=user.role, action="project.create",
        target=str(payload["project_id"]), project_id=payload["project_id"],
        detail=f"name={body.name}")
    return {"created": payload}


@router.get("/projects/{project_id}")
def projects_detail(
    request: Request,
    project_id: int,
    user: Annotated[object, Depends(require_role("viewer"))],
) -> dict:
    try:
        context = project_service.require_project_access(
            request.app.state.settings, user, project_id, required_role="viewer")
        payload = project_service.get_project(request.app.state.settings, context)
    except ProjectServiceError as exc:
        return _error_response(exc)
    return {"project": payload, "membership_role": context.membership_role or "global-admin"}


@router.patch("/projects/{project_id}")
def projects_update(
    request: Request,
    project_id: int,
    body: UpdateProjectRequest,
    user: AnalystCsrf,
) -> dict:
    try:
        context = project_service.require_project_access(
            request.app.state.settings, user, project_id, required_role="admin")
        payload = project_service.update_project(
            request.app.state.settings, context, actor=user,
            description=body.description, status=body.status)
    except ProjectServiceError as exc:
        return _error_response(exc)
    request.app.state.audit_service.record(
        actor=user.username, role=user.role, action="project.update",
        target=str(project_id), project_id=project_id,
        detail=("description=set" if body.description is not None else "description=unchanged")
               + f" status={body.status or 'unchanged'}")
    return {"updated": payload}


@router.get("/projects/{project_id}/members")
def members_list(
    request: Request,
    project_id: int,
    user: Annotated[object, Depends(require_role("viewer"))],
) -> dict:
    try:
        context = project_service.require_project_access(
            request.app.state.settings, user, project_id, required_role="viewer")
        items = project_service.list_members(request.app.state.settings, context)
    except ProjectServiceError as exc:
        return _error_response(exc)
    return {"count": len(items), "items": items}


@router.post("/projects/{project_id}/members", status_code=201)
def members_add(
    request: Request,
    project_id: int,
    body: AddMemberRequest,
    user: AnalystCsrf,
) -> dict:
    try:
        context = project_service.require_project_access(
            request.app.state.settings, user, project_id, required_role="admin")
        payload = project_service.add_member(
            request.app.state.settings, context, actor=user,
            username=body.username, role=body.role)
    except ProjectServiceError as exc:
        return _error_response(exc)
    request.app.state.audit_service.record(
        actor=user.username, role=user.role, action="project.member.add",
        target=body.username, project_id=project_id,
        detail=f"role={body.role}")
    return {"added": payload}


@router.delete("/projects/{project_id}/members/{username}")
def members_remove(
    request: Request,
    project_id: int,
    username: str,
    user: AnalystCsrf,
) -> dict:
    try:
        context = project_service.require_project_access(
            request.app.state.settings, user, project_id, required_role="admin")
        payload = project_service.remove_member(
            request.app.state.settings, context, actor=user, username=username)
    except ProjectServiceError as exc:
        return _error_response(exc)
    request.app.state.audit_service.record(
        actor=user.username, role=user.role, action="project.member.remove",
        target=username, project_id=project_id)
    return payload


@router.get("/projects/{project_id}/investigations")
def project_investigations(
    request: Request,
    project_id: int,
    user: Annotated[object, Depends(require_role("viewer"))],
) -> dict:
    try:
        context = project_service.require_project_access(
            request.app.state.settings, user, project_id, required_role="viewer")
        items = project_service.list_investigations(request.app.state.settings, context)
    except ProjectServiceError as exc:
        return _error_response(exc)
    return {"count": len(items), "items": items}


@router.post("/projects/{project_id}/investigations", status_code=201)
def investigations_link(
    request: Request,
    project_id: int,
    body: LinkInvestigationRequest,
    user: AnalystCsrf,
) -> dict:
    try:
        context = project_service.require_project_access(
            request.app.state.settings, user, project_id, required_role="analyst")
        payload = project_service.link_investigation(
            request.app.state.settings,
            request.app.state.agentguard_client,
            request.app.state.demo_service,
            context,
            actor=user,
            agentguard_request_id=body.agentguard_request_id,
            display_name=body.display_name,
            notes=body.notes,
            mode_override=_mode_override(request),
        )
    except ProjectServiceError as exc:
        return _error_response(exc)
    request.app.state.audit_service.record(
        actor=user.username, role=user.role, action="project.investigation.link",
        target=body.agentguard_request_id, project_id=project_id,
        detail=f"verification={payload['verification']}")
    return {"linked": payload}


@router.delete("/projects/{project_id}/investigations/{agentguard_request_id}")
def investigations_unlink(
    request: Request,
    project_id: int,
    agentguard_request_id: str,
    user: AnalystCsrf,
) -> dict:
    try:
        context = project_service.require_project_access(
            request.app.state.settings, user, project_id, required_role="analyst")
        payload = project_service.unlink_investigation(
            request.app.state.settings, context, agentguard_request_id=agentguard_request_id)
    except ProjectServiceError as exc:
        return _error_response(exc)
    request.app.state.audit_service.record(
        actor=user.username, role=user.role, action="project.investigation.unlink",
        target=agentguard_request_id, project_id=project_id)
    return payload
