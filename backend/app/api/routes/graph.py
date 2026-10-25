"""Interaction graph routes (B4, project-scoped since B19)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import require_role
from app.integrations.agentguard_client import AgentGuardClient
from app.services import resource_access
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
    user: Viewer,
    request_id: str | None = Query(default=None),
) -> dict:
    try:
        grant = resource_access.require_investigation_access(
            request.app.state.settings, client, user, request_id or "",
            mode_override=_mode_override(request))
        payload, meta = get_graph(
            client, request.app.state.demo_service, mode_override=_mode_override(request), request_id=request_id
        )
    except resource_access.AccessDenied as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": {"error": exc.code, "message": str(exc)}})
    except GraphServiceError as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": {"error": exc.code, "message": str(exc)}})
    if grant.is_global_admin and not grant.project_ids and request_id:
        request.app.state.audit_service.record(
            actor=user.username, role=user.role, action="resource.admin_access",
            target=request_id, detail="interaction_graph.read")
    return {"meta": {**meta, "project_ids": list(grant.project_ids)}, "graph": payload}


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
