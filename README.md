# SaaSGuide

一个面向 AI 应用岗位求职的个人学习 Demo：在虚构的 B2B 项目管理场景中，用风险看板集中查看风险，并让 DeepSeek 在人工确认前提供结构化处理建议。

> 真实性声明：本项目使用虚构 SaaS 和模拟数据，没有真实客户、真实产品接入、生产部署或业务效果数据。

## 能做什么

- 从 `risk-data.json` 读取风险列表，自动统计总数、等级和处理状态。
- 按高、中、低风险筛选，查看风险详情并在当前页面标记已处理。
- 对已有风险调用 DeepSeek，返回 ASK（追问）或 PLAN（建议方案）。
- 新建风险时先进行 AI 分析，只有人工确认的 PLAN 才能保存。
- 保存前校验完整数据，并自动备份修改前的风险文件。
- 将当前风险列表导出为适合表格软件打开的 CSV。
- 提供可选的四步页面导览。
- 保留一个后台 ASK / BUILD 引导生成实验，入口为 `/builder`。

## 核心流程

```text
用户填写风险事实
        ↓
本地服务检查必填信息
        ↓
DeepSeek 返回 ASK 或 PLAN
        ↓
程序检查返回结构是否合格
        ↓
用户确认（AI 不能替用户确认）
        ↓
备份旧数据并写入 risk-data.json
        ↓
页面重新统计并展示新风险
```

## 本地运行

环境要求：Windows、Python 3.11+、可选的 Node.js（仅用于 JavaScript 语法检查）。

```powershell
python -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
```

需要真实 AI 分析时，把 DeepSeek 密钥设置为环境变量。密钥不要写进本项目：

```powershell
$env:DEEPSEEK_API_KEY = '你的密钥'
& '.\.venv\Scripts\python.exe' .\server.py
```

浏览器打开：`http://127.0.0.1:4173/`

## 检查方式

一键检查：

```powershell
& '.\run_checks.ps1'
```

等价的分项命令：

```powershell
& '.\.venv\Scripts\python.exe' -m unittest test_validator.py test_deepseek_ask_build.py test_risk_assistant.py test_server.py
& '.\.venv\Scripts\python.exe' .\validate_data.py
node --check app.js
node --check builder.js
```

截至 2026-09-03：38 项自动测试通过；风险新建真实闭环、刷新持久化、桌面和 390 × 844 手机页面均已验收。

## 文件说明

- `index.html`、`styles.css`、`app.js`：风险看板页面、外观与交互。
- `risk-data.json`、`guide-data.json`：模拟风险和导览内容。
- `server.py`：本地页面、分析接口、确认保存与备份。
- `deepseek_risk_assistant.py`：风险 ASK / PLAN 规则和模型输出校验。
- `deepseek_ask_build.py`：后台引导生成学习实验。
- `validate_data.py`：数据字段、日期、等级、步骤和页面目标校验。
- `test_*.py`：不消耗模型费用的自动测试。
- `*_TEST_RECORD.md`：真实运行与阶段验收记录。
- `DECISION_LOG.md`、`BUG_LOG.md`：关键取舍与真实问题记录。
- `SOURCE_CODE_STUDY_GUIDE.md`：源码关系、形成原因和跨境运营能力迁移说明。
- `DEMO_SCRIPT.md`、`RESUME_EVIDENCE.md`：演示和求职表述边界。

## 已知限制

- Flask 只作为本机开发服务，不是生产服务器。
- JSON 适合单人 Demo，不支持多人同时编辑、账号、权限或数据库查询。
- 新建风险会保存；详情页临时修改的状态和临时采纳计划刷新后会恢复。
- DeepSeek 输出经过结构检查，但建议是否合理仍需人工判断。
- 没有真实业务数据，不能宣称降低了真实公司的风险或产生业务指标。
