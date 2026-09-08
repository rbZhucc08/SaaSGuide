# V3 阶段 1：信息架构与仓库整理测试记录

日期：2026-09-08  
实现提交：`b577452 docs: reorganize V3 information architecture`

## 目标和非目标

目标是清理根目录的历史材料、改进 README 第一屏和阅读路径，并让移动后的 Markdown 链接可以自动检查。本阶段没有改变页面、API、数据、模型或数据库。

## 修改文件

- `README.md`：增加三分钟体验、V1–V3 变化和当前文件地图；
- `docs/history/v1/`：保留 V1 阶段记录、旧 Brief、决策和问题日志；
- `docs/history/handoffs/`：保留 V2、简历和 UI 交接材料；
- `docs/README.md`、`docs/PROJECT_STATUS.md`、`docs/V2_ROADMAP.md`、`SOURCE_CODE_STUDY_GUIDE.md`：更新当前入口和历史位置说明；
- `scripts/check_markdown_links.py`、`run_checks.ps1`：增加仓库内 Markdown 链接检查；
- `docs/specs/V3_PHASE1_INFORMATION_ARCHITECTURE_SPEC.md`：阶段规格。

## 数据或数据库迁移

无。历史文档通过 Git 移动保留，内容没有删除或重写。

## 自动测试

命令：

```powershell
& '.\run_checks.ps1'
git -c safe.directory=D:/CodexProjects/SaaSGuide diff --check
```

实际结果：135 项 Python 测试通过；JSON 数据校验通过；78 个 Markdown 本地链接通过；全部前端 JavaScript 语法检查通过；`git diff --check` 无错误。PowerShell 只提示工作区 LF 将在 Git 处理时转为 CRLF，不是 diff 错误。

## 浏览器验收

- 环境：Codex 应用内 Chromium，本地 Flask `http://127.0.0.1:4173`；
- 路由：`/`、`/data-sources`；
- 视口：本轮应用内浏览器默认桌面视口；
- 步骤：打开首页，确认本地 Demo 边界、8 个主导航入口和真实本地空状态；点击“数据源”，确认页面载入、当前公司和项目列表出现；再返回概览；
- 控制台：warn/error 日志为 `[]`；
- 截图：本轮对话中已保存首页可视截图；阶段 2 将建立完整仓库内前后对照截图目录。

## 真实 API

未调用 DeepSeek 或任何外部 API。浏览器只访问本机 Flask 服务。

## 结果

- 通过：README 阅读路径、历史归档、Markdown 链接、完整自动检查、本地页面入口和导航；
- 失败：无；
- 未验证：Chrome 控制通道返回 `Browser is not available: chrome`，因此本阶段浏览器证据不能写成 Chrome 验收；没有检查外部 Markdown URL 的在线可达性。

## 已知限制与冲突记录

- `SAASGUIDE_V3_HANDOFF.md` 把 `4d8eed0` 写为最新提交，但开始实施时当前干净基线实际为后续的 `3452905 docs: add V3 development handoff`。本阶段从当前基线创建 `codex/v3-development`，没有丢弃交接提交。
- 历史文档中的旧测试数量、旧路由和绝对路径作为当时事实保留；当前入口不把它们当作现状。
