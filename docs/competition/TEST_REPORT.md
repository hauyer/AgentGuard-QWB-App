# 测试报告（TEST_REPORT，候选发布版）

日期：2026-10-24。分支：`feature/b11-b17-application-upgrade`。
详细分阶段报告：`docs/development/B11_TEST_REPORT.md`、`B16_PERF.md`。

## 执行摘要

| 套件 | 结果 | 备注 |
| --- | --- | --- |
| 后端 pytest | **173 passed / 0 failed** | 含安全回归 59 项（B8 6 + B9 34 + B12 14 + B16 5） |
| Ruff | 0 违规 | E/F/W/I/UP/B/SIM/ASYNC/S 规则集 |
| 前端 vitest | **53 passed** | 9 文件 |
| 前端 typecheck/lint/build | 全绿 | build 7.3s |
| Playwright E2E | 1 passed | 真实前端 + 真实 BFF + 真实 AgentGuard |
| 数据库迁移 | upgrade/downgrade/re-upgrade 全 rc=0 | SQLite + PostgreSQL 配置就绪 |
| Docker | compose 配置校验通过（dev + prod fail-closed）；镜像构建由 CI runner 承担 | 本机 Docker daemon 故障如实记录 |
| 真实联调 | 12 PASS / 0 FAIL / 2 BLOCKED_UPSTREAM / 1 UNSUPPORTED | 严格五分类判定 |
| 性能 | Dashboard p50 18.5 ms；列表 p50 15.4 ms；PDF p50 21.7 ms；1000 节点图谱转换 2.2 ms | 实测数据，非人工填写 |

## 安全回归覆盖（节选）

- fail-closed 配置矩阵（无密钥拒启、production 四项强制）
- Demo 账号环境隔离（production 恒拒绝）
- 数据库用户 PBKDF2 + 停用即时吊销 + 数据库故障 fail closed
- 项目越权（非成员 404）、移出/停用即失效、归档写阻断
- 登录限速（10/5min）+ 登录审计（不记录密码内容）
- CSRF 双提交、会话过期、CORS 通配拒绝、上游 URL 注入拒绝
- 代理劫持阻断（trust_env=False）、PDF XML 转义、导出文件名清洗
- 并发竞态（UNIQUE 兜底转 409）、审计持久化与重启恢复

## CI

GitHub Actions 七任务：backend / migrations / frontend / e2e / contract-check /
live-smoke（可选，需 `AGENTGUARD_LIVE_BASE_URL` 变量，SKIP 显式展示）/ docker。

## 未通过/未覆盖项（诚实清单）

- Docker 镜像本机构建：daemon 故障，待 CI/环境恢复后复测。
- 前端 React Flow 大图谱交互帧率：需浏览器人工记录（工作区已限初始节点 ≤24）。
- 多副本部署登录限速共享存储：未实现（单副本进程内限速），已登记 KNOWN_LIMITATIONS。
