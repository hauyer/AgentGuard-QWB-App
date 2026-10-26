# AgentGuard-QWB-App J2.1–J8 最终验收

**日期：** 2026-10-26
**应用分支：** `feature/b25-b33-real-integration`
**本轮起点：** `d1cce0be70222488f3c7d1f0d1d90f338dd6f4b6`

## 固定 AgentGuard I 合同

本轮将应用正式 pin 从 D7 升到经过上游 CI 验收的 I 阶段：`cd3e9f3f26504f74f347656e97913f55c5db8b4a`（`feature/i-reliability-and-live-validation`，版本 `1.1.0rc1`）。该分支的 API 源码快照为 `66dae883fb75cf90ef735b94d2f5c9b565ba5ad3`；后续 pin 提交只更新交接文档。

GitHub Actions 的 [AgentGuard CI run 40209003277](https://github.com/hauyer/AgentGuard/actions/runs/40209003277) 在该固定分支 HEAD 上通过，Python 3.11、3.12、3.13 三个测试任务均成功。上游 OpenAPI 快照共 84 条路径；文件 SHA-256 为 `b7c4e197ffa53531308102bddc40dda5a31bda8be81b816ecb8ddfa19e40b211`，本仓库校验的 canonical JSON SHA-256 为 `e2d6d9bd7cf94441fa508b34af922b8da7cf724778ff62d10b728367a93c3c9f`。快照保存在 `integration-data/agentguard-openapi-cd3e9f3.json`，CI 离线检查通过。

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

应用修改仅限 `AgentGuard-QWB-App`。邻接 AgentGuard 仓库保持只读。所有本地检查完成后按工程可靠性、Loop 创建与恢复、调查导航、界面精修和发布记录分组提交；本轮不会推送远程。
