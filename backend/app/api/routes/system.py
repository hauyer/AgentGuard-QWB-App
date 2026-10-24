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


@router.get("/system/settings")
def system_settings(request: Request, user: CurrentUserDep) -> dict:
    settings = request.app.state.settings
    return {
        "meta": {"data_mode": settings.app_data_mode or "live"},
        "auth_enabled": settings.auth_enabled,
        "current_user": user.to_public() if settings.auth_enabled else None,
        "roles": [
            {"name": "Viewer", "description": "只读调查和报告。"},
            {"name": "Analyst", "description": "创建允许的调查、查看证据。"},
            {"name": "Operator", "description": "管理经授权的操作请求（不等价于 AgentGuard 高权限操作员）。"},
            {"name": "Admin", "description": "管理系统设置和用户。"},
        ],
    }
