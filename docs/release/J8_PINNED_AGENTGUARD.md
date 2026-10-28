# AgentGuard-QWB-App J2.1–J8 最终验收

> 本文后续的“RC2 静态集成更新”覆盖早前记录中的运行时 pin 和 OpenAPI 验收状态；较早章节作为历史记录保留。

**日期：** 2026-10-26
**应用分支：** `feature/b25-b33-real-integration`
**本轮起点：** `d1cce0be70222488f3c7d1f0d1d90f338dd6f4b6`

## 固定 AgentGuard I 合同

应用运行时固定到最新通过上游 CI 的提交 `8a7c154116ca48c80e2dbf5291e1ff70f5dbdd25`（`feature/i-reliability-and-live-validation`，版本 `1.1.0rc1`）。API 合同来源独立固定为源码提交 `66dae883fb75cf90ef735b94d2f5c9b565ba5ad3`；运行时版本与 OpenAPI 来源不混用。

GitHub Actions 的 [AgentGuard CI run 40265747910](https://github.com/hauyer/AgentGuard/actions/runs/40265747910) 在该运行时提交上通过，Python 3.11、3.12、3.13 三个测试任务均成功。对比 `cd3e9f3` 到 `8a7c154` 的完整上游变更后，唯一合同类型文件 `src/agentguard/contracts/investigation_loop.py` 只有说明文字修改，没有 Schema 字段变化；OpenAPI 文件也未出现在提交差异中。直接从两个提交读取 `docs/integration/openapi-1.1.0rc1.json`，字节完全一致：84 条路径、原始文件 SHA-256 `d577e6001883ada17d47f195cafe48c5394e46c5f16f587636eb907a1e1aa78e`，canonical JSON SHA-256 `e2d6d9bd7cf94441fa508b34af922b8da7cf724778ff62d10b728367a93c3c9f`。应用保留该 API 快照，来源仍为 `66dae883fb75cf90ef735b94d2f5c9b565ba5ad3`。

CI 报告中的原始 SHA 差异来自 Windows 换行转换，不是序列化或实际内容变化：Git 提交对象和上游原始文件均为 230,035 字节 LF 文件，SHA 为 `d577e600…`；Windows `core.autocrlf=true` 工作副本将 8,221 个 LF 转为 CRLF，成为 238,256 字节，SHA 为 `b7c4e197…`。canonical JSON 哈希不受换行影响。新增 `.gitattributes` 将固定快照强制为 LF，使不同平台读取到的原始字节保持一致。

最新运行时还加固了 WARDEN 未知状态对账与 Loop 剩余预算/模型调用超时控制；这些是运行时行为变化，不改变 QWB 使用的 OpenAPI Schema 或 84 路径快照。

I7 合同正式包含 Loop 创建/列表/详情/决策/证据变化/预算及策略评价列表/详情。Loop 创建使用必需的 `X-Loop-Idempotency-Key`；同一 key 和请求体重复请求返回已登记 Loop。策略评价读取持久化索引和工件，不启动新实验。上游合同另明确：Loop 列表 `count` 是当前页条数，客户端须按 `next_offset` 翻页；策略评价的 `count` 也为当前页条数，但不含 `next_offset`。

## 应用层实现

- Loop 归属只从服务端已验证的项目调查关系登记；Loop ID 全局唯一，禁止跨项目占用。
- 每个项目/基础调查最多有一个未决提交，数据库部分唯一索引跨进程生效。模糊提交保留锁；普通重复点击不会再次 POST。Operator 显式恢复时只用数据库中保存的原请求体和同一上游幂等 key；仍无法确认时进入人工对账并留下审计记录。
- Loop 对账按 I7 `next_offset` 读完全部页，并拒绝分页游标、计数或身份字段不一致的数据。
- 调查详情展示经归属验证的 Loop；状态、决策、证据变化和预算沿用正式字段。Live 请求失败不会回退到 Synthetic。
- 策略评价页读取 AgentGuard 持久化评价，限制全局研究记录访问并保留空值。报告只组合项目授权的数据；JSON/PDF 使用同一报告对象，保留未知字段、来源和限制，不把防御候选写成已执行结果。
- 导航、标题、颜色与卡片样式已统一，侧栏支持窄屏抽屉；清理了多页冗长说明和误导性的固定项目/Live 状态文案。

## 验收结果

| 检查 | 结果 |
| --- | --- |
| 上游 AgentGuard I CI | PASS；Python 3.11/3.12/3.13 |
| 本仓库 OpenAPI 离线合同校验 | PASS；84 条路径、文件与 canonical SHA、Loop 请求体/必需幂等头、分页及支持端点 |
| 后端全量 Pytest | PASS；260 项中 259 通过、1 项跳过（本机未配置 PostgreSQL） |
| 后端 Ruff | PASS |
| Alembic 空库升级、降级与重升 | PASS；表、用户字段和活动提交锁索引均存在 |
| PostgreSQL 本机并发专项 | NOT_RUN；未配置 `QWB_TEST_POSTGRES_URL` |
| 前端依赖、类型检查、Lint | PASS；`npm ci` 安装 381 个包 |
| 前端单元测试 | PASS；13 个文件、67 项 |
| 前端生产构建 | PASS；Vite 提示单个压缩 JS chunk 超过 500 kB |
| Playwright | PASS；2 项；使用隔离数据库与确定性 Stub，不代表真实模型或 WARDEN 执行 |
| 桌面/移动端视觉检查 | PASS；已复核系统总览和移动导航截图 |
| `docker compose config --quiet` | PASS |
| Docker 镜像构建 | NOT_RUN；本机 Docker Desktop daemon 不可用 |

## 真实联调边界

本轮没有可连接的 AgentGuard HTTP 服务、Operator 凭证或真实基础调查/Loop/评价记录，因此真实业务数据 HTTP Smoke 为 **NOT_RUN**；离线快照、上游 CI 和 Stub 测试没有替代 Live 验收。I 阶段交接文档指出真实 WARDEN Loop 执行仍处于 **BLOCKED**：远端提交的重启恢复与观测证据语义尚未验证。Synthetic 策略评价工件只说明持久化 API 合同可用，不代表真实模型实验。正式 pin 已升级到 I，但本地 QWB-App CI 和 PostgreSQL 服务专项仍需在 CI 环境执行。

## 提交与工作区

应用修改仅限 `AgentGuard-QWB-App`。邻接 AgentGuard 仓库保持只读。J2.1–J8 的实现按工程可靠性、Loop 创建与恢复、调查导航、界面精修和发布记录分组提交。

## 最新 CI 哈希修复与回归

### 文件差异与固定来源

QWB-App CI run [40265680338](https://github.com/hauyer/AgentGuard-QWB-App/actions/runs/40265680338) 的 AgentGuard API contract check 和 Backend lint + tests 失败。原始 OpenAPI 内容没有漂移：应用 Git blob 与 AgentGuard `66dae883fb75cf90ef735b94d2f5c9b565ba5ad3` 中的 OpenAPI 原文件均为 230,035 字节 LF，SHA-256 `d577e6001883ada17d47f195cafe48c5394e46c5f16f587636eb907a1e1aa78e`。Windows `core.autocrlf=true` 曾把工作副本的 8,221 个 LF 转成 CRLF，导致本地计算出 238,256 字节、SHA-256 `b7c4e197ffa53531308102bddc40dda5a31bda8be81b816ecb8ddfa19e40b211`；Linux CI 读取 Git 中的 LF 原始字节，因此原始哈希检查失败。差异确切来自换行转换，不是 JSON 序列化或接口内容。canonical JSON SHA-256 两边相同，仍为 `e2d6d9bd7cf94441fa508b34af922b8da7cf724778ff62d10b728367a93c3c9f`。合同预期值已改为来源原文件哈希，并通过 `.gitattributes` 固定快照为 LF；没有关闭任何哈希检查。

运行时 pin 更新为 AgentGuard `8a7c154116ca48c80e2dbf5291e1ff70f5dbdd25`；API/OpenAPI 来源仍独立记录为 `66dae883fb75cf90ef735b94d2f5c9b565ba5ad3`。上游 [AgentGuard CI run 40265747910](https://github.com/hauyer/AgentGuard/actions/runs/40265747910) 在新运行时提交通过，Python 3.11、3.12、3.13 均成功。逐项检查该运行时提交相对 `cd3e9f3` 的差异后，`src/agentguard/contracts/investigation_loop.py` 仅有说明文本变化，OpenAPI 文件没有变化；从两个提交下载的 OpenAPI 文件字节完全一致。因此继续沿用现有 84 路径快照。运行时新增的 WARDEN 未知状态对账与 Loop 剩余时间/模型超时处理已记录为行为变化，不代表真实 WARDEN Gate 已开放。

### 命令结果

| 命令 | 结果 |
| --- | --- |
| `python scripts/check_agentguard_contract.py --offline-only` | PASS；运行时 pin、原始与 canonical SHA、版本、84 路径、支持端点及关键请求字段通过 |
| `python -m pytest tests/test_contract_snapshot.py` | PASS；4 项 |
| `python -m pytest`（backend） | PASS；259 passed，1 skipped，666.84 秒 |
| `ruff check .`（backend） | PASS；All checks passed |
| `python scripts/verify_migrations.py` | PASS；upgrade/current/downgrade/re-upgrade 均退出码 0，活动提交锁索引存在 |
| `python -m pytest tests/test_postgres_loop_concurrency.py -q` | 本机 1 项 skipped；未设置 `QWB_TEST_POSTGRES_URL`。QWB-App CI run 40265680338 的 PostgreSQL 并发任务通过 |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm run test` | PASS；13 个文件、67 项 |
| `npm run build` | PASS；存在压缩 JS chunk 超过 500 kB 的提示 |
| `npm run e2e` | PASS；2 项 Playwright |
| `docker compose config --quiet` | PASS |
| `docker info` 及 backend/frontend `docker build` | 本机 Docker daemon 不可用，均未能连接 `dockerDesktopLinuxEngine`；QWB-App CI run 40265680338 的 Docker builds 任务通过 |
| `127.0.0.1:8000` AgentGuard 连接检查 | 不可达；真实 HTTP Smoke 为 **NOT_RUN** |

QWB-App run 40265680338 中，SQLite migration、Playwright、前端检查、Docker builds 和 PostgreSQL migration/concurrency 任务通过；合同校验与后端测试因上述原始换行哈希不一致失败，Ruff 检查通过，Live AgentGuard smoke 被跳过。该 CI 记录对应修复前提交；本次修复的验证结果以本节本地命令记录为准。真实服务联调仍为 **NOT_RUN**；WARDEN Live Gate 仍为 **BLOCKED**，未把 Stub 或离线验证描述为真实模型/执行成功。

## RC2 静态集成更新（覆盖本文件早前的 8a7c154 pin）

**核查日期：** 2026-10-26
**运行时 pin：** AgentGuard `63fe1b5662df93fbf06750ecf09c14ee9e6bd5cc`，版本 `1.1.0rc2`，提交主题 `Refresh WARDEN gate implementation snapshot`。
**API 快照来源：** 同一提交 `63fe1b5662df93fbf06750ecf09c14ee9e6bd5cc`。这是 API 来源记录；前一版 API 来源 `66dae883fb75cf90ef735b94d2f5c9b565ba5ad3` 已单独保存在版本合同中。
**上游 CI：** [AgentGuard CI run 40314646080](https://github.com/hauyer/AgentGuard/actions/runs/40314646080)，提交匹配，Python 3.11、3.12、3.13 全部通过。

RC1 快照保留为 84 paths、raw SHA-256 `d577e6001883ada17d47f195cafe48c5394e46c5f16f587636eb907a1e1aa78e`、canonical SHA-256 `e2d6d9bd7cf94441fa508b34af922b8da7cf724778ff62d10b728367a93c3c9f`。RC2 快照为 86 paths、raw SHA-256 `2ce83660a67111a346a2de9772fcaec1938a4a5de713439de34a83e372b9a5e5`、canonical SHA-256 `430a8115f4dfb8c865060d45345a58bf267f60657b1ba8ab1c0faa2ba3acf41c`。静态 diff 新增 `GET /v1/system/identity` 与 `POST /v1/investigation-loops/{loop_id}/reconcile`，没有移除 operation；三个新增 Schema 为 `SystemIdentityResponse`、`InvestigationLoopReconciliationResponse` 和 `ReconciledWorkflowView`。33 个 App-supported operations 的 parameters、requestBody、responses 和 security 未变化。每次离线合同检查会重新验证原始/规范哈希、路径数、operation diff 和这些支持端点的合同。

两个新增 operation 都没有接入 BFF 或 UI。RC2 的 reconcile 在上游文档中为 query-only；没有真实服务响应可验证其运行行为。公开 defense execute、artifact content、Probe train/predict 路由仍不代表 App 已验证这些能力：执行保持 BLOCKED，artifact content 与 Probe/SAE 未暴露。

**验证边界：** 当前环境没有 AgentGuard 服务地址、API/Operator 凭证或 PostgreSQL 测试 URL；真实 HTTP Smoke 为 **NOT_RUN**，WARDEN Live Gate 为 **BLOCKED**。本地 Stub 和离线静态校验不能替代真实服务联调。各阶段的实际命令、通过/失败/跳过数量见下方“本轮验证记录”。

### 本轮验证记录

| 检查 | 结果 |
| --- | --- |
| `python scripts/check_agentguard_contract.py --offline-only` | PASS；RC2 原始/规范化 SHA、版本、86 paths、operation 差异及 33 个已支持端点的请求/响应合同通过 |
| `python -m pytest tests/test_contract_snapshot.py` | PASS；6 passed |
| `python -m pytest`（backend） | PASS；278 passed，1 skipped，743.79 秒 |
| `python -m ruff check app tests`（backend） | PASS；All checks passed |
| `python ../scripts/verify_migrations.py`（backend） | PASS；SQLite upgrade/current/downgrade/re-upgrade 均成功，必需表和活动提交唯一锁存在 |
| `python -m pytest tests/test_postgres_loop_concurrency.py -q` | SKIP；1 项因未配置 `QWB_TEST_POSTGRES_URL` 跳过，未执行 PostgreSQL 并发实测 |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm run test` | PASS；13 个文件、68 项 |
| `npm run build` | PASS；Vite 构建成功，JS bundle 超过 500 kB 提示 |
| `npm run e2e` | PASS；2 项 Playwright，使用确定性 Stub，仅验证应用流程，不构成真实 AgentGuard/WARDEN 验收 |
| `docker compose config --quiet` | PASS |
| `docker compose build` | PASS；前后端镜像构建成功；Docker 内 `npm ci` 报告 11 项依赖审计告警（8 moderate、1 high、2 critical） |
| `git diff --check` | PASS；没有空白错误 |
| AgentGuard HTTP Smoke | **NOT_RUN**；未配置真实服务 URL、API token 或 Operator token |
| 新的 QWB-App GitHub Actions CI | **NOT_RUN**；本轮修改保留在本地，没有推送或触发应用仓库 CI |

已确认的原始哈希问题来自 Windows `core.autocrlf=true`：预期值 `b7c4e197…` 是 8,221 个 LF 被转成 CRLF 后的 238,256 字节工作副本哈希；仓库与固定 RC1 来源文件均为 230,035 字节 LF，原始 SHA `d577e600…`，canonical SHA 一致。合同改为匹配固定原始文件，并以 `.gitattributes` 固定快照换行，没有关闭哈希验证。状态测试也从过时的 `unknown` 预期更新为与 Stub 能力清单一致的 `unsupported`，之后完整后端套件复跑通过。

Docker 首轮构建发现前端 Windows `node_modules` 被复制进 Linux 镜像；新增 `.dockerignore` 后构建上下文降至前端约 2 MB、后端约 0.4 MB，最终镜像构建通过。状态卡片显示 blocker 列表的类型也已改为共享 `LayerStatusSummary`，通过前端类型检查和生产构建。

最终边界：真实 AgentGuard HTTP Smoke 为 **NOT_RUN**，WARDEN Live Gate 仍为 **BLOCKED**。RC2 静态合同、Stub 单测和 Playwright 结果均不代表真实 WARDEN、模型或远端 Loop 执行成功。未推送、未合并、未部署。

## APP 主开发指南与 RC3 静态集成（2026-10-28）

开发指南指定的审计起点已核对为 `feature/b25-b33-real-integration` @ `74627b234a86ef13615e90346e0c8f3a3c86fc7e`；起始工作区干净。基线 QWB-App CI [40336150184](https://github.com/hauyer/AgentGuard-QWB-App/actions/runs/40336150184) 通过。页面、BFF、客户端、项目/RBAC、审计、证据与报告复用审计见 [`docs/research/UI_REUSE_AUDIT.md`](../research/UI_REUSE_AUDIT.md)。

当前固定 AgentGuard runtime 为 `9a8ee1f5e78a0b254c17ea66ac5b140aa7e1e89a`（1.1.0rc3）；OpenAPI 来源独立记录同一代码提交。此提交 [AgentGuard CI 40336215846](https://github.com/hauyer/AgentGuard/actions/runs/40336215846) 的 Python 3.11/3.12/3.13 工作均成功。rc2→rc3 OpenAPI 差异只有 `info.version`，共 86 paths / 98 operations；应用支持的 33 operations 保持原合同。快照 raw SHA-256 为 `fadab4d701d23fabda785413cf0c4536fcffec521ea09cbe6ad73a417c15de1e`，按 AgentGuard identity 算法计算的 canonical SHA-256 为 `52ad0d5dc175e58759196588d1c4ab5b45e82751f882c82ed8540cb963d942f6`。RC1、RC2 快照均保留，离线 checker 会要求 RC3 除版本字段外与 RC2 完全一致。

本轮也将 canonical hash 算法统一为 AgentGuard identity 算法。历史 J8/RC2 记录中的 `e2d6d9…`（RC1）与 `430a8115…`（RC2）是旧 App 序列化器的 digest；当前算法对相同的原始文件分别得到 `cf6967dc…` 和 `d0a04af3…`。原始 OpenAPI 文件字节和 raw SHA 未变化，差别只来自 canonical 序列化规则。

RC3 OpenAPI 确实发布 `POST/GET /v1/studies`、Study detail/integrity/analysis 和 run-scoped paired/intervention 路由；这些自 RC2 起已存在，未纳入 App 的 33-operation 支持合同。上游 Study preregistration 未提供项目归属或 POST 幂等键；analysis 使用 caller-supplied outcome arrays，其 artifact refs/hashes 不是独立来源证明。paired/intervention 操作依赖 run/design/action，真实 backend 缺少 validated `paired_executor` 时返回 `PAIRED_REPLAY_UNAVAILABLE`，且 AgentGuard production API factory 不接受 direct executor。为避免跨项目泄露和模糊 POST 重复，应用继续将这些能力标为 **STATIC_ONLY/BLOCKED**，没有添加 BFF 写路由或 Study 数据库。ExperimentsPage 展示这一门控，不生成假 Arm/指标。

本轮新增/调整的实际检查结果见 [`docs/research/APP_GATE_5.md`](../research/APP_GATE_5.md)：后端全量测试 281 passed、1 skipped；前端类型检查、Lint、69 项单测、生产构建及 2 项 Playwright 均通过；迁移验证和 Docker Compose 配置检查通过。PostgreSQL 并发专项因没有 `QWB_TEST_POSTGRES_URL` 跳过；Docker 镜像构建因本机 Docker Desktop Linux engine pipe 不可用而未能启动。`git diff --check` 和离线合同验证通过。本机没有真实服务凭证，Live HTTP Smoke、identity/readiness 和 AgentGuard→WARDEN 全栈执行为 **NOT_RUN**；WARDEN Live Gate 为 **BLOCKED**。本次只改 App，不推送、合并或部署。
