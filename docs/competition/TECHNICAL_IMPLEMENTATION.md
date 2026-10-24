# 技术实现（TECHNICAL IMPLEMENTATION）

## 技术栈

| 层 | 技术 | 说明 |
| --- | --- | --- |
| 前端 | React 19 + TypeScript + Vite + TanStack Query + Zustand + Tailwind + @xyflow/react | 设计系统组件库（badge/drawer/timeline/data-table 等 20+） |
| BFF | FastAPI + Pydantic v2 + httpx + SQLAlchemy 2 + Alembic | 全同步路由 + TestClient 测试 |
| 数据库 | SQLite（开发）/ PostgreSQL 16（生产，compose profile） | 10 张业务表，Alembic 0001–0003 |
| 测试 | pytest（173）+ vitest（53）+ Playwright（E2E 真实栈） | 全部真实执行 |
| 部署 | Docker Compose（dev 回环绑定 + prod fail-closed overlay） | nginx 反代 + gzip |

## 核心模块与代码索引

| 模块 | 关键文件 | 职责 |
| --- | --- | --- |
| 连接器 | `backend/app/integrations/agentguard_client.py` | 固定上游/超时预算/4 MiB 上限/GET 重试/POST 不重试/拒绝重定向/能力发现/trust_env=False |
| 合同 | `backend/app/schemas/investigations.py` | WardenAuditRequest 镜像 + A8 隐藏真值元数据递归拒绝 |
| 项目 | `backend/app/services/project_service.py` | 双层角色/成员生命周期/调查关联验证/审计范围 |
| 审计 | `backend/app/services/audit_service.py` | 持久化/分页/actor/action/project_id/时间范围过滤 |
| 会话 | `backend/app/core/security.py`、`passwords.py` | HMAC 会话+CSRF、PBKDF2-SHA256（无后备密钥） |
| 图谱 | `backend/app/services/graph_service.py` | C1 适配 + 上游→应用形状转换（溯源 ID 全保留） |
| 报告 | `backend/app/services/reports_service.py` | C2 索引/受控对比/PDF（XML 转义、指标不加 王） |
| 数据模式 | `backend/app/core/data_mode.py` | 四态严格分离 |
| 前端工作区 | `frontend/src/pages/InvestigationWorkspacePage.tsx` | B14 单页联动 |

## 环境变量（要点）

`AGENTGUARD_BASE_URL`（固定上游，校验 http(s)/无凭证/无路径）、`AGENTGUARD_API_TOKEN`
（服务端）、`APP_ENV`（development/demo/production）、`AUTH_ENABLED` + `APP_SECRET_KEY`
（缺一拒启）、`SESSION_COOKIE_SECURE`、`DATABASE_URL`（生产必填）。
完整见 `.env.example`。

## 数据库模式

users（含 password_hash/is_active）、projects（status/created_by）、
project_members（username 身份）、project_investigations（AgentGuard 引用 +
verification）、investigation_bookmarks、report_exports、demo_scenarios、
ui_preferences、app_audit_events（含 project_id）、alembic_version。
BFF 只保存自身业务对象与 AgentGuard 引用，不复制底层审计数据库。

## 联调协议适配层

- 业务端点 16 个固定（`contracts/agentguard-version.json`），OpenAPI 快照 +
  canonical SHA-256 记录；候选端点 available/not_published 清单随 commit 更新。
- 错误码映射：上游 `detail.error` → BFF 语义码（WARDEN_NOT_CONFIGURED→503 等），
  422 清洗透传。
- 版本策略：pin 驱动，不自动追踪上游 main；差异报告归档
  （`docs/api/AGENTGUARD_OPENAPI_DIFF_B10.md`）。
