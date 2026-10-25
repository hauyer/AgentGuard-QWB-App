"""Risk findings and hypotheses routes (B21)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.deps import require_role
from app.core.data_mode import DataMode, effective_data_mode
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.services import resource_access
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
def run_findings(request: Request, run_id: str, user: Viewer) -> dict:
    try:
        resource_access.require_run_access(
            request.app.state.settings, _client(request), user, run_id, mode_override=_mode_override(request))
        payload, meta = get_findings(
            _client(request), _demo(request), mode_override=_mode_override(request), run_id=run_id
        )
    except resource_access.AccessDenied as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": {"error": exc.code, "message": str(exc)}})
    except FindingsServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"error": exc.code, "message": exc.message, "request_id": exc.request_id}},
        )
    return {"meta": meta, **payload}


@router.get("/runs/{run_id}/hypotheses")
def run_hypotheses(request: Request, run_id: str, user: Viewer) -> dict:
    try:
        resource_access.require_run_access(
            request.app.state.settings, _client(request), user, run_id, mode_override=_mode_override(request))
        payload, meta = get_hypotheses(
            _client(request), _demo(request), mode_override=_mode_override(request), run_id=run_id
        )
    except resource_access.AccessDenied as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": {"error": exc.code, "message": str(exc)}})
    except FindingsServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"error": exc.code, "message": exc.message, "request_id": exc.request_id}},
        )
    return {"meta": meta, **payload}


@router.get("/runs/{run_id}/investigation")
def run_investigation(request: Request, run_id: str, user: Viewer) -> dict:
    try:
        resource_access.require_run_access(
            request.app.state.settings, _client(request), user, run_id, mode_override=_mode_override(request))
    except resource_access.AccessDenied as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": {"error": exc.code, "message": str(exc)}})
    mode = effective_data_mode(_mode_override(request), _agentguard_reachable(request))
    if mode == DataMode.LIVE:
        try:
            payload = _client(request).get_run_investigation(run_id)
        except AgentGuardError as exc:
            return JSONResponse(
                status_code=exc.status_code or 502,
                content={"detail": {"error": exc.code or "UPSTREAM_ERROR", "message": str(exc)}},
            )
        return {"meta": {"data_mode": "live"}, **payload}
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        payload = _demo(request).get_investigation_journal(run_id)
        if payload is None:
            return JSONResponse(
                status_code=404,
                content={"detail": {"error": "NOT_FOUND", "message": f"未找到运行 {run_id} 的多轮调查记录"}},
            )
        return {"meta": _demo(request).meta_for("investigation.json"), **payload}
    return JSONResponse(
        status_code=503,
        content={"detail": {"error": "API_UNAVAILABLE", "message": "AgentGuard 不可达且未启用演示模式"}},
    )


def _agentguard_reachable(request: Request) -> bool:
    try:
        _client(request).health()
        return True
    except AgentGuardError:
        return False
