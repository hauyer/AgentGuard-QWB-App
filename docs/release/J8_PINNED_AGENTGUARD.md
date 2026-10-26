# J8 固定版 AgentGuard 联调验收

**日期：** 2026-10-26
**应用仓库：** `feature/b25-b33-real-integration`
**J8 起点：** `b494f3bbe6a67ec77f382801dcd5204364aa0046`
**J8 提交主题：** `docs(release): verify pinned AgentGuard integration`

## 固定版本

应用正式 pin 保持在 AgentGuard D7：`3c34931f983b545c77ee79f866425eb63053807b`，版本 `1.1.0rc1`。本轮没有修改 `contracts/agentguard-version.json`。

OpenAPI 快照共 76 条路径。对 JSON 排序后进行 canonical JSON SHA-256 核验，得到 `ab8535a0ebb6c989e700f9bad3b48a13f29c61a4d3e7c20bfed94def6c7d0117`，与版本清单一致。快照当前位于工作区相邻目录 `../integration-data/agentguard-openapi-3c34931.json`，不在 QWB-App Git checkout 内；清单记载的 `integration-data/agentguard-openapi-3c34931.json` 相对路径在当前 checkout 中不存在，这是当前可复现性限制。

只读 AgentGuard checkout 当前为 `feature/i-reliability-and-live-validation`，HEAD `cd3e9f3f26504f74f347656e97913f55c5db8b4a`，与 D7 pin 不同。该 checkout 有三个既存未跟踪日志文件（`e2-full.log`、`e2-junit.xml`、`e2-test.log`）；本轮未修改该仓库。

未取得 AgentGuard I 阶段 CI 与接口合同验收通过的证据，故 J8 不更新正式 pin，也不将 I 阶段接口标为已集成。

## 固定 D7 HTTP Smoke

Smoke 在精确 D7 源码的临时隔离副本中运行；没有配置 WARDEN URL 或 Operator token。它验证的是固定版 API 行为，不是 WARDEN、模型或已有业务记录的 Live 联调。

| 检查 | 结果 | 观察 |
|---|---|---|
| `GET /v1/system/health` | PASS | HTTP 200，`status=ok`，版本 `1.1.0rc1` |
| `GET /v1/system/readiness` | PASS（分层受限） | API 可用；WARDEN 不可用；run 相关能力显示 unknown、unsupported 或 blocked |
| `GET /v1/investigations/options` | PASS（不可提交） | `available=false`，所有模式 `submittable=false` |
| `GET /v1/investigations`、`GET /v1/reports` | PASS（空数据） | 调查和报告均为 0 条 |
| `GET /v1/runs/{run_id}/findings` | PASS（未知 run 拒绝） | 占位 run 返回 HTTP 404 `run_id not found`；没有真实 findings 记录可验证 |
| 无 Operator token 的 `GET /v1/system/audit-events` | PASS（权限拒绝） | HTTP 403 |
| `GET /openapi.json` | PASS | 76 条路径，与固定快照核验一致 |

## D7 能力边界与验收状态

| 能力 | 状态 | 证据与限制 |
|---|---|---|
| Health、readiness、investigation options、report list | PASS | 以上述精确 D7 HTTP smoke 验证；options 因 WARDEN 缺失而不可提交 |
| Risk/findings | PASS（接口存在）；NOT_RUN（真实记录） | D7 OpenAPI 含 `/v1/runs/{run_id}/findings`；未知 run 返回 404 |
| Loop list/detail/decisions/evidence/budget | UNSUPPORTED | 固定 D7 OpenAPI 没有 `/v1/investigation-loops` 路径；应用不得将缺失上游能力伪装为 Live |
| 策略评价 list/detail | UNSUPPORTED | 固定 D7 OpenAPI 没有 `/v1/research/strategy-evaluations` 路径 |
| Reports | PASS（空列表）；NOT_RUN（真实报告记录） | D7 有 `/v1/reports` 与 `/v1/reports/{run_id}`，隔离服务中没有可读取报告 |
| Operator 权限 | PASS | 缺少 Operator token 的 audit-events 请求返回 403 |
| 应用项目隔离 | PASS | 后端隔离测试与 Playwright 用户/项目隔离流程通过；使用确定性 Stub，显式标记 Synthetic |
| 真实基础调查、Loop、已持久化策略评价 | NOT_RUN | 隔离 D7 服务没有这些记录；未提供可验证的真实记录或访问凭据 |
| 真实 WARDEN / 模型 Live Smoke | NOT_RUN | Smoke 未配置 WARDEN 或模型服务；不能据此宣称 Live 集成通过 |
| AgentGuard I CI 与合同验收 | NOT_RUN | 没有通过证据，因此正式 pin 保持 D7 |

## 应用层验收命令

| 命令 | 结果 |
|---|---|
| `python -m pytest -vv -o faulthandler_timeout=45`（`backend/`） | PASS，248 passed in 700.49s；全量测试，无跳过项 |
| `python -m pytest -q`（`backend/`） | INCOMPLETE；安静模式运行约 7 分钟后被停止以获得逐项进度，随后以上一行命令完整通过同一 248 项测试集 |
| `ruff check .`（`backend/`） | PASS |
| `npm ci`（`frontend/`） | PASS，安装 381 个包；esbuild 安装脚本受 npm allowScripts 限制，类型检查与构建仍通过 |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm run test` | PASS，13 个文件、67 个测试 |
| `npm run build` | PASS；Vite 提示一个压缩后约 621 kB 的 JS chunk |
| `npx playwright test` | PASS，2 项浏览器测试 |
| `docker compose config --quiet` | PASS |
| Docker 镜像构建 | NOT_RUN；Docker Desktop daemon 未运行，当前无法连接容器引擎 |

Playwright 使用隔离 SQLite 和确定性 Stub，覆盖登录、项目与调查、Loop 列表/详情、证据变化、策略评价限制、报告 JSON/PDF 导出、移除成员后的访问拒绝、跨用户/跨项目拒绝及登出。Stub 结果不是 AgentGuard Live 或真实模型实验。

后端全量测试包含空库初始迁移、从 0004 升级且保留数据、ORM/数据库唯一约束一致性，以及 Loop 身份登记和创建恢复用例；均通过。

## 结论

J8 固定版 D7 的 API、权限拒绝和应用隔离已有可复核证据。D7 本身不包含 Loop 与持久化策略评价 API；隔离服务也没有真实调查、Loop 或评价记录。真实记录 Live 验收和 AgentGuard I CI 验收均为 **NOT_RUN**，因此不能宣称完整真实联调通过，也不能升级正式 pin。
