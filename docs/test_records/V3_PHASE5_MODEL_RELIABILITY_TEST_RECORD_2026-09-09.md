# V3 阶段 5 模型稳定性测试记录

日期：2026-09-09  
实现提交：`0fd3529 feat: harden V3 model reliability`

## 目标与非目标

本阶段为 DeepSeek ASK/PLAN 增加严格协议、版本、有限重试、错误分类、预算和去敏遥测，并让页面明确展示失败原因与人工保底路径。没有接第二供应商，没有批量真实调用，也没有承诺模型输出确定性。

## 修改内容

- `services/ai/provider.py`：供应商接口、单次预算策略和批量预算预留；
- `deepseek_ask_build.py`：20 秒超时、最多 2 次重试、退避、错误分类和运行遥测；
- `services/ai/orchestrator.py`：严格 ASK/PLAN 字段、引用白名单、Prompt/协议版本；
- `deepseek_risk_assistant.py`：旧风险入口同步收紧 ASK/PLAN 协议；
- `server.py`：模型能力、预算和失败分类 API，成功/失败运行日志；
- `risk-radar.html/js/css`：模型状态、边界、失败原因、保底路径和折叠遥测；
- `test_model_reliability.py`：9 项阶段 5 故障与边界测试；
- `docs/specs/V3_PHASE5_MODEL_RELIABILITY_SPEC.md` 与限制更新。

没有数据库迁移。运行日志位于被 Git 忽略的 `generated/ai-runs.jsonl`。

## 自动测试

命令：

```powershell
& '.\run_checks.ps1'
git diff --check
```

结果：156 项 Python 自动测试通过，JSON/页面校验、78 个 Markdown 本地链接、全部前端 JavaScript 语法检查和 `git diff --check` 通过。

阶段闸门覆盖：

- 合法 ASK：通过；
- 合法 PLAN：既有编排测试通过；
- 超时：模拟 3 次有限尝试后分类为 `timeout`；
- 限流：模拟 HTTP 429，有限重试后分类为 `rate_limited`；
- 非法 JSON：拒绝；
- 伪造引用：拒绝；
- 单次超预算与批量超预算：请求前拒绝；
- 供应商未配置/不可用：分类并保留人工路径；
- 协议外字段：拒绝；
- 去敏运行 ID、Token、重试和费用不可用状态：通过。

以上故障测试均为本地模拟，不是 DeepSeek 服务实测。

## 浏览器验收

环境：Codex 应用内 Chromium，桌面视口。Chrome 控制通道不可用，本轮不称为 Chrome 验收。控制台 warning/error 为 0。

页面显示：

- DeepSeek 当前已配置；
- 调用失败时规则扫描和人工处理仍可使用；
- 超时 20 秒、最多重试 2 次、单次 10,000 Token 上限；
- 真实调用失败后显示“无法连接 DeepSeek，请检查网络后重试”；
- 人工确认、观察、驳回和标记误报按钮仍可使用；
- 展开后显示去敏 `model-run-*`、`provider_unavailable`、延迟和重试 2 次。

截图：

- `docs/test_records/v3_phase5_model_2026-09-09/model-runtime-status.jpg`；
- `docs/test_records/v3_phase5_model_2026-09-09/provider-failure-fallback.jpg`。

## 真实 API 与费用

浏览器发起 2 次用户级真实 DeepSeek 请求，用于修复前后验收失败状态；两次均在网络层失败，最终分类为 `provider_unavailable`。每次内部最多尝试 3 次。没有取得模型内容，没有可用 Token 数，也没有供应商费用字段。

因此本阶段没有成功的真实 ASK 或 PLAN。不能把“密钥已配置”写成“DeepSeek 可用”，也不能因费用字段为空声称费用为零。

## 已知限制

- Token 输入量为本地保守估算，不等于供应商 tokenizer；
- 批量预算对象只约束显式使用它的单进程批次，不是账号级配额；
- 没有队列、熔断、跨进程限额、多供应商降级或真实费用计算；
- 网络失败很快返回，本次没有验证真实 20 秒服务器超时；
- 严格结构、白名单引用和人工闸门仍不能证明建议在真实业务中正确。
