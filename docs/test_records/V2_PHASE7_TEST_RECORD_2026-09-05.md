# V2 Phase 7 验收记录

日期：2026-09-05

## 自动测试

- P7 新增 4 项，累计 88 项通过。
- 普通 PDF 文本提取、空白 PDF 的 OCR_REQUIRED、0.1 秒 WAV 元数据、live 适配器拒绝和 simulation 无写回均通过。

## PDF 视觉验收

- 使用 bundled ReportLab 创建 1 页 A4 虚构会议纪要。
- `pdfinfo`：1 页、A4、未加密、无 JavaScript。
- 使用 bundled Poppler 144 DPI 渲染并检查第 1 页：中文可读，无裁切、重叠、黑块或缺字，页码清晰。

## 浏览器验收

- 应用内 Chromium：PDF 返回 TEXT_EXTRACTED、1 页、181 字符并显示原文；OCR 明确显示“检测已实现，OCR 未验证”。
- 语音状态显示 `not_configured`、`verified=false`；模拟适配器接受 1 条、写回 false、外部请求 false。
- 390 x 844：内容宽度与滚动宽度均为 375，无页面级横向溢出。
- 控制台错误和警告 0 条。Chrome 扩展浏览器不可用，本阶段只声明应用内 Chromium。

## 限制

- 没有真实 OCR、语音识别或外部账号授权；这些项目必须保持未验证。
- `pypdf 6.10.0` 从 bundled Python 复制到项目虚拟环境；干净环境仍应通过 requirements 安装验证。
