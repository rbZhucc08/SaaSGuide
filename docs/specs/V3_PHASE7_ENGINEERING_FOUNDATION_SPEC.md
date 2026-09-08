# V3 阶段 7：工程结构与自动化规格

日期：2026-09-09

## 目标

在不重写业务链的前提下，建立可逐步拆分的 Flask 路由结构、统一检查入口、精确依赖、关键模块覆盖率、类型注解契约、结构化请求标识和 Windows/Linux CI 定义。

## 实现范围

- `routes/v3_operations.py` 使用 Blueprint 承载独立评测与模型能力只读端点；
- 保留原 API 路径和 `saasguide-v2-orchestrator` 稳定标识，另加 `runtime_version=v3`；
- `scripts/run_checks.py` 成为跨平台检查入口，PowerShell 只负责定位项目虚拟环境；
- `requirements.txt` 精确锁定当前四个运行依赖；
- GitHub Actions 定义 Windows/Ubuntu × Python 3.11/3.12 四格矩阵；
- 每个响应加入随机 `X-Request-ID`；HTTP 错误 JSONL 增加事件、请求 ID、状态和耗时；
- 使用 Python 标准库 `trace` 对四个关键模块建立 60% 聚合语句覆盖率门槛；
- 对四个 V3 关键模块的公开函数执行类型注解完整性审计；
- 增加 Blueprint、请求 ID、依赖、CI 和只读端到端 API 测试。

## 迁移与兼容

阶段 3 已完成 SQLite Schema v1→v2 备份迁移并保留测试。本阶段不新增数据库 Schema。前端 API、关键 DOM ID、人工闸门和报告链路保持不变。

## 非目标与证据边界

- Blueprint 只拆出 V3 运营状态端点，`server.py` 仍是较大的单体文件；
- 标准库覆盖率是关键模块语句行近似，不是 coverage.py 的分支覆盖；
- 注解审计只检查公开函数是否有注解，不做 mypy 语义推断；
- `coverage` 和 `mypy` 安装因当前代理/SSL 网络失败未完成；
- GitHub Actions 只是本地校验过的工作流定义，未推送前没有真实 CI 运行证据；
- 依赖精确版本提高复现性，但当前没有哈希锁文件或供应链签名。

## 完成闸门

- 本地统一检查入口通过；
- 关键模块聚合语句覆盖率不低于 60%；
- 注解契约通过；
- 端点从 Blueprint 注册且页面无回归；
- 浏览器能正常读取模型状态和运行风险扫描；
- 记录外部工具安装失败与未运行 CI。
