# SaaSGuide 项目简历修改交接文档

> 用途：交给新的 Codex 对话。下一对话的目标不是继续开发网站，而是读取当前仓库证据，结合用户提供的现有简历和目标 JD，完成真实、匹配岗位的简历修改。

## 一、给下一对话的最短指令

请进入 `D:\CodexProjects\SaaSGuide`，先完整阅读本文件，再按“建议读取顺序”核对项目。随后请用户提供：

1. 当前简历原文件，优先 DOCX；
2. 目标岗位 JD；
3. 期望投递方向和页数要求。

不要仅根据本交接文档直接编造简历。简历中的每一项能力必须能对应当前代码、测试或验收记录；计划、模拟结果、未验证功能和真实商业成果必须区分。

## 二、项目一句话介绍

SaaSGuide 是一个面向 AI 应用岗位作品集的本地个人学习 Demo：在虚构 B2B 项目管理场景中，把项目数据接入、确定性风险扫描、版本化知识检索、DeepSeek ASK/PLAN、Python 输出校验、人工确认、SQLite 行动审计和报告导出串成可追溯闭环。

真实性边界：项目只使用虚构 SaaS、自建知识文档和模拟数据；没有真实客户、真实企业系统接入、线上用户、生产部署或业务提升数据。

## 三、当前版本与代码状态

- 工作目录：`D:\CodexProjects\SaaSGuide`
- 当前分支：`v2-phase8-release`
- 当前最新提交：`cacc4de feat: add bounded V2 AI orchestration`
- 该提交后工作区已检查为干净。
- 本地入口：`http://127.0.0.1:4173/`
- 启动：`& '.\.venv\Scripts\python.exe' .\server.py`
- 一键检查：`& '.\run_checks.ps1'`
- 2026-09-05 最新结果：107 项自动测试通过。

## 四、当前产品结构

网页保留 V1 的功能板块结构和统一 V2 视觉，但当前根入口只展示用户确认导入、人工审计和 SQLite 行动等本地状态，不再把固定 V1 风险样板当成正式首页数据。

主要页面：

- `/`：V2 项目风险工作台。
- `/data-sources`：XLSX 导入、开放文本列映射、校验、预览和人工确认。
- `/risk-radar`：确定性候选风险、原始证据、DeepSeek 研判和人工决策。
- `/evidence-intake`：TXT、Markdown、DOCX 和普通 PDF 证据接入与人工核对。
- `/knowledge-base`：版本化知识检索、引用、冲突和拒答。
- `/action-tracker`：SQLite 行动、状态机和追加式审计事件。
- `/reports`：Python 指标、CSV 与 XLSX 报告。
- `/input-lab`：普通 PDF、OCR_REQUIRED、WAV 元数据和模拟适配器边界。
- `/builder`：V1 ASK/BUILD 学习实验后台入口，不是当前主产品流程。

旧 `/v2` 演示总览已删除。HR 演示说明独立放在 `docs/SaaSGuide_V2_HR_演示引导.docx`，不再混入产品网页。

## 五、AI Agent、Skills 与 Workflow

### 1. Agent

当前实现一个受控的单 Orchestrator：`saasguide-v2-orchestrator`。这是自管 Python 编排，不是 OpenAI Agents SDK，也不是多 Agent 系统。

### 2. 五个产品领域 Skill 合约

- `project-data-intake`：XLSX/文本/PDF 数据和证据接入。
- `risk-signal-scan`：Python 确定性风险规则和候选去重。
- `evidence-grounded-assessment`：检索当前生效知识版本，建立引用白名单。
- `risk-action-planner`：DeepSeek 在信息不足时返回 ASK，充分时返回带引用 PLAN 草稿。
- `weekly-risk-report`：Python 计算报告指标和生成可核对导出；目前不是模型写作能力。

风险卡一次 AI 调用实际运行其中三个 Skill：

```text
risk-signal-scan
→ evidence-grounded-assessment
→ risk-action-planner
→ Python Guardrails
→ 页面草稿
→ 人工确认闸门
```

数据接入是上游 Skill，周报是下游 Skill。不要写成“五个 AI Agent 同时协作”。

### 3. 模型安全边界

- 候选风险必须来自确定性规则，模型不能凭空创建候选。
- 模型只能使用程序提供的 `citation_id`；伪造引用会被拒绝。
- PLAN 只能有 1 至 3 条连续编号行动。
- 每条行动必须包含行动内容、负责角色和完成信号。
- AI 不能自动修改风险状态、负责人、期限或正式行动。
- 正式决策仍需用户人工确认。
- API Key 只从环境变量读取，不进入前端、日志或 Git。

## 六、已实现且可用于简历的证据

### AI 应用与工程

- 使用 Python、Flask 和 DeepSeek API 实现结构化 ASK/PLAN。
- 实现一个单 Orchestrator，将确定性风险规则、版本知识检索和行动规划串联。
- 使用 Python 校验模型 JSON、枚举字段、引用白名单、行动数量、连续步骤和完成信号。
- 模型失败时保留确定性扫描，避免整个产品不可用。
- 运行概要保留 `run_id`、模型状态和 Skill trace，不记录密钥或完整输入。

### 数据和可追溯性

- XLSX 映射为统一项目 JSON，保留源文件名、SHA-256、原始列和源表行号。
- 支持 TXT、Markdown、DOCX 与普通 PDF 离线解析，并保留原文位置。
- 知识库支持版本、生效状态、引用、冲突提示和无依据拒答。
- SQLite 包含行动、受限状态转换和追加式事件审计。
- Python 统一计算报告指标并导出 UTF-8 BOM CSV 和三表 XLSX。

### 测试和验收

- 最新累计 107 项自动测试通过。
- 覆盖非法 JSON、缺字段、伪造引用、超过 3 条行动、API 失败、请求大小、XLSX 导入、风险规则、审计、MIME 和产品入口。
- 固定模拟风险评测：TP=5、FP=1、FN=1，Precision=83.33%、Recall=83.33%。该结果仅适用于自建固定样本。
- 真实 DeepSeek 浏览器验收取得两次递进 ASK 和两次最终合法 PLAN。
- 最终运行 `ai-run-10d0ed14058e`：中风险、本周处理、3 条行动、3 条允许引用和三段完成 Skill trace。
- 872 CSS 像素宽下无页面级横向溢出，浏览器控制台无 warning/error。

## 七、推荐简历项目名称

优先使用：

**SaaSGuide｜AI 项目风险助手（个人学习 Demo）**

如果版面较窄：

**SaaSGuide｜受控 AI 风险研判 Demo**

不建议使用：

- 企业级智能风险平台
- 多 Agent 风险管理系统
- RAG 智能风控平台
- 已上线 SaaS 产品

这些名称超出了当前证据。

## 八、可作为改写基础的简历要点

以下只是基于当前仓库的证据底稿。下一对话应结合目标 JD 选择 3 至 5 条，不要全部堆进简历。

- 基于 HTML/CSS/JavaScript 与 Flask 搭建本地 AI 项目风险助手，串联 XLSX 数据接入、风险候选、证据引用、人工决策、SQLite 行动跟踪和 CSV/XLSX 报告。
- 接入 DeepSeek 结构化 ASK/PLAN：信息不足时生成追问，信息充分时输出风险等级、优先级、判断依据和带完成信号的行动草稿。
- 设计单 Orchestrator 受控 Workflow，以确定性规则生成候选、版本知识检索提供引用白名单，并由 Python 阻断非法 JSON、伪造引用和越界行动。
- 建立“AI 草稿—人工确认—审计记录”边界，模型不能自动修改风险状态、负责人、期限或正式行动；Provider 失败时确定性扫描仍可使用。
- 编写 107 项自动测试，覆盖模型输出、异常请求、XLSX 映射、风险规则、引用校验、SQLite 状态机、导出和发布回归；完成真实 DeepSeek ASK/PLAN 浏览器验收。

## 九、根据岗位方向如何取舍

### AI 应用、AIGC 产品或 AI 运营岗位

优先突出：

- LLM API 接入；
- ASK/PLAN 结构化输出；
- Agent Workflow；
- Guardrails；
- RAG 边界和引用控制；
- 人工审批；
- 真实 API 与异常测试。

### 产品助理、项目运营或数字化岗位

优先突出：

- 需求拆解；
- 数据导入和字段映射；
- 风险识别；
- 证据追溯；
- 负责人、完成信号和行动状态；
- 报告导出；
- 产品页面纠偏与用户流程优化。

### 跨境电商或跨境 AI 运营岗位

这个项目能证明 AI 应用拆解、结构化数据、工作流、校验和自动化测试，但不能证明：

- Amazon、Ozon、TikTok Shop 等平台实操；
- CTR、CVR、ACOS、ROAS 等广告指标分析；
- 库存、利润、Listing、ERP 或真实店铺运营；
- 跨境业务结果。

因此不能仅因为项目用了“风险”或“运营”字样，就把它改写为跨境运营经验。若目标是跨境岗位，应把 SaaSGuide 作为“AI 工具与自动化能力”项目，并搭配另一个真实的跨境数据/Listing/广告分析作品。

## 十、简历和面试中不能写的内容

- “帮助企业降低风险”——没有真实企业和效果数据。
- “服务真实客户或用户”——没有真实用户验证。
- “已上线生产环境”——只有 localhost Flask 开发服务。
- “实现企业级 Agent”——只有本地单 Orchestrator。
- “实现多 Agent 协作”——未实现。
- “实现向量 RAG”——当前是确定性检索，不是向量 RAG。
- “AI 自动处理风险”——AI 只生成草稿，人工负责确认。
- “完成真实 OCR/语音识别/Jira/飞书集成”——只有检测或模拟适配器边界。
- “具备大模型训练或微调经验”——项目只调用模型 API。
- 把 83.33% 写成真实业务准确率——它只是固定模拟评测结果。

## 十一、尚未实现

- P3 真实模型文本抽取。
- 向量数据库与语义向量 RAG。
- P6 模型周报叙述。
- 多 Agent 与 Agent handoff。
- 真正的多轮 Agent 会话记忆。
- 真实 OCR、语音识别和外部连接器。
- 登录、多租户、企业权限、并发和生产部署。
- GitHub 公开发布和由用户本人录制的演示视频。

这些内容可以作为后续计划，但不能写成简历已完成成果。

## 十二、建议读取顺序

下一对话不需要一开始阅读所有文件，按以下顺序即可：

1. `SAASGUIDE_RESUME_HANDOFF.md`：本文件。
2. `README.md`：运行方式和整体功能。
3. `RESUME_EVIDENCE.md`：已有简历证据边界。
4. `docs/PROJECT_STATUS.md`：当前完成和未完成状态。
5. `docs/V2_AI_ORCHESTRATION_SPEC.md`：Agent、Skill 和 Workflow。
6. `docs/test_records/V2_AI_ORCHESTRATION_TEST_RECORD_2026-09-05.md`：最新测试和真实 DeepSeek 证据。
7. `docs/V2_ARCHITECTURE.md`：架构和信任边界。
8. `DECISION_LOG.md`、`BUG_LOG.md`：关键产品取舍和真实错误。

只有在需要核对具体简历表述时，再打开对应源码：

- `services/ai/orchestrator.py`
- `services/ai/skills.py`
- `services/risk_rules/deterministic_scan.py`
- `services/retrieval/knowledge_base.py`
- `services/ingestion/xlsx_import.py`
- `database/store.py`
- `services/reporting/metrics.py`
- `test_ai_orchestrator.py`

## 十三、下一对话的推荐工作步骤

1. 完整读取用户当前简历，不要只看截图或局部文字。
2. 获取目标 JD，并把岗位要求拆成“必须、加分、无关”三类。
3. 将 JD 要求逐项与本仓库真实证据对应。
4. 标出能够直接写、需要弱化表达和完全不能写的内容。
5. 先给用户一版项目描述和修改理由。
6. 用户确认方向后再修改简历文件。
7. 若输出 DOCX，应渲染全部页面并检查分页、对齐、字体、表格和链接。
8. 最终同时交付修改后的简历和一份“每条表述对应什么证据”的说明。

## 十四、交接给下一对话的推荐提示词

用户可以在新对话中直接发送：

```text
请打开 D:\CodexProjects\SaaSGuide\SAASGUIDE_RESUME_HANDOFF.md，并按其中的读取顺序核对当前项目。你的任务是结合我随后提供的现有简历和目标 JD 修改简历，不要继续扩展项目代码。请严格区分已实现、自动测试、真实 API 验收、模拟数据、计划功能和未实现能力；任何简历表述都必须能对应仓库证据。先向我说明岗位匹配和拟修改内容，再编辑简历文件。
```
