# SaaSGuide V3 Portfolio Candidate

版本：`3.0.0-portfolio-candidate`

日期：2026-09-09

状态：已创建私有 GitHub Pre-release `v3.0.0-portfolio`

## 这个版本完成了什么

SaaSGuide V3 将项目数据校验、确定性风险扫描、当前制度检索、DeepSeek ASK/PLAN、Python 输出约束、风险人工确认、行动人工确认、事件审计和报告汇总连接为一条本地流程。

相较 V2，V3 增加了：

- 更清晰的九页工作台和默认业务主线；
- 规则、检索、模型与人工判断分层评测；
- 模型超时、重试、预算和可观察性；
- 可定位引用的混合检索与版本冲突处理；
- 真实数据安全阻断和威胁模型；
- 飞书多维表格只读连接器底座；
- 真实试点研究协议与证据校验器；
- 跨平台检查、历史审计和干净环境复现。

## 验证结果

- 186 项自动测试通过；
- 关键模块语句覆盖率 89.04%；
- 数据、类型契约、Git 跟踪文件密钥、80 个 Markdown 链接、11 个 JavaScript 文件和 Git 差异检查通过；
- Windows 全新虚拟环境使用锁定依赖完整复现；
- 私有仓库 `rbZhucc08/SaaSGuide` 的 Windows/Linux、Python 3.11/3.12 GitHub Actions 四项矩阵通过；
- 各阶段保存自动测试、浏览器检查和边界记录。

## 运行

```powershell
python -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
& '.\start_v2.ps1'
```

浏览器打开 `http://127.0.0.1:4173/`。

## 后续仍需决定

- 用户本人录制并检查的 4–6 分钟演示；
- 是否公开，以及公开前对历史中两项人工复核内容的处理方式。

## 表述边界

这是本地 AI 应用个人项目，不是生产 SaaS。飞书尚未真实授权，真实参与者为 0，独立标注为 0/2；合成评测不代表企业准确率，自动测试不代表商业效果。
