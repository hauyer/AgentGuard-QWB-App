"""Interaction graph routes (B4)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import require_role
from app.integrations.agentguard_client import AgentGuardClient
from app.services.graph_service import GraphServiceError, get_graph, list_samples

router = APIRouter()


def get_agentguard_client(request: Request) -> AgentGuardClient:
    return request.app.state.agentguard_client


AgentGuardClientDep = Annotated[AgentGuardClient, Depends(get_agentguard_client)]
Viewer = Annotated[object, Depends(require_role("viewer"))]


def _mode_override(request: Request) -> str | None:
    return request.app.state.settings.app_data_mode or None


@router.get("/interaction-graph")
def interaction_graph(
    request: Request,
    client: AgentGuardClientDep,
    _user: Viewer,
    request_id: str | None = Query(default=None),
) -> dict:
    try:
        payload, meta = get_graph(
            client, request.app.state.demo_service, mode_override=_mode_override(request), request_id=request_id
        )
    except GraphServiceError as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": {"error": exc.code, "message": str(exc)}})
    return {"meta": meta, "graph": payload}


@router.get("/interaction-graph/samples")
def interaction_graph_samples(
    request: Request,
    client: AgentGuardClientDep,
    _user: Viewer,
) -> dict:
    try:
        payload, meta = list_samples(client, request.app.state.demo_service, mode_override=_mode_override(request))
    except GraphServiceError as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": {"error": exc.code, "message": str(exc)}})
    return {"meta": meta, "samples": payload}
