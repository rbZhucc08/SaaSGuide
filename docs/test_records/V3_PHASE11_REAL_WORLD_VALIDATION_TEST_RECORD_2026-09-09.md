# V3 阶段 11：真实业务验证准备与外部证据状态记录

## 目标与结论

本阶段把真实业务验证限定为“项目负责人审查延期风险，并决定是否接受、修改或拒绝后续行动建议”，完成研究协议、试用任务、记录模板、证据校验器、描述性分析器和浏览器状态页。

实现提交：`accdbf8 feat: prepare V3 external pilot validation`

当前没有真实参与者、参与同意或授权数据。因此准确结论是：**验证工具与试点方案完成，真实业务验证待外部证据**。不能把模拟用户、测试夹具或 Codex 自行填写的结果称为真实验证。

## 修改与数据边界

- `docs/specs/V3_PHASE11_REAL_WORLD_VALIDATION_SPEC.md`：阶段规格与真实完成条件；
- `docs/validation/PILOT_RESEARCH_PROTOCOL.md`：参与者、授权、流程、停止条件和偏差；
- `docs/validation/INTERVIEW_AND_TRIAL_GUIDE.md`：访谈问题与统一试用任务；
- `docs/validation/RESULT_RECORD_TEMPLATE.md`：基线、试用和建议处置编码；
- `data/validation/phase11_study_template.json`：不含参与者的空白结构模板；
- `services/validation/pilot.py`：授权、去标识化、同意和身份字段校验，以及描述性统计；
- `scripts/analyze_pilot_results.py`：本地分析入口；
- `/api/validation/status` 与 `/validation`：只读状态接口和外部验证页面。

真实结果应保存在被 Git 忽略的 `generated/validation/pilot-results.json`。姓名、联系方式、公司名、账号、客户信息和原始访谈笔记不得进入 Git。没有数据库迁移，也没有把测试夹具保存成真实结果。

## 自动测试

专项运行：

```powershell
& '.\.venv\Scripts\python.exe' -m unittest -v test_pilot_validation.py
```

5 项通过，覆盖：

- 没有证据文件时保持 `external_evidence_required`；
- 授权、去标识化并取得同意的结构化小样本可生成描述性指标；
- 身份字段被拒绝；
- 缺少授权被拒绝；
- 状态 API 与页面明确显示外部证据待完成。

空白模板通过命令行分析时返回退出码 2，并提示必须确认数据授权，证明占位模板不会被算作真实证据。

全量运行：

```powershell
& '.\run_checks.ps1'
```

最终结果：

- 186 项 `unittest` 通过；
- 关键模块语句覆盖率 398/447，即 89.04%；
- 类型契约、Git 跟踪文件密钥扫描、JSON 数据和 78 个 Markdown 本地链接通过；
- 11 个前端 JavaScript 文件语法检查通过；
- `git diff --check` 通过。

## 浏览器验收

浏览器：Codex 应用内 Chromium。

地址：`http://127.0.0.1:4176/validation`。

页面验证：

- 标题为“SaaSGuide｜业务验证”；
- 首屏显示“验证真实使用，而不是模拟认可”；
- 动态状态为“外部证据待完成”；
- 真实参与者为 0，建议处置为 0；
- 页面列出取得同意、记录基线、完成试用和保留拒绝四步；
- 页面明确说明建议接受率不等于正确率，小样本不证明因果、总体效果、商业价值或生产可用性；
- Chromium `warning` 和 `error` 控制台日志为 0。

截图：`docs/test_records/v3_phase11_validation_2026-09-09/external-validation-pending.jpg`。

## 真实 API 与外部依赖

- 没有调用真实飞书或 DeepSeek API；
- 没有邀请或模拟任何真实参与者；
- 没有收集访谈、授权或真实公司数据；
- 真实完成至少需要目标角色参与者、明确同意、授权且去标识化的数据、相同范围的流程基线，以及逐条建议的接受、修改和拒绝记录；
- 即使取得少量记录，系统状态也只称 `pilot_evidence_available`，不称“产品已验证”。

阶段 11 的代码、研究流程和待证据状态可以独立验收；真实业务验证本身无法由本地开发继续完成，必须等待项目所有者组织真实试点。
