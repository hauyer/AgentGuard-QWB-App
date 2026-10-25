"""Risk findings and hypotheses service (B21).

Four-mode dispatch: LIVE proxies AgentGuard public APIs, demo serves
sanitised fixtures, unavailable returns explicit errors. The UI must
clearly separate findings from hypotheses, and never infer causal
conclusions from observation-only data.
"""

from __future__ import annotations

import logging

from app.core.data_mode import DataMode, effective_data_mode
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.services.demo_service import DemoService

logger = logging.getLogger(__name__)


class FindingsServiceError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str, request_id: str | None = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.request_id = request_id
        super().__init__(message)


def _agentguard_reachable(client: AgentGuardClient) -> bool:
    try:
        client.health()
        return True
    except AgentGuardError:
        return False


def get_findings(
    client: AgentGuardClient, demo: DemoService, *, mode_override: str | None, run_id: str
) -> tuple[dict, dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode == DataMode.LIVE:
        try:
            payload = client.get_run_findings(run_id)
        except AgentGuardError as exc:
            raise _to_service_error(exc) from exc
        return payload, {"data_mode": "live"}
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        payload = demo.get_findings(run_id)
        if payload is None:
            raise FindingsServiceError(404, "NOT_FOUND", f"未找到运行 {run_id} 的风险发现记录")
        return payload, demo.meta_for("findings.json")
    raise FindingsServiceError(503, "API_UNAVAILABLE", "AgentGuard 不可达且未启用演示模式，无法读取风险发现")


def get_hypotheses(
    client: AgentGuardClient, demo: DemoService, *, mode_override: str | None, run_id: str
) -> tuple[dict, dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode == DataMode.LIVE:
        try:
            payload = client.get_run_hypotheses(run_id)
        except AgentGuardError as exc:
            raise _to_service_error(exc) from exc
        return payload, {"data_mode": "live"}
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        payload = demo.get_hypotheses(run_id)
        if payload is None:
            raise FindingsServiceError(404, "NOT_FOUND", f"未找到运行 {run_id} 的调查假设记录")
        return payload, demo.meta_for("hypotheses.json")
    raise FindingsServiceError(503, "API_UNAVAILABLE", "AgentGuard 不可达且未启用演示模式，无法读取调查假设")


def _to_service_error(exc: AgentGuardError) -> FindingsServiceError:
    return FindingsServiceError(
        status_code=exc.status_code or 502,
        code=exc.code or "UPSTREAM_ERROR",
        message=str(exc),
        request_id=exc.request_id,
    )
