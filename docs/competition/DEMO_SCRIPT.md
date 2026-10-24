# 演示脚本（DEMO_SCRIPT）

总时长约 12 分钟。主线：**评委可以看到"为什么认为有风险，以及证据支持到什么程度"**。

## 准备（演出前 10 分钟）

```powershell
# 终端 1：WARDEN 内核
cd WARDEN && python -m uvicorn warden.interface.api.app:create_app --factory --host 127.0.0.1 --port 8003
# 终端 2：AgentGuard（pinned 907aa19）
cd AgentGuard && set AGENTGUARD_WARDEN_URL=http://127.0.0.1:8003 && .venv\Scripts\python -m uvicorn agentguard.api.app:app --host 127.0.0.1 --port 8000
# 终端 3：BFF + 前端
cd AgentGuard-QWB-App\backend && set AGENTGUARD_BASE_URL=http://127.0.0.1:8000 && .venv\Scripts\python -m uvicorn app.main:app --port 8001
cd ..\frontend && npm run dev
```

## 第一幕：系统总览与逐层健康（1.5 分钟）

1. 打开 `/` 系统总览。指出三行独立状态：AgentGuard 已连接、WARDEN available、
   模型运行时**不可用**（独立探测，不因 AgentGuard 在线而全绿）。
2. 强调"未知值不置 0"：没有数据的指标显示未知，不显示假的 0。

## 第二幕：三模式治理（1.5 分钟）

3. `/demo` 演示导览：Live/Recorded/Synthetic 三入口；打开任一夹具展示
   fixture_id 与 SHA-256 来源标注；"Demo 提交只记录不假装运行"。

## 第三幕：创建真实调查（2 分钟）

4. `/investigations/new`：选择场景与审计模式，提交。
5. 打开返回的 request_id → 工作区。状态显示真实 preflight blocked；
   时间线标注"状态推导"；页面明确显示阻塞原因
   （THREAT_CONTRACT_NOT_AVAILABLE：上游未注入威胁合同——诚实语义）。
6. 讲解幂等保障：超时后只读对账，永不盲目重提。

## 第四幕：调查工作台与证据链（3 分钟）

7. 演示数据下的完整工作区：时间线（若上游有 run 则显示"来自 AgentGuard
   持久化事件"）、内嵌图谱（候选路径标注"线索非因果"）。
8. 候选风险发现 → 点击 finding → **证据 IDs → 证据页深链**；
   证据等级徽标（synthetic/observational/…）与验证状态。
9. 定向防御页：候选/审批条件/预计成本；**执行按钮不可用**
   （执行器缺失，QWB-INT-002——如实讲解）。

## 第五幕：实验对比与报告（2 分钟）

10. `/experiments`：C2 真实索引；尝试对比 → 系统展示不可比原因
    （metrics_available=false）而非伪造提升率。
11. 报告中心：导出 JSON + PDF；打开 PDF 指出"仅排版字段、不改指标、
    不推断新因果结论"的页脚声明。

## 第六幕：工程与安全底座（2 分钟）

12. `/settings`：角色模型与安全边界；说明 fail-closed（无密钥拒启）、
    登录限速、审计持久化。
13. 收尾：`docs/competition/KNOWN_LIMITATIONS.md`——主动讲清什么没做成。

## 备选降级

- 若现场无 AgentGuard：系统总览进入 unavailable 模式（本身即是演示点：
  应用不伪装），Demo 模式全流程可讲。
- 若评委追问图谱细节：完整图谱页（React Flow）节点抽屉展示
  message_id/evidence_refs 溯源。
