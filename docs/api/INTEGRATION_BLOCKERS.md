# 集成阻塞清单（INTEGRATION_BLOCKERS）

日期：2026-10-24。基线：AgentGuard `7d42809172059b1f38200bd8308c73345efd77dc`
（1.0.0rc1，A8；旧基线 `00d12bee` 为 B0–B8 版本）。
WARDEN / FRACTAL-Bench / StegoPot 只读。本文件登记**应用层**依赖的缺失能力与
处理策略；底层阻塞的权威来源是 AgentGuard `docs/DEPENDENCY_BLOCKERS.md`。

| ID | 缺失能力 | 影响的应用功能 | 应用层行为 | 解除条件 |
| --- | --- | --- | --- | --- |
| QWB-INT-001 | 公共 API 不提供消息级交互图谱（Agent→Agent/Tool 消息边） | B4 交互图谱 | Live 模式显示能力不可用；Demo 模式使用固定标注样本；登记缺失合同 | AgentGuard 公共接口提供治理后的交互摘要 |
| QWB-INT-002 | 外部防御执行器未验证；`/v1/defense-policies/{id}/execute` unsupported | B5 防御执行 | 只展示候选/审批条件/状态；执行按钮不开放；前端不模拟执行成功 | AgentGuard 提供支持执行、权限模型与真实验证的公共接口 |
| QWB-INT-003 | WARDEN 工件无已核实的受控下载/完整性 API；证据带 ArtifactRef | B5 证据分析 | 不打开 file URI；完整性保持 unverified；只展示引用 | AgentGuard Evidence Gateway 提供下载与校验 |
| QWB-INT-004 | WARDEN 默认运行在进程内，无重启恢复；公开 API 无取消/回滚路由 | B3 调查状态 | 远端丢失保持 unknown/unavailable；不重跑冒充恢复；取消标 unsupported | WARDEN 公共 API 提供恢复/取消 |
| QWB-INT-005 | WARDEN 白盒 CLI/Probe Suite 无 REST 等价 Probe/SAE/白盒模型/配对重放接口 | B3 调查创建（Probe/SAE 字段） | 表单仅在能力清单支持时启用；不伪装 WARDEN 代理 | 受支持的 WARDEN 公共接口 |
| QWB-INT-006 | 无真实因果验证结果（历史观察 6/8 完成、2 失败） | B6 实验对比 | 无数据不生成趋势图；观察结果不标成因果确认 | 真实实验与验证完成 |
| QWB-INT-007 | 模型运行时状态无公开查询接口 | 系统总览 | 不因 AgentGuard health 通过就标记模型运行时可用 | 相应公共接口 |
| QWB-INT-008 | **（B10 实测新增）** AgentGuard 1.0.0rc1 + WARDEN 0.2.0 组合下 `GET/POST /v1/defense-policies/{request_id}`（含 preview）返回 500 INTERNAL_SERVER_ERROR（上游日志：TypeError） | B5 防御候选 Live 展示 | 502 透传真实上游错误码，不伪造候选；Demo 夹具保持可用并明确标注 | 上游修复 defense preview 对 WARDEN 工作流的处理 |
| QWB-INT-009 | **（B10 实测新增）** 完整调查闭环需向 AgentGuard 注入威胁合同（`THREAT_CONTRACT_NOT_AVAILABLE`）、StegoPot ModelRuntime 与 RuntimeAdapter；未注入时调查被诚实记录为 `blocked` | B3 Live 调查全链路 | 创建/查询/证据链路已验证真实可用（preflight blocked 为上游诚实语义）；不伪造"运行完成"状态 | 注入威胁合同与模型运行时后重测 |

## B10 实测确认（不再是阻塞的能力）

- AgentGuard 1.0.0rc1 @ `7d42809` 与 BFF 连接器 13 个业务端点 100% 兼容
  （见 `AGENTGUARD_OPENAPI_DIFF_B10.md` 与 `scripts/live_agentguard_check.py` 输出）。
- 真实 WARDEN 0.2.0 内核可经 `AGENTGUARD_WARDEN_URL` 接入；调查创建/幂等重提交/
  详情/证据读取真实可用（`/v1/kernel/status` 独立报告 available）。
- A8 隐藏真值元数据守卫、422 清洗、X-Request-ID 回显实测生效。

## 应用层遵守的边界

- 不直接调用 WARDEN 内部模块/API；不绕过公共接口读内部数据库。
- 不实现 Probe/SAE/Activation Hook/EAP/底层因果干预。
- 合成数据绝不伪装为真实实验结果；Demo 数据不进入经验奖励库。
- 无审批权限不执行防御操作；凭证只存在于服务端。
