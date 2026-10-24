"""Application status routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

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
