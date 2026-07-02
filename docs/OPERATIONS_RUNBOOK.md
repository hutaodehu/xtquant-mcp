# xtqmt-mcp 运行手册

本文说明公开样例仓的安装、配置、启动和验证流程。所有路径均为示例；真实路径必须在本机私有配置中维护。

## 仓库模块地图

- `xtqmt_mcp/`：MCP 服务、配置模型、交易门禁和数据同步运行时。
- `configs/`：公开样例配置。
- `scripts/`：启动、wake、bundle 校验和 flow-smoke 辅助脚本。
- `tests/`：不依赖真实交易的单元测试和契约测试。
- `docs/release/`：开源整理、归档、冻结和验证记录。

## 依赖边界

1. Python 3.11+。
2. Windows PowerShell 7 用于 Windows 侧脚本。
3. MiniQMT / xtquant 由使用者自行安装。
4. 本仓不分发券商客户端、真实账号、真实凭据或真实运行证据。

## 配置文件

从样例复制到本机私有位置后再填写真实值：

```text
configs/data_gateway.example.yaml
configs/trade_gateway.example.yaml
configs/trade_gateway.flow_smoke.yaml
```

需要私有填写的字段包括 MiniQMT 可执行文件、userdata、xtquant bundle、账户号、运行目录和凭据 target。

## 启动顺序

1. 准备本机 MiniQMT / xtquant。
2. 复制示例配置到本机私有配置路径。
3. 校验 xtquant bundle。
4. 启动 Data Gateway。
5. 启动 Trade Gateway。
6. 调用 `gateway.health` 和交易会话探针确认服务状态。

## Data Gateway 常用操作

- 查询服务健康：`gateway.health`
- 解析交易日：`calendar.resolve_trade_day`
- 生成完整性计划：`integrity.plan`
- 查询行情快照：`market.snapshot.batch`
- 提交批量同步：`bulk.sync_job.submit`
- 检查 qlib 验收：`qlib.acceptance.check`

## Trade Gateway 常用操作

- 会话 warm：`session.warm`
- 会话状态：`session.status`
- 连接探针：`probe.connection`
- 查询订单：`orders.list`
- 查询成交：`fills.list`
- 受控下单：`order.place`

## 会话恢复

Trade Gateway 区分端口可连、MiniQMT 登录、xtquant session、账户发现、行情快照和写权限。任一环节失败时应先查看结构化错误和 readiness payload，再决定是否重启 MiniQMT 或重新 warm session。

## 写路径门禁

真实写路径必须满足：

1. 明确配置账户和 userdata。
2. kill switch 未触发。
3. session 和 probe 均 ready。
4. 风险阈值、白名单和交易时段通过。
5. 审计输出可写。

公开测试默认不触发真实交易。`flow_smoke` 用于验证接口语义和门禁，不代表真实成交。

## 证据与归档规则

真实运行态和证据目录不进入公开仓。公开仓只保留 README stub 和 release manifest；真实证据进入私有归档。

## 发布验证

发布前至少执行：

```bash
python -m compileall xtqmt_mcp scripts
python -m pytest
git diff --check
```

若本机环境无法运行完整 pytest，应在 `docs/release/v2.0.0-alpha.1_validation.md` 记录限制和已通过的分组测试。
