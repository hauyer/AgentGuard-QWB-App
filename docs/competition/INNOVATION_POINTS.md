# 创新点（INNOVATION_POINTS）

> 原则：应用层集成不包装成底层算法创新。每条创新说明：原有问题 → 本项目方法 →
> 与现有方案区别 → 实现位置 → 如何验证 → 当前结果与局限。

## 1. 能力发现式降级（Capability Discovery over Status Probing）

- **原有问题**：集成式平台普遍以"上游在线"判定全部功能可用，导致上游部分能力
  缺失时界面撒谎（显示可点击但失败，或展示伪造数据）。
- **本项目方法**：BFF 对 pinned commit 的 `/openapi.json` 做能力发现，8 个跟踪
  端点逐一判定 published/not published；业务能力五态（available/partial/blocked/
  unsupported/unavailable）。上游 C1 图谱响应自带 `available/data_status/limitations`，
  诚实空图谱**原样透传**。
- **与现有方案区别**：AgentGuard 原生只有端点级健康；WARDEN 无应用层视图。
  状态探测式集成（ping /health 即全绿）是行业常见反模式。
- **实现位置**：`agentguard_client.discover_operations()`、`graph_service`、
  `reports_service`、`data_mode.py`。
- **验证**：`tests/test_b13_capabilities.py`（12 项）+ 真实服务联调
  `scripts/live_agentguard_check.py`（12 PASS/0 FAIL/2 BLOCKED/1 UNSUPPORTED，
  阻塞项以真实响应为证据）。
- **结果**：C1/C2 发布当天（907aa19）应用层零猜测接入；未发布接口（readiness、
  options、timeline、reports 列表）显式 UNSUPPORTED。
- **局限**：能力发现按 OpenAPI 路径判定，无法感知端点内部语义变化（靠合同测试
  `check_agentguard_contract.py` 补位）。

## 2. 调查提交的幂等对账恢复（Ambiguity-aware Reconciliation）

- **原有问题**：网络超时的 POST 是模糊状态：重试可能重复创建调查，放弃可能
  丢失已创建的调查。多数集成直接选择"重试"或"报错"。
- **本项目方法**：POST 永不自动重试；超时后以原 request_id 做只读对账 GET，
  三态裁决——found（返回真实记录，标注 recovered_after_timeout）、absent
  （SUBMISSION_NOT_RECORDED，明确可安全重试）、unknown（SUBMISSION_AMBIGUOUS，
  拒绝猜测）。`wait_for_completion` 另有超时预算校验。
- **实现位置**：`investigations_service.create_investigation` + `_reconcile_after_timeout`。
- **验证**：`test_b9_security.py` 三态单测（fake connector 计数 POST 恰好 1 次）。
- **结果**：真实联调幂等检查 `stored_occurrences=1` 通过。
- **局限**：对账依赖 AgentGuard 的 request_id 本地登记语义（A8 合同）。

## 3. 项目级权限隔离与双层角色（B12）

- **原有问题**：单租户工具直接升级为多项目平台时，常见错误是"全局角色=全局权限"。
- **本项目方法**：全局角色 × 项目成员角色双层校验；非成员一律 404（不暴露项目
  存在性）；成员行删除/用户停用**下一次请求即生效**（无缓存会话状态）；
  check-then-insert 竞态由 UNIQUE 约束兜底转 409。
- **实现位置**：`project_service.require_project_access`、路由层、迁移 0003。
- **验证**：`test_b12_projects.py` 14 项 + `test_b16_security.py` 并发竞态项。
- **结果**：不同用户项目/调查引用/权限完全隔离；越权访问测试全绿。
- **局限**：项目成员身份以 username 字符串关联（demo/DB 用户统一命名空间的
  权衡）；删除项目（非归档）未提供。

## 4. 证据导向的调查工作台（B14）

- **原有问题**：安全产品常把"风险分数+炫酷图谱+AI 总结"当卖点，评委无法追问
  "为什么认为有风险、证据支持到什么程度"。
- **本项目方法**：单一工作区页整合状态/时间线（上游事件 vs 状态推导显式区分）/
  图谱（溯源 ID 保留）/候选风险（findings 携带 evidence_ids）/证据/防御/报告入口，
  全部经 request_id/run_id 真实深链；无数据部分显示"未提供"，绝不伪造。
- **实现位置**：`InvestigationWorkspacePage.tsx`、`graph_service._to_app_graph`。
- **验证**：`workspace.test.tsx`（上游时间线标注、诚实空图谱、真实 findings 渲染）。
- **结果**：演示主线可全程追问证据来源。
- **局限**：节点点击抽屉联动在完整图谱页（工作区内嵌为简化视图）。

## 5. 可复现三模式数据治理（B7/B17）

- **原有问题**：演示系统常用"随机造数"，无法回答"这条数据是哪来的"。
- **本项目方法**：Live（真实 API）/ Recorded（脱敏+来源）/ Synthetic（明确标注）
  三模式严格分离，夹具注册表带 SHA-256 校验，Demo 提交只记录不假装运行
  （demo_note），强制 live 上游宕机时自动降级 unavailable。
- **实现位置**：`data_mode.py`、`demo_service`、`demo/fixtures`。
- **验证**：模式分离测试（B9/B10/B13 各覆盖）；夹具哈希注册。
- **结果**：任何页面任何数字都可回答来源。
- **局限**：Recorded 模式数据集目前规模小（演示级）。
