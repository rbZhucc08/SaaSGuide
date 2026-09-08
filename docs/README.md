# SaaSGuide 文档

这组文档按读者问题组织，不按开发日期堆叠。第一次进入项目时，先选择与你最相关的路径。

## 三分钟：这是什么项目

适合招聘人员或第一次查看仓库的人：

1. [仓库首页](../README.md)
2. [HR 项目讲解稿](portfolio/HR_PROJECT_EXPLAINER.md)
3. [项目案例](portfolio/CASE_STUDY.md)
4. [演示路线](portfolio/DEMO_GUIDE.md)
5. [可核实证据](portfolio/EVIDENCE_INDEX.md)

读完应能回答：项目解决什么问题、AI 在哪里、作者具体做了什么、当前不能证明什么。

## 十五分钟：产品为什么这样设计

适合 AI 产品、运营或业务面试：

1. [产品需求文档](product/PRD.md)
2. [功能说明](product/FEATURE_GUIDE.md)
3. [用户手册](product/USER_GUIDE.md)
4. [评测说明](quality/EVALUATION_REPORT.md)
5. [已知限制](quality/KNOWN_LIMITATIONS.md)

## 三十分钟：系统怎么运行

适合技术面试或代码审查：

1. [系统架构](architecture/SYSTEM_ARCHITECTURE.md)
2. [AI Agent 工作流](architecture/AI_AGENT_WORKFLOW.md)
3. [数据与信任边界](architecture/DATA_AND_TRUST_BOUNDARIES.md)
4. [测试策略](quality/TEST_STRATEGY.md)
5. [安全说明](../SECURITY.md)
6. [V2 源码学习指南](../SOURCE_CODE_STUDY_GUIDE.md)

## 当前状态

- 当前实现以 [PROJECT_STATUS.md](PROJECT_STATUS.md) 为准；
- 路线和未完成项以 [V2_ROADMAP.md](V2_ROADMAP.md) 为准；
- 发布前检查见 [RELEASE_CHECKLIST.md](portfolio/RELEASE_CHECKLIST.md)；
- 主要变更见 [CHANGELOG.md](../CHANGELOG.md)。

## 历史资料

以下文件保留用于追溯，不是第一次阅读的入口：

- `V2_PHASE1_SPEC.md` 至 `V2_PHASE8_SPEC.md`：分阶段规格；
- `test_records/`：自动测试、浏览器检查和阶段验收记录；
- `CHANGE_RECORD_2026-09-05_PRODUCTIZATION.md`：产品入口与展示内容调整；
- `history/v1/`：V1 阶段记录、早期 Brief、决策和问题日志；
- `history/handoffs/`：V2、简历和 UI 优化交接材料；
- `specs/`：当前 V3 阶段规格；
- `test_records/`：各阶段实际测试和浏览器验收记录。

历史记录描述当时发生的事，可能包含已经退出当前产品入口的页面或旧测试数量。判断现在能做什么时，应优先查看仓库首页、当前状态和最新验收记录。
