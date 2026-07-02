# MCP 设计

`xtqmt-mcp` 将本地 MiniQMT / xtquant 能力拆成两个 MCP 服务：Data Gateway 和 Trade Gateway。两个服务共享配置模型、运行目录约定和审计输出格式，但工具面保持隔离。

## 服务边界

### Data Gateway

Data Gateway 负责只读数据能力和离线数据同步：

- `gateway.health`
- `calendar.resolve_trade_day`
- `integrity.plan`
- `sector.list`
- `sector.members_at`
- `sector.change_history`
- `market.snapshot.batch`
- `market.history.get_bars`
- `bulk.sync_job.submit`
- `bulk.sync_job.status`
- `bulk.sync_job.cancel`
- `artifact.manifest`
- `qlib.health.check`
- `qlib.acceptance.check`

Data Gateway 不负责账户、委托、成交或任何交易写路径。

### Trade Gateway

Trade Gateway 负责交易相关接口和门禁：

- 会话 warm、status、close。
- 连接探针和 MiniQMT readiness。
- 账户、持仓、订单、成交查询。
- 受控 `order.place`、`order.status`、`order.cancel`。
- 写路径的 dry-run、flow-smoke、kill switch、风险和审计门禁。

Trade Gateway 不把 TCP 端口可连视为交易 ready。ready 必须来自会话、探针、账户、行情和写权限的组合判断。

## 配置原则

1. 默认配置不得包含真实本机路径或真实账户。
2. `xtdata_port` 和 `port_num` 默认使用 `0` 或由示例配置显式指定。
3. 真实 MiniQMT 路径、userdata、bundle root 和账户号由本机配置文件或环境变量注入。
4. 运行态输出必须落在用户本机的 `instance/`、`state/`、`output/` 或 `.tmp/`，这些目录默认不提交。

## 隐私边界

公开仓可以包含字段名，例如 `account_id`、`broker_order_id`、`guard_token`。公开仓不得包含这些字段的真实取值、真实回执、真实日志或真实路径。
