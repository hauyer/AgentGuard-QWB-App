# AgentGuard OpenAPI 差异报告（B10）

日期：2026-10-24。对比基线：

| 版本 | Commit | 说明 |
| --- | --- | --- |
| 旧（B0–B8 基线） | `00d12bee352060ea6014eebea8400edd7c74a029`（A7：Document public API and MCP acceptance） | 上游版本 0.9.x |
| 新（B10 固定） | `7d42809172059b1f38200bd8308c73345efd77dc`（A8：Record A8 cross-version acceptance） | 上游版本 **1.0.0rc1** |

快照：真实服务 `/openapi.json` 已留存于 `integration-data/agentguard-openapi-7d42809.json`
（68 条路径）。应用侧固定文件：`contracts/agentguard-version.json`。

## 结论：业务路径 100% 兼容，行为合同有增强

BFF 连接器使用的 13 个业务端点在新版 OpenAPI 中**全部存在且方法一致**：

```
GET  /v1/system/health              GET  /v1/scenarios
GET  /v1/system/capabilities        POST /v1/investigations
GET  /v1/kernel/status              GET  /v1/investigations
GET  /v1/investigations/{id}        GET  /v1/evidence/investigations/{id}
GET  /v1/defense-policies/{id}      POST /v1/defense-policies/{id}/preview
GET  /v1/reports/{run_id}           GET  /v1/experiences
GET  /v1/system/audit-events
```

无需修改任何业务端点路径。以下为通过真实服务联调确认的差异（均已处理或登记）。

## A8 行为差异与 BFF 适配

| # | 差异 | 上游行为（实测） | BFF 处理 |
| --- | --- | --- | --- |
| D1 | **隐藏真值字段拒绝**（新增） | `WardenAuditRequest.metadata` 递归拒绝 `oracle`/`ground_truth`/`label` 等评估器字段，返回 422（实测确认） | BFF 合同层同步实现 `find_hidden_truth_fields`（`app/schemas/investigations.py`），在转发前以 422 拒绝，错误信息一致 |
| D2 | **422 响应清洗** | 校验错误只含 type/loc/通用消息，不回显原始输入 | BFF 错误映射不变；422 直接透传状态码，不记录请求体 |
| D3 | **路由模块重构** | 公共路由从 app 工厂拆分至 `agentguard/api/public_routes.py`（纯内部重构） | 对 BFF 透明；连接器路径注释已更新 |
| D4 | **`WardenDefenseExecuteRequest` 移入公共合同** | 从 `api/app.py` 移至 `contracts/warden.py`（字段不变：candidate_id + authorization_ref） | 无需改动（BFF 未开放执行入口，见 QWB-INT-002） |
| D5 | **创建响应结构调整** | `POST /v1/investigations` 返回 200（非 201），顶层为 `workflow_id/workflow_status/workflow_revision/status/plan/run/preflight/blockers/note/statistics`，**无顶层 `request_id`** | BFF 保留 `payload.setdefault("request_id", request_id)` 补齐应用侧标识；时间线派生读取的 detail 顶层字段（status/plan_id/run_id/result）在新旧版本均存在 |
| D6 | **创建语义：诚实预检** | 真实 WARDEN 内核接入后，威胁合同/白盒/运行时未注入时返回 `status=blocked`、`preflight.blockers=["THREAT_CONTRACT_NOT_AVAILABLE:..."]`，不假装提交 | BFF 透传全部字段；Demo/前端不把 blocked 显示为成功 |
| D7 | **幂等性** | 同 `request_id` 重复提交返回 200，存储仅一条（实测 `stored_occurrences=1`）；重提交响应不回显 `workflow_id`（上游小缺陷，已登记） | BFF POST 从不自动重试；模糊超时走只读对账（`SUBMISSION_AMBIGUOUS` / `SUBMISSION_NOT_RECORDED`） |
| D8 | **审计日志降噪** | 未预期异常只记录 request_id + 异常类型，不记录堆栈/请求体 | BFF 同等约束已具备 |
| D9 | **测速头/安全头** | 上游响应含 `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY` | BFF 自身响应也补充同款安全头（B9） |

## 新增端点（上游新增，BFF 暂不消费）

`/v1/experiences/bandit-recommendations`、`/v1/experiences/recommendation-policies`（+rollback）、
`/v1/experiences/recommendations`、`/v1/experiences/action-statistics`、`/v1/kernel/doctor`、
`/v1/kernel/contracts`、`/v1/kernel/resources`、`/v1/kernel/audits` 等。经验推荐/策略类接口属于
经验学习闭环，应用层第一版按 B6 决策仅消费 `GET /v1/experiences`（不做 Thompson Sampling）。

## 实测发现的上游问题（登记，不在应用层绕过）

1. **QWB-INT-008**：`GET/POST /v1/defense-policies/{request_id}`（含 preview）在
   AgentGuard 1.0.0rc1 + WARDEN 0.2.0 组合下返回 500 `INTERNAL_SERVER_ERROR`
   （上游日志仅显示 `exception_type=TypeError`）。影响 B5 防御候选 Live 展示。
   解除条件：上游修复 defense preview 对 WARDEN 内核工作流的处理。
2. **幂等响应瑕疵**：重复提交时响应缺 `workflow_id`（D7）。不影响存储正确性，
   BFF 以对账 GET 为准。

## 联调证据

`scripts/live_agentguard_check.py`（真实服务 127.0.0.1:8000 + WARDEN 0.2.0 127.0.0.1:8003）：
**13 PASS / 1 BLOCKED-UPSTREAM / 0 FAIL**。完整输出见 `b10-live-final3.log`
（含 health/capabilities/kernel/scenarios/创建/真值拒绝/幂等/列表/详情/证据/报告/经验/审计门禁）。
