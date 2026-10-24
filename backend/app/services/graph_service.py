"""Interaction graph service (B4, real upstream contract in B13).

Live mode now consumes AgentGuard's C1 message-level interaction graph
(`GET /v1/investigations/{id}/interaction-graph`, published at pinned commit
907aa19). The upstream response self-describes availability: `available=false`
with `limitations[]` is an honest answer (no message metadata recorded for the
workflow), surfaced verbatim - never replaced by fabricated edges. When the
capability is not published on the pinned upstream, the BFF keeps the explicit
503 so the reason is visible. Demo mode still serves the fixed fixture.
"""

from __future__ import annotations

from app.core.data_mode import DataMode, effective_data_mode
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.services.demo_service import DemoService

GRAPH_OPERATION = "GET /v1/investigations/{request_id}/interaction-graph"


class GraphServiceError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(message)


def _agentguard_reachable(client: AgentGuardClient) -> bool:
    try:
        client.health()
        return True
    except AgentGuardError:
        return False


def _validated_graph(payload: dict) -> dict:
    """Pass through the upstream graph with structural sanity checks.

    Nodes/edges keep their upstream IDs (node_id, source/target, message_id,
    evidence_refs); candidate paths stay candidates - never presented as
    confirmed causal paths.
    """
    if not isinstance(payload.get("nodes"), list) or not isinstance(payload.get("edges"), list):
        raise AgentGuardError(502, "API_BAD_RESPONSE",
                              "interaction graph response has invalid nodes/edges")
    for node in payload["nodes"]:
        if not isinstance(node, dict) or not node.get("node_id"):
            raise AgentGuardError(502, "API_BAD_RESPONSE", "interaction graph node missing node_id")
    for edge in payload["edges"]:
        if not isinstance(edge, dict) or not edge.get("source") or not edge.get("target"):
            raise AgentGuardError(502, "API_BAD_RESPONSE", "interaction graph edge missing endpoints")
    return payload


def get_graph(
    client: AgentGuardClient, demo: DemoService, *, mode_override: str | None, request_id: str | None
) -> tuple[dict, dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode == DataMode.LIVE:
        operations = client.discover_operations()
        if not operations.get(GRAPH_OPERATION):
            reason = (f"AgentGuard pinned 版本未发布消息级交互图谱接口（{GRAPH_OPERATION}）"
                      f"（能力发现: {client.discovery_error or 'confirmed absent'}）；"
                      "不从风险分数推导虚假消息边（QWB-INT-001）。")
            raise GraphServiceError(503, "GRAPH_API_UNAVAILABLE", reason)
        if not request_id:
            raise GraphServiceError(422, "REQUEST_ID_REQUIRED", "Live 模式需要 request_id 才能查询交互图谱")
        try:
            payload = _validated_graph(client.get_interaction_graph(request_id))
        except AgentGuardError as exc:
            raise GraphServiceError(
                exc.status_code or 502, exc.code,
                f"{exc}（request_id={request_id}）") from exc
        meta = {
            "data_mode": "live",
            "capability": "available" if payload.get("available") else "upstream_no_data",
            "source": payload.get("source") or "agentguard",
            "limitations": payload.get("limitations", []),
        }
        return payload, meta
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        graph = demo.graph_sample(request_id=request_id)
        if graph is None:
            raise GraphServiceError(404, "NOT_FOUND", f"图谱样本不存在：{request_id}")
        return graph, demo.meta_for("graph.json")
    raise GraphServiceError(
        503, "API_UNAVAILABLE", "AgentGuard 不可达且未启用演示模式，无法提供交互图谱"
    )


def list_samples(client: AgentGuardClient, demo: DemoService, *, mode_override: str | None) -> tuple[list[dict], dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        return demo.graph_samples(), demo.meta_for("graph.json")
    raise GraphServiceError(
        503, "GRAPH_API_UNAVAILABLE", "Live 模式暂无可用的图谱样本列表（样本枚举能力未发布）"
    )
