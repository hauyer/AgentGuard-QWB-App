"""Investigation workflow routes (B3)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import require_role, require_role_csrf
from app.integrations.agentguard_client import AgentGuardClient
from app.schemas.investigations import CreateInvestigationRequest
from app.services.investigations_service import (
    InvestigationServiceError,
    create_investigation,
    get_investigation,
    get_timeline,
    list_investigations,
    list_scenarios,
)

router = APIRouter()


def get_agentguard_client(request: Request) -> AgentGuardClient:
    return request.app.state.agentguard_client


AgentGuardClientDep = Annotated[AgentGuardClient, Depends(get_agentguard_client)]
Viewer = Annotated[object, Depends(require_role("viewer"))]
Analyst = Annotated[object, Depends(require_role("analyst"))]
AnalystCsrf = Annotated[object, Depends(require_role_csrf("analyst"))]


def _mode_override(request: Request) -> str | None:
    return request.app.state.settings.app_data_mode or None


@router.get("/investigations")
def investigations_list(
    request: Request,
    client: AgentGuardClientDep,
    _user: Viewer,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    try:
        payload, meta = list_investigations(
            client,
            request.app.state.demo_service,
            mode_override=_mode_override(request),
            status=status,
            limit=limit,
            offset=offset,
        )
    except InvestigationServiceError as exc:
        return _error_response(exc)
    return {"meta": meta, **payload}


@router.post("/investigations", status_code=201)
def investigations_create(
    request: Request,
    body: CreateInvestigationRequest,
    client: AgentGuardClientDep,
    user: AnalystCsrf,
) -> dict:
    try:
        payload, meta = create_investigation(
            client,
            request.app.state.demo_service,
            mode_override=_mode_override(request),
            request=body,
        )
    except InvestigationServiceError as exc:
        return _error_response(exc)
    request.app.state.audit_service.record(
        actor=user.username,
        role=user.role,
        action="investigation.create",
        target=payload.get("request_id"),
        detail=f"mode={payload.get('mode', body.mode)} data_mode={meta.get('data_mode')}",
    )
    return {"meta": meta, "created": payload}


@router.get("/investigations/{request_id}")
def investigations_detail(
    request: Request,
    request_id: str,
    client: AgentGuardClientDep,
    _user: Viewer,
) -> dict:
    try:
        payload, meta = get_investigation(
            client, request.app.state.demo_service, mode_override=_mode_override(request), request_id=request_id
        )
    except InvestigationServiceError as exc:
        return _error_response(exc)
    return {"meta": meta, "investigation": payload}


@router.get("/investigations/{request_id}/timeline")
def investigations_timeline(
    request: Request,
    request_id: str,
    client: AgentGuardClientDep,
    _user: Viewer,
) -> dict:
    try:
        payload, meta = get_timeline(
            client, request.app.state.demo_service, mode_override=_mode_override(request), request_id=request_id
        )
    except InvestigationServiceError as exc:
        return _error_response(exc)
    return {"meta": meta, "events": payload}


@router.get("/scenarios")
def scenarios_list(
    request: Request,
    client: AgentGuardClientDep,
    _user: Viewer,
) -> dict:
    try:
        payload, meta = list_scenarios(client, request.app.state.demo_service, mode_override=_mode_override(request))
    except InvestigationServiceError as exc:
        return _error_response(exc)
    return {"meta": meta, **payload}


def _error_response(exc: InvestigationServiceError) -> JSONResponse:
    detail = {"error": exc.code, "message": str(exc)}
    if exc.request_id:
        detail["request_id"] = exc.request_id
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})
