# V2 AI 编排纠偏规格

## 目标

在不削弱确定性证据链的前提下，把 DeepSeek 恢复到 V2 的风险研判主流程，并把原交接文档中的五个项目领域 Skill 明确为可检查的运行合约。

## Agent、Skill 与 Workflow

- Agent：`saasguide-v2-orchestrator`，一个受控协调器，不是多 Agent 系统。
- `project-data-intake`：调用既有 XLSX/文本/PDF 接入工具，生成带来源的数据或证据。
- `risk-signal-scan`：调用 Python 确定性规则，生成带原字段证据的候选风险。
- `evidence-grounded-assessment`：只检索当前生效的知识版本，向模型提供引用白名单。
- `risk-action-planner`：由 DeepSeek 在信息不足时返回 ASK，信息充分时返回带引用 PLAN 草稿。
- `weekly-risk-report`：继续由 Python 计算并生成可复核报告；当前没有把模型叙述包装成已完成能力。

风险研判 Workflow：

```text
已校验项目数据
  -> 确定性风险扫描
  -> 当前生效知识检索
  -> DeepSeek ASK / PLAN
  -> Python 结构、字段、步骤与引用校验
  -> 页面展示草稿与 Skill trace
  -> 人工另行确认
```

## 强制边界

- 模型不能创建候选风险，候选必须来自确定性规则。
- 没有知识引用时不能输出 PLAN；模型只能使用程序给出的 `citation_id`。
- PLAN 最多 3 条连续编号行动，每条必须有角色与完成信号。
- AI 结果不能自动修改风险状态、负责人、期限或行动记录。
- API 密钥只从环境变量读取；能力端点只返回是否配置，不返回密钥。
- 运行日志只记录运行号、候选号、模型状态和 Skill trace，不记录密钥或完整用户输入。

## 不在本次范围

- P3 的真实模型文本抽取。
- 向量数据库或语义向量 RAG。
- P6 的真实模型周报叙述。
- 多 Agent、跨 Agent handoff、OCR、语音识别和真实外部连接器。

这些项目仍是后续能力，不能因本次增加一个 Orchestrator 而写成已完成。
