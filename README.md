# AgentGuard-QWB-App

基于 [AgentGuard](https://github.com/hauyer/AgentGuard) 的多智能体安全审计、主动调查与
定向防御应用平台，用于强网杯作品赛展示，并保留向真实应用产品发展的工程扩展能力。

> 本仓库是 **独立应用仓库**，不是新的因果审计框架，也不是 WARDEN 的替代品。
> AgentGuard / WARDEN / FRACTAL-Bench / StegoPot 四个仓库全程**只读**。

## 架构

```
用户 / 安全研究人员 / 比赛评委
        │
        ▼
AgentGuard-QWB-App  ──  React Web Console (frontend)
        │                FastAPI BFF: 会话/权限/业务/审计 (backend)
        │ REST API（仅经 BFF 连接器，上游地址服务端固定）
        ▼
AgentGuard  ── 上层调查与安全决策平台（只读）
        │ WARDEN REST API
        ▼
WARDEN     ── 底层因果审计内核（只读，不直接访问）
```

- **frontend**：React + TypeScript + Vite + TanStack Query + Zustand + Tailwind。
- **backend（BFF）**：FastAPI + Pydantic v2 + httpx + SQLAlchemy 2 + Alembic。
  负责系统状态、业务数据、服务端凭证、AgentGuard REST 调用、响应转换与审计。
  不重新实现 AgentGuard 的调查、证据门控、经验学习和策略算法。

## 当前进度（B0–B8 全部完成）

- [x] **B0** 独立 Git 仓库初始化，前后端基础工程可运行；AgentGuard 接口基线固定：
  `feature/agentguard-upper-layer-v1` @
  `00d12bee352060ea6014eebea8400edd7c74a029`（见 `contracts/agentguard-version.json`）
- [x] BFF AgentGuard 连接器（固定上游、服务端 Token、超时、错误映射、4 MiB 响应上限、
      幂等 GET 受控重试、POST 不重试、拒绝重定向、不记录敏感正文）
- [x] `GET /api/system/status`：应用状态 / AgentGuard 连通性 / WARDEN 状态摘要 /
      数据模式 / 功能可用性；AgentGuard 不可用时明确返回 unavailable，不虚构数据
- [x] **B1** 前端设计系统与通用组件（状态徽标/证据等级/时间线/分页表格/JSON 查看器/
      权限门控/演示回放标识），统一深蓝/白/灰安全平台风格与九项全局导航
- [x] **B2** 系统总览 Dashboard：`GET /api/dashboard`（健康/调查概况/证据等级与验证分布/
      策略状态/审计能力/依赖阻塞）；离线夹具服务（SHA-256 校验 + 来源溯源）；
      Live / Demo / Unavailable 三态显式展示，未知值不置 0
- [x] **B3** 安全调查工作台：`GET/POST /api/investigations`、`/api/investigations/{id}`、
      `/api/investigations/{id}/timeline`、`/api/scenarios`；创建表单按 AgentGuard
      WardenAuditRequest 合同校验（拒绝伪造资源 ID、能力门控 Probe/SAE）；
      详情页时间线只标记有数据支撑的步骤（未确认步骤显式 pending）；
      demo 提交只记录不假装运行（demo_note）；会话/Cookie/CSRF 双提交与角色门控
      （viewer/analyst/operator/admin）已接线
- [x] **B4** 多 Agent 交互图谱：`GET /api/interaction-graph`、`/api/interaction-graph/samples`；
      React Flow 页面（五类节点、筛选、时间回放、候选路径高亮、边/节点元数据抽屉、
      按调查导出 PNG）；Live 模式因公共 API 缺失消息级图谱显式返回
      `503 GRAPH_API_UNAVAILABLE`（QWB-INT-001），绝不补造通信边；Demo 使用固定
      SYNTHETIC 夹具并全程标注不可证明结论
- [x] **B5** 证据分析与定向防御工作台：`GET /api/evidence`、`GET /api/defense`、
      `POST /api/defense/{id}/preview`、`GET /api/defense/outcomes`；证据等级严格区分
      synthetic/observational/interventional/causal_validated（观测结果绝不标注为
      “因果路径已确认”），工件引用只展示元信息；防御候选展示权限要求/预计成本/相关
      证据，execution_supported 恒 false 时不开放执行按钮；预览仅 persist 不执行，
      demo 模式 preview 显式返回 409 DEMO_READONLY（不假装提交/审批）
- [x] **B6** 实验对比、报告与经验中心：`GET /api/experiments`（比较维度表，live 无
      公共列表接口时显式 503 EXPERIMENTS_UNAVAILABLE，绝不虚构趋势）、
      `GET /api/reports/{run_id}` + `GET /api/reports/{run_id}/export`（应用层 reportlab
      生成 PDF：仅排版报告字段，不改指标、不推断新因果结论；pypdf 文本级验证）、
      `GET /api/experiences`（已验证经验展示与查询，第一版不做 Thompson Sampling）
- [x] **B7** 独立 Demo 模式完善：`GET /api/demo/overview` + 前端 `/demo` 演示导览页
      （9 步完整可复现流程：打开平台→选场景→Agent 交互→调查过程→风险发现→
      证据与限制→防御候选→实验比较→生成报告，每步带 fixture_ref 与深链）；
      证据/防御页支持 `?request_id=` 深链；Live/Unavailable 下流程仍可浏览、
      场景数据按模式真实返回；demo/README.md 记录数据模式、夹具注册、流程与安全约束
- [x] **B8** 权限/安全/数据库/部署收尾：
      - 应用层业务表（users/projects/project_members/investigation_bookmarks/
        report_exports/demo_scenarios/ui_preferences/app_audit_events）+ Alembic
        初始迁移 `0001`（SQLite/PostgreSQL 均可执行，含升级/降级测试）
      - 业务操作审计：`GET /api/audit/events`（Operator+），调查创建与防御预览
        自动记录 actor/action/target/detail
      - 会话 Cookie 属性可配置：HttpOnly + SameSite=Lax 恒开，`SESSION_COOKIE_SECURE`
        支持 HTTPS 部署；`GET /api/system/settings` 返回数据模式/认证状态/角色说明
      - 前端 vitest / typecheck / lint / build 全绿；CI 五任务
        （backend/frontend/e2e/contract-check/docker）覆盖真实联调标 skipped
- [x] **B9** 生产安全加固（fail closed）：
      - `AUTH_ENABLED=true` 未配置 `APP_SECRET_KEY` 时**拒绝启动**（移除固定后备密钥，
        签名层二次防御 `SecretKeyNotConfigured`）；新增 `APP_ENV=development|demo|production`，
        production 强制认证 + ≥32 字符密钥 + HTTPS Cookie + DATABASE_URL，缺失即启动失败
      - 硬编码 Demo 账号仅限 development/demo 环境（production 恒拒绝，显式覆盖无效）；
        正式认证使用 `users` 表 + PBKDF2-SHA256 密码哈希（迁移 `0002`，
        `scripts/manage_users.py` 创建/改密/停用；停用即时失效已有会话；数据库不可用时 fail closed）
      - 审计事件持久化到 `app_audit_events`（DATABASE_URL 配置时启动自动 Alembic 升级）；
        `/api/audit/events` 支持 limit/offset 分页与 actor/action 过滤，服务重启可查，
        内存模式显式返回 `persisted=false`
      - 连接器 `trust_env=False`：上游请求不再经过环境/系统代理（防止
        X-AgentGuard-Token 泄露给不可控代理）；BFF 响应统一补 `nosniff/DENY/no-referrer` 安全头
      - Docker Compose 默认端口绑定 `127.0.0.1` 回环；新增 `docker-compose.prod.yml`
        （生产要求显式密钥/口令/CORS，后端端口不发布，要求外部 TLS 反代）
      - PDF 导出对上游字段做 XML 转义（防 reportlab 标记注入）；CSRF Cookie 与会话同周期；
        登录失败不区分用户名存在性
      - 安全回归测试 34 项（tests/test_b9_security.py）：fail-closed 配置矩阵、Demo 门控、
        DB 用户登录/停用、审计持久化/分页/重启恢复、代理不可劫持、PDF 转义、
        会话过期、模式分离等——后端 pytest 140 passed / ruff 0
- [x] **B10** AgentGuard 真实接口联调（基线更新 `7d42809`，1.0.0rc1 A8）：
      - OpenAPI 差异报告 `docs/api/AGENTGUARD_OPENAPI_DIFF_B10.md`：13 个业务端点
        100% 兼容；A8 新增隐藏真值元数据拒绝（BFF 合同同步实现）、422 清洗、
        创建响应改用 `workflow_id`（200 语义）
      - 真实服务联调（AgentGuard 1.0.0rc1 + WARDEN 0.2.0 内核）：
        `scripts/live_agentguard_check.py` **13 PASS / 1 BLOCKED-UPSTREAM / 0 FAIL**
        （health/capabilities/kernel/scenarios/调查创建/幂等/详情/证据/报告/经验/审计门禁）
      - 调查超时幂等恢复：POST 永不自动重试；模糊超时只读对账——上游确认存在则返回
        真实记录（`recovered_after_timeout`）、确认不存在报 `SUBMISSION_NOT_RECORDED`、
        对账不可用报 `SUBMISSION_AMBIGUOUS`；`wait_for_completion` 超时预算校验
      - 新增阻塞登记 QWB-INT-008（上游 defense preview TypeError 500）、
        QWB-INT-009（完整调查闭环需上游注入威胁合同/模型运行时，blocked 为诚实语义）；
        图谱/实验列表/防御执行维持 QWB-INT-001/002/006 阻塞，不伪造数据
      - Live/Recorded/Synthetic/Unavailable 严格分离：强制 `live` 上游不可达时降级
        `unavailable`，绝不假装 LIVE
- [x] **MVP 验收清单**：前后端独立运行、统一界面导航、连接状态真实展示、调查闭环、
      图谱与证据带来源、防御候选不伪造执行、报告导出、离线 Demo 完整、凭证不泄漏、
      测试与构建通过、部署文档完整、不直接调用底层三仓库、不修改 AgentGuard 内核
- [x] 本地 Git 仓库（main）已提交 B0–B8；远程仓库待用户执行 GitHub CLI 命令（见下）

## 快速开始

### 1) 后端（BFF）

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
Copy-Item ..\.env.example ..\.env   # 按需配置 AGENTGUARD_BASE_URL / Token
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8001
```

验证：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/health
Invoke-RestMethod http://127.0.0.1:8001/api/system/status
```

AgentGuard 未运行时，`/api/system/status` 返回 `data_mode=unavailable` 与显式错误，
**不会**返回虚构数据。BFF 默认绑定本机回环地址，不自动暴露公网。

### 2) 前端

```powershell
cd frontend
npm install
npm run dev     # http://localhost:5173，/api 由 Vite 代理到 BFF
```

### 3) 离线验证 LIVE 路径（无真实 AgentGuard 时）

```powershell
cd backend
.\.venv\Scripts\python ..\scripts\run_stub_agentguard.py --port 8002 --kernel available
# 另开终端，配置 .env 后重启 BFF：AGENTGUARD_BASE_URL=http://127.0.0.1:8002
# 前端系统总览应显示 LIVE / AgentGuard 已连接 / WARDEN 可用
```

替身只实现文档化合同形状，**不声称**是真实 WARDEN/模型运行时。

### 4) 测试与检查

```powershell
# 后端
cd backend; .\.venv\Scripts\python -m pytest -q; .\.venv\Scripts\ruff check .
# 前端
cd frontend; npm run typecheck; npm run lint; npm run test; npm run build
# 真实 AgentGuard 合同检查（无真实服务时自动 SKIP，绝不假通过）
python scripts\check_agentguard_contract.py
# 真实联调全链路检查（B10；无真实服务时 SKIP）
backend\.venv\Scripts\python scripts\live_agentguard_check.py
# E2E（需前后端均已启动）
cd frontend; npx playwright test
```

### 5) Docker

```powershell
docker compose up --build          # frontend :5173, backend :8001（默认仅绑定 127.0.0.1）
docker compose --profile postgres up --build   # 追加 PostgreSQL
# 生产部署（要求显式密钥/口令/CORS；端口不直接发布，前置 TLS 反代）：
# docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

默认开发部署绑定本机，不自动暴露公网；PostgreSQL 服务带健康检查、数据持久化卷；
`frontend/Dockerfile` + `nginx.conf` 提供反向代理与 gzip/缓存头。

### 6) 认证与数据库（B8/B9）

```powershell
# 启用四角色认证（生产必须）——B9 fail closed：
# AUTH_ENABLED=true 且未配置 APP_SECRET_KEY 时后端拒绝启动（无后备密钥）
# APP_ENV=production 额外强制：密钥>=32字符、SESSION_COOKIE_SECURE=true、DATABASE_URL
# 演示用户（仅 APP_ENV=development/demo 生效）：viewer/analyst/operator/admin，密码 <用户名>-demo
# 正式用户（production）：
#   1. 配置 DATABASE_URL 并启动后端（自动执行 Alembic 迁移）
#   2. backend\.venv\Scripts\python ..\scripts\manage_users.py create alice --role analyst
#   （PBKDF2-SHA256 哈希入库；deactivate 可即时吊销已有会话）

# 初始化应用层数据库（PostgreSQL 或 SQLite）
cd backend
alembic upgrade head        # 0001 业务表 + 0002 用户密码哈希字段
```

### 7) 真实 AgentGuard 联调（B10）

```powershell
# 终端 1：WARDEN 内核（0.2.0，只读运行）
cd ..\WARDEN
python -m uvicorn warden.interface.api.app:create_app --factory --host 127.0.0.1 --port 8003
# 终端 2：AgentGuard 1.0.0rc1（固定 feature/agentguard-upper-layer-v1 @ 7d42809）
cd ..\AgentGuard
set AGENTGUARD_WARDEN_URL=http://127.0.0.1:8003
.venv\Scripts\python -m uvicorn agentguard.api.app:app --host 127.0.0.1 --port 8000
# 终端 3：BFF + 实测
cd ..\AgentGuard-QWB-App\backend
set AGENTGUARD_BASE_URL=http://127.0.0.1:8000
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
# 真实联调检查（13 PASS / 1 BLOCKED-UPSTREAM / 0 FAIL）
..\backend\.venv\Scripts\python scripts\..\scripts\live_agentguard_check.py
```

实测发现的上游阻塞（QWB-INT-008/009）见 `docs/api/INTEGRATION_BLOCKERS.md`；
应用层不绕过、不伪造。离线无真实服务时 `check_agentguard_contract.py` 与
`live_agentguard_check.py` 均 SKIP，绝不假通过。

### 8) 创建远程仓库（可选，需 GitHub CLI 已登录）

```powershell
gh auth login
gh repo create AgentGuard-QWB-App --private --source . --push
```

未登录 GitHub CLI 时仅维护本地仓库，不影响交付。

## 环境变量

见 `.env.example`。要点：

- `AGENTGUARD_BASE_URL`：服务端固定的上游地址（http/https、无凭证/路径/查询/片段）。
- `AGENTGUARD_API_TOKEN` / `AGENTGUARD_OPERATOR_API_TOKEN`：服务端凭证，绝不下发浏览器。
- `APP_CORS_ORIGINS`：显式来源白名单，通配符被拒绝。
- `APP_DATA_MODE`：可选 `recorded` / `synthetic` 覆盖（用于演示）；留空按连通性裁决。

## 数据模式

| 模式 | 含义 |
| --- | --- |
| `live` | 当前通过 AgentGuard 获取的真实响应 |
| `recorded` | 经脱敏、保留来源信息的历史记录 |
| `synthetic` | 明确生成的教学或演示数据 |
| `unavailable` | 当前无法取得所需数据 |

AgentGuard 健康检查通过**不代表** WARDEN 或模型运行时可用；每层独立探测、独立报告。

## 接口协作与阻塞

- 接口矩阵：`docs/api/AGENTGUARD_API_MATRIX.md`
- 集成阻塞：`docs/api/INTEGRATION_BLOCKERS.md`
- 架构文档：`docs/architecture/overview.md`
- 接口变更只改 BFF 适配层 + 合同测试，应用业务 API 保持稳定。

## 仓库边界（红线）

不修改 AgentGuard/WARDEN/FRACTAL-Bench/StegoPot 源码；不直接调用 WARDEN 内部模块；
不实现 Probe/SAE/Activation Hook/EAP/底层因果干预；不把合成数据伪装成真实实验结果；
无审批权限不执行防御操作；真实模型 API Key 不进前端；未经确认不覆盖现有远程仓库。
