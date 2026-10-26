"""Experiment comparison, reports and experience routes (B6/B13/B19)."""

from __future__ import annotations

import json
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.api.deps import require_role, require_role_csrf
from app.integrations.agentguard_client import AgentGuardClient
from app.services import resource_access
from app.services.project_service import ProjectServiceError, require_project_access
from app.services.reports_service import (
    MAX_REPORT_JSON_BYTES,
    ReportsServiceError,
    build_investigation_loop_report,
    compare_experiments,
    get_report,
    list_experiences,
    list_experiments,
    render_investigation_loop_report_pdf,
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


def _load_investigation_loop_report(request: Request, client: AgentGuardClient, user, request_id: str,
                                    loop_id: str) -> tuple[dict, int, object] | JSONResponse:
    settings = request.app.state.settings
    try:
        investigation_grant = resource_access.require_investigation_access(
            settings, client, user, request_id, mode_override=_mode_override(request))
        if investigation_grant.data_mode.value != "live":
            raise ReportsServiceError(
                503, "LIVE_REPORT_UNAVAILABLE",
                "多轮调查报告只基于 Live 项目数据生成；Recorded/Synthetic 数据不进入 Live 报告。",
            )
        project_id = resource_access.require_trusted_investigation_project(
            settings, request_id, investigation_grant)
        loop_grant = resource_access.require_loop_access(
            settings, client, user, loop_id, mode_override=_mode_override(request))
        if (loop_grant.data_mode.value != "live" or loop_grant.request_id != request_id
                or project_id not in loop_grant.project_ids):
            raise resource_access.AccessDenied(
                "LOOP_NOT_ACCESSIBLE", "调查循环不存在或不可访问", status_code=404)
        project_context = require_project_access(settings, user, project_id, required_role="viewer")
        project = project_context.project
        project_info = {
            "project_id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "created_at": project.created_at.isoformat() if project.created_at else None,
        }
        report = build_investigation_loop_report(
            client, project=project_info, request_id=request_id, loop_id=loop_id)
        return report, project_id, investigation_grant
    except resource_access.AccessDenied as exc:
        return _error_response(exc)
    except resource_access.LoopOwnershipError as exc:
        return _error_response(exc)
    except ProjectServiceError as exc:
        return _error_response(exc)
    except ReportsServiceError as exc:
        return _error_response(exc)


def _safe_report_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)[:80] or "report"


def _report_json_bytes(report: dict) -> bytes:
    try:
        content = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReportsServiceError(502, "REPORT_SERIALIZATION_FAILED", "调查报告不能序列化为 JSON。") from exc
    if len(content) > MAX_REPORT_JSON_BYTES:
        raise ReportsServiceError(413, "REPORT_TOO_LARGE", "生成的 JSON 报告超出 4 MiB 上限。")
    return content


def _audit_loop_report_export(request: Request, user, *, request_id: str, loop_id: str,
                              project_id: int, format_name: str) -> None:
    request.app.state.audit_service.record(
        actor=user.username,
        role=user.role,
        action=f"report.export.{format_name}",
        target=loop_id,
        project_id=project_id,
        detail=f"request_id={request_id}",
    )


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


@router.get("/reports/investigations/{request_id}/loops/{loop_id}", response_model=None)
def investigation_loop_report(
    request: Request,
    request_id: str,
    loop_id: str,
    client: AgentGuardClientDep,
    user: Viewer,
) -> dict | JSONResponse:
    """One project-scoped report snapshot from verified live investigation data."""
    loaded = _load_investigation_loop_report(request, client, user, request_id, loop_id)
    if isinstance(loaded, JSONResponse):
        return loaded
    report, _project_id, _grant = loaded
    return {
        "meta": {
            "data_mode": "live",
            "source": "AgentGuard persisted investigation records and the local project registry",
        },
        "report": report,
    }


@router.get("/reports/investigations/{request_id}/loops/{loop_id}/export.json", response_model=None)
def investigation_loop_report_export_json(
    request: Request,
    request_id: str,
    loop_id: str,
    client: AgentGuardClientDep,
    user: Viewer,
) -> Response:
    loaded = _load_investigation_loop_report(request, client, user, request_id, loop_id)
    if isinstance(loaded, JSONResponse):
        return loaded
    report, project_id, _grant = loaded
    try:
        content = _report_json_bytes(report)
    except ReportsServiceError as exc:
        return _error_response(exc)
    _audit_loop_report_export(
        request, user, request_id=request_id, loop_id=loop_id,
        project_id=project_id, format_name="json",
    )
    filename = f"investigation-report-{_safe_report_part(request_id)}-{_safe_report_part(loop_id)}.json"
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/investigations/{request_id}/loops/{loop_id}/export.pdf", response_model=None)
def investigation_loop_report_export_pdf(
    request: Request,
    request_id: str,
    loop_id: str,
    client: AgentGuardClientDep,
    user: Viewer,
) -> Response:
    loaded = _load_investigation_loop_report(request, client, user, request_id, loop_id)
    if isinstance(loaded, JSONResponse):
        return loaded
    report, project_id, _grant = loaded
    try:
        content = render_investigation_loop_report_pdf(report)
    except ReportsServiceError as exc:
        return _error_response(exc)
    _audit_loop_report_export(
        request, user, request_id=request_id, loop_id=loop_id,
        project_id=project_id, format_name="pdf",
    )
    filename = f"investigation-report-{_safe_report_part(request_id)}-{_safe_report_part(loop_id)}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
