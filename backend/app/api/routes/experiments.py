"""Experiment comparison, reports and experience routes (B6, B13)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.api.deps import require_role, require_role_csrf
from app.integrations.agentguard_client import AgentGuardClient
from app.services.reports_service import (
    ReportsServiceError,
    compare_experiments,
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
AnalystCsrf = Annotated[object, Depends(require_role_csrf("analyst"))]


def _mode_override(request: Request) -> str | None:
    return request.app.state.settings.app_data_mode or None


class CompareExperimentsRequest(BaseModel):
    run_ids: list[str] = Field(min_length=2, max_length=20)


@router.post("/experiments/compare")
def experiments_compare(
    request: Request,
    body: CompareExperimentsRequest,
    client: AgentGuardClientDep,
    _user: AnalystCsrf,
) -> dict:
    """Controlled experiment comparison (B13). Comparability is verified before
    any delta is computed; incomparable input returns reasons, not fabricated
    improvement rates."""
    try:
        payload, meta = compare_experiments(
            client, request.app.state.demo_service,
            mode_override=_mode_override(request), run_ids=body.run_ids)
    except ReportsServiceError as exc:
        return _error_response(exc)
    return {"meta": meta, **payload}


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
