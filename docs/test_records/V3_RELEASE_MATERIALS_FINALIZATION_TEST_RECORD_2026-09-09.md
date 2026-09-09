# V3 发布材料收尾记录

## 目标

将当前 V3 本地发布候选的首页、项目状态、PRD、证据索引、演示路线、测试策略、已知限制、变更记录、Release Notes 和截图统一到同一事实基线。

本次不创建 GitHub 仓库、不推送、不创建 tag 或 Release，也不使用自动生成视频替代项目所有者本人演示。

## 已完成材料

- `README.md`：改用当前 V3 截图并增加发布说明和演示入口；
- `docs/PROJECT_STATUS.md`：从 V2 历史状态更新为 V3 当前能力和外部依赖；
- `docs/product/PRD.md`：更新为 V3 Portfolio Candidate；
- `docs/portfolio/EVIDENCE_INDEX.md`：建立阶段 1–11 的证据映射；
- `docs/portfolio/DEMO_GUIDE.md`：更新为 4–6 分钟 V3 演示，不再突出跨境电商公司；
- `docs/portfolio/RELEASE_NOTES_V3.md`：增加版本说明、验证结果和发布边界；
- `docs/portfolio/SCREENSHOT_INDEX.md`：说明四张发布截图及其证据边界；
- `docs/portfolio/HR_PROJECT_EXPLAINER.md`、`docs/quality/TEST_STRATEGY.md`、`docs/quality/KNOWN_LIMITATIONS.md`、`SOURCE_CODE_STUDY_GUIDE.md` 和 `CHANGELOG.md`：统一当前测试数量、技术口径和限制；
- `/health` 版本由旧 `2.0-demo` 更新为 `3.0.0-portfolio-candidate`，并增加回归断言。

## 浏览器截图

使用 Codex 应用内 Chromium，在 `http://127.0.0.1:4179` 读取当前页面并保存：

- `docs/assets/overview-v3.jpg`；
- `docs/assets/data-sources-v3.jpg`；
- `docs/assets/risk-radar-v3.jpg`；
- `docs/assets/validation-v3.jpg`。

人工检查结果：

- 首页显示本地记录边界、六步主流程和业务验证入口；
- 数据源页显示真实数据阻断、安全控制和飞书“真实授权待完成”；
- 风险雷达显示候选不等于事实、AI 草稿和双人工确认；
- 业务验证页显示真实参与者 0 和外部证据待完成；
- 四个页面的 Chromium `warning` 和 `error` 日志均为 0。

## 自动检查

运行：

```powershell
& '.\run_checks.ps1'
```

结果：

- 186 项 Python 测试通过；
- 关键模块语句覆盖率 398/447，即 89.04%；
- 类型契约、Git 跟踪文件密钥扫描和数据检查通过；
- 80 个 Markdown 本地链接通过；
- 11 个 JavaScript 文件语法检查通过；
- `git diff --check` 通过。

发布材料专项 `test_release.py` 共 18 项通过，并检查当前材料不再使用旧 `v2-phase8-release` 分支名或 135 项测试口径。

## 未完成的外部发布事项

- 项目所有者尚未决定 GitHub 账号或组织、仓库名和私有/公开范围；
- 没有创建远程或推送；
- GitHub Actions 尚无在线运行证据；
- 没有 tag 或 GitHub Release；
- 项目所有者尚未录制并检查 4–6 分钟演示；
- Git 历史审计中的旧 Windows 用户路径和模拟手机号仍需要在真正公开前决定是否接受或重写历史处理。

## 结论

V3 的本地发布材料已经收尾，可以作为私有发布候选交给项目所有者演示和审阅。是否上传 GitHub、是否公开和是否重写历史仍是独立决定，不能由本地材料代替。
