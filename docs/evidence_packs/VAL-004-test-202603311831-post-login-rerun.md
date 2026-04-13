# EvidencePack

Task ID: VAL-004
Role: test
Date: 2026-03-31T18:31:13.9557860+08:00
Acceptance Gate: G3
Conclusion: fail_design

## Env Snapshot

- Link: [VAL-004-test-202603311831-post-login-rerun.md](../env_snapshots/VAL-004-test-202603311831-post-login-rerun.md)
- Host: `CHIYU`
- Shell: `PowerShell 7.6.0`
- Config:
  - [VAL-004.md](../change_packages/VAL-004.md)
  - `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Comparison baselines:
  - [VAL-004-test-202603311806-live-warm-fastfail-rerun.md](./VAL-004-test-202603311806-live-warm-fastfail-rerun.md)
  - [VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md](./VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md)

## Test Scope

1. Re-run the trade gateway on the current Windows repo after the user completed the real broker-side login.
2. Keep the validation inside the non-write chain only; do not call `order.place` and do not start `VAL-003`.
3. Re-run the ordered `G3` chain and read back the trade/login/probe resources.
4. Determine whether the earlier `xttrader connect=-1` blocker still reproduces after real login, or whether a different implementation/design issue becomes the first blocker.

## Commands

1. Fresh gateway wake and preflight:
   - `pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1`
   - `Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 58610,8765,8766 } | Sort-Object LocalPort | Select-Object LocalAddress, LocalPort, OwningProcess, State`
   - `Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8765/healthz' -TimeoutSec 5`
2. Ordered non-write MCP chain over `http://127.0.0.1:8765/mcp`:
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
3. Artifact back-link:
   - `Get-Content D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260331\trade_gateway_calls.jsonl`
   - `Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json`
   - `Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json`
   - `Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json`

## Raw Results

- Fresh runtime truth after login:
  - trade gateway listener came back on `127.0.0.1:8765 -> pid 48672`
  - data gateway listener remained `127.0.0.1:8766 -> pid 46732`
  - vendor port remained `0.0.0.0:58610 -> pid 28824`
  - latest trade-gateway logs:
    - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260331_182839.log`
    - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260331_182839.stderr.log`
  - `/healthz` remained healthy:
    - `ok=true`
    - `bind_port=8765`
    - `evidence_scope=prod`
    - `evidence_state_root=D:\xtquant-mcp\instance\prod\state`
    - `evidence_artifact_root=D:\xtquant-mcp\instance\prod\artifacts`

- Ordered non-write MCP chain after login:
  - `miniqmt.ensure_logged_in`
    - `ok=true`
    - `status=already_logged_in`
    - `trace_id=2a892d06-2858-4a54-b4e6-79cab56753ba`
    - `server_ts=2026-03-31T18:29:29`
    - `duration_ms=105`
    - main-window title now resolved to `8883884325 - 国金证券QMT交易端 2.0.8.300`
  - `session.warm`
    - `ok=true`
    - `ready=true`
    - `account_id=8883884325`
    - `owner_account_id=8883884325`
    - `session_id=1111`
    - `trace_id=6467f154-0c8a-47bb-8d88-465f5c68224e`
    - `server_ts=2026-03-31T18:29:30`
    - `duration_ms=348`
    - warm health succeeded on:
      - `account.show`
      - `positions.list`
      - `orders.list` with `source=xttrader_shadow`, `read_scope=warm_health_only`, `count=3`
  - `session.status`
    - `ok=true`
    - `ready=true`
    - `session_id=1111`
    - `reason=''`
  - `probe.connection`
    - `ok=true`
    - `reason=ok`
    - `session_id=1111`
    - `read_only_ready=true`
    - `write_permission_ready=true`
    - `up_queue_xtquant_exists=true`
    - `probe_mode=owner_managed_session_reuse`
    - `fresh_connect_attempted=false`
    - `trace_id=d982161d-c360-4744-842c-a057975e8ed1`
    - `server_ts=2026-03-31T18:29:30`
    - `duration_ms=18`
  - `account.show`
    - `ok=true`
    - `source=xttrader_shadow`
    - `cash=4197.69`
    - `total_asset=108997.69`
    - `market_value=104800.0`
    - `trace_id=13b7efd1-de2d-4498-b3f4-0d3635135a12`
  - `positions.list`
    - `ok=true`
    - `count=2`
    - `trace_id=7f142de3-1ca7-42c7-80df-b64dc82efbd6`
  - `orders.list`
    - `ok=false`
    - `trace_id=88f8d8ca-e6b2-4e74-89e8-773e0bdbecec`
    - `server_ts=2026-03-31T18:29:30`
    - `duration_ms=0`
    - `error_code=server_env_not_ready`
    - `error_message='NoneType' object has no attribute 'query_open_orders'`
  - `snapshot.l1`
    - `ok=true`
    - `code=000001.SZ`
    - `source=online_pull`
    - `trace_id=5d39ea3f-db08-4ed4-a946-be9cd3022773`
    - `duration_ms=486`

- Resource/state truth after login:
  - `trade://session/current`
    - `ready=true`
    - `account_id=8883884325`
    - `owner_account_id=8883884325`
    - `session_id=1111`
  - `diag://probe/latest`
    - `ok=true`
    - `reason=ok`
    - `session_id=1111`
    - `read_only_ready=true`
    - `write_permission_ready=true`
    - `up_queue_xtquant_exists=true`
  - `diag://login/latest`
    - last write `2026-03-31 18:29:30`
    - `ok=true`
    - `status=already_logged_in`
    - `account_id=8883884325`
    - current main-window title is account-qualified, matching the real logged-in UI
  - state file timestamps:
    - `trade_session_current.json` -> `2026-03-31 18:29:30`
    - `diag_probe_latest.json` -> `2026-03-31 18:29:30`
    - `diag_login_latest.json` -> `2026-03-31 18:29:30`

## Proven Observations

1. After the user completed the real login, the earlier `session.warm -> account.show_exception -> xttrader connect=-1` blocker no longer reproduced.
2. The current repo can now establish a ready owner-managed session on the logged-in host: `session.warm=true`, `session.status=true`, `trade://session/current.ready=true`, `probe.connection.ok=true`, `account.show=true`, `positions.list=true`, and `snapshot.l1=true`.
3. `up_queue_xtquant` is present again after login, and `diag://probe/latest` reports both read-only and write-permission prechecks as `ok=true`.
4. The new first blocker is `orders.list`, which now fails immediately with `'NoneType' object has no attribute 'query_open_orders'` instead of any login/session-not-ready symptom.

## Bounded Inference

1. The previous `VAL-004` conclusion that the host was not truly logged in has now been validated by reversal: once the user completed login, the broker/session-not-ready symptoms disappeared.
2. The remaining first blocker is no longer an environment/login-state blocker. It is now best classified as an implementation/design defect in the current public `orders.list` path.
3. This does not authorize `VAL-003` or any `G4` claim. The scope here remains non-write only, and the ordered `G3` chain is still not fully closed because public `orders.list` is broken.

## Artifact Refs

- Current trade-gateway logs:
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260331_182839.log`
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260331_182839.stderr.log`
- Trade-gateway call log:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260331\trade_gateway_calls.jsonl`
- State files:
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json`
- Key traces:
  - `2a892d06-2858-4a54-b4e6-79cab56753ba`
  - `6467f154-0c8a-47bb-8d88-465f5c68224e`
  - `d982161d-c360-4744-842c-a057975e8ed1`
  - `13b7efd1-de2d-4498-b3f4-0d3635135a12`
  - `7f142de3-1ca7-42c7-80df-b64dc82efbd6`
  - `88f8d8ca-e6b2-4e74-89e8-773e0bdbecec`
  - `5d39ea3f-db08-4ed4-a946-be9cd3022773`

## Verdict

This post-login rerun supersedes the earlier “not truly logged in” blocker shape. `VAL-004` now isolates a different first blocker: the host login/session state is ready enough for `session.warm`, `session.status`, and `probe.connection`, but the current public `orders.list` path fails with a `NoneType.query_open_orders` implementation error. The current test conclusion is therefore `fail_design`, not `fail_env`.
