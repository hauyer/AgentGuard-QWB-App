# 项目研究执行

浏览器仅访问 BFF。新增项目级 Study runs 提交、列表与结果查询均先校验本地 Study 归属，
提交同时校验项目 analyst 权限和既有 CSRF/角色规则。上游错误保持显式错误。
模型、协议、路径、凭据和研究执行都不进入浏览器。

研究详情增加真实任务面板，展示状态、ID、UTC 更新时间、来源、哈希校验与公共摘要；
从服务端恢复持久任务列表，幂等提交键在浏览器刷新后保留。缺少配对结果明确显示 incomplete。
响应式布局修复卡片和嵌套网格的最小宽度，保留真实浏览器溢出断言。

后端固定经过验证的 FastAPI 0.115.6 / Starlette 0.41.3 / HTTPX 0.28.1 / AnyIO 4.8.0；
保留 warnings=error 并删除两条旧弃用忽略规则。没有新增数据库迁移，现有 0001→0009
在本次新建 SQLite 数据库上完整执行。

contracts/agentguard-version.json 保留历史 API 基线来源，并标明本地 additive working-tree
扩展。原有操作未删除；新增接口、完整快照、文件与规范 JSON 哈希同步更新。

scripts/three_repo_smoke.py 通过真实 BFF HTTP 创建 Study、提交并等待独立 Worker，
只在公共摘要核验成功后保存结果；不加载模型、不注入 Stub。

本次验收状态、命令和已知限制见 THREE_REPO_E2E_ACCEPTANCE.md。
