# 集成阻塞清单（INTEGRATION_BLOCKERS）

日期：2026-10-28。当前静态核对基线：AgentGuard runtime `9a8ee1f5e78a0b254c17ea66ac5b140aa7e1e89a`
（1.1.0rc3）；OpenAPI 来源独立记录为 `9a8ee1f5e78a0b254c17ea66ac5b140aa7e1e89a`。
rc2→rc3 只更改 `info.version`，86 paths / 98 operations 不变。旧 rc2/rc1 快照保留作回滚和历史比较。
当前运行服务未配置，不能将静态合同核对描述为 Live 联调。
WARDEN / FRACTAL-Bench / StegoPot 只读。本文件登记**应用层**依赖的缺失能力与
处理策略；底层阻塞的权威来源是 AgentGuard `docs/DEPENDENCY_BLOCKERS.md`。

| ID | 缺失能力 | 影响的应用功能 | 应用层行为 | 解除条件 |
| --- | --- | --- | --- | --- |
| QWB-INT-001 | 公共 API 有消息级图谱路由，但每条边仍须携带 message/evidence 来源；rc2 真实服务行为尚未联调 | B4 交互图谱 | Live 只显示上游可用并有来源的边；无来源边剔除；超限明确标记截断；Demo 图谱与 Live 分开 | 完成目标 rc2 服务联调，确认消息来源、规模与缺失数据语义 |
| QWB-INT-002 | rc2 OpenAPI 发布 defense execute 路由，但 App 未验证真实执行器行为、权限合同和结果 | B5 防御执行 | 仍只展示候选/审批条件/状态；执行按钮不开放；预览不冒充执行成功 | 真实服务验证执行权限、执行结果及安全边界后再评估开放 |
| QWB-INT-003 | rc2 OpenAPI 发布 artifact content 路由；App 尚无受控下载与完整性验证流程，且未做 Live 联调 | B5 证据分析 | 不打开任意 file URI；未验证完整性保持未知/未验证；仅展示受控元数据和引用 | 建立经鉴权、限额和哈希验证的公开下载流程并完成真实联调 |
| QWB-INT-004 | rc2 增加 Loop query-only reconcile；另有 workflow/run cancel 路由，但没有 Loop-scoped cancel 映射；重启恢复与回滚仍未验证 | B3 调查状态 | 已集成恢复逻辑仍保留模糊状态；新 reconcile 路由保持未接入；App 不把不同资源 ID 的 cancel 路由混用 | 对账、重启恢复及 Loop 取消语义有真实服务和运行时证据 |
| QWB-INT-005 | rc2 OpenAPI 发布 Probe train/predict 路由；App 没有已验证的 Probe/SAE 工作流 | B3 调查创建（Probe/SAE 字段） | 不在 App 暴露这些操作；不伪装 WARDEN 代理或白盒结果 | 完成公开 API 权限、数据来源及真实运行结果验证 |
| QWB-INT-006 | 无真实因果验证结果（历史观察 6/8 完成、2 失败） | B6 实验对比 | 无数据不生成趋势图；观察结果不标成因果确认 | 真实实验与验证完成 |
| QWB-INT-007 | rc2 新增 `/v1/system/identity` 仅报告声明的构建身份，不提供模型运行时/Probe/SAE 就绪证明 | 系统总览 | AgentGuard health 不代表模型运行时、Probe/SAE 或威胁合同可用；未知即未知 | 有可验证的公开运行时状态合同并完成真实联调 |
| QWB-INT-008 | **（历史 B10 观察，需在 rc2 重新验证）** AgentGuard 1.0.0rc1 + WARDEN 0.2.0 组合下 defense policies/preview 曾返回 500 INTERNAL_SERVER_ERROR | B5 防御候选 Live 展示 | rc2 真实表现 **NOT_RUN**；不从历史故障推断当前成功或失败；不伪造候选 | 在 rc2 目标服务上重测并记录真实结果 |
| QWB-INT-009 | **（B10 实测新增）** 完整调查闭环需向 AgentGuard 注入威胁合同（`THREAT_CONTRACT_NOT_AVAILABLE`）、StegoPot ModelRuntime 与 RuntimeAdapter；未注入时调查被诚实记录为 `blocked` | B3 Live 调查全链路 | 创建/查询/证据链路已验证真实可用（preflight blocked 为上游诚实语义）；不伪造"运行完成"状态 | 注入威胁合同与模型运行时后重测 |
| QWB-INT-010 | RC3 OpenAPI 有 Study 注册/查询/分析和 run-scoped 配对/干预路由，但这些路由没有经真实服务验证；Study 没有项目归属映射或上游 POST 幂等键，分析输入的数组/工件引用不是独立来源证明；真实 paired executor 不可用 | APP-2 至 APP-4 研究工作台、执行与报告 | Study registry 标记 **STATIC_ONLY**；分析与四层执行标记 **BLOCKED**；真实运行 **NOT_RUN**。不开放 BFF 写入，不创建假 Arm、假指标或因果报告；策略评价仍是独立数据源 | 完成真实目标服务验证；为 Study 建立严格项目归属和安全提交/对账合同；可验证数据/工件来源；WARDEN 真实 executor 通过五臂研究与审查门 |

RC3 的完整静态合同与哈希见 [`AGENTGUARD_OPENAPI_DIFF_RC3.md`](AGENTGUARD_OPENAPI_DIFF_RC3.md)。真实 OpenAPI/identity/readiness 和 HTTP Smoke 仍 **NOT_RUN**；上游源码/CI 验收不等于部署服务验收。

## 历史 B10 实测（不代表 rc2 Live 验收）

- AgentGuard 1.0.0rc1 @ `7d42809` 与当时 BFF 连接器 13 个业务端点 100% 兼容
  （见 `AGENTGUARD_OPENAPI_DIFF_B10.md` 与 `scripts/live_agentguard_check.py` 输出）。
- 真实 WARDEN 0.2.0 内核可经 `AGENTGUARD_WARDEN_URL` 接入；调查创建/幂等重提交/
  详情/证据读取真实可用（`/v1/kernel/status` 独立报告 available）。
- A8 隐藏真值元数据守卫、422 清洗、X-Request-ID 回显实测生效。

## 应用层遵守的边界

- 不直接调用 WARDEN 内部模块/API；不绕过公共接口读内部数据库。
- 不实现 Probe/SAE/Activation Hook/EAP/底层因果干预。
- 合成数据绝不伪装为真实实验结果；Demo 数据不进入经验奖励库。
- 无审批权限不执行防御操作；凭证只存在于服务端。
