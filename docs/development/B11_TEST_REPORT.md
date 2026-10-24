# B11 测试报告（TEST_REPORT）

日期：2026-10-24。分支：`feature/b11-b17-application-upgrade`。
环境：Windows 10.0.26200 x64，Python 3.13.16（backend venv）、Node 22（frontend）、
真实服务栈：AgentGuard 1.0.0rc1 @ `907aa19`（127.0.0.1:8000）+ WARDEN 0.2.0（127.0.0.1:8003）。

## 1. 后端

```
backend > python -m pytest -q
  → 140 passed, 0 failed（B8 106 + B9 安全回归 34）
backend > ruff check .
  → All checks passed!
```

覆盖重点（全部自动化断言，非人工检查）：
- fail-closed 配置矩阵（无密钥拒启、production 四项强制、无效 APP_ENV）
- Demo 账号环境隔离（production 恒拒绝、显式覆盖无效、开发可关闭）
- 数据库用户 PBKDF2 登录、停用即时吊销会话、数据库故障 fail closed
- 审计持久化（跨服务实例重启可查、分页、actor/action 过滤、persisted 标志）
- 代理不可劫持（HTTP_PROXY 指向死端口时上游连接仍成功）
- PDF 上游字段转义（恶意标记原样呈现、渲染不崩溃）
- 会话过期、CSRF Cookie 周期、调查超时预算、三态对账、模式严格分离

## 2. 数据库迁移

```
python scripts/verify_migrations.py
  alembic upgrade head → current → downgrade 0001 → downgrade base → upgrade head
  全部 rc=0
tables: alembic_version, users, projects, project_members, investigation_bookmarks,
        report_exports, demo_scenarios, ui_preferences, app_audit_events
users columns: 含 password_hash, is_active
```

另验证 BFF 启动自动迁移（功能 BFF 以 SQLite DATABASE_URL 启动时日志出现
`Running upgrade -> 0001` / `0001 -> 0002` / `database schema upgraded to head`）。

## 3. 功能验证（真实运行 BFF，10/10 PASS）

`scripts/functional_auth_check.py` 对端口 8021 的真实 BFF 执行：

```
[PASS] manage_users_create_analyst / _operator（PBKDF2 哈希入库）
[PASS] db_user_login（source=database）
[PASS] authenticated_me（会话 Cookie 生效）
[PASS] wrong_password_rejected（401）
[PASS] system_settings_with_auth（auth_enabled=True, audit_persisted=True）
[PASS] analyst_denied_audit（403 PERMISSION_DENIED，真实角色门控）
[PASS] operator_login / operator_reads_persisted_audit（persisted=True）
```

## 4. 前端

```
npm ci                         → 成功（需先清理被残留进程占用的 esbuild/rollup 文件）
npm run typecheck              → 通过
npm run lint                   → 通过
npm run test -- --run          → 8 files, 51 passed
npm run build                  → 成功（7.31s；chunk 体积警告为既有已知项）
npx playwright test            → 1 passed（真实前端 + 真实 BFF + 真实 AgentGuard）
```

## 5. 真实 AgentGuard 合同与联调

```
python scripts/check_agentguard_contract.py
  → PASS: all 16 pinned endpoints present in live OpenAPI; health ok.
    (pinned: 907aa19 @ feature/qwb-public-api-integration)

python scripts/live_agentguard_check.py --json-out docs/development/b11-live-check.json
  → 12 PASS, 0 FAIL, 2 BLOCKED_UPSTREAM, 1 UNSUPPORTED

  PASS               system_health / capabilities / warden_kernel_status(available) /
                     scenarios / create_investigation(200, preflight=blocked) /
                     truth_guard_metadata_rejection(422) / investigation_idempotency
                     (stored_occurrences=1) / investigation_detail / evidence_read /
                     interaction_graph(HTTP 200, C1 新接口) / experiences_search /
                     system_audit_events_auth(403 fail-closed)
  BLOCKED_UPSTREAM   report_read（工作流 preflight 阻塞无 run_id，报告未读取，
                     不计入 PASS——修复了旧脚本把无 run_id 计为通过的问题）；
                     defense_policies（HTTP 500 INTERNAL_SERVER_ERROR，
                     QWB-INT-008 上游 TypeError，证据为真实响应）
  UNSUPPORTED        investigation_timeline（GET /v1/investigations/{id}/timeline
                     未在 pinned commit 的 OpenAPI 发布；上游存在 GET
                     /v1/runs/{run_id}/timeline 供 B13 评估）
```

## 6. Docker 与 CI

- `docker compose config`（dev）：VALID。
- prod overlay：带必填变量 VALID；缺变量时 fail-closed（预期拒绝）。
  日志：`docs/development/compose-check-b11.log`。
- Docker image 构建：**本机 Docker Desktop daemon 无法启动**
  （`Docker Desktop is unable to start`，已尝试启动并等待 3 分钟以上），
  构建验收由 CI 的 `docker` job（ubuntu runner）承担；本机限制如实记录，
  未伪造构建结果。

## 7. 结论

B11 全部可执行测试通过；真实联调项的 PASS / BLOCKED / SKIP / UNSUPPORTED
语义准确并附机器可读报告。基线就绪，可进入 B12。
