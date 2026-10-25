"""Application status routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.deps import CurrentUserDep
from app.integrations.agentguard_client import AgentGuardClient
from app.schemas.system import SystemStatus
from app.services.status_service import build_system_status

router = APIRouter()


def get_agentguard_client(request: Request) -> AgentGuardClient:
    client: AgentGuardClient = request.app.state.agentguard_client
    return client


AgentGuardClientDep = Annotated[AgentGuardClient, Depends(get_agentguard_client)]


@router.get("/system/status", response_model=SystemStatus)
def system_status(
    request: Request,
    client: AgentGuardClientDep,
) -> SystemStatus:
    data_mode_override = request.app.state.settings.app_data_mode or None
    return build_system_status(client, data_mode_override=data_mode_override)


@router.get("/system/readiness")
def system_readiness(
    request: Request,
    client: AgentGuardClientDep,
    _user: CurrentUserDep,
) -> dict:
    """B20 layered readiness: per-capability status from the D-round endpoint,
    with capability discovery verdicts layered on top. Unknown layers are
    reported as such - API reachability never implies probe/SAE/intervention
    support."""
    data_mode_override = request.app.state.settings.app_data_mode or None
    mode = request.app.state.settings.app_data_mode or (
        "live" if _reachable(client) else "unavailable")
    operations = client.discover_operations()
    discovery = {
        "interaction_graph": operations.get("GET /v1/investigations/{request_id}/interaction-graph", False),
        "investigation_timeline": operations.get("GET /v1/investigations/{request_id}/timeline", False),
        "investigation_options": operations.get("GET /v1/investigations/options", False),
        "experiments_index": operations.get("GET /v1/experiments", False),
        "report_list": operations.get("GET /v1/reports", False),
        "run_findings": operations.get("GET /v1/runs/{run_id}/findings", False),
        "run_hypotheses": operations.get("GET /v1/runs/{run_id}/hypotheses", False),
        "run_investigation_journal": operations.get("GET /v1/runs/{run_id}/investigation", False),
        "discovery_error": client.discovery_error,
    }
    readiness_payload = None
    readiness_error = None
    if _reachable(client):
        try:
            readiness_payload = client.get_readiness()
        except Exception as exc:  # noqa: BLE001 - degraded readiness is data, not a crash
            readiness_error = f"{type(exc).__name__}"
    else:
        # B20-4: an unreachable upstream is an explicit readiness failure,
        # never a silent degrade to another data mode.
        readiness_error = "AGENTGUARD_UNREACHABLE"
    return {
        "data_mode": data_mode_override or mode,
        "readiness": readiness_payload,
        "readiness_error": readiness_error,
        "capabilities": discovery,
    }


def _reachable(client: AgentGuardClient) -> bool:
    from app.integrations.agentguard_client import AgentGuardError

    try:
        client.health()
        return True
    except AgentGuardError:
        return False


@router.get("/system/settings")
def system_settings(request: Request, user: CurrentUserDep) -> dict:
    settings = request.app.state.settings
    return {
        "meta": {"data_mode": settings.app_data_mode or "live"},
        "auth_enabled": settings.auth_enabled,
        "app_env": settings.app_env,
        "demo_users_enabled": settings.demo_users_enabled and settings.auth_enabled,
        "audit_persisted": bool(settings.database_url),
        "current_user": user.to_public() if settings.auth_enabled else None,
        "roles": [
            {"name": "Viewer", "description": "只读调查和报告。"},
            {"name": "Analyst", "description": "创建允许的调查、查看证据。"},
            {"name": "Operator", "description": "管理经授权的操作请求（不等价于 AgentGuard 高权限操作员）。"},
            {"name": "Admin", "description": "管理系统设置和用户。"},
        ],
    }
