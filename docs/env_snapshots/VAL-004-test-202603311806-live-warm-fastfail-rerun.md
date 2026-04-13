# EnvSnapshot

Task ID: VAL-004
Date: 2026-03-31T18:23:42.3845442+08:00
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
- EvidencePack: [VAL-004-test-202603311806-live-warm-fastfail-rerun.md](../evidence_packs/VAL-004-test-202603311806-live-warm-fastfail-rerun.md)
- ChangePack: [VAL-004.md](../change_packages/VAL-004.md)
- Working scope: current Windows repo only, no WSL, no `order.place`, no `VAL-003`

## Process and Listener State

- Trade gateway before reload:
  - listener: `127.0.0.1:8765`
  - pid: `36116`
  - start time: `2026-03-31 17:54:55`
  - command line:
    `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Trade gateway after reload:
  - listener: `127.0.0.1:8765`
  - pid: `47588`
  - parent pid: `36888`
  - start time: `2026-03-31 17:58:37`
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

- Trade gateway `/healthz` after reload:
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
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260331_175837.log`
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260331_175837.stderr.log`
- Trade-gateway call log:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260331\trade_gateway_calls.jsonl`
- State files touched by the rerun:
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json`

## Observation Window

- Fresh trade-gateway process start time: `2026-03-31 17:58:37`
- Latest `miniqmt.ensure_logged_in` server timestamp: `2026-03-31T18:01:44`
- Latest `session.warm` server timestamp: `2026-03-31T18:01:44`
- Follow-up `session.status` and downstream public tools: `2026-03-31T18:04:00`
- Snapshot recorded: `2026-03-31T18:23:42.3845442+08:00`

## State Snapshot

- `diag_login_latest.json`
  - last write: `2026-03-31 18:01:44`
  - `ok=true`
  - `status=already_logged_in`
  - `account_id=8883884325`
  - `credential_target=paper_trader_v1/miniqmt/8883884325`
  - `port_ready=true`
  - `submit_attempted=false`
  - interpretation boundary: this shows visible window plus reachable `58610`, not proven broker trade-login completion
- `trade_session_current.json`
  - last write: `2026-03-31 18:04:00`
  - `ready=false`
  - `reason=session_not_ready`
  - `account_id=''`
  - `session_id=''`
- `diag_probe_latest.json`
  - last write: `2026-03-31 18:04:00`
  - only contract-level fields were present

## Notes

- The outer stop+wake wrapper timed out during reload, but the fresh listener pid, fresh process start time, new log files, and healthy `/healthz` together prove that a new repo-loaded trade-gateway process was started.
- This snapshot intentionally does not claim broker login readiness. The visible main window and `already_logged_in` login artifact do not prove that a password-submit flow happened or that the broker trading session is ready.
