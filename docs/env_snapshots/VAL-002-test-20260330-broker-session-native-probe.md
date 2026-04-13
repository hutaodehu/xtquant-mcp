# EnvSnapshot

Task ID: VAL-002
Date: 2026-03-30T11:17:31.2889758+08:00
Role: test

## Host

- OS: Microsoft Windows NT 10.0.26200.0
- Hostname: CHIYU
- Shell: PowerShell 7.6.0
- Working Directory: `D:\xtquant-mcp\repo`
- Live Instance Root: `D:\xtquant-mcp\instance\prod`

## Runtime

- Python Executable: `D:\xtquant-mcp\venv313\Scripts\python.exe`
- Python Version: `3.13.12 (tags/v3.13.12:1cbe481, Feb  3 2026, 18:22:25) [MSC v.1944 64 bit (AMD64)]`
- Trade Config Path: `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Data Config Path: `D:\xtquant-mcp\instance\prod\config\data_gateway.local.yaml`
- EvidencePack: [VAL-002-test-20260330-broker-session-native-probe.md](../evidence_packs/VAL-002-test-20260330-broker-session-native-probe.md)
- TaskCard: [VAL-002.md](../task_cards/VAL-002.md)
- Prior live comparison:
  - [VAL-002-test-20260330-full-postpatch-rerun.md](../evidence_packs/VAL-002-test-20260330-full-postpatch-rerun.md)
  - [VAL-002-review-20260330-full-postpatch-rerun.md](../reviews/VAL-002-review-20260330-full-postpatch-rerun.md)

## Config Baseline

- `trade_gateway.local.yaml`
  - `qmt.qmt_exe = D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
  - `qmt.qmt_userdata = D:\lh\国金证券QMT交易端\userdata_mini`
  - `qmt.xtdata_host = 127.0.0.1`
  - `qmt.xtdata_port = 58610`
  - `trade.session_id = 100`
  - `trade.session_candidates = [100, 101, 111]`
  - `trade.auto_account = true`
- `data_gateway.local.yaml`
  - `qmt.qmt_exe = D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
  - `qmt.qmt_userdata = D:\lh\国金证券QMT交易端\userdata_mini`
  - `qmt.xtdata_host = 127.0.0.1`
  - `qmt.xtdata_port = 58610`

## Behavioral Reference

- Official ThinkTrader native API reference: <https://dict.thinktrader.net/nativeApi/xttrader.html>
- Bounded behavioral assumptions used for this env investigation:
  - one `XtQuantTrader` instance is usually sufficient
  - `session_id` must not collide
- This snapshot intentionally stayed within that official-pattern envelope and did not expand into wider multi-instance stress behavior.

## Process and Listener State

- `XtMiniQmt`
  - pid: `25880`
  - start time: `2026-03-30T00:32:23.4186077+08:00`
  - executable path: `D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
- `miniquote`
  - pid: `20604`
  - start time: `2026-03-30T00:32:23.6051081+08:00`
  - executable path: `D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe`
- Trade gateway
  - live bind: `127.0.0.1:8765`
  - health state was already known healthy from the prior same-day rerun
- Data gateway
  - live bind: `127.0.0.1:8766`
- `127.0.0.1:58610`
  - `TcpTestSucceeded=True`

## Gateway-side State Files

- `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json`
  - `ok=true`
  - `status=already_logged_in`
  - `process_id=25880`
  - `port_ready=true`
  - main window title captured as `8883884325 - 国金证券QMT交易端 2.0.8.300`
- `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json`
  - `ready=false`
  - `reason=session_not_ready`
  - `session_id=''`
  - `owner_generation=0`
- `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json`
  - contract-only resource state, without a warmed broker session

## Native Probe Runtime

- Probe Python: `D:\xtquant-mcp\venv313\Scripts\python.exe`
- `xtquant` package root: `D:\xtquant-mcp\vendor\xtquant_250807\xtquant`
- `XtQuantTrader.__init__`: `(self, path, session, callback=None)`
- Native methods confirmed visible:
  - `connect`
  - `query_account_infos`
  - `query_stock_asset`
  - `query_stock_positions`
  - `query_stock_orders`
  - `start`
  - `stop`
  - `subscribe`
- Probe target user data:
  - `D:\lh\国金证券QMT交易端\userdata_mini`
- Session ids tested in this bounded run:
  - `100`
  - `101`

## Observation Window

- Current process and port baseline captured: `2026-03-30T11:14:21.7053506+08:00`
- Native probe started: `2026-03-30T11:16:48.136649+08:00`
- Session `100` connect window:
  - start: `2026-03-30T11:16:48.179280+08:00`
  - finish: `2026-03-30T11:16:51.180991+08:00`
  - result: `connect_code=-1`
- Session `101` connect window:
  - start: `2026-03-30T11:16:51.210921+08:00`
  - finish: `2026-03-30T11:16:54.222546+08:00`
  - result: `connect_code=-1`
- Snapshot recorded: `2026-03-30T11:17:31.2889758+08:00`

## Native Probe State

- Session `100`
  - `start()` succeeded
  - `connect()` returned `-1`
  - no callback events captured
  - `query_account_infos`, `subscribe`, `query_stock_asset`, `query_stock_positions`, `query_stock_orders` were not reached
- Session `101`
  - `start()` succeeded
  - `connect()` returned `-1`
  - no callback events captured
  - `query_account_infos`, `subscribe`, `query_stock_asset`, `query_stock_positions`, `query_stock_orders` were not reached

## Environment Classification

- Stronger evidence supports `fail_env`:
  - login recovered
  - MiniQMT runtime visible
  - xtdata port reachable
  - direct native `xttrader.connect()` still fails outside the gateway
- Not established as `fail_design` in this bounded run:
  - the failure reproduced before account/order query lifecycle could start
  - no gateway-only bug was isolated by this experiment
- Remaining narrow design hypothesis, not yet proven:
  - static session candidate choice may need a later controlled allocation strategy because official guidance only requires non-collision
  - that is a later dev hypothesis, not a validated test conclusion from this run

## Notes

- This snapshot was intentionally bounded to the two owned documentation files only.
- No repo source files were edited.
- No task card, change package, or review record was edited.
- The test remains blocked at the environment layer and does not change the formal blocked posture of `VAL-002`.
- `VAL-003` remains out of scope and still must not be unblocked from this evidence.
