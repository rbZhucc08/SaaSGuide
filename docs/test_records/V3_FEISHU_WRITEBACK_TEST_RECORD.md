# V3 飞书人工确认写回验收记录

验收日期：见 Git 提交时间
范围：把飞书连接器从"只读"扩展为"人工确认后写回"，并修复本机 PowerShell 检查脚本。

> 历史状态说明：本文记录写回合约首次完成时的 207 项测试与“真实验收待完成”状态。后续真实租户验收及 217 项当前检查见 `V3_FEISHU_LIVE_INTEGRATION_TEST_RECORD_2026-09-13.md` 和最终收尾记录。

## 目标与非目标

目标：

- 在已有只读连接器之上增加写入路径，让已人工确认的行动可以回到飞书；
- 写入必须由代码强制拦截未确认内容，而不是依赖界面约定；
- 写入目标必须是独立的行动表，不得修改客户原表；
- 重复推送不得产生重复记录；
- 原有只读行为、测试和证据不得被破坏。

非目标：

- 不读取飞书聊天消息；
- 不做自动写入（模型永远不能自己落库）；
- 不做服务端变更流、队列、熔断或多供应商降级；
- 不改动首页统计口径、规则、检索和报告逻辑。

## 安全与设计边界

| 项 | 设计 |
|---|---|
| 确认闸门 | `validate_actions` 要求每条行动带 `confirmation_status == "已确认"`，否则返回 `action_not_confirmed`（409），**不发任何网络请求** |
| 写入默认关闭 | `writeback_configured` 需要显式开启（`FEISHU_BITABLE_WRITEBACK_ENABLED` 或构造参数）。仅配置读表凭据不会打开写路径 |
| 写回目标 | `FEISHU_BITABLE_WRITEBACK_TABLE_ID` 必须显式指定独立行动表；读写表相同时拒绝写回 |
| 幂等 | 已写入的 `action_id` 记录在 `generated/connectors/feishu/writeback.json`，重复推送被跳过 |
| 字段校验 | 必填 `action_id`、`task_id`、`content`、`policy_reference`、`suggested_owner`、`completion_signal`；批次内 `action_id` 不得重复 |
| 审计 | 每次写回追加一条脱敏记录到 `generated/connectors/feishu/audit.jsonl`，事件名 `feishu_writeback` |
| 凭据 | 只从环境变量读取；状态接口不返回值，测试断言凭据不出现在状态中 |

## 修改文件

| 文件 | 变更 |
|---|---|
| `services/connectors/feishu_bitable.py` | 新增 `CREATE_PATH`、`BATCH_CREATE_PATH`、`REQUIRED_ACTION_FIELDS`、`CONFIRMED_STATUS`、`MAX_BATCH_ACTIONS`；新增 `create_records`、`validate_actions`、`writeback_actions`、`_action_fields`；`FeishuBitableClient` 增加写回目标与显式开启开关；`connector_status` 增加写回状态字段 |
| `routes/v3_connectors.py` | 新增 `POST /api/connectors/feishu/push-actions`；抽出 `_load_written_action_ids`；写回日志与审计落盘 |
| `test_feishu_writeback.py` | 新增 21 项合约测试 |
| `run_checks.ps1` | 修复：文件改为 UTF-8 BOM，并在调用原生命令期间临时放宽 `$ErrorActionPreference`，改用退出码作为判据 |

## 自动测试

命令：

```powershell
& '.\run_checks.ps1'
```

结果：

- **207 项 `unittest` 通过**（原 186 项 + 新增 21 项）；
- 关键模块标准库覆盖率 398/447，89.04%（最低要求 60%）；
- 类型注解契约、跟踪文件密钥扫描、数据校验、81 个 Markdown 链接、11 个 JavaScript 文件和 `git diff --check` 全部通过；
- 脚本退出码 **0**，中文输出正常（修复前为解析错误 `UnexpectedToken` / 退出码 1）。

新增测试覆盖：

| 类别 | 覆盖内容 |
|---|---|
| 确认闸门 | 未确认被拒（409）、缺确认字段被拒、缺业务字段被拒（422）、批次内重复被拒、空/非数组被拒、超 500 条被拒 |
| 写入行为 | 已确认行动写入独立行动表、单独配置时**不指向读表**、重复推送被跳过、仅新行动写入、缺写回凭据被拒、未确认行动**不产生任何网络请求** |
| 状态 | 写回标记为需确认、**默认关闭**、仅开启开关而缺凭据仍不可写、凭据不出现在状态中 |
| 路由 | 写入并记录审计与日志、跨请求幂等、拒绝未确认（409）、缺凭据（409）、畸形负载不写入（400） |

## 模拟、真实调用与外部依赖

- 本次全部写入验证使用**本地模拟 HTTP 合约测试**（`WritebackOpener` 记录出站请求供断言）；
- **没有真实调用飞书 API**，没有写入任何真实多维表格；
- **真实验收仍需要外部配置**：创建飞书自建应用、发布并授权、把应用添加为对应多维表格的协作者，并设置：
  - `FEISHU_APP_ID`、`FEISHU_APP_SECRET`
  - `FEISHU_BITABLE_APP_TOKEN`、`FEISHU_BITABLE_TABLE_ID`（读表）
  - `FEISHU_BITABLE_WRITEBACK_APP_TOKEN`、`FEISHU_BITABLE_WRITEBACK_TABLE_ID`（独立行动表）
  - `FEISHU_BITABLE_WRITEBACK_ENABLED=1`（显式开启写回）
- 接口路径字面量（`CREATE_PATH` / `BATCH_CREATE_PATH`）以飞书开放平台文档为准，**开发环境无法访问外网，未做正文级核对**。

## 未验证项

- 真实飞书授权、真实读写同步与真实写入结果；
- 写回表字段名与真实多维表格字段类型的匹配（当前以中文字段名写入，真实表需同名或调整映射）；
- 并发写入、配额限制与限流下的实际表现；
- 浏览器页面尚未接入写回按钮（当前仅提供 API 端点）。

## 结论

人工确认写回路径、默认关闭的写回开关、独立行动表目标和跨请求幂等已完成，并有 21 项合约测试覆盖；真实飞书授权与写入验收待外部配置。同时修复了本机 `run_checks.ps1` 在无 BOM 时的解析失败与退出码误报。
