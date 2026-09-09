# 基线与试点结果记录模板

本模板供研究者在取得参与同意后使用。不要填写姓名、联系方式、公司名、客户名、账号或可反推出身份的自由文本。原始访谈记录保存在仓库外。

## 研究级信息

- 研究编号：
- 场景编号：`risk-to-action-review`
- 数据授权已确认：是 / 否
- 数据已去标识化：是 / 否
- 项目所有者已确认授权范围：是 / 否
- 已记录任务顺序与学习效应：是 / 否

## 每位参与者

- 化名编号：`participant-___`
- 角色类别：
- 参与同意已确认：是 / 否
- 基线任务耗时（分钟）：
- 系统任务耗时（分钟）：
- 基线阶段遇到的阻塞数量：
- 系统阶段遇到的阻塞数量：

## 每条系统建议

- 建议编号：
- 处置：`accepted` / `modified` / `rejected`
- 编码原因：
  - `useful_as_written`
  - `needs_context`
  - `wrong_priority`
  - `not_actionable`
  - `unsupported_by_evidence`
  - `outside_role`
  - `other_coded_reason`

## 结构化分析文件

复制 `data/validation/phase11_study_template.json` 到被 Git 忽略的 `generated/validation/pilot-results.json`，仅填入上述去标识化字段，然后运行：

```powershell
& '.\.venv\Scripts\python.exe' '.\scripts\analyze_pilot_results.py' '.\generated\validation\pilot-results.json'
```

分析结果只用于描述本次小样本观察。不要把耗时差异解释成系统导致的效率提升，也不要把建议接受率解释成建议正确率。
