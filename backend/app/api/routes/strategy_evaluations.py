"""Read persisted AgentGuard strategy evaluation records (J5)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import require_role
from app.core.data_mode import DataMode, effective_data_mode
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.services import resource_access
from app.services.auth_service import AppUser

router = APIRouter()

STRATEGY_EVALUATIONS_LIST = "GET /v1/research/strategy-evaluations"
STRATEGY_EVALUATIONS_DETAIL = "GET /v1/research/strategy-evaluations/{evaluation_id}"


def get_agentguard_client(request: Request) -> AgentGuardClient:
    return request.app.state.agentguard_client


AgentGuardClientDep = Annotated[AgentGuardClient, Depends(get_agentguard_client)]
Viewer = Annotated[AppUser, Depends(require_role("viewer"))]
DataPartition = Literal["training", "validation", "test", "held_out_family"]


def _mode_override(request: Request) -> str | None:
    return request.app.state.settings.app_data_mode or None


def _agentguard_reachable(client: AgentGuardClient) -> bool:
    try:
        client.health()
        return True
    except AgentGuardError:
        return False


def _live_admin_gate(request: Request, client: AgentGuardClient, user: AppUser) -> JSONResponse | None:
    mode = effective_data_mode(_mode_override(request), _agentguard_reachable(client))
    if mode == DataMode.UNAVAILABLE:
        return _error_response(
            503,
            "AGENTGUARD_UNAVAILABLE",
            "AgentGuard 当前不可达，无法读取策略评价。",
        )
    if mode != DataMode.LIVE:
        return _error_response(
            503,
            "STRATEGY_EVALUATIONS_LIVE_ONLY",
            "策略评价来自 AgentGuard 的持久化研究记录；当前数据模式不提供此类数据。",
        )
    try:
        resource_access.require_admin_scope(
            user,
            code="STRATEGY_EVALUATIONS_SCOPE_RESTRICTED",
            message="策略评价暂无可信项目归属：Live 模式仅全局管理员可读。",
        )
    except resource_access.AccessDenied as exc:
        return _error_response(exc.status_code, exc.code, str(exc))
    return None


def _require_capabilities(client: AgentGuardClient) -> JSONResponse | None:
    operations = client.discover_operations()
    if not operations.get(STRATEGY_EVALUATIONS_LIST) or not operations.get(STRATEGY_EVALUATIONS_DETAIL):
        return _error_response(
            503,
            "STRATEGY_EVALUATIONS_UNAVAILABLE",
            "AgentGuard 固定版本未发布完整的策略评价列表与详情接口；不生成替代评价数据。",
        )
    return None


@router.get("/research/strategy-evaluations", response_model=None)
def strategy_evaluations_list(
    request: Request,
    client: AgentGuardClientDep,
    user: Viewer,
    data_partition: Annotated[DataPartition | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict | JSONResponse:
    gate_error = _live_admin_gate(request, client, user)
    if gate_error:
        return gate_error
    capability_error = _require_capabilities(client)
    if capability_error:
        return capability_error
    try:
        payload = client.list_strategy_evaluations(
            data_partition=data_partition, limit=limit, offset=offset
        )
    except AgentGuardError as exc:
        return _upstream_error(exc)
    if not isinstance(payload.get("items"), list):
        return _error_response(
            502, "STRATEGY_EVALUATIONS_BAD_RESPONSE", "AgentGuard 策略评价列表合同无效。"
        )
    for item in payload["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("evaluation_id"), str):
            return _error_response(
                502, "STRATEGY_EVALUATIONS_BAD_RESPONSE", "AgentGuard 策略评价条目缺少 evaluation_id。"
            )
    return {
        "meta": {
            "data_mode": "live",
            "capability": "available",
            "source_note": "来自 AgentGuard 持久化策略评价索引；应用不会触发新实验或计算替代指标。",
        },
        **payload,
    }


@router.get("/research/strategy-evaluations/{evaluation_id}", response_model=None)
def strategy_evaluation_detail(
    request: Request,
    evaluation_id: str,
    client: AgentGuardClientDep,
    user: Viewer,
) -> dict | JSONResponse:
    gate_error = _live_admin_gate(request, client, user)
    if gate_error:
        return gate_error
    capability_error = _require_capabilities(client)
    if capability_error:
        return capability_error
    try:
        payload = client.get_strategy_evaluation(evaluation_id)
    except AgentGuardError as exc:
        return _upstream_error(exc)
    if not isinstance(payload.get("comparison_id"), str):
        return _error_response(
            502, "STRATEGY_EVALUATIONS_BAD_RESPONSE", "AgentGuard 策略评价详情合同无效。"
        )
    return {
        "meta": {
            "data_mode": "live",
            "capability": "available",
            "source_note": "详情来自 AgentGuard 持久化评价工件；指标按上游原值呈现。",
        },
        "evaluation": payload,
    }


def _upstream_error(exc: AgentGuardError) -> JSONResponse:
    return _error_response(
        exc.status_code or 502,
        exc.code,
        str(exc),
        exc.request_id,
    )


def _error_response(
    status_code: int, code: str, message: str, request_id: str | None = None
) -> JSONResponse:
    detail = {"error": code, "message": message}
    if request_id:
        detail["request_id"] = request_id
    return JSONResponse(status_code=status_code, content={"detail": detail})
