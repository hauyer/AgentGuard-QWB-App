"""Interaction graph service (B4).

Live mode: AgentGuard does not yet expose message-level interaction graphs
(QWB-INT-001), so the BFF reports the feature as unavailable instead of
fabricating edges from risk scores. Demo mode serves the fixed fixture with
clear provenance. Every node/edge keeps its source_id.
"""

from __future__ import annotations

from app.core.data_mode import DataMode, effective_data_mode
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.services.demo_service import DemoService


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


def get_graph(
    client: AgentGuardClient, demo: DemoService, *, mode_override: str | None, request_id: str | None
) -> tuple[dict, dict]:
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode == DataMode.LIVE:
        raise GraphServiceError(
            503,
            "GRAPH_API_UNAVAILABLE",
            "AgentGuard 当前公共 API 未提供消息级交互图谱（QWB-INT-001），Live 模式无法获取图谱数据。",
        )
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
        503, "GRAPH_API_UNAVAILABLE", "Live 模式暂无可用的图谱样本列表（QWB-INT-001）"
    )
