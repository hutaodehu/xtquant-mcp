# xtqmt-mcp

`xtqmt-mcp` 是面向本地 MiniQMT / xtquant 的 MCP 样例项目，提供两个本地服务：

1. `xtqmtDataGateway`：行情、交易日、板块、批量同步、artifact manifest 和 qlib 验收检查。
2. `xtqmtTradeGateway`：MiniQMT 登录、交易会话、探针、账户、订单、成交和受控写路径。

本仓库不包含真实账户、真实凭据、真实交易证据、真实成交、真实持仓、真实资金或真实本机路径。

## 项目定位

这是一个可运行的开源样例项目，用来展示如何把本地 MiniQMT / xtquant 能力封装为 agent 可消费的 MCP 服务。真实券商客户端、xtquant bundle 和用户账户由使用者在本机私有配置中提供。

## 能力边界

- Data Gateway 只提供数据和同步能力，不提供交易写路径。
- Trade Gateway 提供交易查询和受控写路径，但默认必须经过 dry-run、flow-smoke、kill switch、交易时段、风险和审计门禁。
- TCP 端口可连不等于 readiness；readiness 必须由服务级探针和结构化状态确认。

## 模块地图

- `xtqmt_mcp/`：核心 Python 包。
- `configs/`：脱敏样例配置。
- `scripts/`：启动、wake、bundle 校验和 flow-smoke 脚本。
- `tests/`：不依赖真实交易的单元测试和契约测试。
- `docs/`：公开设计、运行手册、验收标准和 release 记录。

## 安装前提

1. Python 3.11+。
2. Windows PowerShell 7。
3. 本机已安装 MiniQMT / xtquant。
4. 根据 `pyproject.toml` 安装 Python 依赖。

示例：

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

## 配置示例

从公开样例复制到本机私有路径后填写真实值：

```text
configs/data_gateway.example.yaml
configs/trade_gateway.example.yaml
configs/trade_gateway.flow_smoke.yaml
```

需要私有化填写的字段包括 MiniQMT 可执行文件、userdata、xtquant bundle、账户号、凭据 target 和运行态目录。

## 启动顺序

```powershell
pwsh -File scripts/bootstrap_runtime.ps1
pwsh -File scripts/wake_miniqmt.ps1
pwsh -File scripts/wake_data_gateway.ps1
pwsh -File scripts/wake_trade_gateway.ps1
```

`scripts/run_data_gateway_http.py` 和 `scripts/run_trade_gateway_http.py` 可直接启动对应 HTTP MCP 服务。

## Data Gateway 工具面

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

## Trade Gateway 门禁

真实写路径必须同时满足：

1. 明确账户和 userdata。
2. MiniQMT 登录和 session ready。
3. 连接探针通过。
4. kill switch 未触发。
5. 风险阈值、交易时段和审计输出通过。

`configs/trade_gateway.flow_smoke.yaml` 仅用于非真实流程烟测，不代表真实委托或成交。

## 隐私与运行态

- `.tmp/`、`instance/`、`output/`、`state/` 和 `.pytest_cache/` 默认不提交。
- 真实 EnvSnapshot、EvidencePack、ReviewPack 和运行态 latest 文件不进入公开仓。
- 公开仓只允许字段名和脱敏样例值，例如 `ACC001`、`<broker_order_id>`。

## 文档

- [运行手册](docs/OPERATIONS_RUNBOOK.md)
- [MCP 设计](docs/MCP_DESIGN.md)
- [当前状态](docs/CURRENT_STATUS.md)
- [验收标准](docs/ACCEPTANCE_STANDARD.md)
- [发布说明](docs/release/v2.0.0-alpha.1.md)

## 许可证

MIT License。详见 [LICENSE](LICENSE)。
