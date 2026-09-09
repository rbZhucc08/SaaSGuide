# V3 阶段 10：GitHub 作品集发布候选验收记录

## 目标与边界

本阶段把当前 V3 分支整理为可审计的本地发布候选，并核对公开前仍需满足的条件。没有配置 Git 远程、推送代码、运行在线 GitHub Actions、创建 tag 或 Release，也没有公开部署。

实现提交：`7dc235e feat: prepare V3 portfolio release candidate`

## 修改与证据

- 更新 `README.md`、`.env.example` 和 `docs/portfolio/RELEASE_CHECKLIST.md`，同步 V3 阶段 1–9 的现状、飞书只读连接器配置和安全边界；
- 新增 `scripts/audit_git_history.py`，扫描所有可达 Git 历史文本 blob，并且不在报告中保存或回显匹配值；
- 新增发布候选回归测试；
- 历史扫描报告：`docs/test_records/v3_phase10_release_2026-09-09/history-audit.json`；
- 浏览器截图：`docs/test_records/v3_phase10_release_2026-09-09/release-candidate-overview.png`。

本阶段没有数据模型或数据库迁移。

## 自动检查

运行：

```powershell
& '.\run_checks.ps1'
```

2026-09-09 最终结果：

- 181 项 `unittest` 通过；
- 关键模块语句覆盖率为 398/447，即 89.04%；
- 4 个关键模块类型注解契约通过；
- Git 跟踪文件启发式密钥扫描通过；
- JSON 数据校验通过；
- 78 个本地 Markdown 链接通过；
- 10 个前端 JavaScript 文件语法检查通过；
- `git diff --check` 通过。

## Git 历史审计

运行：

```powershell
& '.\.venv\Scripts\python.exe' '.\scripts\audit_git_history.py' --report '.\docs\test_records\v3_phase10_release_2026-09-09\history-audit.json'
```

结果：

- 扫描 688 个可达文本 blob；
- 0 项 `blocking` 级密钥发现；
- 状态为 `review_required`；
- 两项需要人工判断：历史 V1 测试记录中的旧 Windows 用户路径，以及安全测试中的模拟手机号；
- 报告不包含匹配值；
- 该工具是启发式检查，不能证明完整历史绝对没有秘密或个人信息，二进制内容仍需在真正公开前复核。

没有为了清理旧路径而改写 Git 历史。历史重写会改变现有提交标识，必须由项目所有者另行决定。

## 干净环境复现

在新的 `work/v3_phase10_clean_env` 虚拟环境中两次尝试按 `requirements.txt` 安装依赖：第一次使用当前沙箱网络，第二次在允许外部网络后重试。两次均因当前 PyPI/清华镜像代理不可达而失败，Flask 等依赖没有安装；后续出现的 `ModuleNotFoundError` 是安装失败的连锁结果，不是应用回归测试失败。

因此在首次验收时，“干净环境安装和完整检查”保持未完成。主 `.venv` 的 181 项通过不能替代这一项。

### 后续补充复验

2026-09-09 在保持用户 VPN 连接的情况下，新建 `work/v3_clean_env_vpn`，显式使用官方索引 `https://pypi.org/simple`。沙箱内第一次直连因 Windows 网络权限返回 `WinError 10013`；随后使用受控网络权限执行相同安装命令，四项锁定依赖及其传递依赖全部安装成功。

使用新环境运行：

```powershell
& '.\work\v3_clean_env_vpn\Scripts\python.exe' '.\scripts\run_checks.py'
```

补充结果：186 项 `unittest` 通过，关键模块语句覆盖率 89.04%，类型契约、跟踪文件密钥扫描、JSON 数据、78 个 Markdown 链接、11 个 JavaScript 文件及 `git diff --check` 全部通过。干净环境安装与完整检查由“未完成”更新为“已完成”。VPN 无需断开。

## 浏览器验收

浏览器：Codex 应用内 Chromium。

地址：`http://127.0.0.1:4175/`。

检查结果：

- 页面标题为“SaaSGuide｜项目风险工作台”；
- 默认首页显示“从项目事实到可追溯行动”和六步风险处理主流程；
- 首页明确标注本地 Demo、个人学习 Demo、人工确认和不代表真实企业效果；
- 最近活动只展示本地保存记录；
- 控制台日志为空；
- 截图已保存至上述证据目录。

首次验收曾用错误标题等待并超时；随后使用页面实际标题验证成功。该超时不属于应用失败。

## 外部状态

- Git 远程：未配置；
- GitHub 仓库：未创建；
- 推送：未执行；
- GitHub Actions：只有工作流定义，没有在线运行证据；
- tag 与 GitHub Release：未创建；
- 演示视频：未录制和人工检查；
- 公网 Demo：未部署；
- 真实 API：本阶段未调用。

## 验收结论

阶段 10 的本地发布候选、当前文件检查、历史启发式审计、干净环境复验和 Chromium 页面验收完成。GitHub 发布、在线 Actions、Release、演示视频和公网范围仍待外部条件与项目所有者决定，不能称为已经发布。
