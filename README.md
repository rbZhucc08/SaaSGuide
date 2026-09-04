# SaaSGuide

一个面向 AI 应用岗位求职的个人学习 Demo：在虚构的 B2B 项目管理场景中，用风险看板集中查看风险，并让 DeepSeek 在人工确认前提供结构化处理建议。V2 在不覆盖 V1 的前提下，逐阶段增加可核验的数据接入与风险分析能力。

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
- 在独立的 `/data-sources` 页面导入项目任务 XLSX，完成列映射、校验、预览、人工确认和标准化 JSON 保存。

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

- V1 风险看板：`http://127.0.0.1:4173/`
- V2-P1 数据源：`http://127.0.0.1:4173/data-sources`

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

截至 2026-09-04：53 项自动测试通过，其中原有 V1 的 38 项及 2 项新增请求上限回归测试均通过；V2-P1 新增 13 项导入测试。V2-P1 的内置样本浏览器闭环、确认后落盘、桌面和 390 × 844 手机页面已验收。用户手动确认 Chrome 可选择两份本地 XLSX 并触发预览；受自动化权限限制，该文件选择动作不是自动化复现结果。

## 当前状态与文档入口

- `docs/PROJECT_STATUS.md`：当前真正完成、验证和未验证的内容。
- `docs/V2_ROADMAP.md`：V2 阶段路线与当前闸门。
- `docs/EVIDENCE_RULES.md`：实现、自动测试、浏览器验收等证据等级。
- `docs/RISKS_AND_ASSUMPTIONS.md`：已知风险、假设与成本。
- `docs/V2_PHASE1_SPEC.md`：V2-P1 的范围和验收条件。
- `docs/test_records/V2_PHASE1_TEST_RECORD_2026-09-04.md`：V2-P1 实际验收记录。

阶段简称统一为 `V1-Pn` 和 `V2-Pn`。根目录旧有的 `PHASE1_TEST_RECORD.md` 至 `PHASE6_TEST_RECORD.md` 是 V1 历史记录，不重命名，以免破坏旧引用。

## 文件说明

- `index.html`、`styles.css`、`app.js`：风险看板页面、外观与交互。
- `data-sources.html`、`data-sources.css`、`data-sources.js`：V2-P1 数据源导入页面。
- `services/ingestion/xlsx_import.py`：XLSX 解析、映射、校验和确认保存。
- `data/samples/`、`data/evaluation/`：模拟 XLSX 与固定标准答案。
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
