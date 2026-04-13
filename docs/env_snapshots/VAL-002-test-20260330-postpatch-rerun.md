# EnvSnapshot

Task ID: VAL-002
Date: 2026-03-30T09:07:57+08:00
Role: test

## Host

- OS: Microsoft Windows NT 10.0.26200.0
- Hostname: CHIYU
- Shell: PowerShell 7.6.0
- Working Directory: D:\xtquant-mcp\repo

## Runtime

- Python Executable: D:\xtquant-mcp\venv313\Scripts\python.exe
- Python Version: 3.13.12 (tags/v3.13.12:1cbe481, Feb  3 2026, 18:22:25) [MSC v.1944 64 bit (AMD64)]
- Trade Config Path: D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml
- EvidencePack: D:\xtquant-mcp\repo\docs\evidence_packs\VAL-002-test-20260330-postpatch-rerun.md
- Prior Live Baseline: D:\xtquant-mcp\repo\docs\evidence_packs\VAL-002-test-202603300306.md

## Process and Listener State

- Trade gateway before restart:
  - Listener: `127.0.0.1:8765`
  - pid: `35040`
  - Start Time: `2026-03-30T08:34:16+08:00`
  - Executable Path: `C:\Python313\python.exe`
  - Command Line: `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Trade gateway after restart:
  - Listener: `127.0.0.1:8765`
  - pid: `22620`
  - Start Time: `2026-03-30T09:03:52.5743997+08:00`
  - Executable Path: `C:\Python313\python.exe`
  - Command Line: `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Data gateway:
  - Listener: `127.0.0.1:8766`
  - pid: `29436`
  - Start Time: `2026-03-30T08:37:49.5204491+08:00`
  - Executable Path: `C:\Users\Yun\AppData\Local\Programs\Python\Python311\python.exe`
- XtMiniQmt:
  - pid: `25880`
  - Start Time: `2026-03-30T00:32:23.4186077+08:00`
  - Executable Path: `D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
- miniquote:
  - Listener: `127.0.0.1:58610`
  - pid: `20604`
  - Start Time: `2026-03-30T00:32:23.6051081+08:00`
  - Executable Path: `D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe`

## Port Reachability

- `127.0.0.1:8765` -> `TcpTestSucceeded=True`
- `127.0.0.1:8766` -> `TcpTestSucceeded=True`
- `127.0.0.1:58610` -> `TcpTestSucceeded=True`

## Health and Artifact Context

- Trade gateway `/healthz` after restart:
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
- Trade gateway current logs:
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_090352.log`
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_090352.stderr.log`

## Observation Window

- Restart observation started: `2026-03-30T09:02:53+08:00`
- New trade gateway process observed: `2026-03-30T09:03:52.5743997+08:00`
- Minimal live preflight window: `2026-03-30T09:06:59.771266+08:00` to `2026-03-30T09:07:29.730376+08:00`
- Snapshot captured: `2026-03-30T09:07:57.5609178+08:00`

## Notes

- The repo currently provides `scripts\wake_trade_gateway.ps1` as the supported launch path, but no dedicated restart helper script.
- This rerun therefore used a controlled stop of the existing `8765` listener process followed by `pwsh -File scripts\wake_trade_gateway.ps1`.
- The combined stop+wake shell command timed out after `124033 ms`, but restart success is evidenced by the changed listener pid (`35040 -> 22620`), the new process start time, the new `trade_gateway_20260330_090352.*` log files, and a healthy `/healthz`.
- The live preflight on the restarted process produced these MCP traces:
  - `miniqmt.ensure_logged_in`: `101bd2a2-078b-4d88-95c0-5d57714b20fd`
  - `session.warm`: `d12c5157-44ab-498d-86fe-65b99332907e`
  - `session.status`: `0db86a8a-ada9-4c46-9e16-3a3807386f51`
- Environment remained blocked after restart: `miniqmt.ensure_logged_in` returned `login_window_not_found`, `session.warm` returned `server_env_not_ready`, and `trade://session/current` stayed `session_not_ready`.
