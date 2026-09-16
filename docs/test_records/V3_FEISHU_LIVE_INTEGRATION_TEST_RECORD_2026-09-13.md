# 飞书真实租户端到端验收记录

验收日期：2026-09-13
范围：在真实飞书租户上完成自建应用授权、多维表格读同步、风险扫描、人工确认与行动写回的完整闭环。

> 后续安全收尾（2026-09-16）：诊断脚本默认隐藏资源标识符；写回表 ID 改为必须显式配置，且读写同表会被代码拒绝；缺少任务编号或真实制度依据的本地行动会跳过，不再生成占位依据。当前完整检查为 217 项测试。

## 目标与非目标

目标：

- 在真实飞书租户上完成自建应用创建与授权，取得可用的 `tenant_access_token`；
- 用真实的 `records/search` 读回客户表格数据并归一化；
- 验证归一化结果能驱动确定性规则扫描产出候选风险；
- 验证人工确认闸门在真实数据上拦截未确认内容；
- 验证已确认行动写入独立的行动表，且客户原表不被修改；
- 验证重复推送的幂等性。

非目标：

- 不读取飞书聊天消息；
- 不向客户原表写入；
- 不部署到公网，不改变本地单用户形态；
- 不使用真实企业敏感数据（本次数据为作者自建的演示数据）。

## 授权与凭据

| 项 | 内容 |
|---|---|
| 应用类型 | 企业自建应用（`SaaSGuide-ProjectRisk`） |
| 授权方式 | 应用身份 `tenant_access_token` |
| 已开通权限 | 多维表格读写；`wiki:wiki` / `wiki:wiki:readonly` / `wiki:node:read` |
| 资源级授权 | 应用已被添加为该多维表格的文档协作者（可编辑） |
| 凭据存放 | 仅本机 `.env.local`（已被 `.gitignore` 的 `.env.*` 规则忽略）；状态接口不返回值 |
| 写回开关 | `FEISHU_BITABLE_WRITEBACK_ENABLED=1` 显式开启 |

### 真实环境发现

1. **wiki 节点 token ≠ 多维表格 app_token。** 文档建立在知识库中时，URL 的 `/wiki/<token>` 是知识库节点 token。Bitable 接口使用它会返回 `91402 NOTEXIST`。必须通过 `wiki/v2/spaces/get_node` 取得 `obj_token` 才是真正的 `app_token`。
2. **开放平台会在错误响应里直接给出自助授权链接**（`99991672` 附带 `https://open.feishu.cn/app/<app_id>/auth?q=<scope>`），开通后必须重新创建并发布版本才生效。
3. **PowerShell 5.1 会吞掉 HTTP 错误响应正文**，同一请求用 Python 的 HTTP 栈可以看到完整的 `code` / `msg`。排障脚本因此以 Python 实现。

## 真实缺陷与修复

**现象**：首次真实同步后，日期字段被归一化为字符串 `"1788192000000"`。

**原因**：飞书多维表格日期字段通过 API 返回**毫秒时间戳**，而连接器原先只做文本归一化。

**影响**：规则引擎按 `YYYY-MM-DD` 字符串比较日期，时间戳字符串会导致**逾期与临期风险全部漏判**，扫描功能在真实数据上实质失效。

**为什么既有测试没有发现**：原有测试的模拟数据使用 `"2026-09-30"` 这类字符串，与真实响应形态不一致；模拟 HTTP 合约无法覆盖真实字段类型。

**修复**：新增 `_field_date()`，对 `due_date` 与 `updated_at` 识别 13 位毫秒与 10 位秒时间戳并转换为本地时区（UTC+8）的 ISO 日期，已是日期字符串的值原样放行；超出可解析范围时返回 `invalid_field_value`（422）。

**回归保护**：新增 5 项测试覆盖毫秒时间戳、秒时间戳、日期字符串放行、对象数组文本解包、超范围时间戳报错。

## 自动测试

命令：`& '.\run_checks.ps1'`

- **212 项 `unittest` 通过**（原 207 项 + 本次新增 5 项）；
- 关键模块语句覆盖率 398/447，89.04%；
- 类型注解契约、跟踪文件密钥扫描、数据校验、82 个 Markdown 链接、11 个 JavaScript 文件和 `git diff --check` 全部通过；
- 脚本退出码 0。

## 真实调用验收

| 环节 | 真实结果 |
|---|---|
| 鉴权 | `tenant_access_token` 获取成功 |
| 读同步 | 从客户表格读回 **5 条**记录，`applied_count=5`，游标 `1789286283000` |
| 日期归一化 | `1788192000000 → 2026-09-01`、`1788537600000 → 2026-09-05`、`1789401600000 → 2026-09-15`、`1789488000000 → 2026-09-16`、`1790265600000 → 2026-09-25` |
| 规则扫描 | 从归一化数据产出 **5 条候选**：2 条已逾期（12 天 / 8 天，high）、1 条阻塞（high）、2 条临期低进度（medium）。与所用测试数据的预期完全一致 |
| 人工确认闸门 | 未确认行动返回 `action_not_confirmed`（409），**未发出任何网络请求** |
| 写回 | 已确认行动写入行动表，飞书返回记录 ID（具体值已脱敏） |
| 读回核对 | 行动表中 3 条记录字段完整：行动编号、关联任务、建议内容、制度依据、建议负责人、完成信号、确认状态 |
| 客户原表 | **未被修改**，同步与写回后 5 条原始记录与时间戳保持不变 |
| 幂等 | 重复推送同一 `action_id` 返回 `written_count=0`、`skipped_count=1` |
| 本地闸门 | 推送时状态为 `cancelled` 的本地行动被明确列为 `skipped_local_actions` 并跳过 |
| 审计 | 每次写回追加一条脱敏记录到 `generated/connectors/feishu/audit.jsonl`，事件名 `feishu_writeback` |

## 修改文件

| 文件 | 变更 |
|---|---|
| `services/connectors/feishu_bitable.py` | 新增 `_field_date()` 与 `_DATE_FIELDS`；`normalize_record` 对日期字段应用时间戳转换 |
| `database/store.py` | `action_items` 增量新增 `task_id`、`policy_reference` 列；`create_action` 持久化这两个字段 |
| `routes/v3_connectors.py` | 新增 `POST /api/connectors/feishu/push-local-actions`；新增 `_pushable_actions()` 只放行通过确认闸门的本地行动 |
| `server.py` | 向连接器蓝图传入 `database_path` |
| `risk-radar.js` | 预填行动时从当前 AI 引用的生效制度带上 `policy_reference` 与 `task_id` |
| `action-tracker.html` / `action-tracker.js` | 行动表单新增"制度依据"；行动列表新增"推送已确认行动到飞书" |
| `data-sources.html` / `data-sources.js` | 连接器卡片由"只读"更新为读写并标注写回约束 |
| `test_feishu_connector.py` | 模拟数据改为真实字段形态；新增 5 项日期与文本归一化测试 |
| `scripts/` | 新增真实排障脚本：`show_feishu_wiki_node.py`、`list_feishu_tables.py`、`create_feishu_action_table.py`、`run_feishu_sync.py`、`run_feishu_writeback.py`、`probe_feishu_python.py` |
| `.env.example`、`start_with_env.ps1` | 凭据模板与从本机文件读取凭据的启动脚本 |

## 未验证项

- 批量写入的真实上限（本次仅验证单条与少量记录）；
- 并发写入、配额限制与限流下的实际表现；
- 飞书表格中"人员"类型、含时间的日期类型、公式字段等其他字段类型；
- 多租户隔离（当前为单租户单应用）；
- 长期稳定性与真实 SLA。

## 结论

飞书连接器在真实租户上完成了从读同步、日期归一化、规则扫描、人工确认闸门到写回独立行动表的完整闭环，客户原表未被修改，幂等与审计均已验证。过程中发现并修复了一个只有在真实数据上才会暴露的日期类型缺陷，并补充了回归测试。该项状态可由"真实授权待完成"更新为"真实链路已验证"。
