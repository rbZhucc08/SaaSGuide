# 第五阶段完整流程连接测试记录

## 阶段目的

把网页输入、DeepSeek ASK / BUILD 判断、Python 校验、结果保存和 HTML 预览连接成一条可运行的本地流程。

## 输入

用户在 `/builder` 页面填写：功能名称、功能说明、目标用户、功能入口、操作步骤和成功状态。页面元素清单固定为当前风险看板真实存在的四个目标，避免浏览器随意提交不存在的 id。

## 处理

1. 浏览器把 Brief 作为 JSON 发送给本地 Flask 服务。
2. Flask 调用 `deepseek_ask_build.py`。
3. 明显缺字段时本地返回 ASK；字段齐全时调用 DeepSeek。
4. DeepSeek 结果必须通过 ASK / BUILD 结构和页面目标校验。
5. ASK 只显示问题并写运行日志，不生成引导文件。
6. 只有通过校验的 BUILD 才保存 JSON 和独立 HTML 预览。

API 密钥只由 Python 从 `DEEPSEEK_API_KEY` 环境变量读取，不会进入网页代码、请求正文、生成文件或运行日志。

## 输出

- 网页结果区：显示 ASK 问题或 BUILD 步骤。
- `generated/guide-data.generated.json`：最近一次合格 BUILD 的结构化结果。
- `generated/guide-preview.generated.html`：最近一次合格 BUILD 的独立预览。
- `generated/run-log.jsonl`：记录时间、功能名、判断、来源、模型和 token 用量，不记录密钥。

`generated/` 已加入 `.gitignore`，避免以后把临时运行数据误提交到公开仓库。

## 自动检查

执行环境：项目 `.venv`，Flask 3.1.3。

执行命令：

```powershell
& '.\.venv\Scripts\python.exe' -W error::ResourceWarning -m unittest -v test_validator.py test_deepseek_ask_build.py test_server.py
```

结果：21 项测试全部通过，无 ResourceWarning。

覆盖内容：

- 原有 JSON 和页面目标校验 6 项。
- DeepSeek ASK / BUILD 离线测试 8 项。
- Flask 连接测试 7 项：页面可读取、非 JSON 拒绝、ASK 不生成文件、BUILD 保存 JSON/HTML、HTML 转义用户文字、模型输出错误、DeepSeek 服务错误。
- Python 语法、`app.js` 与 `builder.js` JavaScript 语法均通过。
- 原有 `guide-data.json`、`risk-data.json` 与 `index.html` 仍一致。

## 真实端到端验收

验收日期：2026-09-03。地址：`http://127.0.0.1:4173/builder`。

### 完整 Brief

- 网页真实提交成功，HTTP 200。
- DeepSeek 返回 BUILD。
- 页面显示 4 个步骤和“已通过校验”。
- 模型：`deepseek-v4-flash`。
- 本次记录：1286 tokens。
- JSON 和 HTML 文件实际保存，HTML 预览可在浏览器打开。

### 含糊 Brief

- 网页真实提交成功，HTTP 200。
- DeepSeek 返回 ASK。
- 页面追问目标用户、入口、操作步骤和成功状态。
- 本次记录：842 tokens。
- ASK 没有覆盖前一次合格 BUILD 的生成文件。

### 页面检查

- 桌面尺寸：表单和结果双栏显示，输入、按钮、步骤、链接均可见。
- 390 × 844：浏览器报告视口和页面宽度均为 390，没有页面级横向溢出；表单与结果改为上下排列，提交按钮宽度正常。
- 页面控制台未发现错误或警告。
- 生成预览实际显示 4 个步骤、页面目标、模型和生成时间。

## 真实发现的问题与修复

1. 项目默认 Python 镜像连接被代理中断，导致 Flask 第一次安装失败；改用 Python 官方软件源后成功安装 Flask 3.1.3。
2. Flask 页面读取测试最初出现未关闭文件的 ResourceWarning；关闭测试响应后，使用“把 ResourceWarning 当错误”的方式重新执行，21 项全部通过。
3. 浏览器最初请求不存在的 favicon，服务日志出现 404；两个页面增加空白 favicon 声明后消除该请求。
4. 浏览器普通手机尺寸开关没有实际改变视口；没有误报通过，改用开发者尺寸模拟，最终确认 390 × 844 和页面宽度 390。

## 当前限制

- 这是本机 Flask 开发服务，不是生产服务器或线上部署。
- 没有登录、多用户、数据库、历史版本、权限控制或并发设计。
- 生成结果只保留最近一次合格 BUILD；运行日志会持续追加。
- DeepSeek 请求期间页面需要等待，尚未加入取消、重试或队列。
- 页面元素仍固定为当前虚构风险看板，不支持连接真实 SaaS 页面。
- 完整异常矩阵属于第六阶段，本阶段只验证了主要连接路径和离线错误分支。
