# 架构总览

```
用户 / 安全研究人员 / 比赛评委
        │
        ▼
┌──────────────────────────────┐
│  AgentGuard-QWB-App          │  ← 本仓库（独立 Git 仓库）
│  React Web Console (frontend)│
│  BFF: 会话/权限/业务/审计     │  ← FastAPI (backend)
└──────────────┬───────────────┘
               │ REST API / SDK（仅通过 BFF 连接器）
               ▼
          AgentGuard            上层调查与安全决策平台（只读，不修改）
               │ WARDEN REST API
               ▼
             WARDEN             底层因果审计内核（只读，不直接访问）
```

## 分层职责

- **frontend（React + TS + Vite）**：界面、导航、状态展示。只与 BFF 的 `/api`
  通信；不接触 AgentGuard；不持有任何上游凭证。
- **backend（FastAPI BFF）**：系统状态聚合、业务数据、服务端凭证、AgentGuard
  REST 调用、响应转换、操作审计、报告组织。BFF 是唯一上游访问点；
  不重新实现 AgentGuard 的调查/证据门控/经验学习/策略算法。
- **AgentGuard / WARDEN / FRACTAL-Bench / StegoPot**：全部只读。应用层只通过
  AgentGuard 公共 API 集成，不直接调用底层仓库。

## 关键决策（B0）

1. **上游地址服务端固定**：`AGENTGUARD_BASE_URL` 在启动时校验（http/https、
   无凭证/路径/查询/片段），前端无法指定任意上游（防 SSRF）。
2. **凭证只存服务端**：浏览器只接收应用会话；AgentGuard Token 永不进前端。
3. **诚实状态**：AgentGuard health 通过不代表 WARDEN/模型运行时可用；每层独立
   探测；无法取得数据时返回显式 unavailable，不虚构数值。
4. **数据模式**：LIVE / RECORDED / SYNTHETIC / UNAVAILABLE 四种，由 BFF 统一裁决。
5. **客户端安全规则**：不自动重试写请求；幂等 GET 受控重试；拒绝重定向；
   限制响应 4 MiB；统一错误映射（code + request_id）；不记录敏感请求正文。
6. **接口变更隔离**：上游路径集中在 `app/integrations/agentguard_client.py`，
   变更只改适配层 + 合同测试，应用业务 API 保持稳定。

## 依赖方向

应用层只能依赖 `agentguard_client` 访问 AgentGuard；业务服务（services）依赖
连接器；API 路由依赖服务；前端依赖 BFF 路由。
