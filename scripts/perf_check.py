"""B16 performance measurement (real, bounded, local).

Measures with the contract stub over real HTTP:
  * dashboard latency (p50/p95 over N calls)
  * investigation list pagination latency
  * PDF export latency
  * graph conversion scaling at 100/500/1000 nodes
  * 50 concurrent read-only requests against the BFF
Frontend rendering performance (React Flow pan/zoom) is out of scope for this
script and is recorded as a manual item in B16_PERF.md.

Usage: backend\\.venv\\Scripts\\python scripts\\perf_check.py
"""

from __future__ import annotations

import io
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import uvicorn  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.integrations.agentguard_client import AgentGuardClient  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.conftest import _serve  # noqa: E402
from tests.stub_agentguard import create_stub_app  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "development" / "B16_PERF.md"


def percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(ratio * len(ordered)))
    return ordered[index]


def main() -> int:
    stub_url = _serve(create_stub_app(kernel_status="available", warden_available=True))
    app = create_app()
    client = TestClient(app)
    client.__enter__()
    settings = type(app.state.settings).model_validate({
        "agentguard_base_url": stub_url, "agentguard_api_timeout": 15.0,
    })
    app.state.settings = settings
    app.state.agentguard_client = AgentGuardClient(settings)
    app.state.audit_service = type(app.state.audit_service)(settings)

    lines: list[str] = [
        "# B16 性能实测（PERF）",
        "",
        f"日期：2026-10-24。环境：Windows 10.0.26200 x64，Python 3.13，BFF TestClient + "
        f"stub 上游（真实 HTTP）。有界执行，未发起任何真实模型调用。",
        "",
    ]

    # 1. dashboard latency
    samples: list[float] = []
    for _ in range(30):
        start = time.perf_counter()
        response = client.get("/api/system/status")
        assert response.status_code == 200
        samples.append((time.perf_counter() - start) * 1000)
    lines += [f"- Dashboard `/api/system/status`：30 次，p50={percentile(samples, 0.5):.1f} ms，"
              f"p95={percentile(samples, 0.95):.1f} ms，max={max(samples):.1f} ms"]

    # 2. investigation list pagination
    samples = []
    for _ in range(30):
        start = time.perf_counter()
        response = client.get("/api/investigations", params={"limit": 50, "offset": 0})
        assert response.status_code == 200
        samples.append((time.perf_counter() - start) * 1000)
    lines += [f"- 调查列表分页 `/api/investigations?limit=50`：30 次，p50={percentile(samples, 0.5):.1f} ms，"
              f"p95={percentile(samples, 0.95):.1f} ms"]

    # 3. PDF export
    samples = []
    sizes = []
    for _ in range(10):
        start = time.perf_counter()
        response = client.get("/api/reports/run-stub-0001/export")
        assert response.status_code == 200
        samples.append((time.perf_counter() - start) * 1000)
        sizes.append(len(response.content))
    lines += [f"- PDF 导出（含渲染）：10 次，p50={percentile(samples, 0.5):.1f} ms，"
              f"p95={percentile(samples, 0.95):.1f} ms，大小 {min(sizes)//1024}–{max(sizes)//1024} KiB"]

    # 4. graph conversion scaling (backend conversion cost at scale)
    from app.services.graph_service import _to_app_graph

    for node_count in (100, 500, 1000):
        payload = {
            "nodes": [{"node_id": f"n{i}", "node_type": "agent"} for i in range(node_count)],
            "edges": [{"source": f"n{i}", "target": f"n{(i + 1) % node_count}",
                       "event_type": "message", "message_id": f"m{i}"} for i in range(node_count)],
            "candidate_paths": [], "limitations": [],
        }
        start = time.perf_counter()
        converted = _to_app_graph(payload)
        elapsed = (time.perf_counter() - start) * 1000
        assert len(converted["nodes"]) == node_count
        lines += [f"- 图谱形状转换 {node_count} 节点/{node_count} 边：{elapsed:.1f} ms（后端单次）"]

    # 5. 50 concurrent read-only requests
    def one_call(_: int) -> float:
        start = time.perf_counter()
        assert client.get("/api/investigations", params={"limit": 20}).status_code == 200
        return (time.perf_counter() - start) * 1000

    with ThreadPoolExecutor(max_workers=50) as pool:
        latencies = list(pool.map(one_call, range(50)))
    lines += [f"- 50 并发只读 `/api/investigations`：全部 200，p50={percentile(latencies, 0.5):.1f} ms，"
              f"p95={percentile(latencies, 0.95):.1f} ms，max={max(latencies):.1f} ms（TestClient 线程池，"
              f"含 GIL 竞争；生产 uvicorn 多进程表现只会在 CI 同法复测）"]

    # 6. AgentGuard unreachable timeout recovery
    client_bad = AgentGuardClient(type(settings).model_validate({
        "agentguard_base_url": "http://127.0.0.1:9", "agentguard_api_timeout": 2.0}))
    start = time.perf_counter()
    try:
        client_bad.health()
        unreachable = "unexpected success"
    except Exception as exc:  # noqa: BLE001
        unreachable = f"{type(exc).__name__} in {(time.perf_counter() - start) * 1000:.0f} ms"
    client_bad.close()
    lines += [f"- 上游不可达（死端口, 2s 超时, GET 重试关闭路径）快速失败：{unreachable}"]

    lines += ["",
              "## 记录为手动/后续的项",
              "",
              "- 前端 React Flow 100/500/1000 节点交互帧率：需要浏览器环境人工记录"
              "（B14 工作区已限制初始渲染节点数 ≤24，完整图谱页由 React Flow 自适应视口承担）。",
              "- 多副本 BFF 部署下的登录限速迁移到共享存储：登记于 KNOWN_LIMITATIONS。"]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    client.__exit__(None, None, None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
