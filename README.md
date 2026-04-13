# xtqmt-mcp

`xtqmt-mcp` 是一套面向 agent 的 Windows 本地 MCP 服务，职责只保留两类：

1. `xtqmtTradeGateway`
   负责 `MiniQMT` 登录、交易会话、账户/持仓/委托/成交、`L1` 快照、下单撤单和诊断证据。
2. `xtqmtDataGateway`
   负责 `xtdata` 实时/批量数据能力，以及异步下载作业。

## 目录约定

- 代码仓：`D:\xtquant-mcp\repo`
- 运行时：`D:\xtquant-mcp\instance\prod`
- vendor bundle：`D:\xtquant-mcp\vendor\xtquant_250807`
- Python venv：`D:\xtquant-mcp\venv313`

## 当前原则

- 不再依赖 `D:\lh\qlib`、`.venv311` 或 QMT 安装目录下的 `site-packages`
- `xtquant` 通过受控 vendor bundle 挂载到 venv
- 两个 MCP 服务都只绑定 `127.0.0.1`
- WSL/agent 侧只通过 MCP 调用，不在 WSL 直接 `import xtquant`
- 生产实例的 trade 配置必须设置非空 `kill_switch_file`；空值只能保留在非 prod / 示例上下文
- `trade://...` / `xtdata://...` 资源现在会显式区分 `live_runtime_truth` 与 `cached_last_known_state`，不能再把旧缓存误读成当前 listener 真相

## 入口脚本

- `scripts/bootstrap_runtime.ps1`
- `scripts/run_trade_gateway_http.py`
- `scripts/run_data_gateway_http.py`
- `scripts/wake_miniqmt.ps1`
- `scripts/wake_trade_gateway.ps1`
- `scripts/wake_data_gateway.ps1`

## 配置文件

- 样例：`configs/trade_gateway.example.yaml`
- 非真实流程烟测：`configs/trade_gateway.flow_smoke.yaml`
- 样例：`configs/data_gateway.example.yaml`
- 实例：`D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- 实例：`D:\xtquant-mcp\instance\prod\config\data_gateway.local.yaml`

## 协作与验收

- 仓库协作规则：`AGENTS.md`
- repo-local harness skill：`.agents/skills/spec-task-harness/SKILL.md`
- harness 主控模式：`controller-only`（默认）与 `controller-with-delegation`（显式授权多 agent 编排时）
- 子代理最低门槛：`gpt-5.4` + `high`
- board export / sync 样例：`.agents/skills/spec-task-harness/examples/board_export.sample.json`、`.agents/skills/spec-task-harness/examples/board_sync.sample.json`
- 执行与工件规范：`docs/EXECUTION_AND_ARTIFACT_STANDARD.md`
- 任务流转与外部看板字段：`docs/WORKFLOW_AND_BOARD.md`
- xtquant MCP 验收标准：`docs/ACCEPTANCE_STANDARD.md`
- 协作模板：`docs/TEMPLATES.md`
- 首轮任务拆分：`docs/FIRST_WAVE_TASK_BREAKDOWN.md`
- 设计文档：`docs/MCP_DESIGN.md`
- 当前状态：`docs/CURRENT_STATUS.md`
- 设计审查：`docs/DESIGN_REVIEW_20260327.md`

## 推荐启动顺序

```powershell
pwsh -File scripts/bootstrap_runtime.ps1
pwsh -File scripts/wake_miniqmt.ps1
pwsh -File scripts/wake_data_gateway.ps1
pwsh -File scripts/wake_trade_gateway.ps1
```

## Bundle 校验

```powershell
D:\xtquant-mcp\venv313\Scripts\python.exe scripts\verify_xtquant_bundle.py --import-check
```

## Non-Prod Flow Smoke

盘后或 broker/live gate 未闭合时，如需先验证 MCP 发单生命周期，可使用 `execution_mode=flow_smoke` 的 non-prod 配置。这条路径只验证 `session.warm -> order.place -> order.status -> orders.list -> order.cancel -> fills.list` 的流程闭环，不会生成真实 broker 委托，也不能作为 `VAL-003/G4` 放行证据。

```powershell
D:\xtquant-mcp\venv313\Scripts\python.exe scripts\run_trade_flow_smoke.py --config configs\trade_gateway.flow_smoke.yaml --output-json .tmp\trade_flow_smoke\latest.json
```

默认参数会对 `515880.SH` 以 `BUY 100`、`price_mode=fixed`、`limit_price=1.23` 运行本地 flow-smoke 生命周期。结果会明确标记为 `execution_mode=flow_smoke` 且 `broker_truth_confirmed=false`。
