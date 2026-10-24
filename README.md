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

## 当前进度（B0–B3）

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
- [x] 后端 pytest（66 passed）、前端 vitest（34 passed）、Playwright 冒烟、CI 工作流、
      Docker 构建
- [ ] B4 交互图谱 → B5 证据与防御 → B6 实验/报告/经验 → B7 离线 Demo 完善 →
      B8 权限/部署/发布

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
# E2E（需前后端均已启动）
cd frontend; npx playwright test
```

### 5) Docker

```powershell
docker compose up --build          # frontend :5173, backend :8001
docker compose --profile postgres up --build   # 追加 PostgreSQL
```

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
