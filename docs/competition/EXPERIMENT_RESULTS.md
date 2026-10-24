# 实验结果（EXPERIMENT_RESULTS）

日期：2026-10-24。全部数据来自真实执行，测量环境与命令见
`docs/development/B11_TEST_REPORT.md` 与 `docs/development/B16_PERF.md`。

## 1. 真实链路联调（AgentGuard 1.0.0rc1 @ 907aa19 + WARDEN 0.2.0）

`scripts/live_agentguard_check.py`（严格五分类判定，机器可读报告
`docs/development/b11-live-check.json`）：

| 判定 | 数量 | 条目 |
| --- | --- | --- |
| PASS | 12 | health / capabilities / warden_kernel_status(available) / scenarios / create_investigation(200, preflight=blocked) / truth_guard_rejection(422) / idempotency(stored=1) / detail / evidence / interaction_graph / experiences / audit_events_auth(403) |
| BLOCKED_UPSTREAM | 2 | report_read（无 run_id，报告未读取——不计 PASS）；defense_policies（HTTP 500 INTERNAL_SERVER_ERROR，QWB-INT-008 上游 TypeError） |
| UNSUPPORTED | 1 | investigation_timeline（端点未发布） |
| FAIL | 0 | — |

关键语义实测：调查创建真实落库并诚实返回 preflight blocked
（THREAT_CONTRACT_NOT_AVAILABLE——上游未注入威胁合同，属预期）；同 request_id
重复提交存储仅一条；隐藏真值元数据被上游 422 拒绝。

## 2. 端到端测试

| 套件 | 结果 |
| --- | --- |
| 后端 pytest | **173 passed / 0 failed**（B8 安全 6 + B9 加固 34 + B12 项目 14 + B13 能力 12 + B16 专项 5 + 功能回归 102） |
| Ruff | 0 违规 |
| 前端 vitest | **53 passed**（8 文件） |
| 前端 typecheck / lint / build | 全绿（build 7.3s） |
| Playwright E2E | 1 passed（真实前端 + 真实 BFF + 真实 AgentGuard，`console boots and shows system status`） |
| 迁移链 | 0001→0002→0003 upgrade / downgrade→base / re-upgrade 全 rc=0，10 表齐 |
| 合同检查 | 16 固定端点全部存在于 live OpenAPI |

## 3. 性能实测（节选，完整见 B16_PERF.md）

| 指标 | 数值 |
| --- | --- |
| Dashboard `/api/system/status`（30 次） | p50=18.5 ms, p95=21.7 ms |
| 调查列表分页（30 次） | p50=15.4 ms, p95=20.4 ms |
| PDF 导出含渲染（10 次） | p50=21.7 ms, p95=58.8 ms |
| 图谱形状转换 1000 节点/1000 边 | 2.2 ms |
| 50 并发只读 | 全部 200，p50=539 ms（TestClient 线程池 GIL 限制，如实记录） |
| 上游不可达快速失败（2 s 超时） | AgentGuardUnavailable in ~7.5 s（含受控重试路径） |

## 4. 当前没有结果的部分（诚实清单）

- **防御执行**：外部执行器未验证（QWB-INT-002），无执行结果可展示；
  且 defense preview 在 pinned 组合下上游 500（QWB-INT-008）。
- **完整因果调查闭环**：需上游注入威胁合同与模型运行时（QWB-INT-009），
  当前真实创建的调查停在 preflight blocked——这是上游诚实语义，应用不伪装完成。
- **实验对比统计**：当前索引内条目 metrics_available=false（synthetic_report），
  按可比性门控全部拒绝计算——无伪造提升率。
- **经验学习**：`/v1/experiences` 返回真实空集（items=0），无已验证经验可展示。
