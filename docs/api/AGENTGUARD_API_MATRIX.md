# AgentGuard API Matrix

Pinned baseline (B10): AgentGuard `7d42809172059b1f38200bd8308c73345efd77dc`
(`feature/agentguard-upper-layer-v1`, "Record A8 cross-version acceptance", 1.0.0rc1).
Previous baseline (B0–B8): `00d12bee352060ea6014eebea8400edd7c74a029`.
Business paths are unchanged between both baselines; behavior differences are
documented in `AGENTGUARD_OPENAPI_DIFF_B10.md`.
Machine-readable record: `contracts/agentguard-version.json`.

Legend — BFF 支持: `client`=BFF 连接器已实现方法；`used`=当前阶段被应用服务使用；
`page`=计划使用的应用页面（阶段）。

| AgentGuard 路由 | 方法 | 用途 | BFF 方法 | B0 使用 | 应用页面（阶段） |
| --- | --- | --- | --- | --- | --- |
| `/v1/system/health` | GET | 服务健康（不代表 WARDEN/模型运行时） | `health()` | used | 系统总览 (B2) |
| `/v1/system/capabilities` | GET | 能力清单 CapabilityManifest | `capabilities()` | used | 系统总览 (B2) |
| `/v1/kernel/status` | GET | WARDEN 集成状态与阻塞 | `kernel_status()` | used | 系统总览 (B2) |
| `/v1/scenarios` | GET | 公开场景目录 | `list_scenarios()` | client | 调查创建 (B3) |
| `/v1/investigations` | POST | 提交 WardenAuditRequest | `create_investigation()` | client | 调查创建 (B3) |
| `/v1/investigations` | GET | 分页工作流摘要 | `list_investigations()` | client | 调查列表 (B3) |
| `/v1/investigations/{request_id}` | GET | 持久状态、远端 ID、安全结果摘要 | `get_investigation()` | client | 调查详情 (B3) |
| `/v1/evidence/investigations/{request_id}` | GET | 治理后证据摘要（不打开工件 URI） | `get_evidence()` | client | 证据分析 (B5) |
| `/v1/defense-policies/{request_id}` | GET | 只读防御候选 | `get_defense_policies()` | client | 定向防御 (B5) |
| `/v1/defense-policies/{request_id}/preview` | POST | 生成/更新候选预览（不执行） | `preview_defense_policies()` | client | 定向防御 (B5) |
| `/v1/reports/{run_id}` | GET | 读取 AgentGuard 报告 | `get_report()` | client | 报告中心 (B6) |
| `/v1/experiences` | GET | 已验证经验查询 | `search_verified_experiences()` | client | 经验中心 (B6) |
| `/v1/system/audit-events` | GET | 操作员审计页 | `get_api_audit_events()` | client | 系统设置 (B8) |

## 响应合同（已从目标 commit 源码核实）

- 列表分页：`{items, count, offset, limit, next_offset}`。
- 调查详情：`{request_id, status, workflow_status, revision, statistics, created_at,
  updated_at, plan_id, run_id, result, error_code, error_message}`。
- 证据：`{request_id, workflow_status, run_status, items: [GovernedEvidence], limitations}`；
  `evidence_level ∈ {synthetic, observational, interventional, causal_validated}`；
  `verification_status ∈ {verified, unverified, blocked, failed, unsupported}`。
- 防御候选：`DefensePreview {schema_version, run_id, status, candidates, policy_notes,
  execution_performed, evidence_mode}`；`execution_supported` 默认 false。
- 调查提交请求体：`WardenAuditRequest`（见 `src/agentguard/contracts/warden.py`）。
- 错误体：`{"detail": {"error": CODE, "message": ...}}` + `X-Request-ID`。
- 鉴权：通用 `X-AgentGuard-Token`；操作员路由 `X-AgentGuard-Operator-Token`。

## 稳定性策略

- BFF 是唯一上游访问点；上游路径不散落在前端组件。
- 上游不兼容变化 → 更新 `app/integrations/agentguard_client.py` 适配层 + 合同测试，
  保持 `/api/*` 应用接口稳定。
- 不修改 AgentGuard 以适配前端页面；新接口需求形成接口需求单交给 AgentGuard A8 流程。
