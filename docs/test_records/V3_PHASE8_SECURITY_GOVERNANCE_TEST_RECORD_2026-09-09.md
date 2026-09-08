# V3 阶段 8 安全、权限与数据治理验收记录

## 目标与非目标

本阶段建立真实数据使用阻断条件，并补充本地 Demo 可验证的输入和仓库防护。它没有实现登录、RBAC、真正租户隔离、数据库加密、托管密钥或恶意软件扫描，因此状态保持 `blocked_for_real_data`，不允许真实数据或公网部署。

## 修改与数据影响

- 新增 `services/security/governance.py`：敏感样式检测、Office 压缩边界、进程内写接口限流和安全就绪状态；
- 文本证据与 XLSX 预览增加敏感类别提示，不返回匹配原文；
- 新增 `/api/security/readiness` 和数据源页真实数据闸门；
- 新增 `scripts/scan_tracked_secrets.py` 并纳入完整检查；
- 新增威胁模型和阶段规格；
- 没有数据库迁移，没有导入真实数据，没有调用模型 API。

## 自动测试

命令：`& '.\\run_checks.ps1'`

- 173 项 `unittest` 通过；
- 关键模块标准库覆盖率近似值 398/447，89.04%，门槛 60%；
- 4 个关键模块公开函数类型注解契约通过；
- Git 跟踪文件启发式密钥扫描通过；
- 数据校验通过；
- 78 个 Markdown 本地链接通过；
- 10 个 JavaScript 文件语法通过；
- `git diff --check` 通过。

首次密钥扫描把 `test_model_reliability.py` 中的测试夹具 `secret-test-key` 识别为疑似密钥。扫描规则随后只把带 `test-key` 的显式测试占位值排除，再次运行通过；这不是生产密钥，也没有回显匹配值。

## 浏览器验收

- 环境：Codex 应用内 Chromium；Chrome 控制通道未作为替代证据；
- 路由：`http://127.0.0.1:4174/data-sources`；
- 页面明确显示“真实数据已阻断”，并分别列出 6 项已实现控制和 6 项未实现控制；
- `company_id` 文案明确为本地上下文，不称租户隔离；
- 展开“开发评测样本”并加载有效 XLSX，得到 6 条任务、7 条依赖、0 个错误；
- 控制台 warning/error：0；
- 截图：`docs/test_records/v3_phase8_security_2026-09-09/security-readiness.png`；
- 截图：`docs/test_records/v3_phase8_security_2026-09-09/xlsx-preview-security.png`。

## 真实 API 与外部依赖

- 没有调用 DeepSeek 或外部平台 API；
- 没有真实身份提供商、角色目录、KMS、恶意软件引擎或生产数据库；
- 跟踪文件扫描不是完整 Git 历史扫描；
- 进程内限流在重启后清零，不是公网或多实例限流；
- 自动保留期限执行器未实现，设备所有者仍需管理本地运行产物和备份。

## 结论

阶段 8 的本地安全治理闸门和可验证控制已完成；生产安全与真实数据准入未完成，并被产品明确阻断。实现提交：`8091fcd feat: add V3 security governance gate`。
