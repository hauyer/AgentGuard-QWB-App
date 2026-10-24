"""Dashboard route."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.integrations.agentguard_client import AgentGuardClient
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import build_dashboard

router = APIRouter()


def get_agentguard_client(request: Request) -> AgentGuardClient:
    return request.app.state.agentguard_client


AgentGuardClientDep = Annotated[AgentGuardClient, Depends(get_agentguard_client)]


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(request: Request, client: AgentGuardClientDep) -> DashboardResponse:
    data_mode_override = request.app.state.settings.app_data_mode or None
    demo = request.app.state.demo_service
    return build_dashboard(client, demo, data_mode_override=data_mode_override)
