# SaaSGuide

一个面向 AI 应用岗位求职的个人学习 Demo：在虚构的 B2B 项目管理场景中，将用户确认导入的项目数据、风险审计、文本证据、知识引用、行动与报告串成可追溯的本地闭环。V1 的固定风险看板保留在 Git 历史中，不再作为当前产品入口。

> 真实性声明：本项目使用虚构 SaaS 和模拟数据，没有真实客户、真实产品接入、生产部署或业务效果数据。

## 能做什么

V2 本地工作台：`http://127.0.0.1:4173/`

- 根工作台区分可编辑模拟公司档案、用户确认导入、人工审计和 SQLite 行动；没有人工结果时显示真实空状态。
- 保留一个后台 ASK / BUILD 引导生成实验，入口为 `/builder`。
- 在 `/data-sources` 导入项目任务 XLSX；原始列名可自由输入，并提供原表头建议，服务端会拦截不存在的列。
- 在 `/data-sources` 页面新增、编辑、删除项目与任务，也可继续导入 XLSX；固定样本只收纳在折叠的开发评测入口。
- 在独立的 `/risk-radar` 页面选择当前可编辑项目运行确定性规则，查看原始证据，并记录确认、观察、驳回或误报选择。
- 在候选卡中按需调用一个受控 Orchestrator：检索当前生效知识后由 DeepSeek 返回 ASK 或带引用 PLAN，再由 Python 校验；AI 不自动确认或保存行动。
- 解析 TXT、Markdown、DOCX 与普通 PDF，保留文件哈希、原文位置和人工核对记录。
- 用可新增、编辑、删除的版本化自建知识库回答并引用当前生效文档；无依据时拒答。
- 用 SQLite 保存行动、状态事件和人工决策审计；产品运行时不再自动写入固定行动。
- 报告与 CSV/XLSX 均从当前人工决策和行动实时计算，不再回退到固定报告样板。

## 可编辑模拟公司数据

- 版本化 Seed：`data/demo/nebula_company_seed.json`，包含 1 家虚构公司、6 个部门、5 个项目、25 条任务、16 个制度/历史案例版本。
- 本地运行副本：`generated/company-data.json`，首次访问复制一次，此后保留用户修改。
- 清空后重启不会自动恢复；只有点击“恢复模拟公司数据”才会覆盖为 Seed。
- 这属于数据驱动检索与受控 Agent 上下文，不是训练或微调 DeepSeek。
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
当前生效知识检索与引用白名单
        ↓
DeepSeek ASK / PLAN 草稿
        ↓
Python 结构与引用校验
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

- V2 工作台：`http://127.0.0.1:4173/`
- V2-P1 数据源：`http://127.0.0.1:4173/data-sources`
- V2-P2 风险雷达：`http://127.0.0.1:4173/risk-radar`
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
& '.\.venv\Scripts\python.exe' -m unittest test_validator.py test_deepseek_ask_build.py test_risk_assistant.py test_server.py test_xlsx_import.py test_risk_rules.py test_text_evidence.py test_knowledge_base.py test_sqlite_store.py test_reporting.py test_multimodal_adapters.py test_ai_orchestrator.py test_release.py
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

截至 2026-09-07：累计 120 项自动测试通过；可编辑项目已在浏览器完成编辑、跨刷新保存和风险扫描，真实 DeepSeek 对当前项目返回带 3 条当前制度引用、3 条行动草稿的 PLAN。固定评测夹具继续保留，但已与产品运行数据隔离。所有指标只能描述自建模拟样本。

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
- `docs/V2_ARCHITECTURE.md`、`docs/V2_SECURITY_AND_LIMITS.md`：架构与安全边界。
- `docs/V2_AI_ORCHESTRATION_SPEC.md` 与对应测试记录：V2 Orchestrator、五个领域 Skill 和真实 DeepSeek 验收。
- `docs/SaaSGuide_V2_HR_演示引导.docx`：脱离产品页面的 HR 演示讲解稿。

阶段简称统一为 `V1-Pn` 和 `V2-Pn`。根目录旧有的 `PHASE1_TEST_RECORD.md` 至 `PHASE6_TEST_RECORD.md` 是 V1 历史记录，不重命名，以免破坏旧引用。

## 文件说明

- `index.html`、`styles.css`、`app.js`：V2 工作台页面、外观与本地状态汇总交互。
- `data-sources.html`、`data-sources.css`、`data-sources.js`：V2-P1 数据源导入页面。
- `services/ingestion/xlsx_import.py`：XLSX 解析、映射、校验和确认保存。
- `data/demo/`：可恢复的丰富模拟公司 Seed；`services/company_data/`：运行数据校验、持久化与 CRUD。
- `data/samples/`、`data/evaluation/`：仅供隔离测试的模拟 XLSX 与固定标准答案。
- `risk-radar.html`、`risk-radar.css`、`risk-radar.js`：V2-P2 候选风险页面。
- `services/risk_rules/deterministic_scan.py`：确定性规则、去重、评测与人工决策记录。
- `services/ingestion/text_evidence.py`、`pdf_audio.py`：文本、DOCX、普通 PDF 和 WAV 元数据。
- `services/retrieval/knowledge_base.py`：版本检索、引用、冲突和拒答。
- `services/ai/skills.py`、`services/ai/orchestrator.py`：五个产品领域 Skill 合约与受控 DeepSeek 风险编排。
- `database/store.py`：SQLite 迁移、行动状态机和审计事件。
- `services/reporting/metrics.py`：确定性报告指标和 CSV。
- `risk-data.json`、`guide-data.json`：V1 历史模拟数据与后台学习实验兼容数据，不供 V2 工作台统计。
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
- 当前 DeepSeek 只用于风险行动规划；P3 模型文本抽取、向量 RAG 和 P6 模型周报叙述仍未实现。
- 没有真实业务数据，不能宣称降低了真实公司的风险或产生业务指标。
- 没有公开部署、生产 WSGI/TLS、真实 OCR、语音识别或外部系统授权。
