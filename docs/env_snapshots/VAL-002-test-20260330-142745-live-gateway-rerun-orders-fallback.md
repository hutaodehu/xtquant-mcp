# EnvSnapshot

Task ID: VAL-002
Date: 2026-03-30T14:27:45.669592+08:00
Role: test

## Host

- OS: Microsoft Windows 11 专业工作站版 (`10.0.26200`)
- Hostname: `CHIYU`
- Shell: PowerShell `7.6.0`
- Working Directory: `D:\xtquant-mcp\repo`

## Runtime

- Python Executable: `D:\xtquant-mcp\venv313\Scripts\python.exe`
- Python Version: `3.13.12`
- Trade Config Path: `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- EvidencePack: [VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md](../evidence_packs/VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md)
- ChangePack: [VAL-002.md](../change_packages/VAL-002.md)
- Prior comparison baselines:
  - [VAL-002-test-20260330-134330-live-gateway-rerun.md](../evidence_packs/VAL-002-test-20260330-134330-live-gateway-rerun.md)
  - [VAL-002-review-20260330-135658-live-gateway-rerun-followup.md](../reviews/VAL-002-review-20260330-135658-live-gateway-rerun-followup.md)
  - [TG-004.md](../change_packages/TG-004.md)
- Git metadata:
  - `git rev-parse HEAD` and `git status --short` are unavailable because this workspace does not expose `.git`

## Process and Listener State

- Trade gateway before restart:
  - Observed at: `2026-03-30T14:14:47.0902745+08:00`
  - Listener: `127.0.0.1:8765`
  - pid: `36532`
  - Start Time: `2026-03-30T13:37:03.631422+08:00`
  - Executable Path: `C:\Python313\python.exe`
  - Command Line:
    `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Trade gateway restart method:
  - Repo-supported launch path: `pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1`
  - Repo restart helper: not present
  - This rerun therefore used a controlled stop of the existing `8765` listener process followed by the supported wake path.
  - Combined stop+wake wrapper result: shell capture timed out after `124049 ms`
- Trade gateway after restart:
  - Observed at: `2026-03-30T14:20:18.3695570+08:00`
  - Listener: `127.0.0.1:8765`
  - pid: `3984`
  - Start Time: `2026-03-30T14:17:23.795229+08:00`
  - Executable Path: `C:\Python313\python.exe`
  - Command Line:
    `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Data gateway:
  - Listener: `127.0.0.1:8766`
  - pid: `29436`
  - Start Time: `2026-03-30T08:37:49.520449+08:00`
  - Executable Path: `C:\Users\Yun\AppData\Local\Programs\Python\Python311\python.exe`
  - Command Line:
    `"C:\Users\Yun\AppData\Local\Programs\Python\Python311\python.exe" \\wsl.localhost\Ubuntu-22.04\home\yun\qlib\scripts\..\scripts\run_xtdata_gateway.py --transport streamable-http --host 127.0.0.1 --port 8766 --path /mcp`
- XtMiniQmt:
  - pid: `25880`
  - Start Time: `2026-03-30T00:32:23.4186077+08:00`
  - Executable Path: `D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
- miniquote:
  - Listener: `0.0.0.0:58610`
  - pid: `20604`
  - Start Time: `2026-03-30T00:32:23.6051081+08:00`
  - Executable Path: `D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe`

## Port Reachability

- `127.0.0.1:8765`
  - pre-restart: `TcpTestSucceeded=True`
  - post-restart: `TcpTestSucceeded=True`
- `127.0.0.1:8766` -> `TcpTestSucceeded=True`
- `127.0.0.1:58610` -> `TcpTestSucceeded=True`

## Health and Artifact Context

- Trade gateway `/healthz` before restart:
  - timestamp: `2026-03-30T14:14:47.1429170+08:00`
  - `ok=true`
  - `bind_port=8765`
  - `account_contract=single_account_primary`
  - `account_input_mode=service_context_only`
  - `evidence_scope=prod`
- Trade gateway `/healthz` after restart:
  - timestamp: `2026-03-30T14:20:18.3705368+08:00`
  - `ok=true`
  - `server_name=xtqmtTradeGateway`
  - `server_version=2.0.0a0`
  - `bind_port=8765`
  - `mcp_path=/mcp`
  - `health_path=/healthz`
  - `account_contract=single_account_primary`
  - `account_input_mode=service_context_only`
  - `readiness_layers.read_only.blocking=true`
  - `readiness_layers.write_permission.blocking=false`
  - `evidence_scope=prod`
  - `evidence_state_root=D:\xtquant-mcp\instance\prod\state`
  - `evidence_artifact_root=D:\xtquant-mcp\instance\prod\artifacts`
- Trade gateway call log:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260330\trade_gateway_calls.jsonl`
- Trade gateway logs for the restarted process:
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_141723.log`
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_141723.stderr.log`
- State files touched by the ordered chain:
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json` (`2026-03-30T14:21:52.3730699+08:00`)
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json` (`2026-03-30T14:22:38.356528+08:00`)
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json` (`2026-03-30T14:22:38.3805674+08:00`)

## Observation Window

- Pre-restart live-state captured: `2026-03-30T14:14:47.0902745+08:00`
- Fresh trade gateway process start time: `2026-03-30T14:17:23.795229+08:00`
- Restarted gateway confirmed healthy: `2026-03-30T14:20:18.3705368+08:00`
- Full live `G3` MCP window:
  - initialize started: `2026-03-30T14:21:52.287489+08:00`
  - last tool `server_ts`: `2026-03-30T14:23:23`
- Post-chain resource re-read window:
  - `trade://session/current` read finished: `2026-03-30T14:27:45.668690+08:00`
  - `diag://probe/latest` read finished: `2026-03-30T14:27:45.669198+08:00`
  - `diag://login/latest` read finished: `2026-03-30T14:27:45.669592+08:00`
- Snapshot recorded: `2026-03-30T14:27:45.669592+08:00`

## Trace Inventory

- `miniqmt.ensure_logged_in`
  - `trace_id=56e03e01-9549-415b-bb75-5db8a6facee1`
  - `server_ts=2026-03-30T14:21:52`
  - Result: `ok=true`, `status=already_logged_in`, `process_id=25880`, `port_ready=true`
- `session.warm`
  - `trace_id=b70269d1-d8e3-4b99-bb7b-5b54e5f40290`
  - `server_ts=2026-03-30T14:21:52`
  - Result: `ok=true`, `ready=true`, `session_id=100`, `owner_generation=1`
- `session.status`
  - `trace_id=fde946b2-8c60-438f-b1c5-8f4a0933ba54`
  - `server_ts=2026-03-30T14:22:38`
  - Result: `ok=true`, `ready=true`, `session_id=100`
- `probe.connection`
  - `trace_id=f043f961-4e8c-4215-8de6-4247a9af6e42`
  - `server_ts=2026-03-30T14:22:38`
  - Result: `ok=true`, `probe_mode=owner_managed_session_reuse`, `read_only_source=active_owner_shadow`, `write_permission_source=userdata_precheck`
- `account.show`
  - `trace_id=7bf71dce-08e3-4837-b570-190c8e249144`
  - `server_ts=2026-03-30T14:22:38`
  - Result: `ok=true`, `source=xttrader_shadow`
- `positions.list`
  - `trace_id=766beaca-8dc9-4807-8367-be137977be98`
  - `server_ts=2026-03-30T14:22:38`
  - Result: `ok=true`, `count=2`
- `orders.list`
  - `trace_id=f3468625-da8e-48e9-9a35-4f84ef54dc2d`
  - `server_ts=2026-03-30T14:22:38`
  - Result:
    - `ok=true`
    - `degraded=true`
    - `fallback_used=true`
    - `fallback_reason=broker_connect_failed`
    - `source=active_owner_shadow`
    - `read_scope=public_fallback`
    - `broker_read.ok=false`
    - `broker_read.fresh_connect_attempted=true`
    - `broker_read.fresh_connect_ok=false`
- `snapshot.l1`
  - `trace_id=c3090037-b7e0-40fd-b723-c4b8db3901c3`
  - `server_ts=2026-03-30T14:23:23`
  - Result: `ok=true`, `code=000001.SZ`, `source=online_pull`

## Resource State After Chain

- `trade://session/current`
  - re-read at `2026-03-30T14:27:45.666151+08:00` -> `2026-03-30T14:27:45.668690+08:00`
  - `ready=true`
  - `account_id=8883884325`
  - `owner_account_id=8883884325`
  - `session_id=100`
  - `owner_generation=1`
- `diag://probe/latest`
  - re-read at `2026-03-30T14:27:45.668731+08:00` -> `2026-03-30T14:27:45.669198+08:00`
  - `ok=true`
  - `reason=ok`
  - `probe_mode=owner_managed_session_reuse`
  - `session_id=111`
  - `session_reused=true`
  - `fresh_connect_attempted=false`
  - `readiness_layers.read_only.ok=true`
  - `readiness_layers.read_only.source=active_owner_shadow`
  - `readiness_layers.write_permission.ok=true`
  - `readiness_layers.write_permission.source=userdata_precheck`
- `diag://login/latest`
  - re-read at `2026-03-30T14:27:45.669234+08:00` -> `2026-03-30T14:27:45.669592+08:00`
  - `ok=true`
  - `status=already_logged_in`
  - `message=MiniQMT already logged in`

## Notes

- This rerun differs from the prior fresh rerun in restart shape:
  - previous fresh rerun started from `8765 down`
  - this rerun started from a healthy existing listener and therefore required controlled stop + supported wake
- The runtime delta versus the previous rerun is concentrated in public `orders.list`:
  - previous: explicit public failure
  - current: explicit public degraded fallback success, with broker failure preserved in `broker_read`
- One payload-level observation remains separate from the formal chain result:
  - `session.status` and `trade://session/current` report `session_id=100`
  - `probe.connection` and `diag://probe/latest` report reused shadow `session_id=111`
  - this snapshot records that identifier split as observation only
- The chain is complete, but this snapshot does not replace review:
  - workflow-wise, test evidence can move the task from `Blocked` to `In Review`
  - only a ReviewPack can move the task to `Accepted`
