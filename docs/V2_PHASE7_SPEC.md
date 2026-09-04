# V2 Phase 7 扩展输入与适配器规格

## 目标

扩展普通 PDF、扫描 PDF 检测、WAV 元数据和外部适配器合约，同时把“接口存在”“已运行”“真实服务已验证”分开。

## 验收

- 普通 PDF 提取页码、原文、字符数和 SHA-256。
- 无可提取文本的 PDF 返回 OCR_REQUIRED，且 `ocr_status=not_run`。
- WAV 只读取时长、声道、采样率；`transcription_status=not_run`。
- 外部适配器只允许 simulation；不发送请求、不写回。

## 不在本阶段完成

- 真实语音转写、OCR 引擎质量、真实 Jira/飞书/企业微信等连接器。
- 浏览器麦克风录音和任何外部通知。
