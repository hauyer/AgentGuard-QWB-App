"""Evidence analysis and defense workspace (B5).

Four-mode dispatch like investigations: LIVE proxies AgentGuard public APIs,
demo serves sanitised fixtures (never pretending execution), unavailable
returns explicit errors. The UI must clearly separate synthetic /
observational / interventional / causal_validated evidence and never mark
preview as execution.
"""

from __future__ import annotations

import logging

from app.core.data_mode import DataMode, effective_data_mode
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.schemas.defense import normalize_defense_payload
from app.schemas.evidence import normalize_evidence_payload
from app.services.demo_service import DemoService

logger = logging.getLogger(__name__)


class EvidenceServiceError(RuntimeError):
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


def get_evidence(
    client: AgentGuardClient, demo: DemoService, *, mode_override: str | None, request_id: str
) -> tuple[dict, dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode == DataMode.LIVE:
        try:
            payload = client.get_evidence(request_id)
        except AgentGuardError as exc:
            raise _to_service_error(exc) from exc
        return normalize_evidence_payload(payload), {"data_mode": "live"}
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        payload = demo.get_evidence(request_id)
        if payload is None:
            raise EvidenceServiceError(404, "NOT_FOUND", f"未找到调查 {request_id} 的证据记录")
        return normalize_evidence_payload(payload), demo.meta_for("evidence.json")
    raise EvidenceServiceError(503, "API_UNAVAILABLE", "AgentGuard 不可达且未启用演示模式，无法读取证据")


def get_defense(
    client: AgentGuardClient, demo: DemoService, *, mode_override: str | None, request_id: str
) -> tuple[dict, dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode == DataMode.LIVE:
        try:
            payload = client.get_defense_policies(request_id)
        except AgentGuardError as exc:
            raise _to_service_error(exc) from exc
        return normalize_defense_payload(payload), {"data_mode": "live"}
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        payload = demo.get_defense(request_id)
        if payload is None:
            raise EvidenceServiceError(404, "NOT_FOUND", f"未找到调查 {request_id} 的防御候选")
        return normalize_defense_payload(payload), demo.meta_for("defense.json")
    raise EvidenceServiceError(503, "API_UNAVAILABLE", "AgentGuard 不可达且未启用演示模式，无法读取防御候选")


def preview_defense(
    client: AgentGuardClient, demo: DemoService, *, mode_override: str | None, request_id: str
) -> tuple[dict, dict]:
    """Generate/refresh candidate preview only. Never executes a defense."""
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode == DataMode.LIVE:
        try:
            payload = client.preview_defense_policies(request_id)
        except AgentGuardError as exc:
            raise _to_service_error(exc) from exc
        return normalize_defense_payload(payload), {"data_mode": "live"}
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        # Recording mode must not fake a submission/approval action.
        raise EvidenceServiceError(
            409,
            "DEMO_READONLY",
            "演示模式不执行提交或审批操作：防御预览仅生成或更新候选，录制数据不得假装提交。",
        )
    raise EvidenceServiceError(503, "API_UNAVAILABLE", "AgentGuard 不可达且未启用演示模式，无法生成防御预览")


def historical_outcomes(
    client: AgentGuardClient, demo: DemoService, *, mode_override: str | None
) -> tuple[list[dict], dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode == DataMode.LIVE:
        # AgentGuard public API does not expose historical outcomes directly;
        # derive nothing and report the capability as unavailable rather than
        # inventing values.
        return [], {"data_mode": "live", "available": False}
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        return demo.historical_outcomes(), demo.meta_for("defense.json")
    raise EvidenceServiceError(503, "API_UNAVAILABLE", "AgentGuard 不可达且未启用演示模式")


def _to_service_error(exc: AgentGuardError) -> EvidenceServiceError:
    code = exc.code
    status_code = exc.status_code or 502
    if code == "WARDEN_NOT_CONFIGURED":
        status_code = 503
    return EvidenceServiceError(status_code, code, str(exc), exc.request_id)
