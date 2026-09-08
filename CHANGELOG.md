# Changelog

本文件记录面向使用者的主要变化。各开发阶段的详细证据保留在 `docs/test_records/`。

## [Unreleased]

- 准备私有作品集发布包：统一 README、PRD、用户手册、架构图、案例说明、质量文档、MIT License 和 GitHub Actions。

## [2.0.0-portfolio] - 2026-09-08

### Added

- 6 家差异化模拟公司、30 个项目、180 条任务和 48 个制度版本；
- 多公司画像、项目、任务和知识版本的本地 CRUD 与上下文切换；
- XLSX、TXT、Markdown、DOCX、普通 PDF 数据接入；
- 确定性风险扫描、来源证据、候选去重和人工决策记录；
- 单 Orchestrator、五个领域 Skill 合约、DeepSeek ASK/PLAN 和引用白名单；
- SQLite 行动状态与事件审计；
- CSV/XLSX 周报；
- 30 项跨公司固定规则基准；
- 135 项自动测试及浏览器验收记录。

### Changed

- 根入口改为真实本地运行记录概览，不再把固定模拟数据作为首页业务指标；
- 开发评测移动到风险雷达的折叠入口；
- XLSX 映射允许输入用户自己的原始字段名；
- V2 页面统一为同一套工作台视觉和导航。

### Boundaries

- 本版本只面向本地单用户模拟演示；
- 没有公开部署、真实企业接入或业务效果；
- 没有多 Agent、向量 RAG、模型训练、真实 OCR、语音识别或外部连接器。
