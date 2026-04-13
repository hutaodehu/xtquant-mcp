# EnvSnapshot

Task ID: VAL-002
Date: 2026-03-30T11:58:00+08:00
Role: test

## Host

- OS: `Microsoft Windows NT 10.0.26200.0`
- Hostname: `CHIYU`
- Shell: `PowerShell 7.6.0`
- Working Directory: `D:\xtquant-mcp\repo`
- EvidencePack: [VAL-002-test-20260330-native-query-chain.md](../evidence_packs/VAL-002-test-20260330-native-query-chain.md)

## Runtime

- Python executable: `D:\xtquant-mcp\venv313\Scripts\python.exe`
- xtquant package root: `D:\xtquant-mcp\vendor\xtquant_250807\xtquant`
- Trade config path: `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Live userdata root: `D:\lh\国金证券QMT交易端\userdata_mini`
- Probe target session: `101`
- Probe pattern: `single_instance_single_lifecycle_native_query_chain`

## Process and Port State

- Observation time: `2026-03-30T11:55:30.9539019+08:00`
- `XtMiniQmt`
  - pid `25880`
  - start `2026-03-30T00:32:23.4186077+08:00`
  - path `D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
- `miniquote`
  - pid `20604`
  - start `2026-03-30T00:32:23.6051081+08:00`
  - path `D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe`
- `127.0.0.1:58610`
  - `TcpTestSucceeded=true`

## Gateway Baseline Context

- Baseline reads performed before the native probe:
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json`
- Observed facts:
  - login state still reported `ok=true`, `status=already_logged_in`, `port_ready=true`
  - trade session still reported `ready=false`, `reason=session_not_ready`, `session_id=""`, `owner_generation=0`
- This means the gateway-side session lifecycle was still not warmed even though the host and login baseline were healthy enough to run the bounded native probe.

## Config Baseline

- `trade_gateway.local.yaml`
  - `qmt.qmt_exe = D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
  - `qmt.qmt_userdata = D:\lh\国金证券QMT交易端\userdata_mini`
  - `qmt.xtdata_host = 127.0.0.1`
  - `qmt.xtdata_port = 58610`
  - `trade.session_id = 100`
  - `trade.session_candidates = [100, 101, 111]`
  - `trade.require_connect_stage = true`
  - `trade.require_subscribe_stage = true`
  - `trade.require_snapshot_stage = true`

## Candidate Session Selection

- Candidate artifact inventory time: `2026-03-30T11:55:31.1772665+08:00`
- Queue-file mtimes:
  - `down_queue_win_101` -> `2026-03-30T11:46:45.5207461+08:00`
  - `down_queue_win_100` -> `2026-03-30T11:16:48.1548852+08:00`
  - `down_queue_win_111` -> `2026-03-30T10:59:06.3285110+08:00`
- Selection rule used:
  - keep to one candidate only
  - prefer the freshest session that had same-day successful native connect evidence
- Chosen session:
  - `session_id=101`

## Native Lifecycle Window

- Probe observed at: `2026-03-30T11:56:43.286253+08:00`
- `start`
  - `2026-03-30T11:56:43.301297+08:00` -> `2026-03-30T11:56:43.328320+08:00`
- `connect`
  - `2026-03-30T11:56:43.328339+08:00` -> `2026-03-30T11:56:43.328821+08:00`
  - `connect_code=0`
- `post_connect_settle`
  - `2026-03-30T11:56:43.328339+08:00` -> `2026-03-30T11:56:44.328898+08:00`
- `query_account_infos`
  - `2026-03-30T11:56:44.328933+08:00` -> `2026-03-30T11:56:44.329560+08:00`
  - returned `1` account row
  - selected `account_id=8883884325`
- `subscribe`
  - `2026-03-30T11:56:44.329583+08:00` -> `2026-03-30T11:56:44.329761+08:00`
  - `subscribe_code=0`
- `post_subscribe_settle`
  - `2026-03-30T11:56:44.329583+08:00` -> `2026-03-30T11:56:45.330182+08:00`
- `query_stock_asset`
  - `2026-03-30T11:56:45.330218+08:00` -> `2026-03-30T11:56:45.330516+08:00`
  - returned `cash=4497.04`, `market_value=111129.00000000001`, `total_asset=115626.04`
- `query_stock_positions`
  - `2026-03-30T11:56:45.330547+08:00` -> `2026-03-30T11:56:45.330679+08:00`
  - returned `2` rows
- `query_stock_orders`
  - `2026-03-30T11:56:45.330704+08:00` -> `2026-03-30T11:56:45.330856+08:00`
  - returned `5` rows
- `stop`
  - `2026-03-30T11:56:45.330891+08:00` -> `2026-03-30T11:56:45.333047+08:00`
- Final native result:
  - `result=success`
  - `first_failure_step=null`
  - Python callback events captured: none

## Host-Log Correlation

Focused lines from `D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log`:

```text
14096:2026-03-30 11:56:43,328 ... onConnected] quant session 101 connected
14097:2026-03-30 11:56:44,328 ... onQueryAccountInfosReq] query accountInfos found 1
14102:2026-03-30 11:56:44,328 ... onSubscribe] account 8883884325 2 subscribed datas in quant session 101
14103:2026-03-30 11:56:45,330 ... onQueryStockAsset] query account detail 8883884325 2, seq:4, tag:101
14104:2026-03-30 11:56:45,330 ... onQueryStockPositions] query positions found 2, 8883884325 2, seq:5, tag:101
14110:2026-03-30 11:56:45,330 ... onQueryStockOrders] query orders found 5, 8883884325 2 0, seq:7, tag:101
14111:2026-03-30 11:56:49,518 ... heartbeat timeout, ssid:101, hsz:4
14113:2026-03-30 11:56:49,520 ... onDisconnected] quant session 101 disconneted
14114:2026-03-30 11:56:49,520 ... lock_down_queue_win_101 file lock not held, offline
```

Host-log implications:

1. The host confirmed every read-only step that the Python probe attempted.
2. `orders` query reached QMT and returned `5` rows in the same lifecycle.
3. The timeout/disconnect sequence appeared only after explicit `stop()`, about `4.187s` later.

## Queue-File State After Probe

- Post-probe check time: `2026-03-30T11:57:01.2804983+08:00`
- `down_queue_win_101`
  - length `75497752`
  - mtime `2026-03-30T11:56:43.3042734+08:00`
- `down_queue_win_101__mutex`
  - mtime `2026-03-30T03:05:03.6122410+08:00`
- No `lock_down_queue_win_101` file was present in the bounded post-probe inventory.

## Environment Classification

- This snapshot does not support keeping the native `101` read-only path classified only as unresolved `fail_env`.
- What it does support:
  - one native instance on `session_id=101` can complete `connect -> account_infos -> subscribe -> asset -> positions -> orders`
  - the gateway-side lifecycle is still stuck at `session_not_ready` despite that
  - the `gateway sequence/lifecycle mismatch` hypothesis is therefore stronger than before
- What it does not yet prove:
  - a specific gateway implementation fault
  - a task-level `fail_design` verdict
  - a `VAL-002` gate pass

## Notes

- This run stayed read-only.
- No repo code, task card, change package, or review file was edited.
- Only the owned `EvidencePack` and `EnvSnapshot` paths were written.
- Task posture remains unchanged:
  - `VAL-002` remains blocked
  - `VAL-003` remains blocked and out of scope
