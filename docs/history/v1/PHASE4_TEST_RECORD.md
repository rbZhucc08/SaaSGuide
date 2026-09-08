# 第四阶段 DeepSeek ASK / BUILD 测试记录

## 阶段目的

把功能 Brief 送入 DeepSeek，并把返回结果限制为两种：信息不足时返回 `ASK`，信息充分时返回 `BUILD`。模型结果必须先经过程序校验，不能直接进入后续页面生成流程。

## 输入契约

完整 Brief 需要包含：

- `featureName`：功能名称。
- `featureBrief`：功能说明。
- `targetUsers`：目标用户。
- `entryPoint`：功能入口。
- `operationSteps`：操作步骤列表。
- `successState`：完成操作后的成功状态。
- `pageElements`：可用页面元素名称与真实 HTML id 的对应表。

示例见 `brief-complete.example.json`、`brief-incomplete.example.json` 和 `brief-ambiguous.example.json`。

## 处理流程

1. 本地预检查先识别明显缺失字段；缺失时直接返回 `ASK`，避免一次没有必要的付费请求。
2. 字段齐全时，`deepseek_ask_build.py` 从环境变量 `DEEPSEEK_API_KEY` 读取密钥，并调用 DeepSeek Chat Completions 接口。
3. 请求启用 `response_format: {"type": "json_object"}`，提示词明确要求 json，并给出 ASK / BUILD 示例。
4. 返回内容先解析为 JSON，再检查决策、追问结构、步骤顺序和页面目标。
5. BUILD 中的 `pageElements` 必须与输入完全一致，模型不能虚构页面 id。

## 官方接口核对

核对日期：2026-09-02。

- 官方文档：`https://api-docs.deepseek.com/`
- JSON Output：`https://api-docs.deepseek.com/guides/json_mode`
- OpenAI 兼容地址：`https://api.deepseek.com`
- 本项目请求地址：`https://api.deepseek.com/chat/completions`
- 当前默认模型：`deepseek-v4-flash`
- 可通过 `DEEPSEEK_MODEL` 环境变量切换官方当前支持的其他模型。
- 官方说明 JSON Output 偶尔可能返回空内容；代码已把空内容视为失败，不会误当成成功。
- 已处理官方列出的 400、401、402、422、429、500、503 状态，错误信息不会暴露密钥。

模型名称和价格会变化，真实调用前应再次查看官方页面。本记录只代表上述核对日期的状态。

## 自动测试结果

执行环境：Codex 随附 Python 3.12.13。

执行命令：

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest -v test_validator.py test_deepseek_ask_build.py
```

实际结果：14 项测试全部通过，其中原校验器 6 项，第四阶段新增 8 项。

第四阶段覆盖：

- 明显缺字段时返回本地 ASK，且不调用 API。
- 完整 Brief 接受合法 BUILD 模拟响应。
- 字段齐全但语义含糊时允许模型返回 ASK。
- 非法 JSON 被拦截。
- 模型虚构页面元素被拦截。
- 重复追问同一字段被拦截。
- 请求确实启用 JSON Output 且关闭流式返回。
- 未配置密钥时在联网前停止。

回归结果：原有 6 项数据校验测试仍全部通过。未修改 `index.html`、`styles.css`、`app.js`、`guide-data.json` 或 `risk-data.json`。

## 手工命令结果

- 对 `brief-incomplete.example.json` 执行：成功返回 `ASK`，列出目标用户、入口、步骤、成功状态和页面元素等缺失项。
- 在配置密钥前，对 `brief-complete.example.json` 执行：程序按预期在联网前停止，并明确显示“未进行真实 API 调用”。

## 真实 DeepSeek 调用结果

验收日期：2026-09-03。使用模型：`deepseek-v4-flash`。

- 环境变量检查只输出是否存在，没有显示密钥内容。
- 第一次在受限执行环境中请求时出现“无法连接 DeepSeek”；这属于本地网络权限限制，不是 DeepSeek API 返回错误，因此没有误记为接口失败。
- 获得外部网络权限后，对 `brief-complete.example.json` 进行真实调用：返回 `BUILD`，生成 4 个顺序连续的引导步骤，页面元素与输入完全一致，并通过现有 Python 校验。
- 对 `brief-ambiguous.example.json` 进行真实调用：返回 `ASK`，追问操作步骤、功能入口、成功状态和目标用户，并通过 ASK 结构校验。
- 两次真实调用都正常结束，退出码为 0。

本次只向 DeepSeek 发送虚构的风险看板功能说明、模拟用户类型、模拟操作步骤和本地页面元素 id，不包含个人信息、真实公司数据或 API 密钥。

## 已实现与未验证边界

已实现并测试：请求结构、环境变量读取、ASK / BUILD 解析、输出校验、错误处理和模拟 API 响应；真实 DeepSeek 的 BUILD 与 ASK 分支均已运行通过。

已验证：当前密钥可完成 DeepSeek 认证，真实响应可被程序解析和校验，可以声称“DeepSeek API 已成功接通并完成两条模拟用例测试”。

尚未验证：大量或并发调用、长期输出稳定性、精确 token 成本记录、余额不足、限流和服务端故障的真实发生过程。相关错误分支只有代码与离线检查，不能声称已经在真实服务中逐项触发。

本阶段没有创建 Flask 后端、数据库、生产部署或真实 SaaS 集成。完整链路和文件保存属于第五阶段。
