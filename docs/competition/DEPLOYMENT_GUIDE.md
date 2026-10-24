# 部署指南（DEPLOYMENT_GUIDE）

## 0. 前置条件

- Python ≥ 3.11、Node ≥ 20（开发）；Docker ≥ 24（容器部署）。
- 上游：AgentGuard 1.0.0rc1（pinned `907aa19`）+ 可选 WARDEN 内核 0.2.0。
  四个上游仓库只读，不随本应用部署修改。

## 1. 开发环境（单机，回环绑定）

```powershell
# 后端
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
Copy-Item ..\.env.example .\.env   # 按需修改
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8001

# 前端
cd frontend
npm ci
npm run dev    # http://localhost:5173，/api 代理到 8001
```

## 2. 上游接入（真实联调）

```powershell
cd WARDEN && python -m uvicorn warden.interface.api.app:create_app --factory --port 8003
cd AgentGuard && set AGENTGUARD_WARDEN_URL=http://127.0.0.1:8003 && .venv\Scripts\python -m uvicorn agentguard.api.app:app --port 8000
# BFF .env: AGENTGUARD_BASE_URL=http://127.0.0.1:8000
```

验证：`backend\.venv\Scripts\python ..\scripts\live_agentguard_check.py`
（无真实服务时 SKIP 42，绝不假通过）。

## 3. 生产部署（docker-compose.prod.yml）

```powershell
# 必填环境变量（缺失任一项 compose 拒绝启动 = fail closed）：
#   APP_SECRET_KEY      python -c "import secrets;print(secrets.token_hex(32))"
#   POSTGRES_PASSWORD   数据库口令
#   APP_CORS_ORIGINS    公网来源白名单
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

生产约束（由配置校验强制）：`APP_ENV=production` 要求 AUTH_ENABLED=true、
密钥 ≥32 字符、SESSION_COOKIE_SECURE=true、DATABASE_URL（PostgreSQL）。
端口不直接发布——前置 TLS 反向代理（nginx/traefik/ALB），后端仅 qwb-internal 网络。

## 4. 初始化用户（生产）

```powershell
cd backend
$env:DATABASE_URL="postgresql+psycopg://qwb:<pw>@127.0.0.1:5432/agentguard_qwb"
..\scripts\manage_users.py create alice --role admin   # 交互输入口令
..\scripts\manage_users.py list
```

首次启动自动执行 Alembic 迁移；也可手动 `alembic upgrade head`。
demo 账号在 APP_ENV=production 下恒拒绝。

## 5. 验证清单

| 项 | 命令 | 期望 |
| --- | --- | --- |
| 后端健康 | `curl /api/health` | 200 |
| 迁移 | `alembic current` | 0003 |
| 合同 | `python scripts/check_agentguard_contract.py` | PASS 或 SKIP(42) |
| 真实联调 | `python scripts/live_agentguard_check.py` | 0 FAIL |
| 认证 | `manage_users.py create` 后登录 | 200 + 会话 Cookie |
| 审计 | operator 查询 `/api/audit/events` | persisted=true |

## 6. 备份与恢复

- PostgreSQL：`pg_dump agentguard_qwb`（业务表 + 审计）。
- 恢复后 `alembic current` 校验版本；审计重启可查（持久化保证）。
- 连接中断：BFF 数据库操作 fail closed（认证拒绝、项目接口 503），恢复后自愈。
