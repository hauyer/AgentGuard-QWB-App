"""Project-scoped, CSRF-protected investigation loop creation routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.deps import require_role, require_role_csrf
from app.core.data_mode import DataMode
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.schemas.investigation_loops import CreateInvestigationLoopRequest
from app.services import resource_access
from app.services.loop_creation_service import (
    LoopCreationError,
    get_submission,
    resume_submission,
    submit_loop,
)
from app.services.project_service import ProjectServiceError, require_project_access

router = APIRouter()

OperatorCsrf = Annotated[object, Depends(require_role_csrf("operator"))]
Viewer = Annotated[object, Depends(require_role("viewer"))]


def _client(request: Request) -> AgentGuardClient:
    return request.app.state.agentguard_client


def _authorize_base(
    request: Request,
    user: object,
    request_id: str,
    *,
    required_role: str,
    require_live: bool = True,
) -> int:
    settings = request.app.state.settings
    client = _client(request)
    grant = resource_access.require_investigation_access(
        settings,
        client,
        user,
        request_id,
        mode_override=settings.app_data_mode or None,
    )
    if require_live and grant.data_mode is not DataMode.LIVE:
        raise LoopCreationError(503, "LIVE_CREATION_UNAVAILABLE", "Loop 创建只支持已授权的 Live 调查")
    project_id = (
        resource_access.require_trusted_investigation_project(settings, request_id, grant)
        if require_live
        else resource_access.require_locally_verified_investigation_project(settings, request_id, grant)
    )
    context = require_project_access(settings, user, project_id, required_role=required_role)
    if context.project.status != "active":
        raise LoopCreationError(409, "PROJECT_ARCHIVED", "项目已归档，不能创建 Loop")
    return project_id


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": {"error": code, "message": message}})


def _result_response(result) -> JSONResponse:
    content = result.payload
    if result.status_code >= 400:
        error = result.payload.get("submission", {}).get("error") or {}
        content = {
            "detail": {
                "error": error.get("code", "LOOP_SUBMISSION_FAILED"),
                "message": error.get("message", "Loop 提交需要核对"),
            },
            **content,
        }
    return JSONResponse(status_code=result.status_code, content=content)


def _audit(request: Request, user: object, *, action: str, request_id: str, project_id: int | None,
           outcome: str, submission_id: str | None = None, error_code: str | None = None) -> None:
    audit = getattr(request.app.state, "audit_service", None)
    if audit is None:
        return
    detail = f"outcome={outcome}"
    if submission_id:
        detail += f" submission_id={submission_id}"
    if error_code:
        detail += f" error={error_code}"
    audit.record(
        actor=user.username,
        role=user.role,
        action=action,
        target=request_id,
        project_id=project_id,
        detail=detail,
    )


@router.post("/investigations/{request_id}/loops")
def create_loop(
    request: Request,
    request_id: str,
    body: CreateInvestigationLoopRequest,
    user: OperatorCsrf,
) -> JSONResponse:
    project_id: int | None = None
    submission_id = str(body.submission_id)
    try:
        project_id = _authorize_base(request, user, request_id, required_role="operator")
        settings = request.app.state.settings
        if not settings.agentguard_operator_api_token or not settings.agentguard_operator_api_token.strip():
            raise LoopCreationError(503, "OPERATOR_TOKEN_REQUIRED", "服务端未配置 AgentGuard Operator Token")

        client = _client(request)
        try:
            investigation = client.get_investigation(request_id)
        except AgentGuardError as exc:
            raise LoopCreationError(
                exc.status_code or 502,
                exc.code or "BASE_INVESTIGATION_UNAVAILABLE",
                str(exc),
            ) from exc
        status = str(investigation.get("status", "")).strip().lower()
        workflow_status = str(investigation.get("workflow_status", "")).strip().lower()
        if status not in {"finished", "completed"} and workflow_status not in {"finished", "completed"}:
            raise LoopCreationError(
                409,
                "BASE_INVESTIGATION_NOT_FINISHED",
                "基础调查必须先完成，才能创建 Loop",
            )

        operations = client.discover_operations()
        discovery_error = getattr(client, "discovery_error", None)
        if discovery_error:
            raise LoopCreationError(
                503,
                "LOOP_CREATE_CAPABILITY_UNVERIFIED",
                "无法确认 AgentGuard 固定版本是否支持 Loop 创建；没有发送创建请求",
            )
        if not operations.get("POST /v1/investigation-loops", False):
            raise LoopCreationError(
                503,
                "LOOP_CREATE_UNSUPPORTED",
                "当前固定的 AgentGuard D7 版本未发布 Loop 创建接口；没有发送创建请求",
            )
        if not operations.get("GET /v1/investigation-loops", False):
            raise LoopCreationError(
                503,
                "LOOP_RECONCILIATION_UNSUPPORTED",
                "AgentGuard 未发布 Loop 列表对账接口；为避免重复执行，创建流程已阻止",
            )

        params = body.model_dump(mode="json", exclude={"submission_id"})
        upstream_payload = {
            "schema_version": "1.0",
            "base_request_id": request_id,
            **params,
        }
        result = submit_loop(
            settings,
            client,
            project_id=project_id,
            request_id=request_id,
            submission_id=submission_id,
            actor=user.username,
            upstream_payload=upstream_payload,
        )
        status_value = result.payload.get("submission", {}).get("status", "unknown")
        _audit(
            request,
            user,
            action="investigation.loop.create",
            request_id=request_id,
            project_id=project_id,
            outcome=status_value,
            submission_id=submission_id,
            error_code=(result.payload.get("submission", {}).get("error") or {}).get("code"),
        )
        return _result_response(result)
    except resource_access.AccessDenied as exc:
        _audit(request, user, action="investigation.loop.create.denied", request_id=request_id,
               project_id=project_id, outcome="denied", submission_id=submission_id, error_code=exc.code)
        return _error_response(exc.status_code, exc.code, str(exc))
    except resource_access.LoopOwnershipError as exc:
        _audit(request, user, action="investigation.loop.create.denied", request_id=request_id,
               project_id=project_id, outcome="denied", submission_id=submission_id, error_code=exc.code)
        return _error_response(exc.status_code, exc.code, str(exc))
    except ProjectServiceError as exc:
        _audit(request, user, action="investigation.loop.create.denied", request_id=request_id,
               project_id=project_id, outcome="denied", submission_id=submission_id, error_code=exc.code)
        return _error_response(exc.status_code, exc.code, str(exc))
    except LoopCreationError as exc:
        _audit(request, user, action="investigation.loop.create", request_id=request_id,
               project_id=project_id, outcome="blocked", submission_id=submission_id, error_code=exc.code)
        return _error_response(exc.status_code, exc.code, str(exc))
    except AgentGuardError as exc:
        _audit(request, user, action="investigation.loop.create", request_id=request_id,
               project_id=project_id, outcome="failed", submission_id=submission_id, error_code=exc.code)
        return _error_response(exc.status_code or 502, exc.code or "UPSTREAM_ERROR", str(exc))


@router.get("/investigations/{request_id}/loop-submissions/{submission_id}")
def loop_submission_status(
    request: Request,
    request_id: str,
    submission_id: UUID,
    user: Viewer,
) -> JSONResponse:
    try:
        project_id = _authorize_base(
            request, user, request_id, required_role="viewer", require_live=False
        )
        payload = get_submission(
            request.app.state.settings,
            project_id=project_id,
            request_id=request_id,
            submission_id=str(submission_id),
        )
    except resource_access.AccessDenied as exc:
        return _error_response(exc.status_code, exc.code, str(exc))
    except resource_access.LoopOwnershipError as exc:
        return _error_response(exc.status_code, exc.code, str(exc))
    except ProjectServiceError as exc:
        return _error_response(exc.status_code, exc.code, str(exc))
    except LoopCreationError as exc:
        return _error_response(exc.status_code, exc.code, str(exc))
    if payload is None:
        return _error_response(404, "SUBMISSION_NOT_FOUND", "未找到该 Loop 提交记录")
    return JSONResponse(status_code=200, content=payload)


@router.post("/investigations/{request_id}/loop-submissions/{submission_id}/reconcile")
def reconcile_loop_submission(
    request: Request,
    request_id: str,
    submission_id: UUID,
    user: OperatorCsrf,
) -> JSONResponse:
    project_id: int | None = None
    key = str(submission_id)
    try:
        project_id = _authorize_base(request, user, request_id, required_role="operator")
        settings = request.app.state.settings
        current = get_submission(
            settings,
            project_id=project_id,
            request_id=request_id,
            submission_id=key,
        )
        if current is None:
            raise LoopCreationError(404, "SUBMISSION_NOT_FOUND", "未找到该 Loop 提交记录")
        client = _client(request)
        operations = client.discover_operations()
        if getattr(client, "discovery_error", None):
            raise LoopCreationError(503, "LOOP_RECONCILIATION_UNAVAILABLE", "无法确认上游恢复能力")
        if not operations.get("GET /v1/investigation-loops", False):
            raise LoopCreationError(503, "LOOP_RECONCILIATION_UNSUPPORTED", "AgentGuard 未发布 Loop 对账接口")
        if current["submission"]["status"] == "PREPARED":
            if not settings.agentguard_operator_api_token or not settings.agentguard_operator_api_token.strip():
                raise LoopCreationError(503, "OPERATOR_TOKEN_REQUIRED", "服务端未配置 AgentGuard Operator Token")
            if not operations.get("POST /v1/investigation-loops", False):
                # A PREPARED record proves no POST was ever claimed, but this
                # fixed upstream still must publish create before it can resume.
                raise LoopCreationError(503, "LOOP_CREATE_UNSUPPORTED", "当前 AgentGuard 固定版本不支持恢复 Loop 创建")
        result = resume_submission(
            settings,
            client,
            project_id=project_id,
            request_id=request_id,
            submission_id=key,
        )
        _audit(
            request, user, action="investigation.loop.reconcile", request_id=request_id,
            project_id=project_id, outcome=result.payload.get("submission", {}).get("status", "unknown"),
            submission_id=key,
            error_code=(result.payload.get("submission", {}).get("error") or {}).get("code"),
        )
        return _result_response(result)
    except resource_access.AccessDenied as exc:
        _audit(request, user, action="investigation.loop.reconcile.denied", request_id=request_id,
               project_id=project_id, outcome="denied", submission_id=key, error_code=exc.code)
        return _error_response(exc.status_code, exc.code, str(exc))
    except resource_access.LoopOwnershipError as exc:
        return _error_response(exc.status_code, exc.code, str(exc))
    except ProjectServiceError as exc:
        return _error_response(exc.status_code, exc.code, str(exc))
    except LoopCreationError as exc:
        _audit(request, user, action="investigation.loop.reconcile", request_id=request_id,
               project_id=project_id, outcome="blocked", submission_id=key, error_code=exc.code)
        return _error_response(exc.status_code, exc.code, str(exc))
