# V3 阶段 7 工程结构与自动化测试记录

日期：2026-09-09  
实现提交：`478a64e feat: establish V3 engineering checks`

## 实施结果

- 独立评测与模型能力端点迁入 `v3_operations` Blueprint，API 路径保持不变；
- 运行依赖锁定为当前验证的精确版本；
- 跨平台 Python 检查入口覆盖单元测试、关键模块覆盖率、注解契约、数据、Markdown、JavaScript 与 Git 差异；
- CI 定义扩展为 Windows/Ubuntu × Python 3.11/3.12；
- HTTP 响应增加去敏请求 ID，错误 JSONL 增加结构化耗时字段；
- 新增 5 项工程基础测试。

没有新增数据库 Schema；阶段 3 的 v1→v2 备份迁移测试继续通过。

## 自动测试

`run_checks.ps1` 结果：

- 166 项 Python 测试通过；
- 关键模块聚合语句覆盖率：398/447，89.04%，门槛 60%；
- `provider.py` 92.31%、`independent.py` 80.14%、`knowledge_base.py` 94.40%、`database/store.py` 92.25%；
- 4 个关键模块公开函数类型注解契约通过；
- JSON/页面校验、78 个 Markdown 本地链接、10 个 JavaScript 文件语法和 `git diff --check` 通过。

覆盖率由 Python 标准库 `trace` 对 AST 语句行近似计算，不是分支覆盖。注解契约只验证注解存在，不是完整静态类型推断。

## 外部工具失败

尝试安装精确版本 `coverage==7.10.7` 和 `mypy==1.18.2`。沙箱内请求被网络权限阻断；放宽沙箱后再次请求，仍因代理/SSL 连接失败无法下载。因此没有运行 coverage.py 或 mypy，不能写成通过。

## 浏览器验收

环境：Codex 应用内 Chromium，桌面视口。重启服务后打开 `/risk-radar?phase7=1`：

- Blueprint 提供的模型能力端点正常加载；
- 页面显示 DeepSeek 状态、超时、重试和预算；
- 点击“扫描所选项目”，生成 7 条候选、11 次规则命中；
- 控制台 warning/error 为 0。

HTTP 只读验收同时确认 `/api/agent/capabilities` 返回 200、`runtime_version=v3`，响应头含随机 `X-Request-ID`。

截图：`docs/test_records/v3_phase7_engineering_2026-09-09/blueprint-risk-scan.jpg`。

## 未验证与限制

- 工作流文件尚未推送，GitHub Actions 四格矩阵没有真实运行结果；
- Linux 只在 CI 定义和跨平台脚本层完成，本机不是 Linux；
- `server.py` 仍包含多数业务端点，拆分没有完成到全量 Blueprint；
- 没有哈希依赖锁、分支覆盖、mypy 语义检查、负载测试或生产监控；
- 结构化 JSONL 是本地文件日志，不是集中式可观测平台。
