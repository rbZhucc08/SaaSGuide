# V3 阶段 9：飞书多维表格只读连接器规格

## 平台选择

用户明确排除电商平台，并选择可能实际使用的办公平台飞书。首个数据面限定为飞书多维表格，不读取聊天消息，也不同时接入多个平台。

## 官方接口边界

- 查询记录：`POST /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records/search`；
- 官方文档说明单次最多 500 行并支持 `page_token` 分页；
- 使用 `tenant_access_token`，应用必须拥有表格读取权限；
- 请求 `automatic_fields=true` 获取修改时间，用于本地增量应用游标和幂等合并。当前仍分页读取整张表，再在本地只应用较新的记录；不是服务端变更流。

官方文档：<https://open.feishu.cn/document/docs/bitable-v1/app-table-record/search?lang=zh-CN>

## 实现范围

- 本机环境变量凭据，不在接口、日志或 Git 中返回值；
- 获取 tenant token、分页读取、有限重试和错误分类；
- 可配置字段映射，按 `record_id` 和修改时间幂等保存本地快照；
- 保存最大 `last_modified_time` 游标和去敏同步审计；
- 页面显示配置、只读和真实验收状态；
- 不向飞书写回，不自动形成正式风险或行动。

## 完成边界

无真实应用凭据时，只能证明连接器合约、分页、幂等、错误恢复和页面阻断状态。真实授权、权限和实际数据同步必须在用户创建飞书自建应用并设置本机环境变量后单独验收。
