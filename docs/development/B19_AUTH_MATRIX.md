# B19 授权矩阵（审计结果与修复后目标态）

日期：2026-10-24。基线：`7d484b9`（B18）。

## 审计发现（修复前）

| 入口 | 全局角色 | 项目校验 | 越权风险 |
| --- | --- | --- | --- |
| GET /api/investigations（LIVE） | viewer | **无** | 任意 viewer 读取上游全量调查列表 |
| POST /api/investigations | analyst | **无** | 创建的调查不归属任何项目，人人可读 |
| GET /api/investigations/{id}（LIVE） | viewer | **无** | 猜测 request_id 读取他人调查 |
| GET /api/investigations/{id}/timeline（LIVE） | viewer | **无** | 同上 |
| GET /api/evidence?request_id（LIVE） | viewer | **无** | 跨项目证据读取 |
| GET /api/defense?request_id（LIVE） | viewer | **无** | 跨项目防御候选读取 |
| POST /api/defense/{id}/preview（LIVE） | analyst | **无** | 跨项目预览触发上游持久化 |
| GET /api/interaction-graph?request_id（LIVE） | viewer | **无** | 跨项目图谱读取 |
| GET /api/reports/{run_id}（LIVE） | viewer | **无** | 猜测 run_id 读取他人报告 |
| GET /api/reports/{run_id}/export（LIVE） | viewer | **无** | 跨项目 PDF 导出 |
| GET /api/experiments（LIVE，C2） | viewer | **无**（上游全量索引） | 普通用户读取全部上游实验记录 |
| POST /api/experiments/compare（LIVE） | analyst | **无** | 同上 |
| GET /api/experiences（LIVE） | viewer | **无**（上游全量） | 同上 |
| GET /api/defense/outcomes | viewer | 无业务对象（历史汇总） | 低 |
| GET /api/dashboard | viewer | 系统健康聚合，业务摘要仅 demo | 低 |
| Demo（recorded/synthetic）各读入口 | viewer | 不适用（隔离命名空间） | 需保持登录（已有） |

共享凭证：所有上游调用使用同一服务端 Token（设计使然）；因此**应用层授权必须在
发起上游调用之前完成**——修复前的所有 LIVE 业务读取均违反此原则。

## 修复后目标态（本轮实现）

- **LIVE 数据 = 项目数据**：LIVE 模式下所有业务对象读取/操作必须经
  `resource_access` 服务验证 request_id（或 run_id→request_id）在
  `project_investigations` 中归属到用户为成员的项目；全局 admin 例外但逐操作审计。
- **无归属 LIVE 对象**（历史/未关联）：非成员 404（不泄露存在性）；admin 可访问。
- **新建调查（LIVE）**：必须带 `project_id`，先过项目成员 analyst+ 校验再提交
  上游；上游成功后立即持久化本地关联；关联失败返回 `link_pending` + 审计，
  绝不重发第二次创建。
- **run_id 授权**：`project_investigations.last_known_run_id`（迁移 0004）在
  已授权的调查读取时回填；报告访问按 run_id→关联行→项目成员判定；
  未映射 run_id 对非 admin 404。
- **上游全量记录（实验/经验）**：LIVE 模式仅全局 admin 可读（403
  `EXPERIMENTS_SCOPE_RESTRICTED`/`EXPERIENCES_SCOPE_RESTRICTED`），普通用户走
  demo 夹具或项目内引用；不以后端过滤伪装服务端授权。
- **Demo 命名空间**：recorded/synthetic 数据不进入项目索引、经验与审计统计；
  登录要求不变（viewer+），不涉及项目成员概念。
- **分页语义**：LIVE 调查列表改为从本地 `project_investigations`（按用户可访问
  集合）分页，真实空集；不再透传上游全量列表。

## 已知保留限制

- run_id 映射依赖已授权读取时的回填；未经工作台路径出现的 run_id 需 admin 认领。
- 同一 request_id 关联多个项目时，任一成员项目均可访问（设计语义，测试覆盖）。
- Dashboard 的业务摘要仅来自 demo 命名空间，不含 LIVE 业务对象。
