"""Evidence + defense workspace routes (B5, project-scoped since B19)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import require_role, require_role_csrf
from app.integrations.agentguard_client import AgentGuardClient
from app.services import resource_access
from app.services.evidence_service import (
    EvidenceServiceError,
    get_defense,
    get_evidence,
    historical_outcomes,
    preview_defense,
)

router = APIRouter()


def get_agentguard_client(request: Request) -> AgentGuardClient:
    return request.app.state.agentguard_client


AgentGuardClientDep = Annotated[AgentGuardClient, Depends(get_agentguard_client)]
Viewer = Annotated[object, Depends(require_role("viewer"))]
AnalystCsrf = Annotated[object, Depends(require_role_csrf("analyst"))]


def _mode_override(request: Request) -> str | None:
    return request.app.state.settings.app_data_mode or None


def _guard(request: Request, user, request_id: str):
    """Shared project-scope gate for request_id-addressed live objects."""
    return resource_access.require_investigation_access(
        request.app.state.settings, request.app.state.agentguard_client, user,
        request_id, mode_override=_mode_override(request))


@router.get("/evidence")
def evidence_list(
    request: Request,
    client: AgentGuardClientDep,
    user: Viewer,
    request_id: str = Query(description="调查 request_id，必填"),
) -> dict:
    try:
        grant = _guard(request, user, request_id)
        payload, meta = get_evidence(
            client, request.app.state.demo_service, mode_override=_mode_override(request), request_id=request_id
        )
    except resource_access.AccessDenied as exc:
        return _error_response(exc)
    except EvidenceServiceError as exc:
        return _error_response(exc)
    _audit_admin_access(request, user, grant, request_id, "evidence.read")
    return {"meta": {**meta, "project_ids": list(grant.project_ids)}, "evidence": payload}


@router.get("/defense")
def defense_list(
    request: Request,
    client: AgentGuardClientDep,
    user: Viewer,
    request_id: str = Query(description="调查 request_id，必填"),
) -> dict:
    try:
        grant = _guard(request, user, request_id)
        payload, meta = get_defense(
            client, request.app.state.demo_service, mode_override=_mode_override(request), request_id=request_id
        )
    except resource_access.AccessDenied as exc:
        return _error_response(exc)
    except EvidenceServiceError as exc:
        return _error_response(exc)
    _audit_admin_access(request, user, grant, request_id, "defense.read")
    return {"meta": {**meta, "project_ids": list(grant.project_ids)}, "defense": payload}


@router.post("/defense/{request_id}/preview")
def defense_preview(
    request: Request,
    request_id: str,
    client: AgentGuardClientDep,
    user: AnalystCsrf,
) -> dict:
    """Generate/refresh candidate preview only; never executes a defense."""
    try:
        grant = _guard(request, user, request_id)
        payload, meta = preview_defense(
            client, request.app.state.demo_service, mode_override=_mode_override(request), request_id=request_id
        )
    except resource_access.AccessDenied as exc:
        return _error_response(exc)
    except EvidenceServiceError as exc:
        return _error_response(exc)
    _audit_admin_access(request, user, grant, request_id, "defense.preview.admin")
    request.app.state.audit_service.record(
        actor=user.username,
        role=user.role,
        action="defense.preview",
        target=request_id,
        project_id=grant.project_ids[0] if grant.project_ids else None,
        detail=f"data_mode={meta.get('data_mode')} execution_performed={payload.get('execution_performed')}",
    )
    return {"meta": {**meta, "project_ids": list(grant.project_ids)}, "defense": payload}


@router.get("/defense/outcomes")
def defense_outcomes(
    request: Request,
    client: AgentGuardClientDep,
    _user: Viewer,
) -> dict:
    try:
        payload, meta = historical_outcomes(
            client, request.app.state.demo_service, mode_override=_mode_override(request)
        )
    except EvidenceServiceError as exc:
        return _error_response(exc)
    return {"meta": meta, "outcomes": payload}


def _audit_admin_access(request: Request, user, grant, request_id: str, action: str) -> None:
    if grant.is_global_admin and not grant.project_ids:
        request.app.state.audit_service.record(
            actor=user.username, role=user.role, action="resource.admin_access",
            target=request_id, detail=action)


def _error_response(exc: EvidenceServiceError | resource_access.AccessDenied) -> JSONResponse:
    detail = {"error": exc.code, "message": str(exc)}
    request_id = getattr(exc, "request_id", None)
    if request_id:
        detail["request_id"] = request_id
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})
