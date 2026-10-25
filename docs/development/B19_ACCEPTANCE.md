# B19 验收报告（跨项目安全隔离与资源授权）

日期：2025-10-24 分支 `feature/b19-b25-security-productization`。

## 交付内容

1. **授权审计矩阵**：`docs/development/B19_AUTH_MATRIX.md`——修复前 13 个 LIVE
   业务入口存在"共享凭证+无项目校验"越权面，逐项列出修复后目标态。
2. **统一资源授权服务** `app/services/resource_access.py`：
   - `require_investigation_access`：request_id → project_investigations → 成员
     校验（全局×项目角色联合判断）；
   - `require_run_access`：run_id → `last_known_run_id` 桥接 → 同上；
   - `require_admin_scope`：上游全量记录（实验索引/经验）LIVE 模式仅全局 admin；
   - 对象无归属 → 非成员 404（不泄露存在性）；admin 例外逐操作审计
     （`resource.admin_access`）。
3. **迁移 0004**：`project_investigations.last_known_run_id`（run_id 授权桥），
   已授权读取时回填。
4. **路由接线**：调查详情/时间线/列表、证据、防御（含 preview）、图谱、报告
   （含导出）、实验索引/对比/经验全部接入授权检查，且发生在任何上游共享凭证
   调用之前。
5. **创建归属**：LIVE 创建必须 `project_id`（422 PROJECT_REQUIRED），先过项目
   成员 analyst+ 校验再提交上游；成功后本地关联持久化，失败返回
   `link_pending` + 审计（绝不重发第二次创建）；demo 命名空间不受影响。
6. **调查列表语义**：LIVE 列表改为本地项目索引分页（source=local_project_index），
   不再透传上游全量列表；分页在授权过滤后的集合上语义正确。
7. **前端适配**：创建表单按数据模式要求选择归属项目（Live 必选），服务层类型
   更新。

## 测试结果（真实执行）

- 新增 `tests/test_b19_isolation.py` **23 项全过**：跨项目读取 404（调查/证据/
  防御/图谱/preview）、猜测 run_id 404（读取+导出）、成员正常读取、
  LIVE 列表仅含已链接对象、未链接对象对非成员隐藏、admin 例外带审计、
  LIVE 实验/经验/对比仅 admin（403 + 明确错误码）、demo 命名空间登录即读且
  不入项目索引、移除成员即失效、停用即失效、归档读允许写阻断（409）、
  同一 request_id 双项目双成员可读。
- 回归：受影响旧测试更新为项目授权语义（live_project_env fixture、创建带
  project_id、列表断言本地索引、admin bypass 审计）；**后端 198 passed / 0 failed**。
- Ruff：0 违规。
- 迁移链：0001→0002→0003→0004 upgrade/downgrade/re-upgrade rc=0。
- 前端：typecheck + lint + vitest 55 passed + build 全绿。

## 已知限制（进入 B24/B25 处理）

- run_id 桥依赖已授权读取回填；旁路出现的 run_id 需 admin 认领（报告中心在
  LIVE 模式仅 admin 可浏览上游报告，普通用户经工作台链接进入）。
- 旧未归属调查的批量迁移工具未提供（admin 逐个通过项目页关联即可；不会因
  升级丢失——对象仍在 AgentGuard，admin 可访问）。
- Dashboard 业务摘要仅 demo 命名空间，无 LIVE 业务对象暴露（矩阵已记录）。
