# EnvSnapshot

Task ID: VAL-002
Date: 2026-03-30T11:00:43.3485741+08:00
Role: test

## Host

- OS: Microsoft Windows NT 10.0.26200.0
- Hostname: CHIYU
- Shell: PowerShell 7.6.0
- Working Directory: D:\xtquant-mcp\repo

## Runtime

- Python Executable: `D:\xtquant-mcp\venv313\Scripts\python.exe`
- Python Version: `3.13.12 (tags/v3.13.12:1cbe481, Feb  3 2026, 18:22:25) [MSC v.1944 64 bit (AMD64)]`
- Trade Config Path: `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- EvidencePack: [VAL-002-test-20260330-full-postpatch-rerun.md](../evidence_packs/VAL-002-test-20260330-full-postpatch-rerun.md)
- TaskCard: [VAL-002.md](../task_cards/VAL-002.md)
- ChangePack: [VAL-002.md](../change_packages/VAL-002.md)
- Prior live baselines:
  - [VAL-002-test-202603300306.md](../evidence_packs/VAL-002-test-202603300306.md)
  - [VAL-002-test-20260330-postpatch-rerun.md](../evidence_packs/VAL-002-test-20260330-postpatch-rerun.md)
- Git metadata:
  - `git rev-parse HEAD` and `git status --short` were unavailable because this workspace does not expose `.git`

## Process and Listener State

- Trade gateway before restart:
  - Listener: `127.0.0.1:8765`
  - pid: `22620`
  - Start Time: `2026-03-30T09:03:52.574399+08:00`
  - Executable Path: `C:\Python313\python.exe`
  - Command Line: `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Trade gateway stop event:
  - Stopped at: `2026-03-30T10:55:06.8550276+08:00`
  - Stopped pid: `22620`
- Trade gateway after restart:
  - Listener: `127.0.0.1:8765`
  - pid: `42768`
  - Start Time: `2026-03-30T10:55:16.961535+08:00`
  - Executable Path: `C:\Python313\python.exe`
  - Command Line: `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Data gateway:
  - Listener: `127.0.0.1:8766`
  - pid: `29436`
  - Start Time: `2026-03-30T08:37:49.520449+08:00`
  - Executable Path: `C:\Users\Yun\AppData\Local\Programs\Python\Python311\python.exe`
  - Command Line: `"C:\Users\Yun\AppData\Local\Programs\Python\Python311\python.exe" \\wsl.localhost\Ubuntu-22.04\home\yun\qlib\scripts\..\scripts\run_xtdata_gateway.py --transport streamable-http --host 127.0.0.1 --port 8766 --path /mcp`
- XtMiniQmt:
  - pid: `25880`
  - Start Time: `2026-03-30T00:32:23.418607+08:00`
  - Executable Path: `D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
  - Command Line: `"D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe" "linkMini"`
- miniquote:
  - Listener: `127.0.0.1:58610`
  - pid: `20604`
  - Start Time: `2026-03-30T00:32:23.605108+08:00`
  - Executable Path: `D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe`
  - Command Line: `"D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe" ""`

## Port Reachability

- `127.0.0.1:8765` -> `TcpTestSucceeded=True`
- `127.0.0.1:8766` -> `TcpTestSucceeded=True`
- `127.0.0.1:58610` -> `TcpTestSucceeded=True`

## Health and Artifact Context

- Trade gateway `/healthz` before restart at `2026-03-30T10:54:56.0702144+08:00`:
  - `ok=true`
  - `server_name=xtqmtTradeGateway`
  - `bind_port=8765`
  - `account_contract=single_account_primary`
  - `account_input_mode=service_context_only`
  - `evidence_scope=prod`
  - `evidence_state_root=D:\xtquant-mcp\instance\prod\state`
  - `evidence_artifact_root=D:\xtquant-mcp\instance\prod\artifacts`
- Trade gateway `/healthz` after restart at `2026-03-30T10:57:04.2564051+08:00`:
  - `ok=true`
  - `server_name=xtqmtTradeGateway`
  - `bind_port=8765`
  - `account_contract=single_account_primary`
  - `account_input_mode=service_context_only`
  - `evidence_scope=prod`
  - `evidence_state_root=D:\xtquant-mcp\instance\prod\state`
  - `evidence_artifact_root=D:\xtquant-mcp\instance\prod\artifacts`
- Trade gateway call log:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260330\trade_gateway_calls.jsonl`
- Trade gateway logs for the restarted process:
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_105516.log`
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_105516.stderr.log`
- Wake-path note:
  - `pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1` was the repo-supported launch path
  - The shell call timed out after `94035 ms`, but restart success is evidenced by the changed listener pid, the newer start time, the new log files, and healthy `/healthz`

## Observation Window

- Pre-restart baseline captured: `2026-03-30T10:54:56.0702144+08:00`
- Existing trade gateway stopped: `2026-03-30T10:55:06.8550276+08:00`
- New trade gateway process start time: `2026-03-30T10:55:16.961535+08:00`
- Restarted gateway confirmed healthy: `2026-03-30T10:57:04.2564051+08:00`
- Full live `G3` MCP window:
  - initialize started: `2026-03-30T10:57:37.057735+08:00`
  - final resource read finished: `2026-03-30T10:59:09.432290+08:00`
- Snapshot recorded: `2026-03-30T11:00:43.3485741+08:00`

## Trace Inventory

- `miniqmt.ensure_logged_in`
  - `trace_id=debddf2f-324d-406f-9f1d-dfede04e2de9`
  - `server_ts=2026-03-30T10:57:37`
  - Result: `ok=true`, `status=already_logged_in`
- `session.warm`
  - `trace_id=1742ea3a-4eb2-4035-b5a1-e40c0e24ad34`
  - `server_ts=2026-03-30T10:57:37`
  - Result: `ok=false`, `reason=orders.list_exception`, broker failure `xttrader connect failed: -1`
- `session.status`
  - `trace_id=befe406d-8c9c-43f3-bc24-dc5ba0034cf5`
  - `server_ts=2026-03-30T10:59:09`
  - Result: `ready=false`, `reason=session_not_ready`
- `probe.connection`
  - `trace_id=7654528f-44c9-42a2-acf1-5bb2f5e0a61a`
  - `server_ts=2026-03-30T10:59:09`
  - Result: `error.code=session_not_ready`
- `account.show`
  - `trace_id=3c08c256-cd6c-4116-b19b-2ac79f9abe29`
  - `server_ts=2026-03-30T10:59:09`
  - Result: `error.code=session_not_ready`
- `positions.list`
  - `trace_id=3322c617-79a3-4f81-9f2c-b46a952dc50b`
  - `server_ts=2026-03-30T10:59:09`
  - Result: `error.code=session_not_ready`
- `orders.list`
  - `trace_id=f8c7bd6b-8354-40d5-9df3-c1785c90a4bd`
  - `server_ts=2026-03-30T10:59:09`
  - Result: `error.code=session_not_ready`
- `snapshot.l1`
  - `trace_id=1ed6418b-cb9b-423f-85f0-98787d4cf9f4`
  - `server_ts=2026-03-30T10:59:09`
  - Result: `error.code=session_not_ready`

## Notes

- This full post-patch rerun confirms a real process restart and a fresh code load through the repo-supported wake path.
- The MiniQMT UI visibility/login state is improved relative to the earlier baseline:
  - `miniqmt.ensure_logged_in` now returns `already_logged_in`
  - `diag://login/latest` reflects the same result
- The current hard stop moved deeper into the chain:
  - `session.warm` now reaches shadow `account.show` and `positions.list`
  - it still fails before owner-managed session readiness because broker-side `orders.list` hits `xttrader connect failed: -1`
- After that failure, `trade://session/current` remains `session_not_ready`, and the explicit downstream read tools stay blocked with `session_not_ready`
- This snapshot therefore does not clear the task-card level `Blocked` posture for `VAL-002`
