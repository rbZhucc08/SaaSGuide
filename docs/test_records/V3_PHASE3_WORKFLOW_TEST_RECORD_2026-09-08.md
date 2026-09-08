# V3 阶段 3：完整业务闭环测试记录

日期：2026-09-08  
实现提交：`45b1fb0 feat: connect V3 risk-to-action workflow`

## 目标和非目标

目标是让扫描批次、候选、风险人工决策、PLAN 草稿、行动人工确认、状态事件和报告共享可追溯 ID。本阶段没有让 AI 自动保存行动，也没有增加权限、通知、外部写回或新 Agent。

## 修改文件

- `services/risk_rules/deterministic_scan.py`：增加稳定 `scan_id`、`decision_id` 和候选决策元数据；
- `database/store.py`：Schema v2、迁移前备份、候选与风险决策入库、行动决策闸门、PLAN 追溯字段和可重开状态机；
- `server.py`：风险决策同步到 SQLite、报告按候选读取最新决策并返回追溯 ID；
- `risk-radar.js`：PLAN 草稿预填入口；风险确认前入口禁用；
- `action-tracker.html/css/js`：PLAN 步骤选择、预填和第二次人工确认；
- `test_v3_workflow.py`、`test_sqlite_store.py`、`test_release.py`：闭环、迁移、状态和前端保护测试；
- `docs/specs/V3_PHASE3_END_TO_END_WORKFLOW_SPEC.md`：阶段规格。

## 数据库迁移

- Schema 版本：1 → 2；
- 兼容策略：只增加候选来源/扫描/证据字段，以及行动的风险决策、PLAN run 和步骤字段；
- 备份：检测到已有 v1 数据库时，迁移前自动创建 `*.db.pre-v2.bak`；自动测试验证备份存在并验证新列；
- 本轮浏览器运行库位于 `generated/`，未进入 Git。

## 自动测试

命令：

```powershell
& '.\run_checks.ps1'
git -c safe.directory=D:/CodexProjects/SaaSGuide diff --check
```

实际结果：139 项 Python 测试通过；JSON、78 个 Markdown 本地链接和全部 JavaScript 语法检查通过；`git diff --check` 无错误。

新增覆盖包括：无风险确认禁止行动、无行动确认禁止保存、决策 ID 不匹配、最新非确认决策阻断行动、PLAN run/step 追溯、完成、重开、撤销、非法转换、报告 ID 回溯和 v1 迁移备份。

## 浏览器验收

- 环境：Codex 应用内 Chromium，桌面视口，本地 Flask；
- 模拟项目：星云数科（模拟）/ 企业客户单点登录上线；
- 步骤与结果：
  1. 在风险雷达扫描所选项目，生成 7 条候选和 11 次规则命中；
  2. 对首条候选尝试一次真实 DeepSeek 研判，页面明确返回“无法连接 DeepSeek，请检查网络后重试”；规则结果和人工按钮仍可用；
  3. 人工确认候选 `candidate-7c730a7f99b4a1ed`；
  4. 在行动跟踪手工填写负责人、期限、完成信号和确认人，并勾选第二次人工确认；
  5. 成功创建行动 `action-186b3c1327f9`；
  6. 依次操作进行中、完成、重新打开和撤销，最终状态为 `cancelled`；
  7. 报告显示 1 条候选、1 条高风险、1 条已确认和同一行动明细；
- 控制台：warn/error 为 `[]`；
- 截图：`docs/test_records/v3_phase3_workflow_2026-09-08/report-after-workflow.png`。

## 真实 API

真实 DeepSeek 调用尝试 1 次，失败原因是当前网络无法连接。没有取得 ASK 或 PLAN，也没有把失败写成成功证据。发送内容只有仓库内虚构候选、虚构项目和模拟制度上下文。

## 结果

- 通过：规则扫描到风险确认、行动确认、状态审计和报告的无模型降级链路；数据库迁移与自动测试；
- 失败：本轮真实 DeepSeek 网络调用未完成；
- 未验证：浏览器没有取得真实 PLAN，因此 PLAN 预填由前端契约测试和服务端闭环测试覆盖，真实浏览器预填仍待外部网络恢复后复核。

## 已知限制

- 文件 JSONL 与 SQLite 是两个本地持久层，单次决策写入无法提供跨文件的原子事务；失败会返回错误并需要人工复核运行日志；
- 当前状态机和审计只适用于本地单用户；
- 报告数字来自最新人工决策与本地行动，不代表真实企业效果。
