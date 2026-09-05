# SaaSGuide V2 AI 编排纠偏验收记录

## 验收结论

V2 风险雷达已真实接入 DeepSeek，并完成“确定性候选 -> 生效知识引用 -> ASK/PLAN -> Python 校验 -> 人工确认隔离”的受控编排。当前是一个 Orchestrator Agent，不是多 Agent 系统。

## 自动测试

- `& '.\.venv\Scripts\python.exe' -m unittest discover -v`：107 项通过，0 项失败，0 项错误。
- `& '.\.venv\Scripts\python.exe' validate_data.py`：通过。
- `node --check risk-radar.js`：通过。
- `git diff --check`：无空白错误，仅有 Windows 行尾提示。
- 新增覆盖：五个 Skill 合约、本地缺信息 ASK、不调用模型、合法 PLAN、伪造引用拦截、超过 3 条行动拦截、Agent API 依赖注入、Provider 失败映射、能力端点不泄露密钥、前端调用入口和 `nosniff` 下的正确资源 MIME。

## 真实 DeepSeek 浏览器验收

环境：Codex 应用内 Chromium、`http://127.0.0.1:4173/risk-radar`、已配置环境变量、模型 `deepseek-v4-flash`。发送内容只有仓库内虚构项目候选、模拟补充信息和自建模拟知识文档。

实际结果：

- `ai-run-daffe9f18fd7`：返回 ASK，要求补充延期原因、依赖/里程碑影响和恢复计划。
- `ai-run-c960fcf3a086`：补充部分信息后仍返回 ASK，进一步要求截止日期变更审批、下游影响评估以及新完成日期写入系统的确认记录。
- 两次复杂 PLAN 尝试曾返回空内容；页面明确报错，没有生成或保存伪造结果。随后将 JSON 输出上限从 2000 调整为 4000 token，并把 PLAN 收紧为最多 3 条行动。
- `ai-run-56ed8c8b8e70`：真实返回 PLAN。页面显示中风险、立即处理、3 条行动草稿、3 条允许引用，以及以下运行轨迹：
  - `risk-signal-scan · completed · 2 rule hit(s) supplied`
  - `evidence-grounded-assessment · completed · 3 effective citation(s) retrieved`
  - `risk-action-planner · completed · DeepSeek returned PLAN`
- 完成 1 至 3 条行动的最终校验收紧并重启服务后，`ai-run-10d0ed14058e` 再次返回合法 PLAN：中风险、本周处理、3 条行动、3 条允许引用和相同的三段完成轨迹。

页面截图检查中，AI 面板与既有 V2 卡片风格一致，文字换行正常；872 CSS 像素宽下 `scrollWidth` 与 `clientWidth` 均为 872，无页面级横向溢出，浏览器控制台无 warning/error。验收没有点击“确认”，因此没有把 AI 草稿写成正式行动或正式风险。

## 真实性边界

- 真实 API 验收证明的是当前固定模拟输入下的 ASK/PLAN 行为，不证明模型在真实企业数据上的准确率或稳定性。
- 3 条引用来自自建小型知识库，不是向量 RAG，也不证明大规模检索质量。
- 五个 Skill 是项目运行时领域合约；本次 DeepSeek 风险调用实际运行其中三个。数据接入在其上游，周报仍由确定性 Python 生成。
- Codex 开发过程使用的 `openai-docs`、`computer-use` 等 Codex Skills 与产品运行时 Skills 是两套概念，不能混称。
