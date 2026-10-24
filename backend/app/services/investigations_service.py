"""Investigation workflow (B3).

Live mode proxies the AgentGuard public API. Demo mode serves the offline
fixtures (clearly labelled) and records demo-only submissions in an in-memory
overlay without ever pretending a real WARDEN run happened. Unavailable mode
returns explicit errors - no fabricated investigations.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from app.core.data_mode import DataMode, effective_data_mode
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.schemas.investigations import CreateInvestigationRequest
from app.services.demo_service import DemoService

logger = logging.getLogger(__name__)

TIMELINE_STEPS = [
    ("created", "调查创建"),
    ("validated", "请求验证"),
    ("capabilities", "能力检查"),
    ("planned", "审计计划"),
    ("submitted", "运行提交"),
    ("running", "运行中"),
    ("evidence", "证据生成"),
    ("completed", "调查完成"),
]


class InvestigationServiceError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str, request_id: str | None = None) -> None:
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        super().__init__(message)


def _mode_for(settings, agentguard_available: bool) -> DataMode:
    return effective_data_mode(settings.app_data_mode or None, agentguard_available)


def list_investigations(
    client: AgentGuardClient,
    demo: DemoService,
    *,
    mode_override: str | None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[dict, dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode == DataMode.LIVE:
        try:
            payload = client.list_investigations(status=status, limit=limit, offset=offset)
        except AgentGuardError as exc:
            raise _to_service_error(exc) from exc
        return payload, {"data_mode": "live"}
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        payload = demo.list_investigations(status=status, limit=limit, offset=offset)
        return payload, demo.meta_for("investigations.json")
    raise InvestigationServiceError(
        503, "API_UNAVAILABLE", "AgentGuard 不可达且未启用演示模式，无法提供调查列表"
    )


def create_investigation(
    client: AgentGuardClient,
    demo: DemoService,
    *,
    mode_override: str | None,
    request: CreateInvestigationRequest,
) -> tuple[dict, dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    request_id = f"inv-{uuid.uuid4().hex[:16]}"
    if mode == DataMode.LIVE:
        try:
            payload = client.create_investigation(request.to_warden_payload(request_id))
        except AgentGuardError as exc:
            raise _to_service_error(exc) from exc
        payload = dict(payload)
        payload.setdefault("request_id", request_id)
        return payload, {"data_mode": "live"}
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        created = demo.record_demo_investigation(
            request_id,
            {
                "request_id": request_id,
                "contract_id": request.contract_id,
                "model_id": request.model_id,
                "runtime_id": request.runtime_id,
                "mode": request.mode,
                "scenario_id": request.scenario_id,
                "risk_type": request.risk_type,
                "status": "pending",
                "workflow_status": "validating",
                "revision": 1,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "plan_id": None,
                "run_id": None,
                "error_code": None,
                "error_message": None,
                "demo_note": "演示模式：请求已记录，不会提交到 AgentGuard/WARDEN。",
            },
        )
        return created, demo.meta_for("investigations.json")
    raise InvestigationServiceError(
        503, "API_UNAVAILABLE", "AgentGuard 不可达且未启用演示模式，无法创建调查"
    )


def get_investigation(
    client: AgentGuardClient, demo: DemoService, *, mode_override: str | None, request_id: str
) -> tuple[dict, dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode == DataMode.LIVE:
        try:
            return client.get_investigation(request_id), {"data_mode": "live"}
        except AgentGuardError as exc:
            raise _to_service_error(exc) from exc
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        item = demo.get_investigation(request_id)
        if item is None:
            raise InvestigationServiceError(404, "NOT_FOUND", f"调查不存在：{request_id}")
        return item, demo.meta_for("investigations.json")
    raise InvestigationServiceError(503, "API_UNAVAILABLE", "AgentGuard 不可达且未启用演示模式")


def get_timeline(
    client: AgentGuardClient, demo: DemoService, *, mode_override: str | None, request_id: str
) -> tuple[list[dict], dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode == DataMode.LIVE:
        try:
            detail = client.get_investigation(request_id)
        except AgentGuardError as exc:
            raise _to_service_error(exc) from exc
        return _derive_timeline(detail), {"data_mode": "live"}
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        return demo.get_timeline(request_id), demo.meta_for("timeline.json")
    raise InvestigationServiceError(503, "API_UNAVAILABLE", "AgentGuard 不可达且未启用演示模式")


def list_scenarios(
    client: AgentGuardClient, demo: DemoService, *, mode_override: str | None
) -> tuple[dict, dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode == DataMode.LIVE:
        try:
            return client.list_scenarios(), {"data_mode": "live"}
        except AgentGuardError as exc:
            raise _to_service_error(exc) from exc
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        return demo.list_scenarios(), demo.meta_for("scenarios.json")
    raise InvestigationServiceError(503, "API_UNAVAILABLE", "AgentGuard 不可达且未启用演示模式")


def _agentguard_reachable(client: AgentGuardClient) -> bool:
    try:
        client.health()
        return True
    except AgentGuardError:
        return False


def _derive_timeline(detail: dict) -> list[dict]:
    """Honest timeline from real fields only. Steps without confirming fields
    stay pending; we never guess that an unreported step has completed."""
    created_at = detail.get("created_at")
    updated_at = detail.get("updated_at")
    status = detail.get("status") or detail.get("workflow_status")
    plan_id = detail.get("plan_id")
    run_id = detail.get("run_id")
    result = detail.get("result")
    error_code = detail.get("error_code")
    error_message = detail.get("error_message")

    events: list[dict] = []
    events.append(_event("created", "调查创建", "completed" if created_at else "pending", created_at, None))
    events.append(_event("validated", "请求验证", "completed" if created_at else "pending", created_at, None))
    events.append(
        _event(
            "capabilities",
            "能力检查",
            "blocked" if error_code == "PLAN_BLOCKED" else "pending",
            None,
            None,
        )
    )
    events.append(
        _event(
            "planned",
            "审计计划",
            "completed" if plan_id else "pending",
            None,
            plan_id and f"计划 {plan_id}",
        )
    )
    events.append(
        _event("submitted", "运行提交", "completed" if run_id else "pending", None, run_id and f"运行 {run_id}")
    )
    if status == "completed":
        run_state = "completed"
    elif status in {"running", "submitted"} and run_id:
        run_state = "running"
    else:
        run_state = "pending"
    events.append(_event("running", "运行中", run_state, None, None))
    evidence_done = status == "completed" and (result is not None)
    events.append(_event("evidence", "证据生成", "completed" if evidence_done else "pending", None, None))
    if status == "completed":
        events.append(_event("completed", "调查完成", "completed", updated_at, None))
    elif status in {"blocked", "failed", "plan_blocked", "run_failed"}:
        events.append(
            _event("completed", "调查完成", "blocked" if "block" in status else "failed", updated_at, error_message)
        )
    else:
        events.append(_event("completed", "调查完成", "pending", None, None))
    return events


def _event(step: str, label: str, status: str, at: str | None, detail: str | None) -> dict:
    event = {"step": step, "label": label, "status": status, "at": at}
    if detail:
        event["detail"] = detail
    return event


def _to_service_error(exc: AgentGuardError) -> InvestigationServiceError:
    code = exc.code
    status_code = exc.status_code or 502
    if code == "WARDEN_NOT_CONFIGURED":
        status_code = 503
    return InvestigationServiceError(status_code, code, str(exc), exc.request_id)
