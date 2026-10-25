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
from app.integrations.agentguard_client import (
    AgentGuardClient,
    AgentGuardError,
    AgentGuardUnavailable,
)
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


def _link(settings, project_id: int | None, request_id: str, user) -> bool:
    """Persist the project link after a successful submission. A failed link is
    logged and reported via link_pending - never a second upstream submission."""
    if project_id is None:
        return True  # demo namespace or unlinked (should not happen in live)
    from app.services.resource_access import link_investigation_after_creation

    persisted = link_investigation_after_creation(settings, project_id, request_id, user.username)
    if not persisted:
        logger.error("project link persistence failed for %s (project %s); link_pending",
                     request_id, project_id)
    return persisted


def list_investigations(
    client: AgentGuardClient,
    demo: DemoService,
    *,
    mode_override: str | None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    settings=None,
    user=None,
) -> tuple[dict, dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode == DataMode.LIVE:
        # B19: live investigations are project-scoped. The list is the caller's
        # locally-linked set (paged with correct semantics), never the upstream
        # global listing.
        if settings is None or user is None:
            raise InvestigationServiceError(503, "AUTH_STORAGE_UNAVAILABLE", "授权存储不可用")
        from sqlalchemy import func, select

        from app.core.db import open_session
        from app.models.app import ProjectInvestigation, ProjectMember

        session = open_session(settings)
        if session is None:
            raise InvestigationServiceError(503, "AUTH_STORAGE_UNAVAILABLE", "授权存储不可用")
        with session:
            member_projects = select(ProjectMember.project_id).where(
                ProjectMember.username == user.username)
            conditions = [ProjectInvestigation.project_id.in_(member_projects)]
            total = session.scalar(
                select(func.count()).select_from(ProjectInvestigation).where(*conditions))
            rows = session.scalars(
                select(ProjectInvestigation)
                .where(*conditions)
                .order_by(ProjectInvestigation.created_at.desc(), ProjectInvestigation.id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
            items = [
                {
                    "request_id": row.agentguard_request_id,
                    "project_id": row.project_id,
                    "display_name": row.display_name,
                    "verification": row.verification,
                    "last_known_run_id": row.last_known_run_id,
                    "linked_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
        return ({"items": items, "count": len(items), "offset": offset, "limit": limit,
                 "total": int(total or 0)},
                {"data_mode": "live", "source": "local_project_index"})
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
    settings=None,
    user=None,
    project_id: int | None = None,
) -> tuple[dict, dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    request_id = f"inv-{uuid.uuid4().hex[:16]}"
    if mode == DataMode.LIVE:
        # B19: live creations must belong to a project the caller can operate on.
        if settings is None or user is None:
            raise InvestigationServiceError(503, "AUTH_STORAGE_UNAVAILABLE", "授权存储不可用")
        if project_id is None:
            raise InvestigationServiceError(
                422, "PROJECT_REQUIRED",
                "Live 模式创建调查必须指定 project_id（调查将归属到该项目并在本地持久化引用）")
        from app.services.project_service import ProjectServiceError, require_project_access

        try:
            require_project_access(settings, user, project_id, required_role="analyst")
        except ProjectServiceError as exc:
            raise InvestigationServiceError(exc.status_code, exc.code, str(exc)) from exc
        # The audit timeout must fit inside the HTTP budget, otherwise the BFF
        # would disconnect while the upstream run is still executing.
        if (
            settings is not None
            and request.wait_for_completion
            and settings.agentguard_api_timeout < request.timeout_seconds + 2
        ):
            raise InvestigationServiceError(
                422,
                "TIMEOUT_BUDGET_INVALID",
                "wait_for_completion=true 要求 AGENTGUARD_API_TIMEOUT 大于 timeout_seconds + 2 秒"
                f"（当前 HTTP 预算 {settings.agentguard_api_timeout}s，审计超时 {request.timeout_seconds}s）；"
                "请提高服务端超时或改用异步轮询。",
            )
        try:
            payload = client.create_investigation(request.to_warden_payload(request_id))
        except AgentGuardUnavailable as exc:
            # POST is never retried. AgentGuard records workflows synchronously
            # under our request_id before any remote submit, so a read-only
            # reconciliation GET decides whether the investigation actually
            # exists. We never auto-resubmit (A8 ambiguity contract).
            outcome, detail = _reconcile_after_timeout(client, request_id)
            if outcome == "found":
                detail = dict(detail)
                detail.setdefault("request_id", request_id)
                detail["recovered_after_timeout"] = True
                link_pending = not _link(settings, project_id, request_id, user)
                logger.warning("investigation %s reconciled after upstream timeout (found, link_pending=%s)",
                               request_id, link_pending)
                return detail, {"data_mode": "live", "recovered_after_timeout": True,
                                "link_pending": link_pending}
            if outcome == "absent":
                # Confirmed absent upstream: the original submission never
                # landed, so the client may safely retry with a new request.
                raise InvestigationServiceError(
                    exc.status_code or 503,
                    "SUBMISSION_NOT_RECORDED",
                    "AgentGuard 提交超时，且对账确认该调查未创建（request_id 未登记）；可安全重试。",
                    request_id,
                ) from exc
            raise InvestigationServiceError(
                503,
                "SUBMISSION_AMBIGUOUS",
                "AgentGuard 提交超时且对账不可用；状态不明确，请稍后按 request_id 查询对账，"
                "系统不会自动重新提交。",
                request_id,
            ) from exc
        except AgentGuardError as exc:
            raise _to_service_error(exc) from exc
        payload = dict(payload)
        payload.setdefault("request_id", request_id)
        # Reliable local link; failure is surfaced as link_pending (audited by
        # the route) instead of a blind second submission.
        link_pending = not _link(settings, project_id, request_id, user)
        return payload, {"data_mode": "live", "link_pending": link_pending}
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


RUN_TIMELINE_OPERATION = "GET /v1/runs/{run_id}/timeline"
REQUEST_TIMELINE_OPERATION = "GET /v1/investigations/{request_id}/timeline"


def get_timeline(
    client: AgentGuardClient, demo: DemoService, *, mode_override: str | None, request_id: str
) -> tuple[list[dict], dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode == DataMode.LIVE:
        try:
            detail = client.get_investigation(request_id)
        except AgentGuardError as exc:
            raise _to_service_error(exc) from exc
        operations = client.discover_operations()
        run_id = detail.get("run_id")
        # B20: D7 publishes the request_id-scoped timeline - prefer it, then the
        # run-scoped form, then the clearly-labelled derived view.
        if operations.get(REQUEST_TIMELINE_OPERATION):
            try:
                payload = client.get_investigation_timeline(request_id)
                events = _normalize_run_timeline(payload, run_id or request_id)
                return events, {"data_mode": "live", "timeline_source": "upstream",
                                "run_id": run_id, "upstream_form": "investigation"}
            except AgentGuardError as exc:
                if exc.status_code != 404:
                    raise _to_service_error(exc) from exc
        if run_id and operations.get(RUN_TIMELINE_OPERATION):
            try:
                payload = client.get_run_timeline(run_id)
                events = _normalize_run_timeline(payload, run_id)
                return events, {"data_mode": "live", "timeline_source": "upstream",
                                "run_id": run_id, "upstream_form": "run"}
            except AgentGuardError as exc:
                if exc.status_code != 404:
                    raise _to_service_error(exc) from exc
        reason = ("调查尚未产生 run_id（preflight blocked）" if not run_id
                  else "上游尚无该调查的持久化时间线（404）")
        return (_derive_timeline(detail),
                {"data_mode": "live", "timeline_source": "derived", "derived_reason": reason})
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        return demo.get_timeline(request_id), demo.meta_for("timeline.json")
    raise InvestigationServiceError(503, "API_UNAVAILABLE", "AgentGuard 不可达且未启用演示模式")


def _normalize_run_timeline(payload: dict, run_id: str) -> list[dict]:
    """Map upstream run timeline events to the app timeline shape verbatim.

    Unknown event kinds stay as-is (raw_status preserved); nothing is inferred
    from state that the upstream did not report.
    """
    raw_events = payload.get("events", payload.get("items", []))
    if not isinstance(raw_events, list):
        raise AgentGuardError(502, "API_BAD_RESPONSE", "run timeline response has invalid events")
    events: list[dict] = []
    for item in raw_events:
        if not isinstance(item, dict):
            continue
        events.append({
            "step": str(item.get("event_type") or item.get("step") or "event"),
            "label": str(item.get("label") or item.get("event_type") or "事件"),
            "status": "completed" if item.get("status") in (None, "completed") else str(item.get("status")),
            "at": item.get("at") or item.get("created_at"),
            "detail": item.get("detail") or item.get("message"),
        })
    return events


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


def _reconcile_after_timeout(client: AgentGuardClient, request_id: str) -> tuple[str, dict | None]:
    """Read-only reconciliation after an ambiguous POST timeout (B10).

    Returns ("found", payload) when the investigation exists upstream,
    ("absent", None) when the upstream conclusively reports 404 (the
    submission never landed), or ("unknown", None) when reconciliation
    itself failed - in which case the caller must keep the outcome ambiguous
    instead of guessing. Never resubmits.
    """
    try:
        payload = client.get_investigation(request_id)
    except AgentGuardError as exc:
        if exc.status_code == 404:
            return "absent", None
        return "unknown", None
    return "found", payload


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
