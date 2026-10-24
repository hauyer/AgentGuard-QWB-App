"""Demo centre route (B7)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.deps import require_role
from app.integrations.agentguard_client import AgentGuardClient
from app.services.demo_center_service import get_demo_overview

router = APIRouter()


def get_agentguard_client(request: Request) -> AgentGuardClient:
    return request.app.state.agentguard_client


AgentGuardClientDep = Annotated[AgentGuardClient, Depends(get_agentguard_client)]
Viewer = Annotated[object, Depends(require_role("viewer"))]


def _mode_override(request: Request) -> str | None:
    return request.app.state.settings.app_data_mode or None


@router.get("/demo/overview")
def demo_overview(
    request: Request,
    client: AgentGuardClientDep,
    _user: Viewer,
) -> dict:
    payload, meta = get_demo_overview(client, request.app.state.demo_service, mode_override=_mode_override(request))
    return {"meta": meta, **payload}
