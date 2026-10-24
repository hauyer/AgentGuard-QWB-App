# B11 基线（BASELINE）

日期：2026-10-24。分支：`feature/b11-b17-application-upgrade`（自
`feature/b9-b10-security-integration` @ `cb9630b46a68a179cea253b3caeb8574db3811da` 创建）。

## 起点状态

- B9 生产安全加固与 B10 真实联调已合入开发分支并通过本地验收
  （pytest 140 / ruff 0 / 前端四项 / Playwright / 真实服务联调）。
- 工作区在分支创建时干净，无未提交的用户修改。

## 本轮固定版本

| 组件 | 固定值 |
| --- | --- |
| AgentGuard 分支 | `feature/qwb-public-api-integration` |
| AgentGuard commit | `907aa1971bd4aff3b481a51b8ae19ee04eb82db4`（C2：Add read-only experiment index and comparison API） |
| 上一 pin | `7d42809172059b1f38200bd8308c73345efd77dc`（A8，B10 所用） |
| OpenAPI | 72 条路径，canonical SHA-256 `a40d20c7...44f0b22`，快照 `integration-data/agentguard-openapi-907aa19.json` |

上游在 B10 之后新增三个已提交的公共接口能力（C0 对齐审计、C1 消息级交互图谱、
C2 只读实验索引与对比），B11 已验证并登记（见 `B11_API_STATUS.md`）。
本地 AgentGuard 克隆中另有未提交的 SystemReadiness 开发（只读，不纳入 pin，
登记于候选清单 `in_progress_upstream`）。

## B11 验证矩阵（全部真实执行）

| 验证项 | 结果 | 证据 |
| --- | --- | --- |
| 后端 pytest | 140 passed, 0 failed | `backend`（执行日志见 TEST_REPORT） |
| Ruff | All checks passed | `ruff check .` |
| 前端 typecheck / lint / vitest / build | 全部通过（vitest 51 passed, build 7.31s） | `frontend/*-b11.log` |
| Playwright E2E（真实前端+真实 BFF+真实 AgentGuard） | 1 passed | `docs/development/playwright-b11.log` |
| Alembic 迁移链（新库 upgrade→downgrade→re-upgrade） | rc=0，9 张业务表齐，users 含 `password_hash`/`is_active` | `scripts/verify_migrations.py` → `docs/development/migration-check.log` |
| BFF 启动自动迁移 | 0001→0002 自动执行（服务日志） | `docs/development/bff-functional-b11.log` |
| 正式数据库用户登录 / 角色门控 / 审计持久化 | 10 项功能检查全 PASS | `scripts/functional_auth_check.py` → `docs/development/b11-functional.log` |
| 真实 AgentGuard 合同检查 | PASS：16 个固定端点全部存在于 live OpenAPI | `scripts/check_agentguard_contract.py` |
| 真实联调（严格判定） | 12 PASS / 0 FAIL / 2 BLOCKED_UPSTREAM / 1 UNSUPPORTED | `scripts/live_agentguard_check.py` → `docs/development/b11-live-check.log` + JSON |
| Docker Compose 配置 | dev VALID；prod overlay 带必填变量 VALID、缺变量 fail-closed | `docs/development/compose-check-b11.log` |
| Docker image 构建 | CI 已配置（GitHub Actions ubuntu runner）；本机 Docker daemon 无法启动，已如实登记 | `docs/development/B11_TEST_REPORT.md` |

## B11 修正项

1. `scripts/live_agentguard_check.py` 判定语义重写为五分类
   （PASS / FAIL / SKIP_NOT_CONFIGURED / BLOCKED_UPSTREAM / UNSUPPORTED），
   每项验证必填字段与来源语义；阻塞项必须以真实响应为证据（如
   WARDEN_NOT_CONFIGURED、上游 500 INTERNAL_SERVER_ERROR）。
2. `scripts/check_agentguard_contract.py` 修复方法前缀对比 bug
   （OpenAPI 按操作重建 `METHOD /path` 再比对）。
3. CI 新增迁移验证 job 与可选真实烟测 job（`AGENTGUARD_LIVE_BASE_URL` 变量
   存在时才运行，SKIP 显式展示）。

## 遗留问题（进入 B12+）

- Docker 本机 daemon 故障：镜像构建依赖 CI runner 验证。
- AgentGuard 端 QWB-INT-008（defense preview 500 TypeError）与 QWB-INT-009
  （完整调查闭环需上游注入威胁合同/运行时）维持阻塞。
- 未发布的候选接口（readiness、调查 options、时间线、报告列表）保持
  UNSUPPORTED 语义，B13 按能力发现接入。
