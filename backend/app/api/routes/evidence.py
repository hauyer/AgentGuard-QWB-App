"""Evidence + defense workspace routes (B5)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import require_role, require_role_csrf
from app.integrations.agentguard_client import AgentGuardClient
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


@router.get("/evidence")
def evidence_list(
    request: Request,
    client: AgentGuardClientDep,
    _user: Viewer,
    request_id: str = Query(description="调查 request_id，必填"),
) -> dict:
    try:
        payload, meta = get_evidence(
            client, request.app.state.demo_service, mode_override=_mode_override(request), request_id=request_id
        )
    except EvidenceServiceError as exc:
        return _error_response(exc)
    return {"meta": meta, "evidence": payload}


@router.get("/defense")
def defense_list(
    request: Request,
    client: AgentGuardClientDep,
    _user: Viewer,
    request_id: str = Query(description="调查 request_id，必填"),
) -> dict:
    try:
        payload, meta = get_defense(
            client, request.app.state.demo_service, mode_override=_mode_override(request), request_id=request_id
        )
    except EvidenceServiceError as exc:
        return _error_response(exc)
    return {"meta": meta, "defense": payload}


@router.post("/defense/{request_id}/preview")
def defense_preview(
    request: Request,
    request_id: str,
    client: AgentGuardClientDep,
    _user: AnalystCsrf,
) -> dict:
    """Generate/refresh candidate preview only; never executes a defense."""
    try:
        payload, meta = preview_defense(
            client, request.app.state.demo_service, mode_override=_mode_override(request), request_id=request_id
        )
    except EvidenceServiceError as exc:
        return _error_response(exc)
    return {"meta": meta, "defense": payload}


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


def _error_response(exc: EvidenceServiceError) -> JSONResponse:
    detail = {"error": exc.code, "message": exc.message}
    if exc.request_id:
        detail["request_id"] = exc.request_id
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})
