"""Risk findings and hypotheses routes (B21)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.deps import require_role
from app.integrations.agentguard_client import AgentGuardClient
from app.services.demo_service import DemoService
from app.services.findings_service import FindingsServiceError, get_findings, get_hypotheses

router = APIRouter()

Viewer = Annotated[object, Depends(require_role("viewer"))]


def _client(request: Request) -> AgentGuardClient:
    return request.app.state.agentguard_client


def _demo(request: Request) -> DemoService:
    return request.app.state.demo_service


def _mode_override(request: Request) -> str | None:
    return request.app.state.settings.app_data_mode or None


@router.get("/runs/{run_id}/findings")
def run_findings(request: Request, run_id: str, _user: Viewer) -> dict:
    try:
        payload, meta = get_findings(
            _client(request), _demo(request), mode_override=_mode_override(request), run_id=run_id
        )
    except FindingsServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"error": exc.code, "message": exc.message, "request_id": exc.request_id}},
        )
    return {"meta": meta, **payload}


@router.get("/runs/{run_id}/hypotheses")
def run_hypotheses(request: Request, run_id: str, _user: Viewer) -> dict:
    try:
        payload, meta = get_hypotheses(
            _client(request), _demo(request), mode_override=_mode_override(request), run_id=run_id
        )
    except FindingsServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"error": exc.code, "message": exc.message, "request_id": exc.request_id}},
        )
    return {"meta": meta, **payload}
