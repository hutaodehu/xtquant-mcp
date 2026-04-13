# EnvSnapshot

Task ID: VAL-002
Date: 2026-03-30T13:43:30.636772+08:00
Role: test

## Host

- OS: Microsoft Windows 11 专业工作站版 (`10.0.26200`)
- Hostname: CHIYU
- Shell: PowerShell `7.6.0`
- Working Directory: `D:\xtquant-mcp\repo`

## Runtime

- Python Executable: `D:\xtquant-mcp\venv313\Scripts\python.exe`
- Python Version: `3.13.12`
- Trade Config Path: `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- EvidencePack: [VAL-002-test-20260330-134330-live-gateway-rerun.md](../evidence_packs/VAL-002-test-20260330-134330-live-gateway-rerun.md)
- TaskCard: [VAL-002.md](../task_cards/VAL-002.md)
- ChangePack: [VAL-002.md](../change_packages/VAL-002.md)
- Prior comparison baselines:
  - [VAL-002-test-20260330-124617-live-gateway-rerun.md](../evidence_packs/VAL-002-test-20260330-124617-live-gateway-rerun.md)
  - [VAL-002-review-20260330-live-gateway-rerun.md](../reviews/VAL-002-review-20260330-live-gateway-rerun.md)
  - [TG-004.md](../change_packages/TG-004.md)
- Git metadata:
  - `git rev-parse HEAD` and `git status --short` are unavailable because this workspace does not expose `.git`

## Process and Listener State

- Trade gateway before restart:
  - Observed at: `2026-03-30T13:36:38.6072342+08:00`
  - Listener: not present on `127.0.0.1:8765`
  - `/healthz`: connection refused (`127.0.0.1:8765`)
  - `TcpTestSucceeded=False`
- Trade gateway wake attempt:
  - Repo-supported path: `pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1`
  - Result: shell command returned `exit_code=0`
  - Direct wake-script JSON was not emitted in this shell capture
- Trade gateway after restart:
  - Observed at: `2026-03-30T13:37:22.5259169+08:00`
  - Listener: `127.0.0.1:8765`
  - pid: `36532`
  - Start Time: `2026-03-30T13:37:03.631422+08:00`
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
  - Listener: `0.0.0.0:58610`
  - pid: `20604`
  - Start Time: `2026-03-30T00:32:23.605108+08:00`
  - Executable Path: `D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe`
  - Command Line: `"D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe" ""`

## Port Reachability

- `127.0.0.1:8765`
  - pre-restart: `TcpTestSucceeded=False`
  - post-restart: `TcpTestSucceeded=True`
- `127.0.0.1:8766` -> `TcpTestSucceeded=True`
- `127.0.0.1:58610` -> `TcpTestSucceeded=True`

## Health and Artifact Context

- Trade gateway `/healthz` before restart:
  - timestamp: `2026-03-30T13:36:38.6072342+08:00`
  - result: unavailable (`connection refused`)
- Trade gateway `/healthz` after restart:
  - timestamp: `2026-03-30T13:37:22.5259169+08:00`
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
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_133703.log`
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_133703.stderr.log`
- State files touched by the ordered chain:
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json` (`2026-03-30T13:37:52.3867948+08:00`)
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json` (`2026-03-30T13:38:14.2651638+08:00`)
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json` (`2026-03-30T13:38:14.2782795+08:00`)

## Observation Window

- Pre-restart down state captured: `2026-03-30T13:36:38.6072342+08:00`
- New trade gateway process start time: `2026-03-30T13:37:03.631422+08:00`
- Restarted gateway confirmed healthy: `2026-03-30T13:37:22.5259169+08:00`
- Full live `G3` MCP window:
  - initialize started: `2026-03-30T13:37:52.285554+08:00`
  - final chain response finished: `2026-03-30T13:39:00.112238+08:00`
- Post-chain resource re-read window:
  - `trade://session/current` read finished: `2026-03-30T13:43:30.635871+08:00`
  - `diag://probe/latest` read finished: `2026-03-30T13:43:30.636386+08:00`
  - `diag://login/latest` read finished: `2026-03-30T13:43:30.636772+08:00`
- Snapshot recorded: `2026-03-30T13:43:30.636772+08:00`

## Trace Inventory

- `miniqmt.ensure_logged_in`
  - `trace_id=9d13f7ff-5c6b-4d39-b7e8-919188441db9`
  - `server_ts=2026-03-30T13:37:52`
  - Result: `ok=true`, `status=already_logged_in`, `process_id=25880`, `port_ready=true`
- `session.warm`
  - `trace_id=9ca5d486-ca94-421e-89c9-2e5ec6f76cfb`
  - `server_ts=2026-03-30T13:37:52`
  - Result: `ok=true`, `ready=true`, `session_id=100`, `owner_generation=1`
- `session.status`
  - `trace_id=326848a6-fcdf-41dd-ac0a-201ff0382935`
  - `server_ts=2026-03-30T13:38:14`
  - Result: `ok=true`, `ready=true`, `session_id=100`
- `probe.connection`
  - `trace_id=333e5c86-7250-4b0b-afb1-5e9d31d77f57`
  - `server_ts=2026-03-30T13:38:14`
  - Result: `ok=true`, `probe_mode=owner_managed_session_reuse`, `read_only_source=active_owner_shadow`, `write_permission_source=userdata_precheck`
- `account.show`
  - `trace_id=8edeb477-3004-423a-96d6-d8555f8450d8`
  - `server_ts=2026-03-30T13:38:14`
  - Result: `ok=true`, `source=xttrader_shadow`
- `positions.list`
  - `trace_id=bbc6778f-0d2f-4cd3-a23c-7e71911a13c3`
  - `server_ts=2026-03-30T13:38:14`
  - Result: `ok=true`, `count=2`
- `orders.list`
  - `trace_id=362e87d2-9aa1-4282-80c8-ceccf2e0d939`
  - `server_ts=2026-03-30T13:38:14`
  - Result: `ok=false`, `error.message=xttrader connect failed: -1 after 3 attempts (...)`
- `snapshot.l1`
  - `trace_id=f2700f2c-cf32-4046-ac72-5bcc8e01e824`
  - `server_ts=2026-03-30T13:38:59`
  - Result: `ok=true`, `code=000001.SZ`, `source=online_pull`

## Resource State After Chain

- `trade://session/current`
  - read at `2026-03-30T13:43:30.633718+08:00` -> `2026-03-30T13:43:30.635871+08:00`
  - `ready=true`
  - `account_id=8883884325`
  - `owner_account_id=8883884325`
  - `session_id=100`
  - `owner_generation=1`
- `diag://probe/latest`
  - read at `2026-03-30T13:43:30.635942+08:00` -> `2026-03-30T13:43:30.636386+08:00`
  - `ok=true`
  - `reason=ok`
  - `probe_mode=owner_managed_session_reuse`
  - `session_reused=true`
  - `fresh_connect_attempted=false`
  - `readiness_layers.read_only.ok=true`
  - `readiness_layers.read_only.source=active_owner_shadow`
  - `readiness_layers.write_permission.ok=true`
  - `readiness_layers.write_permission.source=userdata_precheck`
  - `write_permission_probe.implies_write_permission=false`
- `diag://login/latest`
  - read at `2026-03-30T13:43:30.636441+08:00` -> `2026-03-30T13:43:30.636772+08:00`
  - `ok=true`
  - `status=already_logged_in`
  - `message=MiniQMT already logged in`

## Notes

- This rerun again started from a pre-restart `8765 down` state and revalidated the repo-supported wake path against that scenario.
- The runtime delta versus the previous fresh rerun is concentrated in two places:
  - `miniqmt.ensure_logged_in` no longer fails with `desktop_not_interactive`; it now returns `already_logged_in`
  - `probe.connection` no longer fails with `connect_failed`; it now reports owner-managed shadow-session reuse with separated read-only and write-permission readiness fields
- Public `orders.list` is still an explicit failing public path, so this snapshot still does not support `G3 pass`, does not unblock `VAL-002`, and does not authorize `VAL-003`.
- One payload-level observation remains separate from the environment blocker:
  - `session.status` / `trade://session/current` reported `session_id=100`
  - `diag://probe/latest` reported reused shadow `session_id=101`
  - This snapshot records that identifier difference as an observation only; it does not, by itself, reclassify the run as `fail_design`.
