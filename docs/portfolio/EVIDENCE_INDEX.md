# 证据索引

这份索引用来区分“代码存在”“自动测试通过”“浏览器看见”和“真实外部服务调用”。任何简历或演示表述都应能指向对应证据。

## 当前发布基线

| 项目 | 当前证据 |
|---|---|
| 分支 | `v2-phase8-release` |
| 跨公司评测提交 | `cac64aa feat: add cross-company risk benchmark` |
| 自动测试 | 135 项通过 |
| 数据规模 | 6 公司、30 项目、180 任务、48 制度版本 |
| 规则基准 | TP=119、FP=4、FN=18、Precision=96.75%、Recall=86.86% |
| 模型 | DeepSeek ASK/PLAN；真实浏览器调用有独立记录 |
| 部署 | 本地 `127.0.0.1`；未公开部署 |

本地发布包的提交号以 `git log -1 --oneline` 为准；当前未配置远程仓库，也未推送或创建 GitHub Release。

## 功能证据

| 能力 | 实现文件 | 测试/验收 |
|---|---|---|
| XLSX 映射和确认 | `services/ingestion/xlsx_import.py` | `test_xlsx_import.py`、V2-P1 验收记录 |
| 风险扫描和去重 | `services/risk_rules/deterministic_scan.py` | `test_risk_rules.py`、V2-P2 验收记录 |
| 文本证据 | `services/ingestion/text_evidence.py` | `test_text_evidence.py`、V2-P3 验收记录 |
| 版本化知识检索 | `services/retrieval/knowledge_base.py` | `test_knowledge_base.py`、V2-P4 验收记录 |
| SQLite 行动审计 | `database/store.py` | `test_sqlite_store.py`、V2-P5 验收记录 |
| CSV/XLSX 报告 | `services/reporting/metrics.py` | `test_reporting.py`、V2-P6 验收记录 |
| PDF/WAV/适配器边界 | `services/ingestion/pdf_audio.py`、`services/adapters/contracts.py` | `test_multimodal_adapters.py`、V2-P7 验收记录 |
| 本地发布和安全头 | `server.py`、`start_v2.ps1` | `test_release.py`、V2-P8 验收记录 |
| DeepSeek 编排 | `services/ai/orchestrator.py`、`services/ai/skills.py` | `test_ai_orchestrator.py`、AI 编排验收记录 |
| 多公司数据 | `services/company_data/store.py` | `test_company_data.py`、多公司数据验收记录 |
| 跨公司规则基准 | `services/evaluation/company_benchmark.py` | `test_company_benchmark.py`、跨公司评测验收记录 |

## 关键验收记录

- [V2-P1 数据接入](../test_records/V2_PHASE1_TEST_RECORD_2026-09-04.md)
- [V2-P2 风险扫描](../test_records/V2_PHASE2_TEST_RECORD_2026-09-04.md)
- [V2-P3 文本证据](../test_records/V2_PHASE3_TEST_RECORD_2026-09-04.md)
- [V2-P4 知识检索](../test_records/V2_PHASE4_TEST_RECORD_2026-09-04.md)
- [V2-P5 行动审计](../test_records/V2_PHASE5_TEST_RECORD_2026-09-05.md)
- [V2-P6 报告导出](../test_records/V2_PHASE6_TEST_RECORD_2026-09-05.md)
- [V2-P7 多模态边界](../test_records/V2_PHASE7_TEST_RECORD_2026-09-05.md)
- [V2-P8 本地发布](../test_records/V2_PHASE8_TEST_RECORD_2026-09-05.md)
- [DeepSeek 与 Orchestrator](../test_records/V2_AI_ORCHESTRATION_TEST_RECORD_2026-09-05.md)
- [UI/UX 精修](../test_records/V2_UI_REFINEMENT_TEST_RECORD_2026-09-07.md)
- [多公司数据](../test_records/V2_MULTI_COMPANY_DATA_TEST_RECORD_2026-09-08.md)
- [差异化业务数据](../test_records/V2_DIFFERENTIATED_COMPANY_DATA_TEST_RECORD_2026-09-08.md)
- [跨公司规则基准](../test_records/V2_CROSS_COMPANY_BENCHMARK_TEST_RECORD_2026-09-08.md)

## 浏览器证据

- 当前发布截图：`docs/assets/`；
- 8 个页面的桌面和移动端前后对照：`docs/test_records/ui_baseline_2026-09-07/`；
- DeepSeek ASK/PLAN 细节：AI 编排与 UI 精修验收记录；
- 跨公司评测结果：2026-09-08 跨公司基准验收记录。

## 不能从这些证据推出的结论

- 自动测试通过不等于生产稳定；
- 固定模拟评测不等于真实企业准确率；
- 一次合法 PLAN 不等于模型长期稳定；
- `company_id` 上下文隔离不等于生产多租户；
- PDF 文本提取不等于真实 OCR；
- WAV 元数据检查不等于语音识别；
- 模拟适配器不等于已经连接 Jira、飞书或其他平台。
