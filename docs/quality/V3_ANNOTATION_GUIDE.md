# V3 独立评测标注说明

## 谁来标注

需要两位未参与案例生成、没有查看系统预测的人。可以使用匿名编号，例如 `reviewer-a` 和 `reviewer-b`；编号只用于区分来源，不记录姓名或联系方式。

当前仓库没有已完成的人工标签。页面显示 `0/2` 是预期事实，不是故障。

## 准备文件

分别打开：

- 开发集：`data/evaluation/v3/development_blind.json`；
- 留出集：`data/evaluation/v3/holdout_blind.json`；
- 模板：`data/evaluation/v3/annotation_template.json`。

每位标注者独立复制模板。不要在标注前运行系统、查看跨公司固定基准或交换答案。

## 字段标准

### 风险标签 `risk_label`

- `positive`：事实足以支持当前存在需要处理或观察的项目风险；
- `negative`：事实明确表明没有目标风险；
- `insufficient`：缺少日期、状态、直接依赖或其他关键事实，无法可靠判断。

### 严重度 `severity`

- `high`：已阻塞关键路径、明显逾期且影响关键节点，或需要立即升级；
- `medium`：风险已经形成但仍有恢复窗口；
- `low`：需要观察，短期影响有限；
- `not_applicable`：风险标签为 negative；
- `insufficient`：无法判断严重度。

### 决策 `desired_decision`

- `ASK`：需要补充最少的关键事实；
- `PLAN`：现有事实和可用依据足以形成行动草稿；
- `insufficient`：仅用于无法确定 ASK 或 PLAN 的特殊情况，依据中必须解释。

### 引用和行动

- `required_doc_ids`：判断所需的制度编号；没有可支持制度时为空列表；
- `citation_supported`：系统引用是否真实支持结论；未看到系统输出时填 `not_reviewed`；
- `action_executable`：行动是否具体、有人负责且有完成信号；未看到系统输出时填 `not_reviewed`。

### 错误标签 `error_tags`

允许值：`false_positive`、`false_negative`、`citation_error`、`insufficient_information`、`unexecutable_action`、`severity_mismatch`、`none`。

`rationale` 必须引用案例中的具体事实，不能只写“同意”或“看起来合理”。

## 一致性与裁决

程序按风险标签、严重度、ASK/PLAN、引用支持和行动可执行性分别计算简单一致率，并列出分歧字段。它不把同一人的两份文件算作独立标注。

分歧案例必须逐条裁决。裁决记录保留案例编号与最终完整标签；没有裁决的案例不会被静默选择其中一方。

## 留出集纪律

开发集可用于修改规则或 Prompt。留出集在方案冻结后运行；不能看完留出答案再反复调参并仍称其为留出评测。发生这种情况时，需要新建未见案例。

## 结果表述

在两位外部标注者和裁决完成前，只能写“独立评测框架完成，外部标注待完成”。即使之后得到分数，也只能说明本次模拟案例和标注标准下的结果，不能扩展为企业准确率或商业效果。
