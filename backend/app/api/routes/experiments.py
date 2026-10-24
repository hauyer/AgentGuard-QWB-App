"""Experiment comparison, reports and experience routes (B6)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response

from app.api.deps import require_role
from app.integrations.agentguard_client import AgentGuardClient
from app.services.reports_service import (
    ReportsServiceError,
    get_report,
    list_experiences,
    list_experiments,
    render_report_pdf,
)

router = APIRouter()


def get_agentguard_client(request: Request) -> AgentGuardClient:
    return request.app.state.agentguard_client


AgentGuardClientDep = Annotated[AgentGuardClient, Depends(get_agentguard_client)]
Viewer = Annotated[object, Depends(require_role("viewer"))]


def _mode_override(request: Request) -> str | None:
    return request.app.state.settings.app_data_mode or None


@router.get("/experiments")
def experiments_list(
    request: Request,
    client: AgentGuardClientDep,
    _user: Viewer,
) -> dict:
    try:
        payload, meta = list_experiments(client, request.app.state.demo_service, mode_override=_mode_override(request))
    except ReportsServiceError as exc:
        return _error_response(exc)
    return {"meta": meta, **payload}


@router.get("/reports/{run_id}")
def reports_detail(
    request: Request,
    run_id: str,
    client: AgentGuardClientDep,
    _user: Viewer,
) -> dict:
    try:
        payload, meta = get_report(
            client, request.app.state.demo_service, mode_override=_mode_override(request), run_id=run_id
        )
    except ReportsServiceError as exc:
        return _error_response(exc)
    return {"meta": meta, "report": payload}


@router.get("/reports/{run_id}/export")
def reports_export_pdf(
    request: Request,
    run_id: str,
    client: AgentGuardClientDep,
    _user: Viewer,
) -> Response:
    """Application-layer PDF export. Read-only: does not alter metrics and does
    not infer new causal conclusions."""
    try:
        payload, meta = get_report(
            client, request.app.state.demo_service, mode_override=_mode_override(request), run_id=run_id
        )
        pdf = render_report_pdf(payload, meta)
    except ReportsServiceError as exc:
        return _error_response(exc)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report-{run_id}.pdf"'},
    )


@router.get("/experiences")
def experiences_list(
    request: Request,
    client: AgentGuardClientDep,
    _user: Viewer,
) -> dict:
    try:
        payload, meta = list_experiences(client, request.app.state.demo_service, mode_override=_mode_override(request))
    except ReportsServiceError as exc:
        return _error_response(exc)
    return {"meta": meta, **payload}


def _error_response(exc: ReportsServiceError) -> JSONResponse:
    detail = {"error": exc.code, "message": exc.message}
    if exc.request_id:
        detail["request_id"] = exc.request_id
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})
