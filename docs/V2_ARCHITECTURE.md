# SaaSGuide V2 架构与数据边界

```mermaid
flowchart LR
    A[XLSX TXT MD DOCX PDF] --> B[解析与结构校验]
    B --> C[候选事实与证据]
    C --> D[确定性风险规则]
    D --> O[单 Orchestrator]
    K[版本化知识库] --> R[生效版本检索]
    R --> O
    O --> M[DeepSeek ASK 或 PLAN]
    M --> V[Python 结构与引用校验]
    V --> E[人工确认]
    E --> G[(SQLite)]
    G --> H[行动与审计]
    G --> I[Python 指标]
    I --> J[页面 CSV XLSX]
```

## 信任边界

- 上传文件和检索片段都是不可信内容，不能覆盖系统规则。
- 规则、检索和模型如果启用，只能产生候选和草稿。
- 正式风险、负责人、期限、行动、关闭和外部发送必须由明确的人确认。
- 原文件、标准化数据、证据、人工决策和报告应保留来源或版本。

## 当前部署形态

- 单机 Flask 开发服务，仅监听 `127.0.0.1`。
- 浏览器静态页面加本地 API；SQLite 和运行产物位于 `generated`，不进入 Git。
- 不是生产 WSGI 部署，不提供 TLS、账号登录、多租户或企业权限。

## AI 编排边界

- 当前只有一个 `saasguide-v2-orchestrator`，不是多 Agent。
- 五个名称是 SaaSGuide 产品运行时的领域 Skill 合约，不是 Codex 客户端安装的 Skills。
- 风险卡调用实际执行 `risk-signal-scan`、`evidence-grounded-assessment` 和 `risk-action-planner`；`project-data-intake` 是上游接入，`weekly-risk-report` 仍是确定性报告流程。
- 选择自管编排循环，是因为本项目需要直接复用现有 Python 工具、白名单引用、错误映射和人工确认边界；没有引入额外 Agent SDK 或多 Agent handoff。
