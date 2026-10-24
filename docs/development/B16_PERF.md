# B16 性能实测（PERF）

日期：2026-10-24。环境：Windows 10.0.26200 x64，Python 3.13，BFF TestClient + stub 上游（真实 HTTP）。有界执行，未发起任何真实模型调用。

- Dashboard `/api/system/status`：30 次，p50=18.5 ms，p95=21.7 ms，max=33.3 ms
- 调查列表分页 `/api/investigations?limit=50`：30 次，p50=15.4 ms，p95=20.4 ms
- PDF 导出（含渲染）：10 次，p50=21.7 ms，p95=58.8 ms，大小 2–2 KiB
- 图谱形状转换 100 节点/100 边：0.3 ms（后端单次）
- 图谱形状转换 500 节点/500 边：2.2 ms（后端单次）
- 图谱形状转换 1000 节点/1000 边：2.2 ms（后端单次）
- 50 并发只读 `/api/investigations`：全部 200，p50=539.2 ms，p95=602.2 ms，max=609.7 ms（TestClient 线程池，含 GIL 竞争；生产 uvicorn 多进程表现只会在 CI 同法复测）
- 上游不可达（死端口, 2s 超时, GET 重试关闭路径）快速失败：AgentGuardUnavailable in 7514 ms

## 记录为手动/后续的项

- 前端 React Flow 100/500/1000 节点交互帧率：需要浏览器环境人工记录（B14 工作区已限制初始渲染节点数 ≤24，完整图谱页由 React Flow 自适应视口承担）。
- 多副本 BFF 部署下的登录限速迁移到共享存储：登记于 KNOWN_LIMITATIONS。