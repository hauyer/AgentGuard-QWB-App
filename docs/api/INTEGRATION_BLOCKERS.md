# 集成阻塞清单（INTEGRATION_BLOCKERS）

日期：2026-10-23。基线：AgentGuard `00d12bee352060ea6014eebea8400edd7c74a029`。
WARDEN / FRACTAL-Bench / StegoPot 只读。本文件登记**应用层**依赖的缺失能力与
处理策略；底层阻塞的权威来源是 AgentGuard `docs/DEPENDENCY_BLOCKERS.md`。

| ID | 缺失能力 | 影响的应用功能 | 应用层行为 | 解除条件 |
| --- | --- | --- | --- | --- |
| QWB-INT-001 | 公共 API 不提供消息级交互图谱（Agent→Agent/Tool 消息边） | B4 交互图谱 | Live 模式显示能力不可用；Demo 模式使用固定标注样本；登记缺失合同 | AgentGuard 公共接口提供治理后的交互摘要 |
| QWB-INT-002 | 外部防御执行器未验证；`/v1/defense-policies/{id}/execute` unsupported | B5 防御执行 | 只展示候选/审批条件/状态；执行按钮不开放；前端不模拟执行成功 | AgentGuard 提供支持执行、权限模型与真实验证的公共接口 |
| QWB-INT-003 | WARDEN 工件无已核实的受控下载/完整性 API；证据带 ArtifactRef | B5 证据分析 | 不打开 file URI；完整性保持 unverified；只展示引用 | AgentGuard Evidence Gateway 提供下载与校验 |
| QWB-INT-004 | WARDEN 默认运行在进程内，无重启恢复；公开 API 无取消/回滚路由 | B3 调查状态 | 远端丢失保持 unknown/unavailable；不重跑冒充恢复；取消标 unsupported | WARDEN 公共 API 提供恢复/取消 |
| QWB-INT-005 | WARDEN 0.3.0 新增白盒 CLI/Probe Suite，但 REST 无等价 Probe/SAE/白盒模型/配对重放接口 | B3 调查创建（Probe/SAE 字段） | 表单仅在能力清单支持时启用；不伪装 WARDEN 代理 | 受支持的 WARDEN 公共接口 |
| QWB-INT-006 | 无真实因果验证结果（历史观察 6/8 完成、2 失败） | B6 实验对比 | 无数据不生成趋势图；观察结果不标成因果确认 | 真实实验与验证完成 |
| QWB-INT-007 | 模型运行时状态无公开查询接口 | 系统总览 | 不因 AgentGuard health 通过就标记模型运行时可用 | 相应公共接口 |

## 应用层遵守的边界

- 不直接调用 WARDEN 内部模块/API；不绕过公共接口读内部数据库。
- 不实现 Probe/SAE/Activation Hook/EAP/底层因果干预。
- 合成数据绝不伪装为真实实验结果；Demo 数据不进入经验奖励库。
- 无审批权限不执行防御操作；凭证只存在于服务端。
