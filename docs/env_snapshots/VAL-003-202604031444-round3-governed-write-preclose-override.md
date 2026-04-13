# EnvSnapshot
Task ID: VAL-003
Date: 2026-04-03T14:44:09+08:00
Role: test

## Metadata

- Executor: `controller direct test substitution`
- Authorization Basis: explicit user authorization in the current turn allowing controller to execute this round's `test` work
- EvidencePack: [VAL-003-test-202604031444-round3-governed-write-preclose-override.md](../evidence_packs/VAL-003-test-202604031444-round3-governed-write-preclose-override.md)
- TaskCard: [VAL-003.md](../task_cards/VAL-003.md)
- ChangePack: [VAL-003.md](../change_packages/VAL-003.md)
- Controller Judgment: `.tmp/spec-task-harness/VAL-003-controller-judgment-20260403T142713+0800-preclose-override.md`
- Raw Runtime Capture: `.tmp/spec-task-harness/val003-controller-direct-runtime-20260403T144409+0800.json`

## Host

- Working Directory: `D:\xtquant-mcp\repo`
- Instance Root: `D:\xtquant-mcp\instance\prod`
- Trade Gateway: `http://127.0.0.1:8765/mcp`
- Trade `/healthz`: `http://127.0.0.1:8765/healthz`
- Data `/healthz`: `http://127.0.0.1:8766/healthz`

## Packet And Budget

- side: `BUY`
- symbol: `515880.SH`
- qty: `100`
- price_mode: `l1_protect`
- cancel_timeout: `30s`
- prior real `order.place` attempts earlier today: `2`
- additional attempts authorized in this override round: `3`
- additional attempts actually used in this override round: `1`
- cumulative real `order.place` attempts today after this run: `3`
- broker-side progress obtained: `no`

## Wall Clock

- run start: `2026-04-03T14:43:27.1127135+08:00`
- `miniqmt.ensure_logged_in`: `2026-04-03T14:43:27+08:00`
- `session.warm`: `2026-04-03T14:43:27+08:00`
- `session.status`: `2026-04-03T14:43:27+08:00`
- `probe.connection`: `2026-04-03T14:43:27+08:00`
- `orders.list` before write: `2026-04-03T14:43:27+08:00`
- `order.place`: `2026-04-03T14:43:27+08:00`
- connect gate finished: `2026-04-03T14:44:09+08:00`
- post-failure `session.status`: `2026-04-03T14:44:09+08:00`
- post-failure `probe.connection`: `2026-04-03T14:44:09+08:00`
- post-failure `orders.list`: `2026-04-03T14:44:09+08:00`
- run end: `2026-04-03T14:44:09.6706928+08:00`

## Gateway Health Snapshot

- trade `/healthz`
  - `ok=true`
  - `server_name=xtqmtTradeGateway`
  - `bind_port=8765`
  - `evidence_scope=prod`
- data `/healthz`
  - `ok=true`
  - `server_name=xtqmtDataGateway`
  - `bind_port=8766`
  - `evidence_scope=prod`

## Fresh Preflight Snapshot

- `miniqmt.ensure_logged_in`
  - `trace_id=deac02fa-1337-420a-b29b-f2d497445059`
  - `ok=true`
  - `status=already_logged_in`
  - `port_ready=true`
- `session.warm`
  - `trace_id=5e5563d8-9b0f-424b-8c89-b0b1c5d3ddee`
  - `ready=true`
  - `session_id=1111`
- `session.status`
  - `trace_id=3d172113-4891-4003-a256-456678a031ff`
  - `ready=true`
  - `session_id=1111`
- `probe.connection`
  - `trace_id=879dd4f1-8b7f-4598-b1b9-08d561ed794b`
  - `ok=true`
  - `overall_trade_ready=true`
  - `read_only_ready=true`
  - `write_permission_ready=true`
  - `write_permission_probe.implies_write_permission=false`
- `orders.list`
  - `trace_id=da917d63-8190-4f5f-8f92-e86e8f30c2c6`
  - `ok=true`
  - `degraded=true`
  - `fallback_used=true`
  - `fallback_reason=broker_missing`
  - `rows=[]`

## Governed Write Snapshot

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

## Connect Gate Snapshot

- `enabled=true`
- `attempts=5`
- `ok_count=0`
- `success_rate=0.0`
- `threshold=0.9`
- `started_at=2026-04-03T14:43:27+08:00`
- `finished_at=2026-04-03T14:44:09+08:00`
- `reason=connect_gate_failed`
- samples for `session_id=2111`
  - attempt 1: `connect_code=-1` at `2026-04-03T14:43:27+08:00`
  - attempt 2: `connect_code=-1` at `2026-04-03T14:43:36+08:00`
  - attempt 3: `connect_code=-1` at `2026-04-03T14:43:45+08:00`
  - attempt 4: `connect_code=-1` at `2026-04-03T14:43:54+08:00`
  - attempt 5: `connect_code=-1` at `2026-04-03T14:44:03+08:00`

## Post-Failure Runtime Snapshot

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

## Resource Snapshot

- `trade://session/current`
  - reread completed after the failed write
- `diag://probe/latest`
  - reread completed after the failed write
- `diag://login/latest`
  - reread completed after the failed write

## Supporting Artifact Snapshot

- authoritative call log:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260403\trade_gateway_calls.jsonl`
- absent trade_ops CSVs after the failed write:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_ops\20260403\real\orders_submit_log.csv` -> `False`
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_ops\20260403\real\orders_state_timeline.csv` -> `False`
- state DB:
  - `D:\xtquant-mcp\instance\prod\state\trade_ops\order_state_timeline.sqlite3`
  - `LastWriteTime=2026-03-30 03:06:19`

## Host Log Snapshot

- owner session `1111` remained readable during the run:
  - `2026-04-03 14:43:27` query account / positions / orders on tag `1111`
  - `2026-04-03 14:43:27` `quant session 1111 connected`
- same-call candidate `2111` stayed unstable:
  - `2026-04-03 14:43:30` `quant session 2111 connected`
  - `2026-04-03 14:43:34` `heartbeat timeout, ssid:2111`
  - `2026-04-03 14:43:39` `quant session 2111 connected`
  - `2026-04-03 14:43:43` `heartbeat timeout, ssid:2111`
  - `2026-04-03 14:43:48` `quant session 2111 connected`
  - `2026-04-03 14:43:52` `heartbeat timeout, ssid:2111`
  - `2026-04-03 14:43:57` `quant session 2111 connected`
  - `2026-04-03 14:44:01` `heartbeat timeout, ssid:2111`
  - `2026-04-03 14:44:06` `quant session 2111 connected`
  - `2026-04-03 14:44:10` `heartbeat timeout, ssid:2111`

## Classification Notes

- Classification: `fail_env`
- Blocking Layer: `broker/session connect gate`
- Design vs Environment: `environment blocker`

This snapshot records a fresh third real `order.place` attempt for the day, but it still stops before broker submission. The environment signal is stronger than before because the same-call `connect_gate` again returns a fresh complete `0/5` failure set on `session_id=2111`, while `orders.list` remains on degraded public fallback with no broker rows.
