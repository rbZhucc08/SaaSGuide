# SaaSGuide

一个面向 AI 应用岗位求职的个人学习 Demo：在虚构的 B2B 项目管理场景中，用风险看板集中查看风险，并让 DeepSeek 在人工确认前提供结构化处理建议。V2 在不覆盖 V1 的前提下，逐阶段增加可核验的数据接入与风险分析能力。

> 真实性声明：本项目使用虚构 SaaS 和模拟数据，没有真实客户、真实产品接入、生产部署或业务效果数据。

## 能做什么

V2 本地总览：`http://127.0.0.1:4173/v2`

- 从 `risk-data.json` 读取风险列表，自动统计总数、等级和处理状态。
- 按高、中、低风险筛选，查看风险详情并在当前页面标记已处理。
- 对已有风险调用 DeepSeek，返回 ASK（追问）或 PLAN（建议方案）。
- 新建风险时先进行 AI 分析，只有人工确认的 PLAN 才能保存。
- 保存前校验完整数据，并自动备份修改前的风险文件。
- 将当前风险列表导出为适合表格软件打开的 CSV。
- 提供可选的四步页面导览。
- 保留一个后台 ASK / BUILD 引导生成实验，入口为 `/builder`。
- 在独立的 `/data-sources` 页面导入项目任务 XLSX，完成列映射、校验、预览、人工确认和标准化 JSON 保存。
- 在独立的 `/risk-radar` 页面运行确定性风险规则，查看原始证据、固定评测指标，并记录确认、观察、驳回或误报选择。
- 解析 TXT、Markdown、DOCX 与普通 PDF，保留文件哈希、原文位置和人工核对记录。
- 用版本化自建知识库回答并引用当前生效文档；无依据时拒答。
- 用 SQLite 保存行动、状态事件和人工决策审计。
- 由 Python 计算周报指标，并导出 UTF-8 BOM CSV 与三表 XLSX。
- 检测需要 OCR 的 PDF、检查 WAV 元数据和模拟适配器；真实 OCR、语音识别和外部连接器尚未验证。

## 核心流程

V1 的主动风险分析：

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

V2 本地闭环：

```text
项目任务 XLSX
        ↓
列映射、校验与人工确认
        ↓
统一项目 JSON（保留来源与行号）
        ↓
Python 确定性规则与去重
        ↓
带原始证据的候选风险
        ↓
版本化知识引用与拒答
        ↓
人工确认 / 观察 / 驳回 / 标记误报
        ↓
SQLite 行动与事件审计
        ↓
Python 指标、CSV 和 XLSX 周报
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
- V2-P2 风险雷达：`http://127.0.0.1:4173/risk-radar`
- V2 总览：`http://127.0.0.1:4173/v2`
- 文本证据：`http://127.0.0.1:4173/evidence-intake`
- 知识库：`http://127.0.0.1:4173/knowledge-base`
- 行动跟踪：`http://127.0.0.1:4173/action-tracker`
- 报告与导出：`http://127.0.0.1:4173/reports`
- 输入实验室：`http://127.0.0.1:4173/input-lab`
- 健康检查：`http://127.0.0.1:4173/health`

也可以直接运行：

```powershell
& '.\start_v2.ps1'
```

## 检查方式

一键检查：

```powershell
& '.\run_checks.ps1'
```

等价的分项命令：

```powershell
& '.\.venv\Scripts\python.exe' -m unittest test_validator.py test_deepseek_ask_build.py test_risk_assistant.py test_server.py test_xlsx_import.py test_risk_rules.py test_text_evidence.py test_knowledge_base.py test_sqlite_store.py test_reporting.py test_multimodal_adapters.py test_release.py
& '.\.venv\Scripts\python.exe' .\validate_data.py
node --check app.js
node --check builder.js
node --check data-sources.js
node --check risk-radar.js
node --check evidence-intake.js
node --check knowledge-base.js
node --check action-tracker.js
node --check reports.js
node --check input-lab.js
```

截至 2026-09-05：91 项自动测试通过。P2 固定规则集 Precision 与 Recall 均为 83.33%；P4 的 10 题同源小型固定集检索、引用与拒答均为 100%。这些指标只能描述自建模拟样本。P4-P8 在应用内 Chromium 完成桌面、390 × 844 和控制台验收；当时 Chrome 扩展浏览器不可用，不能外推为 Chrome 验收。

## 当前状态与文档入口

- `docs/PROJECT_STATUS.md`：当前真正完成、验证和未验证的内容。
- `docs/V2_ROADMAP.md`：V2 阶段路线与当前闸门。
- `docs/EVIDENCE_RULES.md`：实现、自动测试、浏览器验收等证据等级。
- `docs/RISKS_AND_ASSUMPTIONS.md`：已知风险、假设与成本。
- `docs/V2_PHASE1_SPEC.md`：V2-P1 的范围和验收条件。
- `docs/test_records/V2_PHASE1_TEST_RECORD_2026-09-04.md`：V2-P1 实际验收记录。
- `docs/V2_PHASE2_SPEC.md`：V2-P2 的规则、指标和人工决策边界。
- `docs/test_records/V2_PHASE2_TEST_RECORD_2026-09-04.md`：V2-P2 实际验收记录。
- `docs/V2_PHASE3_SPEC.md` 至 `docs/V2_PHASE8_SPEC.md`：后续阶段规格。
- `docs/test_records/V2_PHASE3_TEST_RECORD_2026-09-04.md` 至 `V2_PHASE8_TEST_RECORD_2026-09-05.md`：实际验收记录。
- `docs/V2_ARCHITECTURE.md`、`docs/V2_SECURITY_AND_LIMITS.md`、`docs/V2_DEMO_SCRIPT.md`：架构、安全边界与演示顺序。

阶段简称统一为 `V1-Pn` 和 `V2-Pn`。根目录旧有的 `PHASE1_TEST_RECORD.md` 至 `PHASE6_TEST_RECORD.md` 是 V1 历史记录，不重命名，以免破坏旧引用。

## 文件说明

- `index.html`、`styles.css`、`app.js`：风险看板页面、外观与交互。
- `data-sources.html`、`data-sources.css`、`data-sources.js`：V2-P1 数据源导入页面。
- `services/ingestion/xlsx_import.py`：XLSX 解析、映射、校验和确认保存。
- `data/samples/`、`data/evaluation/`：模拟 XLSX 与固定标准答案。
- `risk-radar.html`、`risk-radar.css`、`risk-radar.js`：V2-P2 候选风险页面。
- `services/risk_rules/deterministic_scan.py`：确定性规则、去重、评测与人工决策记录。
- `services/ingestion/text_evidence.py`、`pdf_audio.py`：文本、DOCX、普通 PDF 和 WAV 元数据。
- `services/retrieval/knowledge_base.py`：版本检索、引用、冲突和拒答。
- `database/store.py`：SQLite 迁移、行动状态机和审计事件。
- `services/reporting/metrics.py`：确定性报告指标和 CSV。
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
- SQLite 仍是单机 Demo，不支持多人同时编辑、账号或企业权限。
- 确定性规则和检索不理解复杂语义或完整间接依赖链，存在误报、漏报和同源评测过拟合。
- 新建风险会保存；详情页临时修改的状态和临时采纳计划刷新后会恢复。
- DeepSeek 输出经过结构检查，但建议是否合理仍需人工判断。
- 没有真实业务数据，不能宣称降低了真实公司的风险或产生业务指标。
- 没有公开部署、生产 WSGI/TLS、真实 OCR、语音识别或外部系统授权。
