# V3 证据索引

本索引用来区分代码、自动检查、浏览器证据、真实 API 和外部验证。简历、演示或发布文案都应能指向相应证据。

## 当前发布基线

| 项目 | 当前证据 |
|---|---|
| 分支 | `codex/v3-development` |
| 发布状态 | `3.0.0-portfolio-candidate` 私有 GitHub 候选；尚无 tag 或 Release |
| 自动检查 | 186 项测试通过；关键模块语句覆盖率 89.04%；GitHub Actions 四项矩阵通过 |
| 干净环境 | VPN 保持连接，从官方 PyPI 安装锁定依赖并完整通过检查 |
| 数据规模 | 6 家虚构公司、30 个项目、180 条任务、48 个制度版本 |
| 规则基准 | TP=119、FP=4、FN=18、Precision=96.75%、Recall=86.86% |
| 模型 | DeepSeek ASK/PLAN；历史少量真实浏览器调用有独立记录 |
| 飞书 | 多维表格只读连接器底座；真实授权与同步未完成 |
| 业务验证 | 研究与分析工具完成；真实参与者 0 |
| 部署 | 本地 `127.0.0.1`；未公开部署 |

## V3 分阶段证据

| 阶段 | 已验证内容 | 验收记录 |
|---|---|---|
| 1 信息架构 | 当前入口、历史归档、文档链接 | [阶段 1](../test_records/V3_PHASE1_INFORMATION_ARCHITECTURE_TEST_RECORD_2026-09-08.md) |
| 2 UI | 工作台重构、桌面与移动布局、关键 DOM/API 保持 | [阶段 2](../test_records/V3_PHASE2_UI_TEST_RECORD_2026-09-08.md) |
| 3 业务闭环 | 数据到风险、双人工闸门、行动与报告追溯 | [阶段 3](../test_records/V3_PHASE3_WORKFLOW_TEST_RECORD_2026-09-08.md) |
| 4 评测 | 盲标工具、分层指标和错误分类 | [阶段 4](../test_records/V3_PHASE4_EVALUATION_TEST_RECORD_2026-09-08.md) |
| 5 模型可靠性 | 输出协议、重试、预算、错误和可观察性 | [阶段 5](../test_records/V3_PHASE5_MODEL_RELIABILITY_TEST_RECORD_2026-09-09.md) |
| 6 检索 | 混合排序、版本冲突、引用定位和注入防护 | [阶段 6](../test_records/V3_PHASE6_KNOWLEDGE_RETRIEVAL_TEST_RECORD_2026-09-09.md) |
| 7 工程 | Blueprint、覆盖率、类型、CI 定义和跨平台检查 | [阶段 7](../test_records/V3_PHASE7_ENGINEERING_TEST_RECORD_2026-09-09.md) |
| 8 安全 | 敏感样式、压缩边界、限流、密钥检查和威胁模型 | [阶段 8](../test_records/V3_PHASE8_SECURITY_GOVERNANCE_TEST_RECORD_2026-09-09.md) |
| 9 飞书 | 只读连接器、分页、幂等、错误恢复和未授权状态 | [阶段 9](../test_records/V3_PHASE9_FEISHU_CONNECTOR_TEST_RECORD_2026-09-09.md) |
| 10 发布 | 历史审计、干净环境复现和本地发布候选 | [阶段 10](../test_records/V3_PHASE10_PORTFOLIO_RELEASE_TEST_RECORD_2026-09-09.md) |
| 11 试点 | 协议、证据校验、描述性分析和外部证据状态 | [阶段 11](../test_records/V3_PHASE11_REAL_WORLD_VALIDATION_TEST_RECORD_2026-09-09.md) |

私有仓库创建、首次 CI 失败和修复后的四项矩阵通过记录见 [V3 私有 GitHub 发布验收](../test_records/V3_PRIVATE_GITHUB_PUBLISH_TEST_RECORD_2026-09-09.md)。

## 核心实现入口

| 能力 | 实现与测试 |
|---|---|
| XLSX 接入 | `services/ingestion/xlsx_import.py`、`test_xlsx_import.py` |
| 风险扫描 | `services/risk_rules/deterministic_scan.py`、`test_risk_rules.py` |
| 知识检索 | `services/retrieval/knowledge_base.py`、`test_document_retrieval.py` |
| AI 编排 | `services/ai/orchestrator.py`、`services/ai/provider.py`、`test_ai_orchestrator.py` |
| 行动审计 | `database/store.py`、`test_sqlite_store.py` |
| 报告 | `services/reporting/metrics.py`、`test_reporting.py` |
| 安全治理 | `services/security/governance.py`、`test_security_governance.py` |
| 飞书只读连接器 | `services/connectors/feishu_bitable.py`、`test_feishu_connector.py` |
| 真实试点分析 | `services/validation/pilot.py`、`test_pilot_validation.py` |

## 浏览器与截图

- README 当前截图：`docs/assets/overview.png`、`data-sources.png`、`risk-radar.png`；
- V3 各阶段截图保存在对应 `docs/test_records/v3_phase*/` 目录；
- 阶段 11 外部证据待完成页面：[截图](../test_records/v3_phase11_validation_2026-09-09/external-validation-pending.jpg)。

## 不能推出的结论

- 自动测试通过不等于生产稳定；
- 合成基准不等于真实企业准确率；
- 一次合法 PLAN 不等于模型长期稳定或具有 SLA；
- `company_id` 上下文切换不等于生产多租户；
- 本地稀疏词频向量不等于 Embedding 或向量数据库；
- 飞书模拟 HTTP 合约不等于真实授权和同步；
- 研究工具不等于已经完成真实用户验证；
- 当前一次在线 GitHub Actions 四项矩阵通过不等于生产稳定或长期持续通过。
