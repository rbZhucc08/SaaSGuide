# V2-P1 XLSX 导入验收记录（2026-09-04）

## 范围

本记录只覆盖 XLSX 项目任务导入：读取、列映射、校验、预览、人工确认、原件副本与标准化 JSON 保存。没有风险扫描、RAG、数据库、语音、PDF/OCR、真实外部系统或生产部署。

## 自动检查

- `run_checks.ps1` 实际运行通过。
- 53 项 Python 自动测试通过：原有 V1 38 项、V2-P1 导入 13 项，以及为防止 XLSX 全局请求上限放宽 V1 JSON 路由而新增的 2 项回归测试。
- `guide-data.json`、`risk-data.json` 与页面目标校验通过。
- `app.js`、`builder.js`、`data-sources.js` JavaScript 语法检查通过。
- 覆盖内容包括：文件扩展名与大小、压缩包限制、公式、可见工作表、列映射、日期、状态、百分比、重复任务、依赖、确认时重检、哈希和保存。

## Chrome 内置模拟样本验收

环境：Windows 11、Chrome、`http://127.0.0.1:4173/data-sources`。

- `invalid_missing_owner.xlsx`：4 条任务、3 条依赖、1 个错误；第 4 行 `required_value_missing`；确认按钮禁用。
- `invalid_dates.xlsx`：2 条任务、1 条依赖、2 个错误；第 2 行 `invalid_date`、第 3 行 `date_order`；确认按钮禁用。
- `invalid_dependencies.xlsx`：5 条任务、2 条有效依赖、3 个错误；第 4 行 `duplicate_task_id`、第 5 行 `self_dependency`、第 6 行 `dependency_not_found`；确认按钮禁用。
- `valid_project_tasks_cn.xlsx`：6 条任务、7 条依赖、0 个错误；列映射正确，确认按钮可用。
- 点击确认后显示项目“星云 CRM 升级项目（project-001）”、6 条任务、7 条依赖、来源 SHA-256 和标准化 JSON 路径。

内置样本入口明确标注“不等于文件上传”，因此以上不能描述成 Chrome 自动上传验证。

## 落盘核对

- 原件：`data/raw/source-02ac59ad1bcf-valid_project_tasks_cn.xlsx`。
- 标准化结果：`data/normalized/import-20260904212006-02ac59ad.json`。
- 页面、JSON 与原件文件的 SHA-256 均为 `02ac59ad1bcffdf844e68112aaa186ee75157517c656f7e38b82e328e39c137d`。
- JSON 包含 6 条任务、7 条依赖、6 条更新，并保留每条记录的 `source_row`。
- 两个落盘文件属于本地运行产物，已被 `.gitignore` 排除，不进入提交。

## 文件选择人工验证

用户确认在 Chrome 中分别选择了：

- `data/samples/valid_project_tasks_cn.xlsx`
- `data/samples/invalid_dates.xlsx`

两份文件都可被本地文件控件选择，并可触发“生成预览”。浏览器自动化扩展拒绝给文件控件设置路径，因此未自动复现该动作；用户操作后的具体页面结果没有在同一时刻被自动化捕获。上传端点与预览数据正确性另由自动集成测试覆盖。

## 响应式与控制台

- 初始桌面布局和初始 390 × 844 页面通过。
- 有效样本确认后的 390 × 844 状态：`innerWidth=390`、`innerHeight=844`、`scrollWidth=390`、`clientWidth=390`，没有页面级横向溢出。
- 有内容状态下浏览器控制台警告和错误：0 条。
- 测试后已清除临时设备尺寸覆盖。

## 结论与边界

V2-P1 的规格验收条件已满足，可以结束本阶段并提交分支。该结论只适用于本机、固定模拟样本和当前测试集；不证明任意企业 XLSX、其他浏览器、多人并发、生产稳定性或真实业务效果。
