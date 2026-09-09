# V3 私有 GitHub 发布验收记录

## 范围

- GitHub 账号：`rbZhucc08`；
- 仓库：`rbZhucc08/SaaSGuide`；
- 可见性：Private；
- 远程默认分支：`main`；
- 本地开发分支：`codex/v3-development`，跟踪 `origin/main`。

本次没有把仓库改为公开，没有创建 tag、GitHub Release 或公网 Demo。

## 首次在线运行

首次推送提交 `3809c01` 后，GitHub Actions [checks #1](https://github.com/rbZhucc08/SaaSGuide/actions/runs/34370301449) 运行四项矩阵。Ubuntu 两项通过，Windows 两项失败。

失败发生在 `scripts/scan_tracked_secrets.py` 的成功提示输出：Windows runner 的 CP1252 控制台不能编码中文，抛出 `UnicodeEncodeError`。在失败前，186 项测试、32 项覆盖率采样、关键模块覆盖率 89.04% 和类型契约均已通过，因此这次失败属于 CI 控制台编码问题，不是业务断言失败。

同一轮还报告官方 Action 所用 Node.js 20 已弃用的警告。

## 修复与本地验证

提交 `229ee34` 完成以下修复：

- 在 CI 作业中设置 `PYTHONUTF8=1`；
- `actions/checkout` 从 v4 升级到 v5；
- `actions/setup-python` 从 v5 升级到 v6；
- `actions/setup-node` 从 v4 升级到 v5。

本地使用同一 UTF-8 环境运行 `scripts/run_checks.py`，结果为：

- 186 项测试通过；
- 32 项覆盖率采样通过，关键模块覆盖率 398/447，即 89.04%；
- 类型契约、Git 跟踪文件密钥扫描和数据校验通过；
- 80 个 Markdown 本地链接通过；
- 11 个 JavaScript 文件语法检查通过；
- `git diff --check` 通过。

## 第二次在线运行

GitHub Actions [checks #2](https://github.com/rbZhucc08/SaaSGuide/actions/runs/34370884534) 最终状态为 Success，总耗时 1 分 56 秒：

- Windows latest + Python 3.11：通过；
- Windows latest + Python 3.12：通过；
- Ubuntu latest + Python 3.11：通过；
- Ubuntu latest + Python 3.12：通过。

第二次运行没有出现首次运行中的 Node.js 20 弃用警告。

## 结论

私有仓库创建、代码推送和跨平台在线检查已经完成。tag、GitHub Release、公开范围和公网 Demo 仍是独立发布决定。
