"""Demo centre (B7).

Provides the complete, reproducible offline demo flow: open platform -> pick
scenario -> agent interaction -> risk findings -> investigation process ->
evidence & limitations -> defense candidates -> experiment comparison ->
report. Everything served here is clearly labelled replay data (RECORDED /
SYNTHETIC); the demo never fakes live submissions or approvals.
"""

from __future__ import annotations

import logging

from app.core.data_mode import DataMode, effective_data_mode
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.services.demo_service import DemoService

logger = logging.getLogger(__name__)

# App-local guidance, not experiment data: stable across modes.
DEMO_FLOW = [
    {
        "step": 1,
        "title": "打开平台",
        "path": "/",
        "fixture_ref": None,
        "description": "系统总览：确认当前数据模式与 AgentGuard 连接状态，进入演示导览。",
    },
    {
        "step": 2,
        "title": "选择演示场景",
        "path": "/demo",
        "fixture_ref": "fx-scenarios-001",
        "description": "场景「多智能体供应链工具调用滥用审计」，明确风险类型与演示边界。",
    },
    {
        "step": 3,
        "title": "查看 Agent 交互",
        "path": "/interaction-graph",
        "fixture_ref": "fx-graph-001",
        "description": "SYNTHETIC 图谱：五类节点、候选路径与证据引用；边不代表真实消息级传输。",
    },
    {
        "step": 4,
        "title": "查看调查过程",
        "path": "/investigations/inv-qwb-0001",
        "fixture_ref": "fx-inv-001",
        "description": "调查详情与时间线：仅标记有数据支撑的步骤，未确认步骤保持 pending。",
    },
    {
        "step": 5,
        "title": "查看风险发现",
        "path": "/investigations/inv-qwb-0001",
        "fixture_ref": "fx-inv-001",
        "description": "调查结果与后续建议，风险发现来自录制记录。",
    },
    {
        "step": 6,
        "title": "查看证据和限制",
        "path": "/evidence?request_id=inv-qwb-0001",
        "fixture_ref": "fx-evidence-001",
        "description": "证据等级严格区分；观测性证据不被标注为因果已确认。",
    },
    {
        "step": 7,
        "title": "查看防御候选",
        "path": "/defenses?request_id=inv-qwb-0001",
        "fixture_ref": "fx-defense-001",
        "description": "候选展示审批条件与权限；execution_supported 恒 false，不开放执行。",
    },
    {
        "step": 8,
        "title": "查看实验比较",
        "path": "/experiments",
        "fixture_ref": "fx-experiments-001",
        "description": "比较维度表来自可验证实验记录；无数据不生成趋势图。",
    },
    {
        "step": 9,
        "title": "生成报告",
        "path": "/reports",
        "fixture_ref": "fx-reports-001",
        "description": "报告预览 + JSON 下载 + PDF 导出（应用层生成，不改指标、不推断新因果结论）。",
    },
]


class DemoCenterError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _agentguard_reachable(client: AgentGuardClient) -> bool:
    try:
        client.health()
        return True
    except AgentGuardError:
        return False


def get_demo_overview(
    client: AgentGuardClient, demo: DemoService, *, mode_override: str | None
) -> tuple[dict, dict]:
    """Flow guidance is always available; scenario data follows the mode."""
    mode = effective_data_mode(mode_override, _agentguard_reachable(client))
    if mode == DataMode.LIVE:
        try:
            scenarios = client.list_scenarios()
        except AgentGuardError as exc:
            scenarios = {
                "items": [],
                "error": exc.code,
                "note": "AgentGuard 不可用时演示导览仍可浏览流程，场景列表不可用。",
            }
        return {
            "flow": DEMO_FLOW,
            "scenarios": scenarios.get("items", []),
            "scenarios_error": scenarios.get("error") if isinstance(scenarios, dict) and "error" in scenarios else None,
        }, {"data_mode": "live"}
    if mode in (DataMode.RECORDED, DataMode.SYNTHETIC):
        scenarios = demo.list_scenarios()
        return {"flow": DEMO_FLOW, "scenarios": scenarios.get("items", []), "scenarios_error": None}, demo.meta_for(
            "scenarios.json"
        )
    return {"flow": DEMO_FLOW, "scenarios": [], "scenarios_error": "API_UNAVAILABLE"}, {"data_mode": "unavailable"}
