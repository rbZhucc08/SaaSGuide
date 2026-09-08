# V3 阶段 4 独立评测框架测试记录

日期：2026-09-08  
实现提交：`34e9c90 feat: add V3 independent evaluation framework`

## 目标与非目标

本阶段建立盲标包、双人标注校验、分歧裁决、组件指标、状态 API 和风险雷达检查面板。它不填写人工答案，不宣称已得到独立评测分数，也不调用 DeepSeek。

## 修改内容

- `services/evaluation/independent.py`：盲标、标注、一致性、裁决和组件指标；
- `data/evaluation/v3/`：4 个开发案例、4 个留出案例和空白标注模板；
- `GET /api/evaluation/framework`：只读框架状态；
- `risk-radar.html/js/css`：折叠区中的检查入口和结果面板；
- `docs/specs/V3_PHASE4_INDEPENDENT_EVALUATION_SPEC.md`；
- `docs/quality/V3_ANNOTATION_GUIDE.md`；
- `test_independent_evaluation.py` 与 `run_checks.ps1`。

没有数据库 Schema 迁移。人工标注文件未来放在被 Git 忽略的 `generated/evaluation/annotations/`，不进入版本库。

## 自动测试

命令：

```powershell
& '.\run_checks.ps1'
git diff --check
```

结果：

- 147 项 Python 自动测试通过，其中阶段 4 新增 8 项；
- JSON 与页面数据校验通过；
- 78 个 Markdown 本地链接通过；
- 全部前端 JavaScript 语法检查通过；
- `git diff --check` 通过。

覆盖了盲标包禁止预测字段、开发/留出拆分、标注完整性、不同标注者、一致性与分歧、裁决、分组件指标、`0/2` 状态和 API 输出。

## 浏览器验收

环境：Codex 应用内 Chromium，桌面视口。Chrome 控制通道本任务中不可用，因此没有把本次结果记录为 Chrome 验收。

操作：

1. 打开 `/risk-radar?phase4=1`；
2. 展开“开发评测”；
3. 点击“检查独立评测框架”；
4. 核对成功提示与面板字段。

最终页面显示：

- 开发集 4 个案例；
- 留出集 4 个案例；
- 系统预测字段已移除；
- 标注者 `0/2`；
- `独立评测框架完成，外部标注待完成`；
- 五类指标分开列出；
- 模拟数据与无独立结论的范围提示可见。

首次点击发现前端调用了本页面不存在的状态辅助函数，自动语法检查没有发现该运行时错误。修复为页面已有的消息和按钮状态逻辑后，重新加载并通过验收。

截图：`docs/test_records/v3_phase4_evaluation_2026-09-08/framework-status.jpg`。

## 真实 API、失败与未验证项

- DeepSeek 真实调用：0 次；
- 模拟模型调用：0 次；
- 首次浏览器运行时错误：已修复并复验；
- 外部人工标注：未开始，当前 `0/2`；
- 两位真实标注者的一致性、分歧裁决和最终指标：未验证，属于外部依赖；
- 留出集没有运行系统预测，也没有用于调参。

## 已知限制

案例仍由项目作者一侧构造，只有去预测的盲标形式，不能消除场景来源偏差。简单一致率不是 Cohen's kappa。框架验证流程可运行，不证明标签质量、真实业务分布或模型泛化能力。
