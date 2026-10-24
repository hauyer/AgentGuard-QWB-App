"""Dashboard aggregation for the BFF.

Every metric on the dashboard has a concrete source: a live AgentGuard call, a
demo fixture, or an explicit unavailable state. Unknown values are never
reported as 0, and sample-based aggregates are labelled as such.
"""

from __future__ import annotations

import logging

from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.schemas.dashboard import (
    AuditCapability,
    DashboardResponse,
    DependencyBlocker,
    EvidenceSummary,
    InvestigationSummary,
    PolicySummary,
)
from app.schemas.meta import fixture_meta, live_meta
from app.services.demo_service import DemoService
from app.services.status_service import build_system_status

logger = logging.getLogger(__name__)

LIVE_SAMPLE_LIMIT = 200
EVIDENCE_SAMPLE_RUNS = 3

# Known application-layer integration blockers (mirror docs/api/INTEGRATION_BLOCKERS.md).
DEPENDENCY_BLOCKERS: list[DependencyBlocker] = [
    DependencyBlocker(
        id="QWB-INT-001",
        title="消息级交互图谱 API 缺失",
        impact="交互图谱页在 Live 模式不可用，仅演示固定样本",
    ),
    DependencyBlocker(
        id="QWB-INT-002",
        title="外部防御执行器未验证",
        impact="防御候选只能预览，不能执行",
    ),
    DependencyBlocker(
        id="QWB-INT-003",
        title="WARDEN 工件无受控下载/完整性 API",
        impact="证据工件引用不可下载验证",
    ),
    DependencyBlocker(
        id="QWB-INT-004",
        title="WARDEN 进程内运行无恢复机制",
        impact="运行中断无法由应用层恢复",
    ),
    DependencyBlocker(
        id="QWB-INT-005",
        title="Probe/SAE REST 接口缺失",
        impact="调查创建无法在运行时外挂探针",
    ),
    DependencyBlocker(
        id="QWB-INT-006",
        title="无真实因果验证结果",
        impact="causal_validated 证据仅来自演示样例",
    ),
    DependencyBlocker(
        id="QWB-INT-007",
        title="模型运行时无公共查询接口",
        impact="模型运行状态不可由应用层独立核验",
    ),
]

AUDIT_CAPABILITIES: list[tuple[str, str]] = [
    ("probe_training", "探针训练"),
    ("sae_available", "SAE 可用性"),
    ("activation_hooks", "激活挂钩"),
    ("causal_audit", "因果审计"),
]


def _investigation_summary_live(client: AgentGuardClient) -> InvestigationSummary:
    try:
        payload = client.list_investigations(limit=LIVE_SAMPLE_LIMIT, offset=0)
    except AgentGuardError as exc:
        return InvestigationSummary(available=False, error=f"{exc.code}: {exc}")
    items = payload.get("items") or []
    counts = {"total": len(items), "running": 0, "completed": 0, "blocked": 0, "failed": 0, "pending": 0}
    for item in items:
        status = item.get("status") or item.get("workflow_status")
        if status in counts:
            counts[status] += 1
        elif status:
            counts.setdefault(f"other:{status}", 0)
    recent = None
    if items:
        recent = max(items, key=lambda item: item.get("created_at") or "", default=None)
    return InvestigationSummary(
        available=True,
        sample_based=True,
        **counts,
        recent_request_id=recent.get("request_id") if recent else None,
        recent_status=recent.get("status") if recent else None,
    )


def _evidence_summary_live(client: AgentGuardClient, sample_request_ids: list[str]) -> EvidenceSummary:
    by_level: dict[str, int] = {}
    by_verification: dict[str, int] = {}
    for request_id in sample_request_ids:
        try:
            payload = client.get_evidence(request_id)
        except AgentGuardError as exc:
            logger.warning("evidence sample failed for %s: %s", request_id, exc.code)
            continue
        for item in payload.get("items") or []:
            level = item.get("evidence_level") or "unknown"
            verification = item.get("verification_status") or "unknown"
            by_level[level] = by_level.get(level, 0) + 1
            by_verification[verification] = by_verification.get(verification, 0) + 1
    if not by_level and not by_verification:
        return EvidenceSummary(available=False, error="no evidence obtainable from sampled runs")
    return EvidenceSummary(
        available=True,
        sample_based=True,
        by_level=by_level,
        by_verification=by_verification,
        recent_count=sum(by_level.values()),
    )


def _policy_summary_live(client: AgentGuardClient, sample_request_ids: list[str]) -> PolicySummary:
    pending = 0
    approved = 0
    unsupported = 0
    for request_id in sample_request_ids:
        try:
            payload = client.get_defense_policies(request_id)
        except AgentGuardError as exc:
            logger.warning("defense sample failed for %s: %s", request_id, exc.code)
            continue
        for candidate in payload.get("candidates") or []:
            status = candidate.get("status")
            if status == "pending_approval":
                pending += 1
            elif status == "approved":
                approved += 1
            if not candidate.get("execution_supported"):
                unsupported += 1
    if pending == approved == unsupported == 0:
        return PolicySummary(available=False, error="no defense candidates obtainable from sampled runs")
    return PolicySummary(
        available=True,
        sample_based=True,
        pending_approval=pending,
        approved=approved,
        unsupported=unsupported,
        verified_historical=0,
    )


def build_dashboard(
    client: AgentGuardClient, demo: DemoService, *, data_mode_override: str | None = None
) -> DashboardResponse:
    from app.core.data_mode import DataMode

    system = build_system_status(client, data_mode_override=data_mode_override)
    mode = system.data_mode

    if mode == DataMode.LIVE:
        investigation = _investigation_summary_live(client)
        sample_ids: list[str] = []
        if investigation.available and investigation.completed:
            # sample the most recent completed investigations for evidence/policy
            try:
                items = client.list_investigations(limit=LIVE_SAMPLE_LIMIT, offset=0).get("items") or []
                completed = sorted(
                    (item for item in items if (item.get("status") or "") == "completed"),
                    key=lambda item: item.get("created_at") or "",
                    reverse=True,
                )
                sample_ids = [item["request_id"] for item in completed[:EVIDENCE_SAMPLE_RUNS]]
            except AgentGuardError as exc:
                logger.warning("investigation re-list for sampling failed: %s", exc.code)
        evidence = _evidence_summary_live(client, sample_ids)
        policy = _policy_summary_live(client, sample_ids)
        meta = live_meta()
    elif mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        investigation = _summary_from_demo(demo.investigation_summary())
        evidence = _summary_from_demo(demo.evidence_summary())
        policy = _summary_from_demo(demo.policy_summary())
        meta = fixture_meta(demo.meta_for("investigations.json"))
    else:
        investigation = InvestigationSummary(available=False, error="AgentGuard unreachable and demo mode not enabled")
        evidence = EvidenceSummary(available=False, error="AgentGuard unreachable and demo mode not enabled")
        policy = PolicySummary(available=False, error="AgentGuard unreachable and demo mode not enabled")
        meta = live_meta()
        meta.data_mode = "unavailable"  # type: ignore[assignment]

    audit_capabilities = []
    if system.agentguard.capabilities:
        caps = system.agentguard.capabilities.capabilities
        for name, note in AUDIT_CAPABILITIES:
            audit_capabilities.append(AuditCapability(name=name, enabled=bool(caps.get(name)), note=note))
    elif mode == DataMode.LIVE:
        audit_capabilities = [
            AuditCapability(name=name, enabled=False, note=f"{note}：能力清单不可用")
            for name, note in AUDIT_CAPABILITIES
        ]

    return DashboardResponse(
        system=system,
        investigation_summary=investigation,
        evidence_summary=evidence,
        policy_summary=policy,
        dependency_blockers=DEPENDENCY_BLOCKERS,
        audit_capabilities=audit_capabilities,
        meta=meta,
    )


def _summary_from_demo(summary: dict) -> InvestigationSummary | EvidenceSummary | PolicySummary:
    if "pending_approval" in summary:
        return PolicySummary(**summary)
    if "by_level" in summary:
        return EvidenceSummary(**summary)
    return InvestigationSummary(**summary)
