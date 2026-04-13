# EvidencePack

Task ID: VAL-004
Role: test
Date: 2026-03-31T18:23:42.3845442+08:00
Acceptance Gate: G3
Conclusion: fail_env

## Env Snapshot

- Link: [VAL-004-test-202603311806-live-warm-fastfail-rerun.md](../env_snapshots/VAL-004-test-202603311806-live-warm-fastfail-rerun.md)
- Host: `CHIYU`
- Shell: `PowerShell 7.6.0`
- Config:
  - [VAL-004.md](../change_packages/VAL-004.md)
  - `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Comparison baselines:
  - [VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md](./VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md)
  - [VAL-002-review-20260330-143606-live-gateway-rerun-orders-fallback.md](../reviews/VAL-002-review-20260330-143606-live-gateway-rerun-orders-fallback.md)

## Test Scope

1. Keep the scope inside the current Windows repo and the non-write trade-gateway path only.
2. Reload the trade gateway through the repo-supported path and verify the fresh listener, command line, logs, and `/healthz`.
3. Run the ordered non-write MCP chain only:
   - `miniqmt.ensure_logged_in`
   - `session.warm`
   - `session.status`
   - `probe.connection`
   - `account.show`
   - `positions.list`
   - `orders.list`
   - `snapshot.l1`
4. Read `trade://session/current`, `diag://probe/latest`, and `diag://login/latest` after the chain.
5. Compare this rerun against earlier same-day `session.warm` failures to determine whether the remaining blocker is still `up_queue_xtquant`, or whether the blocker has moved to login/broker-session readiness.

## Commands

1. Runtime preflight and fresh listener capture:
   - `Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 58610,8765,8766 } | Sort-Object LocalPort | Select-Object LocalAddress, LocalPort, OwningProcess, State`
   - `Test-NetConnection 127.0.0.1 -Port 58610`
   - `Test-NetConnection 127.0.0.1 -Port 8765`
   - `Test-NetConnection 127.0.0.1 -Port 8766`
   - `Get-CimInstance Win32_Process -Filter "ProcessId=<8765 pid>"`
   - `Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8765/healthz' -TimeoutSec 5`
2. Trade gateway fresh reload:
   - controlled stop of the previous `8765` listener
   - `pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1`
3. Code-state confirmation:
   - `D:\xtquant-mcp\venv313\Scripts\python.exe tests\test_trade_gateway_bootstrap.py`
   - `D:\xtquant-mcp\venv313\Scripts\python.exe tests\test_trade_gateway_session_manager.py`
4. Ordered MCP chain over `http://127.0.0.1:8765/mcp`:
   - `initialize`
   - `tools/call miniqmt.ensure_logged_in {"login_timeout_seconds": 20}`
   - `tools/call session.warm {}`
   - `tools/call session.status {}`
   - `tools/call probe.connection {}`
   - `tools/call account.show {}`
   - `tools/call positions.list {}`
   - `tools/call orders.list {}`
   - `tools/call snapshot.l1 {"code": "000001.SZ"}`
   - `resources/read trade://session/current`
   - `resources/read diag://probe/latest`
   - `resources/read diag://login/latest`
5. Call-log and state-file back-link:
   - `Get-Content D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260331\trade_gateway_calls.jsonl`
   - `Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json`
   - `Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json`
   - `Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json`

## Raw Results

- Fresh runtime truth:
  - previous `8765` owner before reload:
    - pid `36116`
    - start time `2026-03-31 17:54:55`
    - command line:
      `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
  - current `8765` owner after reload:
    - pid `47588`
    - parent pid `36888`
    - start time `2026-03-31 17:58:37`
    - same command line as above
  - fresh logs:
    - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260331_175837.log`
    - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260331_175837.stderr.log`
  - `/healthz` after reload remained healthy:
    - `ok=true`
    - `bind_port=8765`
    - `evidence_scope=prod`
    - `evidence_state_root=D:\xtquant-mcp\instance\prod\state`
    - `evidence_artifact_root=D:\xtquant-mcp\instance\prod\artifacts`

- Host/runtime preflight after reload:
  - `XtMiniQmt.exe` pid `27152`, start time `2026-03-31 16:31:43`
  - `miniquote.exe` pid `28824`, start time `2026-03-31 16:31:44`
  - `127.0.0.1:8765 -> pid 47588`
  - `127.0.0.1:8766 -> pid 46732`
  - `0.0.0.0:58610 -> pid 28824`
  - `Test-NetConnection` for `58610/8765/8766` all returned `TcpTestSucceeded=True`

- Code-side narrowing already loaded in repo:
  - [bootstrap.py](../../xtqmt_mcp/trade_gateway/bootstrap.py) skips explicit session resolution for `session.warm`
  - [session_manager.py](../../xtqmt_mcp/trade_gateway/session_manager.py) stops warm health checks at the first failure
  - narrow deterministic checks both passed:
    - `tests\test_trade_gateway_bootstrap.py` -> `Ran 3 tests`, `OK`
    - `tests\test_trade_gateway_session_manager.py` -> `Ran 3 tests`, `OK`

- Latest ordered non-write MCP chain results from `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260331\trade_gateway_calls.jsonl`:
  - `miniqmt.ensure_logged_in`
    - `server_ts=2026-03-31T18:01:44`
    - `ok=true`
    - `duration_ms=96`
    - `trace_id=4a027996-d8f3-4f8d-bfb6-907c7d1c97aa`
  - `session.warm`
    - `server_ts=2026-03-31T18:01:44`
    - `ok=false`
    - `duration_ms=136557`
    - `trace_id=0bd4f66f-50a4-441a-ae2a-1aad7537689a`
    - `error_code=session_warm_failed`
    - `error_message=session warm health check failed: account.show_exception`
    - `reason=account.show_exception`
    - `ready=false`
  - `session.status`
    - `server_ts=2026-03-31T18:04:00`
    - `ok=true`
    - `duration_ms=0`
    - `trace_id=4870dcfd-86cb-4a95-a23e-239c577317ad`
    - `ready=false`
    - `reason=session_not_ready`
  - `probe.connection`
    - `server_ts=2026-03-31T18:04:00`
    - `ok=false`
    - `trace_id=1b5c8897-e9dd-416d-9ec6-e67dde1dfd8f`
    - `error_code=session_not_ready`
  - `account.show`
    - `server_ts=2026-03-31T18:04:00`
    - `ok=false`
    - `trace_id=3460a539-1b12-4e78-bd61-c457a02d24a2`
    - `error_code=session_not_ready`
  - `positions.list`
    - `server_ts=2026-03-31T18:04:00`
    - `ok=false`
    - `trace_id=5b740cb1-726f-484d-8760-806956af9235`
    - `error_code=session_not_ready`
  - `orders.list`
    - `server_ts=2026-03-31T18:04:00`
    - `ok=false`
    - `trace_id=2f9be04c-75bd-4dac-ba5e-16c29dfb7b3d`
    - `error_code=session_not_ready`
  - `snapshot.l1`
    - `server_ts=2026-03-31T18:04:00`
    - `ok=false`
    - `trace_id=53356fe1-49eb-4681-95c1-90cadc4defb5`
    - `error_code=session_not_ready`

- Exact latest `session.warm` failure shape:
  - `warm_trace_len=1`
  - `status_trace_len=1`
  - the only warm-trace step is `account.show`
  - the only recorded reason is `account.show_exception`
  - the failure message is `xttrader connect=-1` across session plan `1111,1100,1101,100,101,111,2111,2100,2101`
  - the same message shows precheck:
    - `require_up_queue_file=False`
    - `up_queue_xtquant_exists=False`
    - `ok=True`

- Same-day comparison against earlier live failures from the same call log:
  - earlier `session.warm` at `2026-03-31T17:36:32`
    - `trace_id=971031c0-5cd0-4cd7-af2d-607c75dcff9a`
    - `duration_ms=499668`
    - same final reason `account.show_exception`
  - earlier `session.warm` at `2026-03-31T17:37:26`
    - `trace_id=b0ce4f58-80ee-4e8d-bfbd-003e8a4b00c0`
    - `duration_ms=944489`
    - same final reason `account.show_exception`
  - this latest rerun therefore reduced failure latency materially and reduced the warm trace from repeated downstream steps to a single first-failure step

- Current state/resource files after rerun:
  - `diag_login_latest.json`
    - last write `2026-03-31 18:01:44`
    - `ok=true`
    - `status=already_logged_in`
    - `account_id=8883884325`
    - `credential_target=paper_trader_v1/miniqmt/8883884325`
    - `port_ready=true`
    - `submit_attempted=false`
    - no password-submit evidence was retained
  - `trade_session_current.json`
    - last write `2026-03-31 18:04:00`
    - `ready=false`
    - `reason=session_not_ready`
    - account/session fields are empty
  - `diag_probe_latest.json`
    - last write `2026-03-31 18:04:00`
    - only contract-level placeholder fields were present

## Proven Observations

1. The fresh rerun came from a newly loaded trade-gateway process on the current Windows repo, not from an old listener residue.
2. The code-side narrowing changed live behavior measurably: `session.warm` still fails, but it now fails faster and stops at the first failing step instead of repeating the later warm-health steps.
3. `up_queue_xtquant` is no longer the first blocker on this read/warm path. The latest `session.warm` failure carried `require_up_queue_file=False` with a precheck that still evaluated `ok=True`.
4. Broker/session readiness is still not established. The latest `session.warm` still fails with `xttrader connect=-1`, and the follow-up public tools all remain blocked behind `session_not_ready`.
5. `miniqmt.ensure_logged_in` only proves that the main window is visible and `58610` is reachable. It does not prove that a password-submit flow happened, and it does not prove that broker trade login is ready.

## Bounded Inference

1. The currently observed blocker is best classified as an environment/login-state blocker rather than an `up_queue_xtquant` gate problem on this path.
2. Given that no password-submit evidence exists and `xttrader connect=-1` remains the first broker/session failure, the most conservative current explanation is: the broker-side login or trading session is not actually ready yet.
3. This evidence is sufficient to keep `VAL-003` and `G4` blocked, but it is not sufficient to claim a broker implementation defect beyond the not-ready environment/session state.

## Artifact Refs

- Trade gateway call log:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260331\trade_gateway_calls.jsonl`
- Trade gateway logs:
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260331_175837.log`
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260331_175837.stderr.log`
- State files:
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json`
- Key traces:
  - `4a027996-d8f3-4f8d-bfb6-907c7d1c97aa`
  - `0bd4f66f-50a4-441a-ae2a-1aad7537689a`
  - `4870dcfd-86cb-4a95-a23e-239c577317ad`
  - `1b5c8897-e9dd-416d-9ec6-e67dde1dfd8f`
  - `3460a539-1b12-4e78-bd61-c457a02d24a2`
  - `5b740cb1-726f-484d-8760-806956af9235`
  - `2f9be04c-75bd-4dac-ba5e-16c29dfb7b3d`
  - `53356fe1-49eb-4681-95c1-90cadc4defb5`

## Verdict

`VAL-004` current test conclusion is `fail_env`: this rerun proves that the first blocker has moved away from `up_queue_xtquant`, but broker/session readiness is still not established because the host-side login/trading session is not actually ready. `VAL-003` remains blocked, and this evidence must not be used to claim `G4` readiness.
