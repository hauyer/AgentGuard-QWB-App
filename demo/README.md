# demo 目录

离线演示数据与导览（B2 建立夹具服务，B7 完成完整演示流程）。

## 数据模式

应用层统一提供四种状态（`backend/app/core/data_mode.py`）：

- `LIVE`：当前通过 AgentGuard 获取的真实响应。
- `RECORDED`：经脱敏、保留来源信息的历史记录（回放，不是正在运行）。
- `SYNTHETIC`：明确生成的教学或演示数据。
- `UNAVAILABLE`：当前无法取得所需数据（绝不虚构）。

只有 AgentGuard 连通时才可能为 live；`APP_DATA_MODE` 只认 demo 模式（recorded/synthetic）。

## fixtures/

固定样例，全部在 `fixtures/index.json` 注册。每条记录包含：fixture ID、
数据模式（recorded/synthetic）、来源、采集或生成日期、原始 AgentGuard 版本、
关联 commit、是否脱敏、SHA-256、包含的能力、不能用于证明的结论。
`DemoService` 首次加载时校验 SHA-256，被篡改的夹具拒绝服务。

- `scenarios.json`：演示场景（sc-qwb-001 多智能体供应链工具调用滥用审计）。
- `investigations.json` / `timeline.json`：调查记录与时间线。
- `evidence.json`：证据（observational/interventional/causal_validated 分级）。
- `defense.json`：防御候选（execution_supported 恒 false）与历史结果。
- `graph.json`：交互图谱 SYNTHETIC 样本。
- `experiments.json` / `experiences.json` / `reports.json`：实验/经验/报告。
- `scripts/make_fixture_index.py`：生成/校验 index.json。

## 完整可复现演示流程（B7）

演示导览页 `GET /api/demo/overview`（前端 `/demo`）提供 9 步流程：

1. 打开平台 → 系统总览（数据模式与连接状态）
2. 选择演示场景 → sc-qwb-001
3. 查看 Agent 交互 → `/interaction-graph`（fx-graph-001，SYNTHETIC）
4. 查看调查过程 → `/investigations/inv-qwb-0001`（时间线仅标记有数据支撑的步骤）
5. 查看风险发现 → 调查详情结果
6. 查看证据和限制 → `/evidence?request_id=inv-qwb-0001`（等级严格区分）
7. 查看防御候选 → `/defenses?request_id=inv-qwb-0001`（不开放执行）
8. 查看实验比较 → `/experiments`（无数据不生成趋势图）
9. 生成报告 → `/reports`（JSON 下载 + PDF 导出）

即使 AgentGuard 与 WARDEN 都不在线，应用也能启动并展示完整、明确标识的离线
Demo；Demo 状态绝不被显示成真实后端在线（`DemoBanner` 回放标识 + 顶部数据模式）。

## 安全约束

- 不记录真实 API Key；不包含个人隐私与秘密；不包含未授权的真实生产数据。
- 录制数据模式不执行虚假的提交或审批操作（防御 preview 返回 409 DEMO_READONLY）。
- Demo 数据不得进入 AgentGuard 经验奖励库，不得用于真实因果实验统计。
- 界面禁止展示未标识的假统计值；未知值显式显示不可用。
