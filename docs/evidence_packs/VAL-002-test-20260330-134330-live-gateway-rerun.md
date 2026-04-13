# EvidencePack

Task ID: VAL-002
Role: test
Date: 2026-03-30T13:43:30.636772+08:00
Acceptance Gate: G3
Conclusion: partial

## Env Snapshot

- Link: [VAL-002-test-20260330-134330-live-gateway-rerun.md](../env_snapshots/VAL-002-test-20260330-134330-live-gateway-rerun.md)
- Host: `CHIYU`
- Shell: `PowerShell 7.6.0`
- Config:
  - [VAL-002.md](../task_cards/VAL-002.md)
  - [VAL-002.md](../change_packages/VAL-002.md)
  - [TG-004.md](../change_packages/TG-004.md)
  - `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Code Version:
  - `git rev-parse HEAD` and `git status --short` remain unavailable because this workspace does not expose `.git`
  - Runtime freshness was verified by the post-wake process start time `2026-03-30T13:37:03.631422+08:00` and repo entrypoint command line `D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py`

## Test Scope

1. Capture the pre-restart gateway runtime state, including the possibility that `8765` is already down.
2. Start the trade gateway through the repo-supported path so the newest repo code is loaded:
   - `pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1`
3. Run the full live `G3` read-only chain on the restarted gateway:
   - `miniqmt.ensure_logged_in`
   - `session.warm`
   - `session.status`
   - `probe.connection`
   - `account.show`
   - `positions.list`
   - `orders.list`
   - `snapshot.l1`
4. Read `trade://session/current`, `diag://probe/latest`, and `diag://login/latest` after the chain.
5. Compare specifically against the prior fresh rerun baseline:
   - [VAL-002-test-20260330-124617-live-gateway-rerun.md](./VAL-002-test-20260330-124617-live-gateway-rerun.md)
   - [VAL-002-review-20260330-live-gateway-rerun.md](../reviews/VAL-002-review-20260330-live-gateway-rerun.md)

## Commands

1. Pre-restart listener, process, and `/healthz` capture:
   - `Get-NetTCPConnection -LocalPort 8765 -State Listen`
   - `Invoke-RestMethod http://127.0.0.1:8765/healthz`
   - `Test-NetConnection 127.0.0.1 -Port 8765`
   - `Test-NetConnection 127.0.0.1 -Port 58610`
   - `Get-Process XtMiniQmt`
   - `Get-Process miniquote`
2. Repo-supported wake path:
   - `pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1`
3. Post-restart verification:
   - `Get-NetTCPConnection -LocalPort 8765 -State Listen`
   - `Get-CimInstance Win32_Process -Filter "ProcessId=<listener pid>"`
   - `Invoke-RestMethod http://127.0.0.1:8765/healthz`
   - `Get-ChildItem D:\xtquant-mcp\instance\prod\logs\trade_gateway -File | Sort-Object LastWriteTime -Descending | Select-Object -First 6`
4. Full live MCP chain:
   - inline Python over `http.client` against `http://127.0.0.1:8765/mcp`
   - `initialize`
   - `tools/call` for the ordered `G3` chain listed above
5. Post-chain verification:
   - `Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json`
   - `Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json`
   - `Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json`
   - `rg -n --fixed-strings <trace_id> D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260330\trade_gateway_calls.jsonl`

## Raw Results

- Pre-restart gateway state:
  - Observed at: `2026-03-30T13:36:38.6072342+08:00`
  - No listener existed on `127.0.0.1:8765`
  - `/healthz` was unavailable: `由于目标计算机积极拒绝，无法连接。 (127.0.0.1:8765)`
  - `127.0.0.1:8765` -> `TcpTestSucceeded=False`
  - `127.0.0.1:58610` -> `TcpTestSucceeded=True`
  - `XtMiniQmt.exe` and `miniquote.exe` were already present
- Restart/load verification:
  - Repo-supported path used: `pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1`
  - The shell call returned `exit_code=0`
  - The script did not emit its JSON report in this shell capture, so restart success was verified directly from runtime state
  - Post-wake listener observed at `2026-03-30T13:37:22.5259169+08:00`
  - pid: `36532`
  - new process start time: `2026-03-30T13:37:03.631422+08:00`
  - executable path: `C:\Python313\python.exe`
  - command line points at repo entrypoint:
    `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
  - new logs:
    - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_133703.log`
    - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_133703.stderr.log`
  - `/healthz` after restart returned `ok=true`
  - This is sufficient evidence that a fresh repo-loaded gateway process was started for this rerun.

- Full live `G3` chain on the restarted gateway:
  - MCP initialize:
    - Started: `2026-03-30T13:37:52.285554+08:00`
    - Finished: `2026-03-30T13:37:52.288077+08:00`
    - HTTP `200`
    - `mcp_session_id=989aa2ff-b251-4724-853c-49567e2786fb`
  - `miniqmt.ensure_logged_in`
    - Started: `2026-03-30T13:37:52.288107+08:00`
    - Finished: `2026-03-30T13:37:52.387212+08:00`
    - `ok=true`
    - `status=already_logged_in`
    - `message=MiniQMT already logged in`
    - `process_id=25880`
    - `port_ready=true`
    - `trace_id=9d13f7ff-5c6b-4d39-b7e8-919188441db9`
    - `server_ts=2026-03-30T13:37:52`
    - `duration_ms=98`
  - `session.warm`
    - `ok=true`
    - `ready=true`
    - `account_id=8883884325`
    - `owner_account_id=8883884325`
    - `session_id=100`
    - `owner_generation=1`
    - `warm_trace` succeeded on:
      - `account.show`
      - `positions.list`
      - `orders.list` with `count=5`, `source=xttrader_shadow`, `read_scope=warm_health_only`
    - `trace_id=9ca5d486-ca94-421e-89c9-2e5ec6f76cfb`
    - `server_ts=2026-03-30T13:37:52`
    - `duration_ms=21874`
  - `session.status`
    - `ok=true`
    - `ready=true`
    - `session_id=100`
    - `reason=''`
    - `trace_id=326848a6-fcdf-41dd-ac0a-201ff0382935`
    - `server_ts=2026-03-30T13:38:14`
    - `duration_ms=1`
  - `probe.connection`
    - `ok=true`
    - `reason=ok`
    - `connect_code=''`
    - `probe_mode=owner_managed_session_reuse`
    - `session_reused=true`
    - `fresh_connect_attempted=false`
    - `read_only_ready=true`
    - `write_permission_ready=true`
    - `readiness_layers.read_only.source=active_owner_shadow`
    - `readiness_layers.read_only.reused_session=true`
    - `readiness_layers.write_permission.source=userdata_precheck`
    - `write_permission_probe.implies_write_permission=false`
    - `connection_trace` showed:
      - `precheck_userdata_read_only=ok`
      - `precheck_userdata_write_permission=ok`
      - `wait_xtdata_ready=ok`
      - `query_shadow_session_smoke=ok`
    - `trace_id=333e5c86-7250-4b0b-afb1-5e9d31d77f57`
    - `server_ts=2026-03-30T13:38:14`
    - `duration_ms=12`
  - `account.show`
    - `ok=true`
    - `cash=4497.04`
    - `total_asset=116119.04`
    - `market_value=111622.0`
    - `source=xttrader_shadow`
    - `trace_id=8edeb477-3004-423a-96d6-d8555f8450d8`
    - `server_ts=2026-03-30T13:38:14`
    - `duration_ms=0`
  - `positions.list`
    - `ok=true`
    - `count=2`
    - `trace_id=bbc6778f-0d2f-4cd3-a23c-7e71911a13c3`
    - `server_ts=2026-03-30T13:38:14`
    - `duration_ms=0`
  - `orders.list`
    - `ok=false`
    - `error.category=environment`
    - `error.message=xttrader connect failed: -1 after 3 attempts (...)`
    - session in error text: `100`
    - session plan in error text: `100`, `101`, `111`
    - `trace_id=362e87d2-9aa1-4282-80c8-ceccf2e0d939`
    - `server_ts=2026-03-30T13:38:14`
    - `duration_ms=45343`
  - `snapshot.l1`
    - `ok=true`
    - `code=000001.SZ`
    - `last_price=10.99`
    - `source=online_pull`
    - `trace_id=f2700f2c-cf32-4046-ac72-5bcc8e01e824`
    - `server_ts=2026-03-30T13:38:59`
    - `duration_ms=463`

- Resource reads after the chain:
  - `trade://session/current`
    - Re-read at `2026-03-30T13:43:30.633718+08:00` -> `2026-03-30T13:43:30.635871+08:00`
    - `ready=true`
    - `account_id=8883884325`
    - `owner_account_id=8883884325`
    - `session_id=100`
    - `owner_generation=1`
  - `diag://probe/latest`
    - Re-read at `2026-03-30T13:43:30.635942+08:00` -> `2026-03-30T13:43:30.636386+08:00`
    - `ok=true`
    - `reason=ok`
    - `probe_mode=owner_managed_session_reuse`
    - `readiness_layers.read_only.ok=true`
    - `readiness_layers.read_only.source=active_owner_shadow`
    - `readiness_layers.read_only.reused_session=true`
    - `readiness_layers.write_permission.ok=true`
    - `readiness_layers.write_permission.source=userdata_precheck`
    - `write_permission_probe.implies_write_permission=false`
    - `fresh_connect_attempted=false`
  - `diag://login/latest`
    - Re-read at `2026-03-30T13:43:30.636441+08:00` -> `2026-03-30T13:43:30.636772+08:00`
    - `ok=true`
    - `status=already_logged_in`
    - `message=MiniQMT already logged in`

## Comparison Against Previous Fresh Rerun

- Compared with [VAL-002-test-20260330-124617-live-gateway-rerun.md](./VAL-002-test-20260330-124617-live-gateway-rerun.md):
  - The previous fresh rerun also started from `127.0.0.1:8765` down and required the repo-supported wake path.
  - `probe.connection` improved materially:
    - previous: `ok=false`, `reason=connect_failed`, `connect_code=-1`, `readiness_layers.read_only.ok=false`
    - current: `ok=true`, `reason=ok`, `probe_mode=owner_managed_session_reuse`, `readiness_layers.read_only.ok=true`, `fresh_connect_attempted=false`
  - `miniqmt.ensure_logged_in` also improved materially:
    - previous: `ok=false`, `status=desktop_not_interactive`, `diag://login/latest` matched that same login failure
    - current: `ok=true`, `status=already_logged_in`, `diag://login/latest` remains its own separate bucket and matches the tool result
  - Public `orders.list` remained explicit and was not masked:
    - previous: `ok=false`, `xttrader connect failed: -1 after 3 attempts (...)`
    - current: `ok=false`, `xttrader connect failed: -1 after 3 attempts (...)`
  - `session.warm`, `session.status`, `trade://session/current`, `account.show`, `positions.list`, and `snapshot.l1` still succeed on the restarted gateway.

## Failure Classification

- `partial`
  - This rerun is not a `pass`, because the required `G3` ordered chain still fails at public `orders.list`.
  - The remaining blocker in this pack is environment-scoped and explicit:
    - public `orders.list` still returns `xttrader connect failed: -1 after 3 attempts (...)`
- Design-side checks verified by this rerun:
  - `probe.connection` did move from `connect_failed` to owner-session-based read-only success.
  - The payload now clearly separates read-only readiness from write-permission readiness:
    - read-only: `active_owner_shadow`, `reused_session=true`
    - write-permission: `userdata_precheck`, `implies_write_permission=false`
  - `miniqmt.ensure_logged_in` remained independently visible through both the tool call and `diag://login/latest`.
  - public `orders.list` remained independently visible as a failing public connect-based path.
- `fail_design`: not proven by this run
  - This pack validates the intended `TG-004` probe semantics change in real runtime.
  - It does not, by itself, prove a new design-contract failure.

## Artifact Refs

- Trade gateway call log:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260330\trade_gateway_calls.jsonl`
- Call log line verification for this rerun:
  - `trace_id=9d13f7ff-5c6b-4d39-b7e8-919188441db9` at line `43`
  - `trace_id=9ca5d486-ca94-421e-89c9-2e5ec6f76cfb` at line `44`
  - `trace_id=326848a6-fcdf-41dd-ac0a-201ff0382935` at line `45`
  - `trace_id=333e5c86-7250-4b0b-afb1-5e9d31d77f57` at line `46`
  - `trace_id=8edeb477-3004-423a-96d6-d8555f8450d8` at line `47`
  - `trace_id=bbc6778f-0d2f-4cd3-a23c-7e71911a13c3` at line `48`
  - `trace_id=362e87d2-9aa1-4282-80c8-ceccf2e0d939` at line `49`
  - `trace_id=f2700f2c-cf32-4046-ac72-5bcc8e01e824` at line `50`
- Resource state files updated during the chain:
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json`
- Restarted gateway logs:
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_133703.log`
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_133703.stderr.log`

## VAL-002 Status Impact

- Release posture: `no change`
  - `VAL-002` remains `blocked`
  - `VAL-003` must not start from this EvidencePack
- Diagnostic posture: `changed`
  - The previous fresh rerun still had three distinct failing buckets in the ordered chain: login, probe, and public `orders.list`
  - This rerun collapses that live `G3` blocker set to the public `orders.list` path only
  - The intended `TG-004` owner-session reuse semantics are now demonstrated in the real runtime path

## Verdict

`partial`. This fresh live gateway-side rerun restarted the trade gateway through the repo-supported path, loaded a fresh repo-backed process, and validated the new `TG-004` runtime behavior: `probe.connection` now succeeds through owner-managed shadow-session reuse while clearly keeping read-only readiness separate from write-permission readiness. `miniqmt.ensure_logged_in` also remained explicit and improved to `already_logged_in`. The full ordered `G3` chain still did not pass, because public `orders.list` remains an explicit failing connect-based path with `xttrader connect failed: -1 after 3 attempts (...)`. The task-level `VAL-002` posture therefore remains `blocked`, and `VAL-003` must not start.
