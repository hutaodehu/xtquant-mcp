# EnvSnapshot

Task ID: VAL-004
Date: 2026-03-31T18:31:13.9557860+08:00
Role: test

## Host

- OS: Microsoft Windows 11
- Hostname: `CHIYU`
- Shell: PowerShell `7.6.0`
- Working Directory: `D:\xtquant-mcp\repo`

## Runtime

- Python Executable: `D:\xtquant-mcp\venv313\Scripts\python.exe`
- Python Version: `3.13.12`
- Trade Config Path: `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- EvidencePack: [VAL-004-test-202603311831-post-login-rerun.md](../evidence_packs/VAL-004-test-202603311831-post-login-rerun.md)
- ChangePack: [VAL-004.md](../change_packages/VAL-004.md)
- Working scope: current Windows repo only, no WSL, no `order.place`, no `VAL-003`

## Process and Listener State

- Trade gateway:
  - listener: `127.0.0.1:8765`
  - pid: `48672`
  - start time: `2026-03-31 18:28:40`
  - command line:
    `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Data gateway:
  - listener: `127.0.0.1:8766`
  - pid: `46732`
  - start time: `2026-03-31 16:51:59`
- XtMiniQmt:
  - pid: `27152`
  - start time: `2026-03-31 16:31:43`
  - executable: `D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
- miniquote:
  - listener: `0.0.0.0:58610`
  - pid: `28824`
  - start time: `2026-03-31 16:31:44`
  - executable: `D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe`

## Port Reachability

- `127.0.0.1:58610` -> `TcpTestSucceeded=True`
- `127.0.0.1:8765` -> `TcpTestSucceeded=True`
- `127.0.0.1:8766` -> `TcpTestSucceeded=True`

## Health and Artifact Context

- Trade gateway `/healthz`:
  - `ok=true`
  - `server_name=xtqmtTradeGateway`
  - `bind_port=8765`
  - `mcp_path=/mcp`
  - `health_path=/healthz`
  - `account_contract=single_account_primary`
  - `account_input_mode=service_context_only`
  - `evidence_scope=prod`
  - `evidence_state_root=D:\xtquant-mcp\instance\prod\state`
  - `evidence_artifact_root=D:\xtquant-mcp\instance\prod\artifacts`
- Fresh trade-gateway logs:
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260331_182839.log`
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260331_182839.stderr.log`
- Trade-gateway call log:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260331\trade_gateway_calls.jsonl`

## State Snapshot

- `trade_session_current.json`
  - last write: `2026-03-31 18:29:30`
  - `ready=true`
  - `account_id=8883884325`
  - `owner_account_id=8883884325`
  - `session_id=1111`
  - `reason=''`
- `diag_probe_latest.json`
  - last write: `2026-03-31 18:29:30`
  - `ok=true`
  - `reason=ok`
  - `session_id=1111`
  - `read_only_ready=true`
  - `write_permission_ready=true`
  - `up_queue_xtquant_exists=true`
- `diag_login_latest.json`
  - last write: `2026-03-31 18:29:30`
  - `ok=true`
  - `status=already_logged_in`
  - `account_id=8883884325`
  - `credential_target=paper_trader_v1/miniqmt/8883884325`
  - main-window title now shows `8883884325 - 国金证券QMT交易端 2.0.8.300`

## Observation Window

- Fresh trade-gateway process start time: `2026-03-31 18:28:40`
- Latest non-write rerun window:
  - `miniqmt.ensure_logged_in` at `2026-03-31T18:29:29`
  - `session.warm` at `2026-03-31T18:29:30`
  - `session.status`, `probe.connection`, `account.show`, `positions.list`, `orders.list`, `snapshot.l1` at `2026-03-31T18:29:30`
- Snapshot recorded: `2026-03-31T18:31:13.9557860+08:00`

## Notes

- This snapshot supersedes the earlier not-logged-in posture for `VAL-004`. The host/login side is now sufficiently ready for `session.warm`, `session.status`, and `probe.connection` to succeed.
- The remaining first blocker captured in this window is not login-related. It is the public `orders.list` failure: `'NoneType' object has no attribute 'query_open_orders'`.
