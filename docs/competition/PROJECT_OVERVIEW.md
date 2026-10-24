# 项目总览（PROJECT OVERVIEW）

**AgentGuard-QWB-App** —— 多智能体安全审计、主动调查与定向防御应用平台。

## 一句话定位

在 AgentGuard（调查编排/证据治理/经验学习公共 API）之上构建的**应用层**平台：
把"为什么认为有风险、证据支持到什么程度"变成安全研究人员可操作的工作流，
而不是一个只显示风险百分数的看板。

## 四层职责边界（全程不可破）

```
用户/安全研究人员/评委
        │
AgentGuard-QWB-App   ← 本仓库（唯一可修改）：React 控制台 + FastAPI BFF
        │ 公共 REST API（服务端固定上游，浏览器永不直连）
AgentGuard           ← 只读：编排、治理证据、策略决策、经验学习
        │
WARDEN               ← 只读：底层因果审计内核
FRACTAL-Bench / StegoPot ← 只读：实验条件与模型运行
```

## 已交付能力（B0–B17）

| 能力 | 说明 | 数据来源 |
| --- | --- | --- |
| 系统总览 | 健康逐层独立探测（AgentGuard ≠ WARDEN ≠ 模型运行时），未知值不置 0 | 真实 API |
| 项目管理 | 多项目隔离、成员权限双层校验、归档、项目内调查引用 | BFF 数据库（持久化） |
| 安全调查 | 合同校验创建（拒绝伪造资源 ID、隐藏真值元数据）、状态机、幂等与对账恢复 | AgentGuard |
| 调查工作台 | 单页整合状态/时间线/图谱/风险/证据/防御/报告，全部真实 ID 联动 | AgentGuard + BFF |
| 交互图谱 | C1 消息级图谱适配：诚实空图谱原样透传，绝不从风险分造边 | AgentGuard |
| 证据分析 | 四级证据（synthetic/observational/interventional/causal_validated）严格区分 | AgentGuard |
| 定向防御 | 候选/预览只读；执行能力以真实能力清单为准，缺失时按钮不可用 | AgentGuard |
| 实验对比 | C2 索引 + 受控对比；可比性门控，不可比给原因不算提升率 | AgentGuard |
| 报告中心 | JSON/PDF 导出（XML 转义、指标不加 王），全程字段溯源 | AgentGuard + BFF |
| 经验中心 | 已验证经验展示（不做 Thompson Sampling，不重造底层） | AgentGuard |
| 离线演示 | 三模式（Live/Recorded/Synthetic）严格分离，夹具 SHA-256 溯源 | 明确标注 |

## 关键数字（2026-10-24 实测）

- 后端 pytest **173 passed**，ruff 0 违规
- 前端 vitest **53 passed**，typecheck/lint/build 绿
- 真实 AgentGuard 1.0.0rc1 联调：**12 PASS / 0 FAIL / 2 BLOCKED-UPSTREAM / 1 UNSUPPORTED**（严格判定）
- Dashboard p50 18.5 ms；调查列表 p50 15.4 ms；PDF 导出 p50 21.7 ms（见 `docs/development/B16_PERF.md`）
- 数据库迁移 0001→0002→0003 升级/降级/重升级链路验证通过

## 明确不做（红线）

不重造 ExperienceBandit、不实现 Probe/SAE/Activation Hook、不创建另一个因果审计
框架、不访问 FRACTAL-Bench 隐藏真值、无审批不执行防御、合成数据绝不伪装真实结果。
