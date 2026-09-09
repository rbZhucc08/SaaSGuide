# V3 私有发布候选检查清单

目标版本：`3.0.0-portfolio-candidate`

发布范围：本地单用户、模拟或已去标识化测试数据

当前状态：已推送到私有 GitHub 仓库，在线 Actions 四项矩阵通过

## 本地已完成

- [x] README 说明 V3 功能、运行、测试和限制；
- [x] V3 Release Notes、证据索引、4–6 分钟演示稿和截图索引；
- [x] 分阶段规格、测试记录和浏览器截图；
- [x] Windows/Linux、Python 3.11/3.12 Actions 工作流定义；
- [x] 精确锁定 Python 运行依赖；
- [x] 当前跟踪文件密钥扫描；
- [x] 可达 Git 历史文本 blob 启发式扫描；
- [x] `.env`、运行数据、导入、日志、备份和简历目录由 Git 忽略；
- [x] 真实数据安全闸门、模型失败和连接器缺少授权均在页面显示；
- [x] 干净虚拟环境安装与完整检查：2026-09-09 保持 VPN 连接，使用官方 PyPI 和受控网络权限完成安装，186 项测试及全部检查通过；

## 外部事项

- [x] 用户决定 GitHub 账号、仓库名和私有范围：`rbZhucc08/SaaSGuide`；
- [x] 创建私有远程并推送到 `main`；
- [x] 在线 GitHub Actions 四项矩阵作业真实通过：[checks #2](https://github.com/rbZhucc08/SaaSGuide/actions/runs/34370884534)；
- [ ] 配置私有安全联系方式；
- [x] 创建 `v3.0.0-portfolio` tag 和私有 [GitHub Pre-release](https://github.com/rbZhucc08/SaaSGuide/releases/tag/v3.0.0-portfolio)；
- [ ] 用户本人录制并检查 4–6 分钟演示；
- [ ] 通过安全复核后决定是否公开；
- [ ] 公开在线 Demo 仍未决定，且只能使用模拟数据。

未完成项涉及用户账号、外部发布、个人信息或公开范围，不能用本地文件模拟成已完成。
