# J0 基线报告

## HEAD
- Branch: `feature/b25-b33-real-integration`
- SHA: `6eafe7fd9d3032af15d9100240b419bbdd478a11`

## 测试结果
| 测试 | 结果 |
|------|------|
| backend pytest -q | ✅ 全绿 |
| backend ruff check . | ✅ 0 错误 |
| frontend typecheck | ✅ 0 错误 |
| frontend lint | ✅ 0 错误 |
| frontend build | ✅ 成功 |

## 当前 AgentGuard pin
- D7: `3c34931f983b545c77ee79f866425eb63053807b`
- 上游 H 分支: `7a21fdc4168a8176ac71e47b4976b0bc9d8e29e3` (CI 未通过，不可用)

## 数据库版本
- Alembic 迁移: 0001–0005
- 最新: 0005 (project_investigation_loops)

## 已知问题
- J-02: ORM 与迁移唯一约束不一致
- J-03: Loop 列表与详情授权断裂
- J-04: EvidenceChanges 字段合同错误
- J-05: StrategyComparisonPage 使用错误接口
- J-06: MultiRoundReportPage 硬编码
- J-07: contracts/agentguard-version.json 过期
