# 架构说明（ARCHITECTURE）

## 组件拓扑

```
┌────────────────────────────────────────────────────────┐
│ frontend (React 19 + TS + Vite + TanStack Query)       │
│  9 大导航页 + 调查工作区（B14）                          │
│  只与 /api/* 通信（Vite 代理/nginx 反代）                │
└──────────────────────┬─────────────────────────────────┘
                       │ HTTP（会话 Cookie + CSRF 双提交）
┌──────────────────────▼─────────────────────────────────┐
│ backend BFF (FastAPI + Pydantic v2 + SQLAlchemy 2)     │
│  auth/session/角色门控/项目隔离（B12）                   │
│  连接器 AgentGuardClient：固定上游/超时/4MiB 上限/       │
│  GET 受控重试/POST 永不自动重试/拒绝重定向/trust_env=False│
│  能力发现 discover_operations()（B13）                   │
│  服务层：status/dashboard/investigations/graph/          │
│  evidence/defense/reports/demo/projects/audit            │
│  审计：AuditService → app_audit_events（持久化）          │
└───────────┬────────────────────────────┬───────────────┘
            │ Alembic（0001/0002/0003）   │ 公共 REST API
┌───────────▼──────────┐    ┌─────────────▼───────────────┐
│ SQLite（开发默认）/    │    │ AgentGuard 1.0.0rc1 @907aa19 │
│ PostgreSQL（生产）     │    │  ├ WARDEN 0.2.0 内核（独立层）│
│ 业务表 10 张           │    │  └ FRACTAL-Bench/StegoPot   │
└──────────────────────┘    └─────────────────────────────┘
```

## 关键设计决策

| 决策 | 理由 | 位置 |
| --- | --- | --- |
| BFF 唯一上游通道 | 上游地址服务端固定、浏览器不可影响（SSRF 面=0）；Token 永不下发 | `app/integrations/agentguard_client.py` |
| 按能力发现而非连接状态 | AgentGuard 在线 ≠ WARDEN 可用 ≠ 模型可用；每个端点独立判定 available/partial/blocked/unsupported/unavailable | `discover_operations()` |
| 会话 = HMAC 签名 Cookie | 无状态、可配置过期；密钥缺失 fail closed（无后备密钥） | `app/core/security.py` |
| 成员身份 = username 行 | demo 用户与 DB 用户同一命名空间；删除行即时吊销 | `project_members` |
| 审计持久化 + project 范围 | 重启可查、按项目过滤、登录事件也审计 | `app_audit_events` |
| 数据模式四态 | live/recorded/synthetic/unavailable；强制 live 上游宕机降级 unavailable，绝不假装 LIVE | `app/core/data_mode.py` |
| POST 幂等 + 只读对账 | 模糊超时对账三态（found/absent/unknown），永不盲目重提 | `investigations_service` |
| 迁移由 Alembic 独占 | 启动自动 upgrade；降级链路测试验证 | `migrations/versions/0001-0003` |

## 请求生命周期示例（创建调查）

1. 前端 `POST /api/investigations`（CSRF 头 + 会话 Cookie）
2. 依赖链：会话验证 → 角色门控（analyst+）→ CSRF 双提交校验
3. Pydantic 合同校验（含 A8 隐藏真值元数据递归拒绝、capture_targets 唯一非空）
4. 数据模式裁决 → LIVE：`POST /v1/investigations`（X-Request-ID 传播）
5. 网络模糊超时 → 只读对账 GET → found（返回真实记录）/ absent（SUBMISSION_NOT_RECORDED，可安全重试）/ unknown（SUBMISSION_AMBIGUOUS）
6. 审计落库（actor/action/target/project_id）
7. 响应携带 data_mode 元数据；前端按真实状态渲染（blocked 显示 blocked）

## 安全控制清单

CORS 显式白名单（拒绝通配）、会话 HttpOnly+SameSite、CSRF 双提交、
登录限速（10 次/5 分钟/用户）、登录审计、PBKDF2-SHA-256（390k 轮）口令哈希、
审计行 detail 4000 字符上限且不含凭证、响应安全头（nosniff/DENY/no-referrer）、
PDF 字段 XML 转义 + 导出文件名清洗、上游连接 trust_env=False（阻断环境代理劫持 Token）。
