# 已知限制（KNOWN_LIMITATIONS）

> 候选发布版（2026-10-24）。本文件是诚实清单：每一条都说明影响、原因与解除条件。
> 应用层阻塞的权威清单：`docs/api/INTEGRATION_BLOCKERS.md`。

## 上游能力阻塞（应用层无法解除）

| ID | 限制 | 影响 | 解除条件 |
| --- | --- | --- | --- |
| QWB-INT-002 | 防御执行器未验证 | 执行按钮恒不可用；只展示候选/审批条件 | AgentGuard 提供支持执行与真实验证的公共接口 |
| QWB-INT-008 | defense preview 在 AgentGuard 1.0.0rc1 + WARDEN 0.2.0 组合下上游 500 TypeError | Live 防御候选不可展示（透传真实错误码，不伪造候选） | 上游修复 |
| QWB-INT-009 | 完整调查闭环需上游注入威胁合同/模型运行时 | 真实调查停在 preflight blocked（诚实语义） | 隔离环境注入后重测 |
| — | readiness / investigations options / investigations timeline / reports 列表端点未发布 | 对应 UI 使用降级语义（UNSUPPORTED/derived 时间线） | 上游 C3+ 发布（readiness 开发中） |
| — | 实验索引当前条目 metrics_available=false | 对比门控拒绝计算，无提升率可展示 | 上游产出含指标的实验 |

## 应用层已知限制

| 限制 | 说明 | 计划 |
| --- | --- | --- |
| 登录限速为单副本进程内 | 多副本部署需共享存储（Redis/DB）限速 | 生产多副本前迁移 |
| 前端大图谱帧率未自动测 | React Flow 100/500/1000 节点交互帧率需人工记录；工作区已限初始节点 ≤24 | 浏览器性能专项 |
| Docker 镜像本机未构建 | 本机 daemon 故障；CI docker job 承担 | 环境恢复后复测 |
| 项目删除未提供 | 只有归档（保留审计与引用完整性） | 按需评估 |
| Recorded 数据集规模小 | 演示级夹具（带 SHA-256 溯源） | 补充真实脱敏录制 |
| 经验中心无 Thompson Sampling | 按 B6 决策仅展示已验证经验，不重造底层 | 随上游经验 API 演进 |
| 关键词搜索为客户端过滤 | 上游未发布服务端搜索端点 | 端点发布后切换 |

## 明确不做（边界声明）

不重造 AgentGuard ExperienceBandit、不实现 WARDEN Probe/SAE/Activation Hook、
不创建另一个因果审计框架、不访问 FRACTAL-Bench 隐藏真值、不在应用层执行未授权
防御操作、合成数据绝不伪装真实实验结果。
