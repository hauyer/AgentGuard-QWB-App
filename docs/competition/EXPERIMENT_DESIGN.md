# 实验设计（EXPERIMENT_DESIGN）

## 设计原则

1. **证据等级先行**：所有实验结果标注 evidence_level
   （synthetic / observational / interventional / causal_validated），
   观察结果绝不标注为因果确认。
2. **可比性门控**：对比前检查场景一致性、指标可用性（metrics_available）、
   证据等级不混合（synthetic 不与真实证据进同一统计系列）、模型版本匹配。
   不可比时输出原因清单，不计算提升率。
3. **正常任务效用并列**：任何安全收益必须与 normal_task_success_rate 并排展示，
   防御不能以"正常任务全废"为代价而不被看见。

## 实验矩阵（应用层消费视角）

| 维度 | 取值 | 来源 |
| --- | --- | --- |
| 场景 | sc-qwb-001（工具滥用）等注册场景 | AgentGuard `/v1/scenarios` |
| 审计模式 | observation / capture_only / detection / causal_audit / defense_evaluation | WardenAuditRequest.mode |
| 证据等级 | 四级 | GovernedEvidence |
| 执行状态 | planned/running/completed/blocked/failed | AgentGuard 权威 |
| 数据来源 | live / synthetic_report / recorded fixture | data_source + data_mode |

## 对比协议（B13 compare_experiments）

1. 输入 run_ids（≥2，≤20）。
2. 从 C2 索引解析每项 run：scenario_id / evidence_level / metrics_available /
   execution_status。
3. 不可比条件（任一命中即拒绝计算）：
   - 场景集合 >1；
   - 任一 run `metrics_available=false`；
   - synthetic 与非 synthetic 混合。
4. 可比 → 转发上游 `POST /v1/experiments/compare`；结果原样返回，不二次加工。
5. 响应携带 `comparable` 布尔与 `reasons[]`，前端按原因渲染。

## 样本与统计

- 样本量不足时（items 缺失或 metrics_available=false）不输出统计结论。
- 应用层不做自助显著性检验（属于 AgentGuard/底层职责），只展示上游给出的指标。

## 与比赛场景的映射

| 演示场景 | 期望证据形态 |
| --- | --- |
| 正常多 Agent 协作 | observation，风险为空（真实空集） |
| 可疑工具调用 | observation + candidate_paths（线索） |
| 未授权信息流动候选 | candidate path + evidence_refs，标注"候选非因果" |
| 调查被阻塞 | preflight blockers（如 THREAT_CONTRACT_NOT_AVAILABLE） |
| 有证据但无法因果验证 | observational + limitations 说明 |
| 防御候选存在但执行器缺失 | 候选/审批条件展示，执行按钮不可用 |
