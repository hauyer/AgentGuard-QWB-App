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
from app.services.loop_contract import LoopListContractError, read_all_investigation_loops

router = APIRouter()

LOOP_READ_OPERATIONS = (
    "GET /v1/investigation-loops",
    "GET /v1/investigation-loops/{loop_id}",
    "GET /v1/investigation-loops/{loop_id}/decisions",
    "GET /v1/investigation-loops/{loop_id}/evidence-changes",
    "GET /v1/investigation-loops/{loop_id}/budget",
)


def _loop_capability_error(request: Request, *required_operations: str) -> JSONResponse | None:
    client = _client(request)
    operations = client.discover_operations()
    if client.discovery_error:
        return JSONResponse(status_code=503, content={"detail": {
            "error": "LOOP_CAPABILITY_UNVERIFIED",
            "message": "无法核实 AgentGuard 是否支持所需的 Loop 接口。",
        }})
    missing = [operation for operation in required_operations if not operations.get(operation)]
    if missing:
        return JSONResponse(status_code=503, content={"detail": {
            "error": "LOOP_READ_UNSUPPORTED",
            "message": "AgentGuard 固定版本未提供所需的 Loop 读取接口。",
        }})
    return None

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


# ------------------------------------------------------------------ #
# E6 investigation loop read-only routes (B28/B30)
# ------------------------------------------------------------------ #
@router.get("/investigations/{request_id}/loops")
def list_loops_for_investigation(request: Request, request_id: str, user: Viewer) -> dict:
    """List loops for a base investigation. Authorization: request_id → project membership."""
    try:
        grant = resource_access.require_investigation_access(
            request.app.state.settings, _client(request), user, request_id, mode_override=_mode_override(request))
        project_id = resource_access.require_trusted_investigation_project(
            request.app.state.settings, request_id, grant)
        capability_error = _loop_capability_error(request, *LOOP_READ_OPERATIONS)
        if capability_error:
            return capability_error
        items = read_all_investigation_loops(_client(request), request_id)
        resource_access.register_verified_investigation_loops(
            request.app.state.settings,
            request_id=request_id,
            project_id=project_id,
            loop_items=items,
            created_by=user.username,
        )
    except resource_access.AccessDenied as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": {"error": exc.code, "message": str(exc)}})
    except resource_access.LoopOwnershipError as exc:
        return JSONResponse(status_code=exc.status_code,
                            content={"detail": {"error": exc.code, "message": str(exc)}})
    except LoopListContractError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"error": exc.code, "message": str(exc)}},
        )
    except AgentGuardError as exc:
        return JSONResponse(
            status_code=exc.status_code or 502,
            content={"detail": {"error": exc.code, "message": str(exc)}})
    return {
        "meta": {"data_mode": "live", "source": "agentguard", "ownership_verified": True},
        "schema_version": "1.0",
        "items": items,
        "count": len(items),
        "offset": 0,
        "limit": len(items),
        "next_offset": None,
    }


@router.get("/investigation-loops/{loop_id}")
def loop_detail(request: Request, loop_id: str, user: Viewer) -> dict:
    """Read a single investigation loop. Authorization: local loop_id → project map."""
    try:
        grant = resource_access.require_loop_access(
            request.app.state.settings, _client(request), user, loop_id, mode_override=_mode_override(request))
        if grant.data_mode.value != "live":
            return JSONResponse(status_code=503, content={"detail": {
                "error": "LIVE_SOURCE_UNAVAILABLE", "message": "当前数据源不提供已验证的实时 Loop"}})
        capability_error = _loop_capability_error(
            request, "GET /v1/investigation-loops/{loop_id}"
        )
        if capability_error:
            return capability_error
        payload = _client(request).get_investigation_loop(loop_id)
    except resource_access.AccessDenied as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": {"error": exc.code, "message": str(exc)}})
    except AgentGuardError as exc:
        return JSONResponse(
            status_code=exc.status_code or 502,
            content={"detail": {"error": exc.code, "message": str(exc)}})
    return {"meta": {"data_mode": "live"}, **payload}


@router.get("/investigation-loops/{loop_id}/decisions")
def loop_decisions(request: Request, loop_id: str, user: Viewer) -> dict:
    try:
        grant = resource_access.require_loop_access(
            request.app.state.settings, _client(request), user, loop_id, mode_override=_mode_override(request))
        if grant.data_mode.value != "live":
            return JSONResponse(status_code=503, content={"detail": {
                "error": "LIVE_SOURCE_UNAVAILABLE", "message": "当前数据源不提供已验证的实时 Loop"}})
        capability_error = _loop_capability_error(
            request, "GET /v1/investigation-loops/{loop_id}/decisions"
        )
        if capability_error:
            return capability_error
        payload = _client(request).get_investigation_decisions(loop_id)
    except resource_access.AccessDenied as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": {"error": exc.code, "message": str(exc)}})
    except AgentGuardError as exc:
        return JSONResponse(
            status_code=exc.status_code or 502,
            content={"detail": {"error": exc.code, "message": str(exc)}})
    return {"meta": {"data_mode": "live"}, **payload}


@router.get("/investigation-loops/{loop_id}/evidence-changes")
def loop_evidence_changes(request: Request, loop_id: str, user: Viewer) -> dict:
    try:
        grant = resource_access.require_loop_access(
            request.app.state.settings, _client(request), user, loop_id, mode_override=_mode_override(request))
        if grant.data_mode.value != "live":
            return JSONResponse(status_code=503, content={"detail": {
                "error": "LIVE_SOURCE_UNAVAILABLE", "message": "当前数据源不提供已验证的实时 Loop"}})
        capability_error = _loop_capability_error(
            request, "GET /v1/investigation-loops/{loop_id}/evidence-changes"
        )
        if capability_error:
            return capability_error
        payload = _client(request).get_investigation_evidence_changes(loop_id)
    except resource_access.AccessDenied as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": {"error": exc.code, "message": str(exc)}})
    except AgentGuardError as exc:
        return JSONResponse(
            status_code=exc.status_code or 502,
            content={"detail": {"error": exc.code, "message": str(exc)}})
    return {"meta": {"data_mode": "live"}, **payload}


@router.get("/investigation-loops/{loop_id}/budget")
def loop_budget(request: Request, loop_id: str, user: Viewer) -> dict:
    try:
        grant = resource_access.require_loop_access(
            request.app.state.settings, _client(request), user, loop_id, mode_override=_mode_override(request))
        if grant.data_mode.value != "live":
            return JSONResponse(status_code=503, content={"detail": {
                "error": "LIVE_SOURCE_UNAVAILABLE", "message": "当前数据源不提供已验证的实时 Loop"}})
        capability_error = _loop_capability_error(
            request, "GET /v1/investigation-loops/{loop_id}/budget"
        )
        if capability_error:
            return capability_error
        payload = _client(request).get_investigation_loop_budget(loop_id)
    except resource_access.AccessDenied as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": {"error": exc.code, "message": str(exc)}})
    except AgentGuardError as exc:
        return JSONResponse(
            status_code=exc.status_code or 502,
            content={"detail": {"error": exc.code, "message": str(exc)}})
    return {"meta": {"data_mode": "live"}, **payload}


def _agentguard_reachable(request: Request) -> bool:
    try:
        _client(request).health()
        return True
    except AgentGuardError:
        return False
