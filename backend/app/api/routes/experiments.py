"""Experiment comparison, reports and experience routes (B6/B13/B19)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.api.deps import require_role, require_role_csrf
from app.integrations.agentguard_client import AgentGuardClient
from app.services import resource_access
from app.services.reports_service import (
    ReportsServiceError,
    compare_experiments,
    get_report,
    list_experiences,
    list_experiments,
    render_report_pdf,
)

router = APIRouter()


def get_agentguard_client(request: Request) -> AgentGuardClient:
    return request.app.state.agentguard_client


AgentGuardClientDep = Annotated[AgentGuardClient, Depends(get_agentguard_client)]
Viewer = Annotated[object, Depends(require_role("viewer"))]
AnalystCsrf = Annotated[object, Depends(require_role_csrf("analyst"))]


def _mode_override(request: Request) -> str | None:
    return request.app.state.settings.app_data_mode or None


class CompareExperimentsRequest(BaseModel):
    run_ids: list[str] = Field(min_length=2, max_length=20)


@router.get("/experiments")
def experiments_list(
    request: Request,
    client: AgentGuardClientDep,
    user: Viewer,
) -> dict:
    try:
        # B19: the C2 index is upstream-wide with no project attribution; live
        # access is restricted to the global admin (demo namespace unaffected).
        grant_mode = resource_access.effective_mode(
            request.app.state.settings, client, _mode_override(request))
        if grant_mode.value == "live":
            resource_access.require_admin_scope(
                user, code="EXPERIMENTS_SCOPE_RESTRICTED",
                message="实验索引为上游全量数据且无项目归属映射：Live 模式仅全局管理员可读。")
        payload, meta = list_experiments(client, request.app.state.demo_service, mode_override=_mode_override(request))
    except resource_access.AccessDenied as exc:
        return _error_response(exc)
    except ReportsServiceError as exc:
        return _error_response(exc)
    return {"meta": meta, **payload}


@router.post("/experiments/compare")
def experiments_compare(
    request: Request,
    body: CompareExperimentsRequest,
    client: AgentGuardClientDep,
    user: AnalystCsrf,
) -> dict:
    """Controlled experiment comparison (B13). Comparability is verified before
    any delta is computed; incomparable input returns reasons, not fabricated
    improvement rates."""
    try:
        grant_mode = resource_access.effective_mode(
            request.app.state.settings, client, _mode_override(request))
        if grant_mode.value == "live":
            resource_access.require_admin_scope(
                user, code="EXPERIMENTS_SCOPE_RESTRICTED",
                message="实验对比使用上游全量索引且无项目归属映射：Live 模式仅全局管理员可用。")
        payload, meta = compare_experiments(
            client, request.app.state.demo_service,
            mode_override=_mode_override(request), run_ids=body.run_ids)
    except resource_access.AccessDenied as exc:
        return _error_response(exc)
    except ReportsServiceError as exc:
        return _error_response(exc)
    return {"meta": meta, **payload}


@router.get("/reports/{run_id}")
def reports_detail(
    request: Request,
    run_id: str,
    client: AgentGuardClientDep,
    user: Viewer,
) -> dict:
    try:
        grant = resource_access.require_run_access(
            request.app.state.settings, client, user, run_id, mode_override=_mode_override(request))
        payload, meta = get_report(
            client, request.app.state.demo_service, mode_override=_mode_override(request), run_id=run_id
        )
    except resource_access.AccessDenied as exc:
        return _error_response(exc)
    except ReportsServiceError as exc:
        return _error_response(exc)
    _audit_admin_run_access(request, user, grant, run_id, "report.read")
    return {"meta": {**meta, "project_ids": list(grant.project_ids)}, "report": payload}


@router.get("/reports/{run_id}/export")
def reports_export_pdf(
    request: Request,
    run_id: str,
    client: AgentGuardClientDep,
    user: Viewer,
) -> Response:
    """Application-layer PDF export. Read-only: does not alter metrics and does
    not infer new causal conclusions. Authorized like report reads and audited."""
    try:
        grant = resource_access.require_run_access(
            request.app.state.settings, client, user, run_id, mode_override=_mode_override(request))
        payload, meta = get_report(
            client, request.app.state.demo_service, mode_override=_mode_override(request), run_id=run_id
        )
        pdf = render_report_pdf(payload, meta)
    except resource_access.AccessDenied as exc:
        return _error_response(exc)
    except ReportsServiceError as exc:
        return _error_response(exc)
    _audit_admin_run_access(request, user, grant, run_id, "report.export")
    request.app.state.audit_service.record(
        actor=user.username, role=user.role, action="report.export",
        target=run_id, project_id=grant.project_ids[0] if grant.project_ids else None)
    # Sanitize: run_id must not carry header-breaking or path characters.
    import re

    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", run_id)[:80] or "report"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report-{safe_name}.pdf"'},
    )


def _audit_admin_run_access(request: Request, user, grant, run_id: str, action: str) -> None:
    if grant.is_global_admin and not grant.project_ids:
        request.app.state.audit_service.record(
            actor=user.username, role=user.role, action="resource.admin_access",
            target=run_id, detail=action)


@router.get("/experiences")
def experiences_list(
    request: Request,
    client: AgentGuardClientDep,
    user: Viewer,
) -> dict:
    try:
        grant_mode = resource_access.effective_mode(
            request.app.state.settings, client, _mode_override(request))
        if grant_mode.value == "live":
            resource_access.require_admin_scope(
                user, code="EXPERIENCES_SCOPE_RESTRICTED",
                message="经验检索为上游全量数据且无项目归属映射：Live 模式仅全局管理员可读。")
        payload, meta = list_experiences(client, request.app.state.demo_service, mode_override=_mode_override(request))
    except resource_access.AccessDenied as exc:
        return _error_response(exc)
    except ReportsServiceError as exc:
        return _error_response(exc)
    return {"meta": meta, **payload}


def _error_response(exc) -> JSONResponse:
    detail = {"error": exc.code, "message": str(exc)}
    request_id = getattr(exc, "request_id", None)
    if request_id:
        detail["request_id"] = request_id
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})
