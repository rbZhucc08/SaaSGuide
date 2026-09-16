# V3 飞书人工确认写回规格

## 背景

阶段 9 当时只完成了飞书多维表格**只读**连接器：分页、幂等合并、错误分类和脱敏审计，没有写入路径，也没有真实授权。本规格随后补齐“确认后的行动回到工作台”的受控写回路径；当前真实验收状态见专项记录。

## 设计原则

1. **模型永远不能自己落库。** 写回的前置条件是人已经确认。这条由代码拦截，不是界面约定。
2. **不修改客户原表。** 写回目标是独立的"AI 待确认行动"表。原表是客户的业务数据，模型判断错误不得污染它。
3. **写回默认关闭。** 只配置读表凭据不足以打开写路径，必须显式开启。
4. **幂等。** 同一行动重复推送不产生重复记录。
5. **失败可见。** 未确认、缺字段、缺凭据、超批量各自返回可读的错误码，不抛堆栈。

## 接口

| 项 | 内容 |
|---|---|
| 路由 | `POST /api/connectors/feishu/push-actions` |
| 请求体 | `{"actions": [ {...} ]}` |
| 行动字段 | `action_id`、`task_id`、`content`、`policy_reference`、`suggested_owner`、`completion_signal`、`confirmation_status` |
| 确认值 | `confirmation_status` 必须为 `已确认` |
| 批量上限 | 500 条 |

## 错误码

| 码 | 状态 | 触发条件 |
|---|---|---|
| `action_not_confirmed` | 409 | 行动未人工确认 |
| `invalid_actions` | 400 / 422 | 非数组、元素非对象、缺必填字段、批次内编号重复 |
| `no_confirmed_actions` | 400 | 空数组 |
| `batch_too_large` | 400 | 超过 500 条 |
| `writeback_credentials_missing` | 409 | 写回未开启或凭据缺失 |
| `writeback_source_table_forbidden` | 409 | 写回目标与读取源表相同 |
| `permission_denied` | 403 | 飞书授权或表格权限不足 |
| `api_error` | 502 | 飞书返回非零 code |

## 环境变量

| 变量 | 必需 | 说明 |
|---|---|---|
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 是 | 应用凭据 |
| `FEISHU_BITABLE_APP_TOKEN` / `FEISHU_BITABLE_TABLE_ID` | 是 | 读表 |
| `FEISHU_BITABLE_WRITEBACK_APP_TOKEN` | 写回时可选 | 独立行动表所在 Base；可回落到读取 Base |
| `FEISHU_BITABLE_WRITEBACK_TABLE_ID` | 写回时必需 | 必须显式配置独立行动表，且不能与读取表相同 |
| `FEISHU_BITABLE_WRITEBACK_ENABLED` | 写回时 | `1` / `true` / `yes` / `on` 才开启写路径 |

## 落地检查清单

- [x] 在真实租户核对批量新增路径可用；
- [x] 确认应用被添加为对应多维表格协作者；
- [x] 行动表列名与 `_action_fields` 一致；
- [x] 写入后读回行动表，并核对审计与源表未修改；
- [x] 真实验收结果已单独记录；
- [ ] 批量、并发、配额与更多字段类型仍待验证。

## 完成边界

项目已用作者自建演示数据完成一次真实租户端到端验收；这只能证明该固定配置下链路可用，不能推出生产稳定、多租户安全或企业采用。
