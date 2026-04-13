# EvidencePack
Task ID: VAL-003
Role: test
Date: 2026-04-03T14:44:09+08:00
Acceptance Gate: G4
Conclusion: fail_env

## Execution Mode

- Executor: `controller direct test substitution`
- Authorization Basis: explicit user authorization in the current turn allowing controller to perform this round's `test` execution and produce `EvidencePack` / `EnvSnapshot`
- Controller Judgment Link: `.tmp/spec-task-harness/VAL-003-controller-judgment-20260403T142713+0800-preclose-override.md`
- Dispatch Link: `.tmp/spec-task-harness/VAL-003-dispatch-20260403T142713+0800-preclose-override.md`
- Raw Runtime Capture: `.tmp/spec-task-harness/val003-controller-direct-runtime-20260403T144409+0800.json`

## Scope

1. Re-run a fresh Round 3 preflight during the open Beijing afternoon trading window.
2. Execute the first additional governed-write `order.place` attempt under the user's fresh pre-close override authorization.
3. Continue to downstream `G4` follow-up only if a non-empty `broker_order_id` appears.
4. Stop immediately if the first additional attempt conclusively reproduces the same blocker with no broker-side progress.

## Fixed Packet

- side: `BUY`
- symbol: `515880.SH`
- qty: `100`
- price_mode: `l1_protect`
- cancel_timeout: `30s`
- prior real `order.place` attempts earlier today: `2`
- additional attempts authorized in this override round: `3`
- additional attempts actually used in this override round: `1`
- cumulative real `order.place` attempts today after this run: `3`
- broker-side progress obtained in this run: `no`

## Commands

1. Health checks:
   - `Invoke-RestMethod http://127.0.0.1:8765/healthz`
   - `Invoke-RestMethod http://127.0.0.1:8766/healthz`
2. JSON-RPC helper over `http://127.0.0.1:8765/mcp`:
   - `initialize`
   - `tools/call miniqmt.ensure_logged_in {"login_timeout_seconds":20}`
   - `tools/call session.warm {}`
   - `tools/call session.status {}`
   - `tools/call probe.connection {}`
   - `tools/call orders.list {}`
   - `tools/call order.place {"code":"515880.SH","side":"BUY","qty":100,"price_mode":"l1_protect"}`
3. Because no `broker_order_id` was returned:
   - `tools/call session.status {}`
   - `tools/call probe.connection {}`
   - `tools/call orders.list {}`
4. Final resource rereads:
   - `resources/read trade://session/current`
   - `resources/read diag://probe/latest`
   - `resources/read diag://login/latest`
5. Supporting host checks:
   - `Test-Path D:\xtquant-mcp\instance\prod\artifacts\trade_ops\20260403\real\orders_submit_log.csv`
   - `Test-Path D:\xtquant-mcp\instance\prod\artifacts\trade_ops\20260403\real\orders_state_timeline.csv`
   - `Get-Item D:\xtquant-mcp\instance\prod\state\trade_ops\order_state_timeline.sqlite3`
   - `Select-String -Path D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260403.log -Pattern '14:43:27|14:43:36|14:43:45|14:43:54|14:44:03|2111|heartbeat|connected'`

## Raw Results

- Window and gateway health before the write:
   - wall clock start: `2026-04-03T14:43:27.1127135+08:00`
   - trade `/healthz`: `ok=true`, `server_name=xtqmtTradeGateway`, `bind_port=8765`, `evidence_scope=prod`
   - data `/healthz`: `ok=true`, `server_name=xtqmtDataGateway`, `bind_port=8766`, `evidence_scope=prod`

- Fresh preflight chain:
   - `miniqmt.ensure_logged_in`
     - `trace_id=deac02fa-1337-420a-b29b-f2d497445059`
     - `server_ts=2026-04-03T14:43:27+08:00`
     - `ok=true`
     - `status=already_logged_in`
     - `port_ready=true`
   - `session.warm`
     - `trace_id=5e5563d8-9b0f-424b-8c89-b0b1c5d3ddee`
     - `server_ts=2026-04-03T14:43:27+08:00`
     - `ready=true`
     - `session_id=1111`
   - `session.status`
     - `trace_id=3d172113-4891-4003-a256-456678a031ff`
     - `server_ts=2026-04-03T14:43:27+08:00`
     - `ready=true`
     - `session_id=1111`
   - `probe.connection`
     - `trace_id=879dd4f1-8b7f-4598-b1b9-08d561ed794b`
     - `server_ts=2026-04-03T14:43:27+08:00`
     - `ok=true`
     - `overall_trade_ready=true`
     - `read_only_ready=true`
     - `write_permission_ready=true`
     - `write_permission_probe.implies_write_permission=false`
   - `orders.list`
     - `trace_id=da917d63-8190-4f5f-8f92-e86e8f30c2c6`
     - `server_ts=2026-04-03T14:43:27+08:00`
     - `ok=true`
     - `degraded=true`
     - `fallback_used=true`
     - `fallback_reason=broker_missing`
     - `rows=[]`

- Governed write attempt:
   - local wall clock before write: `2026-04-03T14:43:27.3038789+08:00`
   - `order.place`
     - `trace_id=0a3397e0-ca96-4ea6-8f74-7bf7a7770c04`
     - `server_ts=2026-04-03T14:43:27+08:00`
     - `duration_ms=42327`
     - `ok=false`
     - `status=risk_rejected`
     - `code=connect_gate_failed`
     - `message=pretrade connect gate failed`
     - `broker_order_id=""`
     - `intent_id=INT-CLI-20260403144327`
     - `governed_write_path=true`
     - `write_path=governed_service_order_place`

- `connect_gate` detail from the same call:
   - `enabled=true`
   - `attempts=5`
   - `ok_count=0`
   - `success_rate=0.0`
   - `threshold=0.9`
   - `started_at=2026-04-03T14:43:27+08:00`
   - `finished_at=2026-04-03T14:44:09+08:00`
   - `reason=connect_gate_failed`
   - sampled `session_id=2111` results:
     - attempt 1: `connect_code=-1` at `2026-04-03T14:43:27+08:00`
     - attempt 2: `connect_code=-1` at `2026-04-03T14:43:36+08:00`
     - attempt 3: `connect_code=-1` at `2026-04-03T14:43:45+08:00`
     - attempt 4: `connect_code=-1` at `2026-04-03T14:43:54+08:00`
     - attempt 5: `connect_code=-1` at `2026-04-03T14:44:03+08:00`

- Post-failure runtime truth:
   - local wall clock after write: `2026-04-03T14:44:09.6353090+08:00`
   - `session.status`
     - `trace_id=64b0de89-cbbc-4a4a-9131-574623c7e48a`
     - `server_ts=2026-04-03T14:44:09+08:00`
     - `ready=true`
     - `session_id=1111`
   - `probe.connection`
     - `trace_id=3d5e3b1d-344c-407d-92ac-4b435fd26ff4`
     - `server_ts=2026-04-03T14:44:09+08:00`
     - `ok=true`
     - `overall_trade_ready=true`
     - `write_permission_ready=true`
     - `write_permission_probe.implies_write_permission=false`
   - `orders.list`
     - `trace_id=ec176097-dcf8-4959-9808-200c84d2b8ef`
     - `server_ts=2026-04-03T14:44:09+08:00`
     - `ok=true`
     - `degraded=true`
     - `fallback_used=true`
     - `fallback_reason=broker_missing`
     - `rows=[]`

- Resource rereads:
   - `trade://session/current`
   - `diag://probe/latest`
   - `diag://login/latest`
   - local wall clock end: `2026-04-03T14:44:09.6706928+08:00`

- Supporting artifact state:
   - authoritative runtime artifact: `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260403\trade_gateway_calls.jsonl`
   - `orders_submit_log.csv`: `False`
   - `orders_state_timeline.csv`: `False`
   - `order_state_timeline.sqlite3` last write: `2026-03-30 03:06:19`

- Host log correlation from `XtMiniQmt_20260403.log`:
   - `14:43:30` `quant session 2111 connected`
   - `14:43:34` `heartbeat timeout, ssid:2111`
   - `14:43:39` `quant session 2111 connected`
   - `14:43:43` `heartbeat timeout, ssid:2111`
   - `14:43:48` `quant session 2111 connected`
   - `14:43:52` `heartbeat timeout, ssid:2111`
   - `14:43:57` `quant session 2111 connected`
   - `14:44:01` `heartbeat timeout, ssid:2111`
   - `14:44:06` `quant session 2111 connected`
   - `14:44:10` `heartbeat timeout, ssid:2111`

## Classification

- Final Conclusion: `fail_env`
- Failure Layer: `environment`
- Acceptance Position: `G4 not passed`

Reasoning:

1. The fresh preflight remained optimistic at the top level but still showed `write_permission_probe.implies_write_permission=false`.
2. A real fresh `order.place` occurred at `2026-04-03T14:43:27+08:00`.
3. The same-call `connect_gate` again failed before broker submission, this time with a fresh `0/5` sample set on `session_id=2111`.
4. No `broker_order_id`, broker-backed `orders.list`, trade_ops CSV, or fresh order-state DB row appeared.

## Test Conclusion

This pre-close override round produced a fresh third real `order.place` attempt for today and again failed before broker submission with the same `connect_gate_failed` pattern. The blocker remains environment-side, the attempt is already conclusive, and this run does not justify consuming the remaining override-round order budget before close.
