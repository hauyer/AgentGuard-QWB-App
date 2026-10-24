# B11 接口状态（API STATUS）

日期：2026-10-24。Pinned：AgentGuard `907aa19`（`feature/qwb-public-api-integration`，1.0.0rc1）。
判定来源：pinned commit 的 live `/openapi.json`（72 条路径，
SHA-256 canonical `a40d20c7...44f0b22`）+ 真实服务逐项调用。

## BFF 固定消费端点（16，全部经真实服务验证）

| 端点 | 方法 | 实测 | 状态 |
| --- | --- | --- | --- |
| `/v1/system/health` | GET | 200 ok, X-Request-ID 回显 | PASS |
| `/v1/system/capabilities` | GET | 200, provider=mock, backend_mode=synthetic | PASS |
| `/v1/kernel/status` | GET | 200, warden=available（独立层） | PASS |
| `/v1/scenarios` | GET | 200, items≥1 | PASS |
| `/v1/investigations` | POST | 200, workflow_id 回显，preflight=blocked（诚实语义） | PASS |
| `/v1/investigations` | GET | 200, count/offset/limit/next_offset | PASS |
| `/v1/investigations/{id}` | GET | 200, request_id 匹配 | PASS |
| `/v1/investigations/{id}/interaction-graph` | GET | **200（C1 新发布）** | PASS |
| `/v1/evidence/investigations/{id}` | GET | 200, items/limitations/run_status | PASS |
| `/v1/defense-policies/{id}` | GET | 500 INTERNAL_SERVER_ERROR（上游 TypeError） | **BLOCKED_UPSTREAM (QWB-INT-008)** |
| `/v1/defense-policies/{id}/preview` | POST | 同上 | **BLOCKED_UPSTREAM (QWB-INT-008)** |
| `/v1/reports/{run_id}` | GET | 工作流无 run_id（preflight blocked），报告未读取 | **BLOCKED_UPSTREAM**（不可计 PASS） |
| `/v1/experiences` | GET | 200, items=[]（真实空集，非伪造） | PASS |
| `/v1/experiments` | GET | 已发布（C2），BFF 接入在 B13 | PUBLISHED |
| `/v1/experiments/{experiment_id}` | GET | 已发布（C2），BFF 接入在 B13 | PUBLISHED |
| `/v1/system/audit-events` | GET | 403（无 operator token，fail-closed） | PASS |

## B13 候选接口清单（按 pinned OpenAPI 验证）

| 候选路径 | 发布状态 | 说明 |
| --- | --- | --- |
| `GET /v1/investigations/{request_id}/interaction-graph` | ✅ 已发布（C1） | 消息级交互图谱；BFF 适配于 B13 |
| `GET /v1/experiments` | ✅ 已发布（C2） | 只读实验索引；BFF 适配于 B13 |
| `GET /v1/experiments/{experiment_id}` | ✅ 已发布（C2） | 实验详情 |
| `POST /v1/experiments/compare` | ✅ 已发布（C2） | 受控实验对比（可替代应用层 503 EXPERIMENTS_UNAVAILABLE） |
| `GET /v1/system/readiness` | ❌ 未发布 | 上游 SystemReadiness 开发中（本地克隆有未提交文件，未接线路由） |
| `GET /v1/investigations/options` | ❌ 未发布 | 调查表单选项能力不存在 |
| `GET /v1/investigations/{request_id}/timeline` | ❌ 未发布（注意：`GET /v1/runs/{run_id}/timeline` 存在） | 应用时间线继续用 `_derive_timeline` 降级并显式标记 |
| `GET /v1/reports` | ❌ 未发布（仅单报告 `GET /v1/reports/{run_id}`） | 报告列表维持不可用语义 |

## 能力判定原则（B13 起生效）

按能力而非连接状态判定：AgentGuard 在线 ≠ WARDEN 可执行 ≠ 模型运行时可用
≠ 因果干预受支持 ≠ 调查 completed 产生完整图谱。每个业务能力以五态记录：
`available / partial / blocked / unsupported / unavailable`（机器可读状态见
`b11-live-check.json`；应用层状态汇总由 BFF 能力发现端点在 B13 提供）。

## 阻塞清单增量

- QWB-INT-008（defense preview 上游 500 TypeError）：维持，证据为真实响应。
- QWB-INT-009（完整调查闭环需上游注入威胁合同/模型运行时）：维持；
  preflight blocked 为上游诚实语义，应用不伪装"运行完成"。
- B10 报告的 interaction-graph 缺阻塞（QWB-INT-001 的 Live 部分）**随 C1 发布解除
  Live 数据源**，B13 完成适配后更新阻塞清单。
