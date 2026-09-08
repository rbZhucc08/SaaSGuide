# SaaSGuide V2 源码学习指南

更新基线：2026-09-08，以提交 `4db9653` 为前一发布基线的 V2 作品集版本。

这份文档写给不熟悉代码和 Git 的项目所有者。阅读后应能回答三个问题：页面为什么这样设计、一次风险处理是怎么运行的、每项说法可以去哪里核实。

## 1. 先建立正确理解

SaaSGuide 当前用于演示一套本地项目风险处理流程。DeepSeek 通过 API 参与风险研判，模型本身由服务商完成训练。当前版本尚未进入真实企业或线上生产环境。

主要流程包括：

1. 接收项目、任务和制度数据；
2. 用 Python 规则发现候选风险；
3. 读取当前公司的有效制度；
4. 按需调用 DeepSeek，返回追问 `ASK` 或行动草稿 `PLAN`；
5. 用 Python 校验模型结构和引用；
6. 由人决定是否确认、观察或驳回；
7. 保存行动、审计记录并生成报告。

核心链路是：

```text
数据接入
→ 结构校验
→ 确定性风险扫描
→ 当前制度检索
→ DeepSeek ASK / PLAN
→ Python 输出校验
→ 人工确认
→ 行动、审计和报告
```

## 2. 打开文件夹时先看什么

第一次了解项目，不要从 `.git`、测试文件或 50,000 多字节的 `server.py` 开始。

建议按这个顺序：

1. [README](README.md)：项目首页和总体结论；
2. [HR 项目讲解稿](docs/portfolio/HR_PROJECT_EXPLAINER.md)：用通俗语言学习怎么介绍；
3. [功能说明](docs/product/FEATURE_GUIDE.md)：每个页面能做什么；
4. [AI Agent 工作流](docs/architecture/AI_AGENT_WORKFLOW.md)：DeepSeek 和程序怎样配合；
5. [系统架构](docs/architecture/SYSTEM_ARCHITECTURE.md)：文件和模块怎样连接；
6. [证据索引](docs/portfolio/EVIDENCE_INDEX.md)：功能对应哪些代码和测试。

历史阶段记录仍保留在仓库中，但它们描述的是当时状态。判断当前能力时，以 README、`docs/PROJECT_STATUS.md` 和最新验收记录为准。

根目录中的 `PHASE*_TEST_RECORD.md`、`DEMO_SCRIPT.md`、`PROJECT_BRIEF.md` 和 `SAASGUIDE_*_HANDOFF.md` 属于历史记录或交接材料。它们用于追溯项目变化，不是当前版本的首选说明。

## 3. 项目文件夹的分区

```text
SaaSGuide/
├─ README.md                    对外项目首页
├─ server.py                    Flask 服务和 API 入口
├─ start_v2.ps1                Windows 启动脚本
├─ run_checks.ps1              一键运行自动检查
│
├─ index.html / styles.css / app.js
│                               首页结构、样式和交互
├─ data-sources.*              公司、项目、制度和 XLSX 数据页
├─ risk-radar.*                风险扫描、AI 研判和评测页
├─ evidence-intake.*           文本证据接入页
├─ knowledge-base.*            制度检索页
├─ action-tracker.*            人工确认后的行动页
├─ reports.*                   指标和导出页
├─ input-lab.*                 PDF、WAV 和适配器实验页
│
├─ services/
│  ├─ ingestion/               XLSX、文本、PDF、WAV 接入
│  ├─ company_data/            多公司数据和当前公司上下文
│  ├─ risk_rules/              确定性风险规则
│  ├─ retrieval/               版本化制度检索
│  ├─ ai/                      Orchestrator 和 Skill 合约
│  ├─ reporting/               指标、CSV 和 XLSX
│  ├─ evaluation/              跨公司固定规则评测
│  └─ adapters/                模拟外部系统适配器边界
│
├─ database/store.py           SQLite 行动和事件审计
├─ data/                       模拟 Seed、样本和固定标准答案
├─ docs/                       产品、架构、作品集和质量文档
├─ test_*.py                   自动测试
└─ .git/                       Git 的本地历史数据，不要手工修改
```

同名的 `.html`、`.css`、`.js` 可以理解为一个页面的三层：

- HTML 决定页面有哪些区域和按钮；
- CSS 决定颜色、尺寸和布局；
- JavaScript 负责点击、请求 API 和更新页面内容。

## 4. 页面和代码如何对应

| 页面 | 前端文件 | 主要服务端能力 |
|---|---|---|
| 首页 `/` | `index.html`、`styles.css`、`app.js` | `/api/dashboard` |
| 数据源 `/data-sources` | `data-sources.html/.css/.js` | 公司数据、项目扫描、XLSX 导入 API |
| 风险雷达 `/risk-radar` | `risk-radar.html/.css/.js` | 规则扫描、AI 研判、开发评测 API |
| 文本证据 `/evidence-intake` | `evidence-intake.html/.css/.js` | 文本预览与人工核对 API |
| 知识库 `/knowledge-base` | `knowledge-base.html/.css/.js` | 检索回答和固定评测 API |
| 行动跟踪 `/action-tracker` | `action-tracker.html/.css/.js` | SQLite 行动和状态转换 API |
| 报告 `/reports` | `reports.html/.css/.js` | 周报指标和文件导出 API |
| 输入实验室 `/input-lab` | `input-lab.html/.css/.js` | PDF、WAV 和模拟适配器 API |

`server.py` 把这些页面和服务连接起来。它本身不是所有业务逻辑的所在地；具体规则、检索、AI 和报告被拆进 `services/`，这样更容易单独测试。

## 5. 一次风险扫描怎样运行

假设用户在“风险雷达”选择一个项目并点击扫描：

1. `risk-radar.js` 收集项目和扫描日期；
2. 浏览器向 Flask API 发送请求；
3. `server.py` 读取当前公司的项目、任务和风险标准；
4. `services/risk_rules/deterministic_scan.py` 执行规则；
5. 规则返回候选风险、严重度、原始证据和触发原因；
6. 页面把候选展示给用户，但不会自动写成正式风险。

当前确定性规则主要检查：

- 未完成且已经逾期；
- 临近截止且进度偏低；
- 任务本身处于阻塞；
- 直接依赖任务处于阻塞。

这里先用规则，是因为日期比较、进度阈值和直接依赖可以明确计算。把这些全部交给模型，会增加费用、波动和解释成本。

## 6. 一次 DeepSeek 研判怎样运行

用户选择候选风险并请求 AI 研判后：

1. `services/ai/orchestrator.py` 读取候选风险；
2. 读取当前公司画像和风险标准；
3. `services/retrieval/knowledge_base.py` 找到当前生效制度；
4. Orchestrator 生成本次允许引用的制度白名单；
5. 明显缺少信息时，本地程序先返回 `ASK`，避免无效调用；
6. 信息足够时，服务端调用 DeepSeek；
7. DeepSeek 返回 JSON 格式的 `ASK` 或 `PLAN`；
8. Python 再检查字段、行动数量、步骤顺序、负责人角色和引用；
9. 合法结果才显示在页面上；
10. 用户仍需人工确认，模型不能直接修改正式记录。

### ASK 是什么

`ASK` 表示信息不足，需要追问。例如没有明确影响范围、责任角色、时间点或依赖证据。

### PLAN 是什么

`PLAN` 是带依据和引用的行动草稿。合法 PLAN 最多三条行动，每条要有负责人角色和完成信号，并且只能引用本次允许的制度。

### Agent 和 Skill 是什么

当前只有一个 Python Orchestrator，不是多个 AI Agent 自治协作。

项目中的五个 Skill 是领域步骤合约：

- `project-data-intake`：整理输入数据；
- `risk-signal-scan`：生成候选风险；
- `evidence-grounded-assessment`：准备有依据的上下文；
- `risk-action-planner`：让 DeepSeek 返回 ASK 或 PLAN；
- `weekly-risk-report`：从确认记录生成报告。

一次 AI 研判实际使用中间三个步骤。数据接入在上游，周报是独立的确定性流程。

## 7. 多公司数据为什么存在

项目包含 6 家虚构公司、30 个项目、180 条任务和 48 个制度版本。它们覆盖企业软件、跨境电商、制造、物流、营销服务和医疗信息化。

这些数据有两个作用：

1. 检查系统切换公司后，项目、制度、阈值和模型上下文是否跟着切换；
2. 构造不同业务背景，避免只在同一种模板上自我验证。

它们不是训练数据，也不能证明系统已经服务过六家公司。`company_id` 只是本地上下文隔离，不是带账号权限的生产多租户。

## 8. 评测数字应该怎样理解

跨公司固定规则基准得到：

- TP=119；
- FP=4；
- FN=18；
- Precision=96.75%；
- Recall=86.86%；
- 严重度一致率=100%。

这组数据来自作者构造并标注的合成回归集，只能说明当前规则在固定案例上的表现。项目尚未取得 DeepSeek 批量准确率或企业环境准确率的证据。

当前 DeepSeek 证据是少量真实浏览器调用：两次递进 ASK 和一次合法 PLAN。跨公司 30 个项目没有批量调用 DeepSeek，因此不能把预期的 ASK/PLAN 当成模型实际成绩。

## 9. 数据保存在哪里

- 版本化模拟数据保存在 `data/`；
- 用户导入、运行日志、模型结果和本地备份主要保存在 `generated/`；
- 行动和事件审计使用本地 SQLite；
- `generated/`、用户导入和 `.env` 被 `.gitignore` 排除，不进入 Git；
- DeepSeek 密钥只应放在当前进程环境变量中。

因此 Git 中主要保存代码、模拟 Seed、测试和文档，不保存个人运行结果或 API 密钥。

## 10. 自动测试在验证什么

运行：

```powershell
& '.\run_checks.ps1'
```

当前固定结果为 135 项测试通过，同时检查 JSON 数据一致性和前端 JavaScript 语法。

测试覆盖数据导入、规则、检索、SQLite、报告、AI 输出校验、多公司上下文、固定评测和发布文件。自动测试不能代替真实浏览器、真实企业数据或生产负载验证。

## 11. 推荐的源码阅读练习

### 练习一：看懂页面如何请求数据

1. 打开 `risk-radar.html`，找到按钮和结果容器；
2. 打开 `risk-radar.js`，搜索 `/api/risk-scans/`；
3. 在 `server.py` 搜索同一个 API；
4. 再看 `services/risk_rules/deterministic_scan.py`。

这样可以看到“按钮 → 浏览器请求 → API → 业务规则 → 页面结果”的完整关系。

### 练习二：看懂模型为什么不能乱引用

1. 打开 `services/ai/orchestrator.py`；
2. 搜索 `allowed`、`citation` 或 `reference`；
3. 查看 `test_ai_orchestrator.py` 中伪造引用和非法结构测试；
4. 对照 [AI Agent 工作流](docs/architecture/AI_AGENT_WORKFLOW.md)。

### 练习三：看懂评测限制

1. 查看 `data/evaluation/company_scenario_expected.json`；
2. 查看 `services/evaluation/company_benchmark.py`；
3. 阅读 [评测说明](docs/quality/EVALUATION_REPORT.md)；
4. 区分“规则固定基准”和“DeepSeek 真实调用”。

## 12. 修改项目时的安全习惯

修改前：

```powershell
git status
```

修改后先检查和测试：

```powershell
& '.\run_checks.ps1'
git diff
```

确认内容后再保存为新的 Git 版本：

```powershell
git add 具体文件名
git commit -m "说明这次修改做了什么"
```

不要手动修改 `.git`，也不要在不理解影响时使用 `git reset --hard`。

## 13. 你真正需要掌握的结论

你不需要声称自己从零手写了每一行代码。你需要能够解释并核实：

- 为什么规则、模型和人工判断被分开；
- 为什么模型输出必须经过结构与引用校验；
- 为什么多公司模拟数据不是训练数据；
- 为什么固定评测不能当作企业准确率；
- 当前项目已经实现什么，还有什么没实现；
- 每个结论可以在哪个页面、代码或测试记录中找到。

能讲清这些边界，比背诵文件名或代码行数更能证明你理解了这个项目。
