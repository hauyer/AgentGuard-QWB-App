"""Interaction graph service (B4, real upstream contract in B13).

Live mode now consumes AgentGuard's C1 message-level interaction graph
(`GET /v1/investigations/{id}/interaction-graph`, present in the pinned API
contract). The upstream response self-describes availability: `available=false`
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
MAX_GRAPH_NODES = 500
MAX_GRAPH_EDGES = 2000


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
    """Keep only bounded graph data with upstream message/evidence provenance."""
    if not isinstance(payload.get("nodes"), list) or not isinstance(payload.get("edges"), list):
        raise AgentGuardError(502, "API_BAD_RESPONSE",
                              "interaction graph response has invalid nodes/edges")
    for node in payload["nodes"]:
        if not isinstance(node, dict) or not node.get("node_id"):
            raise AgentGuardError(502, "API_BAD_RESPONSE", "interaction graph node missing node_id")
    selected_nodes = payload["nodes"][:MAX_GRAPH_NODES]
    selected_ids = {str(node["node_id"]) for node in selected_nodes}
    verified_edges = []
    missing_provenance = 0
    for edge in payload["edges"]:
        if not isinstance(edge, dict) or not edge.get("source") or not edge.get("target"):
            raise AgentGuardError(502, "API_BAD_RESPONSE", "interaction graph edge missing endpoints")
        evidence_refs = edge.get("evidence_refs")
        has_source = bool(edge.get("message_id")) or (
            isinstance(evidence_refs, list) and any(isinstance(ref, str) and ref for ref in evidence_refs)
        )
        if not has_source:
            missing_provenance += 1
            continue
        if str(edge["source"]) not in selected_ids or str(edge["target"]) not in selected_ids:
            continue
        if len(verified_edges) < MAX_GRAPH_EDGES:
            verified_edges.append(edge)

    limitations = list(payload.get("limitations") or [])
    truncated = len(payload["nodes"]) > MAX_GRAPH_NODES or len(payload["edges"]) > MAX_GRAPH_EDGES
    if truncated:
        limitations.append(
            f"GRAPH_TRUNCATED: showing at most {MAX_GRAPH_NODES} nodes and {MAX_GRAPH_EDGES} edges; "
            "this is not a complete graph."
        )
    if missing_provenance:
        limitations.append(
            f"GRAPH_EDGES_WITHOUT_PROVENANCE_OMITTED: {missing_provenance} edge(s) "
            "had no message or evidence reference."
        )
    return {
        **payload,
        "nodes": selected_nodes,
        "edges": verified_edges,
        "limitations": limitations,
        "app_truncated": truncated,
    }


_NODE_TYPE_MAP = {"agent": "agent", "tool": "tool", "model": "model",
                  "invocation": "invocation", "external_resource": "external_resource"}


def _edge_source_ref(edge: dict) -> str:
    evidence_refs = edge.get("evidence_refs")
    refs = evidence_refs if isinstance(evidence_refs, list) else []
    first_ref = next((ref for ref in refs if isinstance(ref, str) and ref), None)
    return str(first_ref or edge.get("message_id") or "")


def _to_app_graph(payload: dict) -> dict:
    """Convert the upstream C1 graph to the application graph shape used since
    B4, preserving every provenance id (node_id, message_id, evidence_refs).
    No risk value is invented: upstream fields absent stay 'unknown'."""
    nodes = [
        {
            "id": str(node["node_id"]),
            "type": _NODE_TYPE_MAP.get(str(node.get("node_type") or "agent"), "invocation"),
            "label": str(node.get("label") or node["node_id"]),
            "risk": str(node.get("risk") or "unknown"),
            "timestamp": node.get("timestamp"),
            "source_id": str(node.get("source_id") or node["node_id"]),
            "metadata": node.get("metadata") or {k: v for k, v in node.items()
                                                 if k not in ("node_id", "node_type")},
        }
        for node in payload.get("nodes", [])
    ]
    edges = [
        {
            "id": str(edge.get("message_id") or f"{_edge_source_ref(edge)}#edge-{index}"),
            "source": str(edge["source"]),
            "target": str(edge["target"]),
            "type": ("message" if "message" in str(edge.get("event_type") or "")
                     else "result" if "result" in str(edge.get("event_type") or "")
                     else "invocation"),
            "message_id": edge.get("message_id"),
            "risk": str(edge.get("risk") or "unknown"),
            "timestamp": edge.get("timestamp"),
            "source_id": _edge_source_ref(edge),
            "metadata": edge.get("metadata") or {k: v for k, v in edge.items()
                                                 if k not in ("source", "target")},
        }
        for index, edge in enumerate(payload.get("edges", []))
    ]
    candidates = [
        {
            "id": f"candidate-{index}",
            "label": (str(path.get("label") or f"候选路径 {index + 1}")
                      + (f"（score {path.get('score')}）" if path.get("score") is not None else "")),
            "node_ids": [str(item) for item in path.get("nodes", [])],
            "edge_ids": [str(item) for item in path.get("edges", [])],
            "evidence_refs": [str(item) for item in path.get("evidence_refs", [])],
            "risk": str(path.get("risk") or "unknown"),
        }
        for index, path in enumerate(payload.get("candidate_paths", []))
        if isinstance(path, dict)
    ]
    return {
        "scenario_id": payload.get("scenario_id"),
        "nodes": nodes,
        "edges": edges,
        "candidate_paths": candidates,
        "not_provable": [str(item) for item in payload.get("limitations", [])],
        "upstream_available": bool(payload.get("available")),
        "upstream_data_status": payload.get("data_status"),
        "truncated": bool(payload.get("app_truncated")),
    }


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
            payload = _to_app_graph(_validated_graph(client.get_interaction_graph(request_id)))
        except AgentGuardError as exc:
            raise GraphServiceError(
                exc.status_code or 502, exc.code,
                f"{exc}（request_id={request_id}）") from exc
        meta = {
            "data_mode": "live",
            "capability": "available" if payload.get("upstream_available") else "upstream_no_data",
            "source": "agentguard-interaction-graph",
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
