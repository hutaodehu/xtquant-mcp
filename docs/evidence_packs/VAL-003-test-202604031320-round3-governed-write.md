# EvidencePack

Task ID: VAL-003
Role: test
Date: 2026-04-03T13:20:00+08:00
Acceptance Gate: G4
Conclusion: fail_env

## Env Snapshot

- Link: [VAL-003-202604031320-round3-governed-write.md](../env_snapshots/VAL-003-202604031320-round3-governed-write.md)

## Scope

1. Execute the Round 3 governed-write packet in the current 2026-04-03 Beijing afternoon trading window only.
2. Rerun the required Round 3 preflight chain before any write.
3. Use at most one real `order.place` attempt if the first attempt already becomes conclusive.
4. Capture the post-failure runtime truth and stop without a second order once the first attempt is conclusive.

## Fixed Packet

- side: `BUY`
- symbol: `515880.SH`
- qty: `100`
- price_mode: `l1_protect`
- cancel_timeout: `30s`
- attempt budget authorized for this session: `3`
- attempts actually used in this run: `1`
- real `order.place` executed: `yes`
- `attempt_count_used=1`
- `order.place executed=yes`

## Required Sources Re-Read First

1. [VAL-003.md](../task_cards/VAL-003.md)
2. [VAL-003.md](../change_packages/VAL-003.md)
3. [VAL-003_G4_EXECUTION_PLAN.md](../VAL-003_G4_EXECUTION_PLAN.md)
4. [ACCEPTANCE_STANDARD.md](../ACCEPTANCE_STANDARD.md)
5. [OPERATIONS_RUNBOOK.md](../OPERATIONS_RUNBOOK.md)
6. [VAL-003-test-202604021413-round2-broker-session.md](./VAL-003-test-202604021413-round2-broker-session.md)
7. [VAL-003-202604021413-round2-broker-session.md](../env_snapshots/VAL-003-202604021413-round2-broker-session.md)
8. [VAL-003-review-202604021420.md](../reviews/VAL-003-review-202604021420.md)
9. `.tmp/spec-task-harness/VAL-003-controller-delegation-status-20260403T113218+0800.md`
10. `.tmp/spec-task-harness/VAL-003-controller-judgment-20260403T130704+0800.md`
11. `.tmp/spec-task-harness/VAL-003-dispatch-20260403T130704+0800-round3-manual-gate.md`

## Commands

1. Initial same-session host preflight before waking listeners:
   - `Get-Date -Format o`
   - `Get-Process XtMiniQmt,miniquote -ErrorAction SilentlyContinue | Select-Object ProcessName,Id,StartTime,Path | Format-List`
   - `Test-NetConnection 127.0.0.1 -Port 58610 | Select-Object ComputerName,RemotePort,TcpTestSucceeded | Format-List`
   - `Test-NetConnection 127.0.0.1 -Port 8765 | Select-Object ComputerName,RemotePort,TcpTestSucceeded | Format-List`
   - `Test-NetConnection 127.0.0.1 -Port 8766 | Select-Object ComputerName,RemotePort,TcpTestSucceeded | Format-List`
   - `Invoke-RestMethod http://127.0.0.1:8765/healthz | ConvertTo-Json -Depth 8`
   - `Invoke-RestMethod http://127.0.0.1:8766/healthz | ConvertTo-Json -Depth 8`
2. Repo-supported listener recovery:
   - `pwsh -File scripts\wake_trade_gateway.ps1`
   - `pwsh -File scripts\wake_data_gateway.ps1`
3. Post-wake host health confirmation:
   - `Test-NetConnection 127.0.0.1 -Port 8765 | Select-Object ComputerName,RemotePort,TcpTestSucceeded | Format-List`
   - `Test-NetConnection 127.0.0.1 -Port 8766 | Select-Object ComputerName,RemotePort,TcpTestSucceeded | Format-List`
   - `Invoke-RestMethod http://127.0.0.1:8765/healthz | ConvertTo-Json -Depth 8`
   - `Invoke-RestMethod http://127.0.0.1:8766/healthz | ConvertTo-Json -Depth 8`
4. Round 3 preflight chain and same-session resource reads through the preferred interpreter:
   - inline JSON-RPC over `D:\xtquant-mcp\venv313\Scripts\python.exe`
   - `initialize`
   - `tools/call miniqmt.ensure_logged_in {"login_timeout_seconds":20}`
   - `tools/call session.warm {}`
   - `tools/call session.status {}`
   - `tools/call probe.connection {}`
   - `resources/read trade://session/current`
   - `resources/read diag://probe/latest`
   - `resources/read diag://login/latest`
5. Round 3 governed-write attempt and post-failure runtime truth through the same gateway session:
   - `tools/call order.place {"code":"515880.SH","side":"BUY","qty":100,"price_mode":"l1_protect"}`
   - because no `broker_order_id` was returned:
   - `tools/call session.status {}`
   - `tools/call probe.connection {}`
   - `tools/call orders.list {}`
6. Artifact and host-log back-link collection:
   - parse `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260403\trade_gateway_calls.jsonl`
   - `Test-Path D:\xtquant-mcp\instance\prod\artifacts\trade_ops\20260403\real\orders_submit_log.csv`
   - `Test-Path D:\xtquant-mcp\instance\prod\artifacts\trade_ops\20260403\real\orders_state_timeline.csv`
   - `Get-Item D:\xtquant-mcp\instance\prod\state\trade_ops\order_state_timeline.sqlite3 | Select-Object FullName,Length,LastWriteTime | Format-List`
   - `Select-String -Path D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260403.log -Pattern '2111|1111|onConnected|heartbeat|lock_down_queue'`
   - `Get-ChildItem D:\lh\国金证券QMT交易端\userdata_mini -Filter 'lock_down_queue_win_*'`
   - `Get-ChildItem D:\lh\国金证券QMT交易端\userdata_mini -Filter 'down_queue_win_*'`
7. Final resource reread after the conclusive stop:
   - inline JSON-RPC over `D:\xtquant-mcp\venv313\Scripts\python.exe`
   - `initialize`
   - `resources/read trade://session/current`
   - `resources/read diag://probe/latest`
   - `resources/read diag://login/latest`

## Raw Results

- Same-session host preflight before listener recovery:
  - wall clock: `2026-04-03T13:12:11.4049433+08:00`
  - `XtMiniQmt.exe` and `miniquote.exe` were already running from `D:\lh\国金证券QMT交易端\bin.x64\`
  - `127.0.0.1:58610` was reachable
  - `127.0.0.1:8765` and `127.0.0.1:8766` were not reachable
  - both `/healthz` endpoints were refused, so the run first hit a recoverable `G1` listener stop instead of a market-window stop

- Listener recovery before the formal Round 3 chain:
  - repo-supported wake paths were used:
    - `scripts\wake_trade_gateway.ps1`
    - `scripts\wake_data_gateway.ps1`
  - after wake:
    - trade listener `127.0.0.1:8765` became reachable
    - data listener `127.0.0.1:8766` became reachable
    - trade `/healthz` returned `ok=true`, `server_name=xtqmtTradeGateway`, `evidence_scope=prod`
    - data `/healthz` returned `ok=true`, `server_name=xtqmtDataGateway`, `evidence_scope=prod`
    - listener snapshot showed:
      - `8765 -> pid 34064`
      - `8766 -> pid 30432`

- Round 3 preflight chain before the write:
  - MCP `initialize`
    - started `2026-04-03T13:15:47.978244+08:00`
    - HTTP `200`
    - `mcp_session_id=992fa43f-28a1-4e3a-92e6-d98262913ee9`
  - `miniqmt.ensure_logged_in`
    - `trace_id=d4bb02b8-2f6b-4fba-bd4f-fd66d83ffe93`
    - `server_ts=2026-04-03T13:15:47+08:00`
    - `ok=true`
    - `status=already_logged_in`
    - `port_ready=true`
  - `session.warm`
    - `trace_id=cfdc3949-fcb7-4823-9e70-04ebb9dc831d`
    - `server_ts=2026-04-03T13:15:48+08:00`
    - `ready=true`
    - `session_id=1111`
    - `owner_generation=1`
    - `owner_started_reason=initial_warm`
  - `session.status`
    - `trace_id=c6e1cce9-c1e4-4c4c-8a71-a485e209ed99`
    - `server_ts=2026-04-03T13:15:48+08:00`
    - `ready=true`
    - `session_id=1111`
    - `last_error=""`
  - `probe.connection`
    - `trace_id=6d0947ff-987e-487d-af5a-4ad14ba05ec2`
    - `server_ts=2026-04-03T13:15:48+08:00`
    - `ok=true`
    - `reason=ok`
    - `overall_trade_ready=true`
    - `read_only_ready=true`
    - `write_permission_ready=true`
    - `write_permission_blocked=false`
    - `write_permission_probe.implies_write_permission=false`
    - `probe_scope_note` remained: write-permission is still a precheck signal, not proof that broker-side write is already ready

- Conclusive single real `order.place` attempt:
  - packet:
    - side `BUY`
    - symbol `515880.SH`
    - qty `100`
    - `price_mode=l1_protect`
  - attempt count used: `1`
  - `order.place` audit:
    - `trace_id=a067be28-95e0-4698-860e-7d4891a46aa6`
    - `server_ts=2026-04-03T13:15:48+08:00`
    - `duration_ms=39333`
  - `order.place` result:
    - `ok=false`
    - `status=risk_rejected`
    - `code=connect_gate_failed`
    - `message=pretrade connect gate failed`
    - `broker_order_id=""`
    - `client_order_id=COID-CLI-20260403-515880SH-BUY-1`
    - `client_order_key=COID-CLI-20260403-515880SH-BUY-1`
    - `intent_id=INT-CLI-20260403131548`
    - `governed_write_path=true`
    - `write_path=governed_service_order_place`
  - `connect_gate` details from the same call:
    - `enabled=true`
    - `started_at=2026-04-03T13:15:48+08:00`
    - `finished_at=2026-04-03T13:16:27+08:00`
    - `attempts=5`
    - `ok_count=1`
    - `success_rate=0.2`
    - `threshold=0.9`
    - `reason=connect_gate_failed`
    - samples for `session_id=2111`:
      - attempt 1: `connect_code=0` at `2026-04-03T13:15:48+08:00`
      - attempt 2: `connect_code=-1` at `2026-04-03T13:15:54+08:00`
      - attempt 3: `connect_code=-1` at `2026-04-03T13:16:03+08:00`
      - attempt 4: `connect_code=-1` at `2026-04-03T13:16:12+08:00`
      - attempt 5: `connect_code=-1` at `2026-04-03T13:16:21+08:00`

- Post-failure runtime truth inside the same session:
  - `session.status`
    - `trace_id=6056abf3-5610-49bf-9dd5-a768e1f3655c`
    - `server_ts=2026-04-03T13:16:27+08:00`
    - `ready=true`
    - `session_id=1111`
  - `probe.connection`
    - `trace_id=f4bbba29-d49d-4a88-914b-5c669a22aa3b`
    - `server_ts=2026-04-03T13:16:27+08:00`
    - `ok=true`
    - `reason=ok`
    - `overall_trade_ready=true`
    - `write_permission_ready=true`
    - `write_permission_probe.implies_write_permission=false`
  - `orders.list`
    - `trace_id=9ca42e32-889e-4c6e-8c30-f12a68e4060c`
    - `server_ts=2026-04-03T13:16:27+08:00`
    - `ok=true`
    - `count=0`
    - `source=active_owner_shadow`
    - `read_scope=public_fallback`
    - `degraded=true`
    - `fallback_used=true`
    - `fallback_reason=broker_missing`
    - `rows=[]`

- Resource reread after the conclusive stop:
  - at `2026-04-03T13:19:10+08:00`, `trade://session/current` still reported:
    - `ready=true`
    - `session_id=1111`
    - `last_used_at=2026-04-03T13:19:10+08:00`
    - `last_error=""`
  - at `2026-04-03T13:19:10+08:00`, `diag://probe/latest` still pointed to the failed-attempt aftermath:
    - `ts=2026-04-03T13:16:27+08:00`
    - `ok=true`
    - `reason=ok`
    - `write_permission_probe.implies_write_permission=false`
  - at `2026-04-03T13:19:10+08:00`, `diag://login/latest` still reported:
    - `status=already_logged_in`
    - `port_ready=true`

- Artifact back-links and absence facts:
  - authoritative call-log artifact:
    - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260403\trade_gateway_calls.jsonl`
  - the `order.place` envelope declared trade-op artifacts:
    - `D:\xtquant-mcp\instance\prod\artifacts\trade_ops\20260403\real\orders_submit_log.csv`
    - `D:\xtquant-mcp\instance\prod\artifacts\trade_ops\20260403\real\orders_state_timeline.csv`
  - both declared trade-op files were absent immediately after the failed write:
    - `Test-Path ...orders_submit_log.csv -> False`
    - `Test-Path ...orders_state_timeline.csv -> False`
  - state DB snapshot stayed stale:
    - `D:\xtquant-mcp\instance\prod\state\trade_ops\order_state_timeline.sqlite3`
    - `LastWriteTime=2026-03-30 03:06:19`
    - table `order_states` contained no fresh rows for this run

- Host-side supporting facts from `XtMiniQmt_20260403.log` and queue files:
  - owner session `1111` stayed active for read-side queries:
    - `2026-04-03 13:15:48.121` `quant session 1111 connected`
    - `2026-04-03 13:16:27.428-13:16:27.443` repeated `query account detail / query positions / query orders not found` for tag `1111`
  - the connect gate's write-side candidate `2111` was unstable in the same window:
    - `2026-04-03 13:15:51.161` `quant session 2111 connected`
    - `2026-04-03 13:15:54.881` heartbeat timeout `ssid:2111`
    - `2026-04-03 13:16:01.223` heartbeat timeout `ssid:2111`
    - `2026-04-03 13:16:10.286` heartbeat timeout `ssid:2111`
    - `2026-04-03 13:16:19.348` heartbeat timeout `ssid:2111`
  - queue-file snapshot:
    - `lock_down_queue_win_1111` last write `2026-04-03 13:13:48`
    - `lock_down_queue_win_2111` last write `2026-04-03 13:15:51`
    - `down_queue_win_1111` last write `2026-04-03 13:16:21`
    - `down_queue_win_2111` last write `2026-04-03 13:16:24`

## Hard-Stop Assessment

1. `market_window_closed`: does not apply in this run.
   - the governed-write attempt started at `2026-04-03T13:15:48+08:00`, inside the afternoon Beijing trading session.
2. `G1` listener stop existed at the very start of the session, but it was recovered before the formal Round 3 chain.
   - `8765/8766` were initially down and then restored by the repo-supported wake scripts.
3. The first real `order.place` attempt already produced a conclusive stop.
   - the governed write did run
   - the service-side gate truthfully blocked before broker submission
   - `broker_order_id` stayed empty
   - `connect_gate` ended with `success_rate=0.2 < threshold=0.9`
4. A second live order was not justified inside the remaining budget.
   - the same attempt already isolated the blocker to connect-gate instability on `session_id=2111`
   - the post-failure `orders.list` still remained `degraded public_fallback rows=[]`
   - no same-session runtime truth showed broker-side recovery after `13:16:27+08:00`

## Separation Of Notes

- Environment-side findings:
  - market window was open
  - MiniQMT login and owner session reuse were healthy
  - the live write failed because the pretrade connect gate for `session_id=2111` was unstable in the same attempt
  - no broker-side order identifier or state chain materialized
- Governance and control-plane findings:
  - attempt budget consumed: `1`
  - the first attempt is conclusive and the controller explicitly stopped further live attempts
- Design and contract findings:
  - no new `fail_design` signal was found in this run
  - the governed write path reported its own gate failure truthfully and did not fabricate a broker ack

## Execution Boundary

- `order.place` was executed exactly once.
- `order.status` was not executed because no `broker_order_id` was returned.
- `order.cancel` was not executed because no `broker_order_id` was returned.
- `fills.list` was not executed because no `broker_order_id` was returned.
- `orders.list` was executed only as post-failure runtime truth and remained degraded fallback with `rows=[]`.

## Verdict

`fail_env`. This Round 3 governed-write run reached the real `order.place` path during the 2026-04-03 afternoon Beijing trading window and therefore produced conclusive evidence from a single live attempt. The service-side write path did not fabricate success: it returned `ok=false`, `status=risk_rejected`, `code=connect_gate_failed`, `message=pretrade connect gate failed`, and no `broker_order_id`. The underlying connect gate evidence is sufficiently specific to stop further attempts in the same session: for `session_id=2111`, only the first connect sample returned `0`, attempts `2-5` returned `-1`, and the gate finished at `success_rate=0.2` against `threshold=0.9`. Post-failure runtime truth did not show broker recovery: `orders.list` at `2026-04-03T13:16:27+08:00` remained `ok=true` only via `degraded public_fallback rows=[]`, the declared trade-op persistence files were absent, and the state DB had no fresh order rows. Under the repo vocabulary, this is a conclusive `fail_env` outcome for Round 3 with `attempt_count=1`, `order.place executed=yes`, and no justification for a second live order in this window.

## Recommended Next State

- Recommended next state: `Blocked`
- Reason: the first real `order.place` attempt is already conclusive, the blocker is environment-side connect-gate instability on `session_id=2111`, and no broker-side recovery evidence appeared after `2026-04-03T13:16:27+08:00`.
