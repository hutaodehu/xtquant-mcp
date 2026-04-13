# EnvSnapshot

Task ID: VAL-002
Date: 2026-03-30T12:46:17.578620+08:00
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
- EvidencePack: [VAL-002-test-20260330-124617-live-gateway-rerun.md](../evidence_packs/VAL-002-test-20260330-124617-live-gateway-rerun.md)
- TaskCard: [VAL-002.md](../task_cards/VAL-002.md)
- ChangePack: [VAL-002.md](../change_packages/VAL-002.md)
- Prior comparison baselines:
  - [VAL-002-test-20260330-full-postpatch-rerun.md](../evidence_packs/VAL-002-test-20260330-full-postpatch-rerun.md)
  - [VAL-002-test-20260330-native-query-chain.md](../evidence_packs/VAL-002-test-20260330-native-query-chain.md)
  - [VAL-002-review-20260330-native-query-chain.md](../reviews/VAL-002-review-20260330-native-query-chain.md)
- Git metadata:
  - `git rev-parse HEAD` and `git status --short` are unavailable because this workspace does not expose `.git`

## Process and Listener State

- Trade gateway before restart:
  - Observed at: `2026-03-30T12:40:24.0119828+08:00`
  - Listener: not present on `127.0.0.1:8765`
  - `/healthz`: connection refused (`127.0.0.1:8765`)
  - `TcpTestSucceeded=False`
- Trade gateway wake attempt:
  - Repo-supported path: `pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1`
  - Result: shell command timed out after `154028 ms`
  - Direct wake-script JSON was therefore not captured
- Trade gateway after restart:
  - Observed at: `2026-03-30T12:43:30.2759775+08:00`
  - Listener: `127.0.0.1:8765`
  - pid: `34748`
  - Start Time: `2026-03-30T12:40:38.004714+08:00`
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
  - Start Time: `2026-03-30T00:32:23.4186077+08:00`
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
  - timestamp: `2026-03-30T12:40:24.0119828+08:00`
  - result: unavailable (`connection refused`)
- Trade gateway `/healthz` after restart:
  - timestamp: `2026-03-30T12:43:30.2759775+08:00`
  - `ok=true`
  - `server_name=xtqmtTradeGateway`
  - `server_version=2.0.0a0`
  - `bind_port=8765`
  - `mcp_path=/mcp`
  - `health_path=/healthz`
  - `account_contract=single_account_primary`
  - `account_input_mode=service_context_only`
  - `evidence_scope=prod`
  - `evidence_state_root=D:\xtquant-mcp\instance\prod\state`
  - `evidence_artifact_root=D:\xtquant-mcp\instance\prod\artifacts`
- Trade gateway call log:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260330\trade_gateway_calls.jsonl`
- Trade gateway logs for the restarted process:
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_124037.log`
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_124037.stderr.log`
- Raw capture bundle for this rerun:
  - `C:\Users\Yun\AppData\Local\Temp\VAL-002-live-rerun-20260330_123841\01_pre_restart.json`
  - `C:\Users\Yun\AppData\Local\Temp\VAL-002-live-rerun-20260330_123841\03_post_restart.json`
  - `C:\Users\Yun\AppData\Local\Temp\VAL-002-live-rerun-20260330_123841\04_mcp_chain.json`
  - `C:\Users\Yun\AppData\Local\Temp\VAL-002-live-rerun-20260330_123841\06_python_version.txt`
- State files updated during this rerun:
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_account_current.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_orders_today.json`

## Observation Window

- Pre-restart down state captured: `2026-03-30T12:40:24.0119828+08:00`
- New trade gateway process start time: `2026-03-30T12:40:38.004714+08:00`
- Restarted gateway confirmed healthy: `2026-03-30T12:43:30.2759775+08:00`
- Full live `G3` MCP window:
  - initialize started: `2026-03-30T12:43:54.190420+08:00`
  - final resource read finished: `2026-03-30T12:46:17.578620+08:00`
- Snapshot recorded: `2026-03-30T12:46:17.578620+08:00`

## Trace Inventory

- `miniqmt.ensure_logged_in`
  - `trace_id=0eba2b26-bd3a-421b-b29b-fb800b150ef4`
  - `server_ts=2026-03-30T12:43:54`
  - Result: `ok=false`, `status=desktop_not_interactive`, `error.code=miniqmt_not_logged_in`
- `session.warm`
  - `trace_id=ee1eca12-ee08-4ce5-9c1f-161bbf52229f`
  - `server_ts=2026-03-30T12:43:54`
  - Result: `ok=true`, `ready=true`, `session_id=101`, `owner_generation=1`
- `session.status`
  - `trace_id=f7af2184-5590-486e-aa4f-0bd6b19b77fd`
  - `server_ts=2026-03-30T12:44:46`
  - Result: `ok=true`, `ready=true`, `session_id=101`
- `probe.connection`
  - `trace_id=80ab2097-9df1-425c-a170-4d37b5a79162`
  - `server_ts=2026-03-30T12:44:46`
  - Result: `ok=false`, `error.code=connect_failed`, `connect_code=-1`
- `account.show`
  - `trace_id=33803f97-8fbe-46f3-8a94-dd0101ca5662`
  - `server_ts=2026-03-30T12:45:31`
  - Result: `ok=true`, `source=xttrader_shadow`
- `positions.list`
  - `trace_id=27db9be5-77c7-4cfd-bc06-fcb9c879bb0c`
  - `server_ts=2026-03-30T12:45:31`
  - Result: `ok=true`, `count=2`
- `orders.list`
  - `trace_id=06a85f5e-a89f-4437-b12c-e85667fd34f6`
  - `server_ts=2026-03-30T12:45:31`
  - Result: `ok=false`, `error.message=xttrader connect failed: -1 after 3 attempts (...)`
- `snapshot.l1`
  - `trace_id=e2c3306f-4762-4e0a-88c1-9ed6c8ae8f16`
  - `server_ts=2026-03-30T12:46:16`
  - Result: `ok=true`, `code=000001.SZ`, `source=online_pull`

## Resource State After Chain

- `trade://session/current`
  - read at `2026-03-30T12:46:17.569343+08:00`
  - `ready=true`
  - `account_id=8883884325`
  - `owner_account_id=8883884325`
  - `session_id=101`
  - `owner_generation=1`
- `diag://probe/latest`
  - read at `2026-03-30T12:46:17.574278+08:00`
  - `ok=false`
  - `reason=connect_failed`
  - `connect_code=-1`
  - `readiness_layers.read_only.ok=false`
  - `readiness_layers.write_permission.ok=true`
- `diag://login/latest`
  - read at `2026-03-30T12:46:17.578620+08:00`
  - `ok=false`
  - `status=desktop_not_interactive`
  - `message=interactive desktop required`

## Notes

- This rerun did restart the gateway through the repo-supported wake path, but the pre-restart state was `down` rather than “listener already present”.
- The wake command timeout does not imply restart failure; the fresh pid, fresh process start time, new log files, and healthy `/healthz` confirm the current repo code was loaded into a new process.
- The failure shape is materially different from the earlier `session.warm -> session_not_ready` blocker:
  - `session.warm` now succeeds on the restarted gateway
  - `session.status` and `trade://session/current` both report a live owner-managed session
  - `account.show`, `positions.list`, and `snapshot.l1` succeed
  - remaining failures are `miniqmt.ensure_logged_in=desktop_not_interactive`, `probe.connection=connect_failed`, and public `orders.list=xttrader connect failed: -1`
- This snapshot therefore does not support `G3 pass`, does not unblock `VAL-002`, and does not authorize `VAL-003`.
