# EvidencePack

Task ID: VAL-002
Role: test
Date: 2026-03-30T14:27:45.669592+08:00
Acceptance Gate: G3
Conclusion: pass

## Env Snapshot

- Link: [VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md](../env_snapshots/VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md)
- Host: `CHIYU`
- Shell: `PowerShell 7.6.0`
- Config:
  - [VAL-002.md](../change_packages/VAL-002.md)
  - [TG-004.md](../change_packages/TG-004.md)
  - `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Prior comparison baselines:
  - [VAL-002-test-20260330-134330-live-gateway-rerun.md](./VAL-002-test-20260330-134330-live-gateway-rerun.md)
  - [VAL-002-review-20260330-135658-live-gateway-rerun-followup.md](../reviews/VAL-002-review-20260330-135658-live-gateway-rerun-followup.md)

## Test Scope

1. Restart the trade gateway through the repo-supported path so the newest repo code is loaded.
2. Capture pre/post listener pid, process start time, command line, and `/healthz`.
3. Run the full ordered live `G3` read-only chain:
   - `miniqmt.ensure_logged_in`
   - `session.warm`
   - `session.status`
   - `probe.connection`
   - `account.show`
   - `positions.list`
   - `orders.list`
   - `snapshot.l1`
4. Read `trade://session/current`, `diag://probe/latest`, and `diag://login/latest` after the chain.
5. Compare this rerun against the prior fresh live rerun, with specific focus on whether public `orders.list` moved from explicit connect failure to explicit fallback or success.

## Commands

1. Pre-restart listener, process, port, and `/healthz` capture:
   - `Get-NetTCPConnection -LocalPort 8765 -State Listen`
   - `Get-CimInstance Win32_Process -Filter "ProcessId=<listener pid>"`
   - `Invoke-RestMethod http://127.0.0.1:8765/healthz`
   - `Test-NetConnection 127.0.0.1 -Port 8765`
   - `Test-NetConnection 127.0.0.1 -Port 58610`
   - `Get-Process XtMiniQmt`
   - `Get-Process miniquote`
2. Controlled restart via the supported repo launch path:
   - `Stop-Process -Id <old listener pid> -Force`
   - `pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1`
3. Post-restart verification:
   - `Get-NetTCPConnection -LocalPort 8765 -State Listen`
   - `Get-CimInstance Win32_Process -Filter "ProcessId=<new listener pid>"`
   - `Invoke-RestMethod http://127.0.0.1:8765/healthz`
   - `Get-ChildItem D:\xtquant-mcp\instance\prod\logs\trade_gateway -File | Sort-Object LastWriteTime -Descending | Select-Object -First 6`
4. Full live MCP chain:
   - inline Python over `http.client` against `http://127.0.0.1:8765/mcp`
   - `initialize`
   - ordered `tools/call` for the `G3` chain above
5. Post-chain resource re-read:
   - inline Python over `http.client` against `http://127.0.0.1:8765/mcp`
   - `initialize`
   - `resources/read trade://session/current`
   - `resources/read diag://probe/latest`
   - `resources/read diag://login/latest`
6. Artifact back-link:
   - `Select-String` over `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260330\trade_gateway_calls.jsonl`

## Raw Results

- Pre-restart gateway state:
  - Observed at: `2026-03-30T14:14:47.0902745+08:00`
  - Listener existed on `127.0.0.1:8765`
  - old pid: `36532`
  - old process start time: `2026-03-30T13:37:03.631422+08:00`
  - old command line:
    `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
  - `/healthz` before restart remained healthy:
    - observed at `2026-03-30T14:14:47.1429170+08:00`
    - `ok=true`
    - `account_contract=single_account_primary`
    - `account_input_mode=service_context_only`
    - `evidence_scope=prod`
  - `127.0.0.1:8765 -> TcpTestSucceeded=True`
  - `127.0.0.1:58610 -> TcpTestSucceeded=True`
  - `XtMiniQmt.exe` and `miniquote.exe` were already present

- Restart/load verification:
  - Repo-supported launch path remains:
    - `pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1`
  - The repo does not expose a dedicated restart helper, so this rerun used a controlled stop of the old `8765` listener followed by the supported wake path.
  - The combined stop+wake shell capture timed out after `124049 ms`, so no direct wake-script JSON payload was retained from that wrapper call.
  - Fresh process loading was still verified directly from runtime state:
    - post-restart listener observed at `2026-03-30T14:20:18.3695570+08:00`
    - new pid: `3984`
    - new process start time: `2026-03-30T14:17:23.795229+08:00`
    - new command line:
      `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
    - new logs:
      - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_141723.log`
      - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_141723.stderr.log`
    - `/healthz` after restart:
      - observed at `2026-03-30T14:20:18.3705368+08:00`
      - `ok=true`
      - `bind_port=8765`
      - `mcp_path=/mcp`
      - `health_path=/healthz`
      - `account_contract=single_account_primary`
      - `account_input_mode=service_context_only`
      - `evidence_scope=prod`
  - This is sufficient evidence that a fresh repo-loaded gateway process was started for this rerun.

- Full live `G3` chain on the restarted gateway:
  - MCP initialize:
    - Started: `2026-03-30T14:21:52.287489+08:00`
    - Finished: `2026-03-30T14:21:52.290070+08:00`
    - HTTP `200`
    - `mcp_session_id=dfdc790c-a76a-4d68-b2bc-7f4a9be66f34`
  - `miniqmt.ensure_logged_in`
    - Started: `2026-03-30T14:21:52.290102+08:00`
    - Finished: `2026-03-30T14:21:52.381273+08:00`
    - `ok=true`
    - `status=already_logged_in`
    - `message=MiniQMT already logged in`
    - `process_id=25880`
    - `port_ready=true`
    - `trace_id=56e03e01-9549-415b-bb75-5db8a6facee1`
    - `server_ts=2026-03-30T14:21:52`
    - `duration_ms=90`
  - `session.warm`
    - Started: `2026-03-30T14:21:52.381354+08:00`
    - Finished: `2026-03-30T14:22:38.354289+08:00`
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
    - `trace_id=b70269d1-d8e3-4b99-bb7b-5b54e5f40290`
    - `server_ts=2026-03-30T14:21:52`
    - `duration_ms=45971`
  - `session.status`
    - `ok=true`
    - `ready=true`
    - `session_id=100`
    - `reason=''`
    - `trace_id=fde946b2-8c60-438f-b1c5-8f4a0933ba54`
    - `server_ts=2026-03-30T14:22:38`
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
    - `readiness_layers.write_permission.source=userdata_precheck`
    - `write_permission_probe.implies_write_permission=false`
    - `connection_trace` preserved:
      - `precheck_userdata_read_only=ok`
      - `precheck_userdata_write_permission=ok`
      - `wait_xtdata_ready=ok`
      - `query_shadow_session_smoke=ok`
    - `trace_id=f043f961-4e8c-4215-8de6-4247a9af6e42`
    - `server_ts=2026-03-30T14:22:38`
    - `duration_ms=22`
  - `account.show`
    - `ok=true`
    - `cash=4497.04`
    - `total_asset=116374.04`
    - `market_value=111877.0`
    - `source=xttrader_shadow`
    - `trace_id=7bf71dce-08e3-4837-b570-190c8e249144`
    - `server_ts=2026-03-30T14:22:38`
    - `duration_ms=0`
  - `positions.list`
    - `ok=true`
    - `count=2`
    - `trace_id=766beaca-8dc9-4807-8367-be137977be98`
    - `server_ts=2026-03-30T14:22:38`
    - `duration_ms=0`
  - `orders.list`
    - `ok=true`
    - `count=5`
    - `source=active_owner_shadow`
    - `read_scope=public_fallback`
    - `degraded=true`
    - `fallback_used=true`
    - `fallback_reason=broker_connect_failed`
    - `message=broker connect failed; returned orders from active owner-managed shadow session`
    - `shadow_fallback.used=true`
    - `shadow_fallback.source=active_owner_shadow`
    - `shadow_fallback.reused_session=true`
    - `shadow_fallback.session_id=111`
    - broker-first path remained explicit inside the same payload:
      - `broker_read.source=broker`
      - `broker_read.ok=false`
      - `broker_read.fresh_connect_attempted=true`
      - `broker_read.fresh_connect_ok=false`
      - `broker_read.connected_before=false`
      - `broker_read.connected_after=false`
      - `broker_read.error=xttrader connect failed: -1 after 3 attempts (session=100, session_plan=[100, 101, 111], ...)`
    - `trace_id=f3468625-da8e-48e9-9a35-4f84ef54dc2d`
    - `server_ts=2026-03-30T14:22:38`
    - `duration_ms=45281`
  - `snapshot.l1`
    - `ok=true`
    - `code=000001.SZ`
    - `last_price=11.0`
    - `source=online_pull`
    - `trace_id=c3090037-b7e0-40fd-b723-c4b8db3901c3`
    - `server_ts=2026-03-30T14:23:23`
    - `duration_ms=459`

- Resource reads after the chain:
  - secondary MCP initialize:
    - Started: `2026-03-30T14:27:45.663533+08:00`
    - Finished: `2026-03-30T14:27:45.666117+08:00`
    - `mcp_session_id=56136d1a-fd4b-48aa-bfbe-e6aaa661d070`
  - `trade://session/current`
    - Re-read at `2026-03-30T14:27:45.666151+08:00` -> `2026-03-30T14:27:45.668690+08:00`
    - `ready=true`
    - `account_id=8883884325`
    - `owner_account_id=8883884325`
    - `session_id=100`
    - `owner_generation=1`
  - `diag://probe/latest`
    - Re-read at `2026-03-30T14:27:45.668731+08:00` -> `2026-03-30T14:27:45.669198+08:00`
    - `ok=true`
    - `reason=ok`
    - `probe_mode=owner_managed_session_reuse`
    - `session_id=111`
    - `readiness_layers.read_only.ok=true`
    - `readiness_layers.read_only.source=active_owner_shadow`
    - `readiness_layers.read_only.reused_session=true`
    - `readiness_layers.write_permission.ok=true`
    - `readiness_layers.write_permission.source=userdata_precheck`
    - `fresh_connect_attempted=false`
    - `write_permission_probe.implies_write_permission=false`
  - `diag://login/latest`
    - Re-read at `2026-03-30T14:27:45.669234+08:00` -> `2026-03-30T14:27:45.669592+08:00`
    - `ok=true`
    - `status=already_logged_in`
    - `message=MiniQMT already logged in`

## Comparison Against Previous Fresh Rerun

- Compared with [VAL-002-test-20260330-134330-live-gateway-rerun.md](./VAL-002-test-20260330-134330-live-gateway-rerun.md):
  - Previous rerun started from `127.0.0.1:8765 down`; this rerun started from an already-live listener (`pid=36532`) and therefore required a controlled stop before invoking the supported wake path.
  - `miniqmt.ensure_logged_in` was preserved:
    - previous: `ok=true`, `status=already_logged_in`
    - current: `ok=true`, `status=already_logged_in`
  - `session.warm`, `session.status`, `probe.connection`, `account.show`, `positions.list`, and `snapshot.l1` were preserved with no regression.
  - Public `orders.list` changed materially:
    - previous: `ok=false`, explicit `xttrader connect failed: -1 after 3 attempts (...)`
    - current: `ok=true`, explicit fallback payload with:
      - `degraded=true`
      - `fallback_used=true`
      - `fallback_reason=broker_connect_failed`
      - `source=active_owner_shadow`
      - `read_scope=public_fallback`
      - preserved `broker_read.error=xttrader connect failed: -1 after 3 attempts (...)`
  - This means the previous formal blocker moved from public `orders.list` failure to public `orders.list` degraded success with broker-first failure preserved as machine-readable metadata.

## Design and Environment Separation

- Design-side validation confirmed by this rerun:
  - The new broker-first public `orders.list` contract is active in the real runtime.
  - Fallback is explicit rather than masked:
    - `degraded=true`
    - `fallback_used=true`
    - `fallback_reason=broker_connect_failed`
    - `source=active_owner_shadow`
  - `probe.connection` remains separate from `orders.list` and still reports owner-managed shadow-session reuse without implying write permission.
  - `miniqmt.ensure_logged_in` remains independently visible through both tool output and `diag://login/latest`.
- Environment-side observation preserved by the same successful payload:
  - The broker subpath inside public `orders.list` still records `xttrader connect failed: -1 after 3 attempts (...)`.
  - This observation is no longer the public-tool blocker for `G3`, because the public contract now succeeds through explicit degraded fallback.

## Additional Observation

- The session identifier split remains observable but does not block the chain:
  - `session.status` and `trade://session/current` reported `session_id=100`
  - `probe.connection` and `diag://probe/latest` reported reused shadow `session_id=111`
- This pack records the identifier difference as an observation only. It did not break the ordered chain, and it is not used here to reclassify the rerun as `fail_design`.

## Artifact Refs

- Trade gateway call log:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260330\trade_gateway_calls.jsonl`
- Call log line verification for this rerun:
  - `trace_id=56e03e01-9549-415b-bb75-5db8a6facee1` at line `51`
  - `trace_id=b70269d1-d8e3-4b99-bb7b-5b54e5f40290` at line `52`
  - `trace_id=fde946b2-8c60-438f-b1c5-8f4a0933ba54` at line `53`
  - `trace_id=f043f961-4e8c-4215-8de6-4247a9af6e42` at line `54`
  - `trace_id=7bf71dce-08e3-4837-b570-190c8e249144` at line `55`
  - `trace_id=766beaca-8dc9-4807-8367-be137977be98` at line `56`
  - `trace_id=f3468625-da8e-48e9-9a35-4f84ef54dc2d` at line `57`
  - `trace_id=c3090037-b7e0-40fd-b723-c4b8db3901c3` at line `58`
- Resource state files:
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json`
- Restarted gateway logs:
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_141723.log`
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_141723.stderr.log`

## VAL-002 Status Impact

- Evidence conclusion: `pass`
  - The full ordered live `G3` chain completed successfully on the fresh repo-loaded gateway process.
  - public `orders.list` did not flatten broker failure; it succeeded via explicit degraded fallback.
- Workflow posture: `changed`
  - previous posture in the latest rerun pack: `blocked`
  - current test-side recommendation: move from `Blocked` to `In Review`
  - this pack does not declare `Accepted`; review gate is still required
- `VAL-003`:
  - not started in this run
  - this test role does not authorize downstream execution without review

## Verdict

`pass`. This fresh live gateway-side rerun restarted the trade gateway onto a new repo-backed process and preserved the previously recovered live `G3` behavior for `miniqmt.ensure_logged_in`, `session.warm`, `session.status`, `probe.connection`, `account.show`, `positions.list`, and `snapshot.l1`. Public `orders.list` no longer fails the chain; it now returns `ok=true` through the new broker-first, explicit owner-shadow fallback contract, and it keeps the failed broker connect attempt visible as `degraded=true`, `fallback_used=true`, `fallback_reason=broker_connect_failed`, `source=active_owner_shadow`, and `broker_read.error=xttrader connect failed: -1 ...`. The prior formal live `G3` blocker is therefore cleared at the independent-test evidence level. Review is still required before any release or downstream task progression.
