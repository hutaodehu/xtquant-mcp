# EnvSnapshot

Task ID: VAL-003
Date: 2026-04-03T13:20:00+08:00
Role: test

## Host

- Working Directory: `D:\xtquant-mcp\repo`
- EvidencePack: [VAL-003-test-202604031320-round3-governed-write.md](../evidence_packs/VAL-003-test-202604031320-round3-governed-write.md)
- TaskCard: [VAL-003.md](../task_cards/VAL-003.md)
- ChangePack: [VAL-003.md](../change_packages/VAL-003.md)
- Controller Inputs:
  - `.tmp/spec-task-harness/VAL-003-controller-delegation-status-20260403T113218+0800.md`
  - `.tmp/spec-task-harness/VAL-003-controller-judgment-20260403T130704+0800.md`
  - `.tmp/spec-task-harness/VAL-003-dispatch-20260403T130704+0800-round3-manual-gate.md`

## Runtime Scope

- Intended governed-write packet:
  - side: `BUY`
  - symbol: `515880.SH`
  - qty: `100`
  - price_mode: `l1_protect`
  - cancel_timeout: `30s`
- Session budget:
  - authorized attempts: `3`
  - attempts actually used: `1`
  - `attempt_count_used=1`
- Execution posture captured in this snapshot:
  - Round 3 governed write reached real `order.place`
  - first attempt became conclusive
  - no second live order executed
  - `order.place executed=yes`

## Wall Clock

- Initial same-session host preflight:
  - `2026-04-03T13:12:11.4049433+08:00`
- Formal Round 3 preflight chain:
  - `miniqmt.ensure_logged_in`: `2026-04-03T13:15:47+08:00`
  - `session.warm`: `2026-04-03T13:15:48+08:00`
  - `session.status`: `2026-04-03T13:15:48+08:00`
  - `probe.connection`: `2026-04-03T13:15:48+08:00`
- Governed write:
  - `order.place`: `2026-04-03T13:15:48+08:00`
  - connect gate finished: `2026-04-03T13:16:27+08:00`
- Post-failure runtime truth:
  - `session.status`: `2026-04-03T13:16:27+08:00`
  - `probe.connection`: `2026-04-03T13:16:27+08:00`
  - `orders.list`: `2026-04-03T13:16:27+08:00`
- Final resource reread:
  - `2026-04-03T13:19:10+08:00`
- Trading-window assessment:
  - `market_window_closed=false` for the captured governed-write window

## Process And Listener Snapshot

- MiniQMT processes before wake:
  - `XtMiniQmt.exe` pid `24380`, start `2026-04-01 23:57:03`
  - `miniquote.exe` pid `24184`, start `2026-04-01 23:57:03`
- Initial port state at `2026-04-03T13:12:11+08:00`:
  - `58610 -> TcpTestSucceeded=True`
  - `8765 -> TcpTestSucceeded=False`
  - `8766 -> TcpTestSucceeded=False`
- Listener state after repo-supported wake:
  - `8765 -> pid 34064`
  - `8766 -> pid 30432`
- Health after wake:
  - trade `/healthz`:
    - `ok=true`
    - `server_name=xtqmtTradeGateway`
    - `evidence_scope=prod`
  - data `/healthz`:
    - `ok=true`
    - `server_name=xtqmtDataGateway`
    - `evidence_scope=prod`

## Preflight Snapshot

- `miniqmt.ensure_logged_in`
  - `trace_id=d4bb02b8-2f6b-4fba-bd4f-fd66d83ffe93`
  - `status=already_logged_in`
  - `port_ready=true`
- `session.warm`
  - `trace_id=cfdc3949-fcb7-4823-9e70-04ebb9dc831d`
  - `ready=true`
  - `session_id=1111`
  - `owner_generation=1`
  - `owner_started_reason=initial_warm`
- `session.status`
  - `trace_id=c6e1cce9-c1e4-4c4c-8a71-a485e209ed99`
  - `ready=true`
  - `session_id=1111`
- `probe.connection`
  - `trace_id=6d0947ff-987e-487d-af5a-4ad14ba05ec2`
  - `ok=true`
  - `reason=ok`
  - `overall_trade_ready=true`
  - `read_only_ready=true`
  - `write_permission_ready=true`
  - `write_permission_blocked=false`
  - `write_permission_probe.implies_write_permission=false`

## Governed Write Snapshot

- `order.place`
  - `trace_id=a067be28-95e0-4698-860e-7d4891a46aa6`
  - `server_ts=2026-04-03T13:15:48+08:00`
  - `duration_ms=39333`
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
- `connect_gate`
  - `enabled=true`
  - `started_at=2026-04-03T13:15:48+08:00`
  - `finished_at=2026-04-03T13:16:27+08:00`
  - `attempts=5`
  - `ok_count=1`
  - `success_rate=0.2`
  - `threshold=0.9`
  - `reason=connect_gate_failed`
  - per-attempt samples on `session_id=2111`:
    - attempt 1: `connect_code=0` at `2026-04-03T13:15:48+08:00`
    - attempt 2: `connect_code=-1` at `2026-04-03T13:15:54+08:00`
    - attempt 3: `connect_code=-1` at `2026-04-03T13:16:03+08:00`
    - attempt 4: `connect_code=-1` at `2026-04-03T13:16:12+08:00`
    - attempt 5: `connect_code=-1` at `2026-04-03T13:16:21+08:00`

## Post-Failure Runtime Snapshot

- `session.status` after the failed write:
  - `trace_id=6056abf3-5610-49bf-9dd5-a768e1f3655c`
  - `server_ts=2026-04-03T13:16:27+08:00`
  - `ready=true`
  - `session_id=1111`
- `probe.connection` after the failed write:
  - `trace_id=f4bbba29-d49d-4a88-914b-5c669a22aa3b`
  - `server_ts=2026-04-03T13:16:27+08:00`
  - `ok=true`
  - `reason=ok`
  - `overall_trade_ready=true`
  - `write_permission_ready=true`
  - `write_permission_probe.implies_write_permission=false`
- `orders.list` after the failed write:
  - `trace_id=9ca42e32-889e-4c6e-8c30-f12a68e4060c`
  - `server_ts=2026-04-03T13:16:27+08:00`
  - `ok=true`
  - `count=0`
  - `degraded=true`
  - `fallback_used=true`
  - `fallback_reason=broker_missing`
  - `read_scope=public_fallback`
  - `rows=[]`

## Resource Snapshot

- `trade://session/current` at `2026-04-03T13:19:10+08:00`:
  - `ready=true`
  - `session_id=1111`
  - `last_used_at=2026-04-03T13:19:10+08:00`
  - `last_error=""`
- `diag://probe/latest` at `2026-04-03T13:19:10+08:00`:
  - latest payload timestamp `2026-04-03T13:16:27+08:00`
  - `ok=true`
  - `reason=ok`
  - `overall_trade_ready=true`
  - `write_permission_probe.implies_write_permission=false`
- `diag://login/latest` at `2026-04-03T13:19:10+08:00`:
  - `status=already_logged_in`
  - `port_ready=true`

## Artifact Snapshot

- Authoritative call-log artifact:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260403\trade_gateway_calls.jsonl`
  - last write after the failed write: `2026-04-03 13:16:27`
- Declared by the `order.place` envelope but absent after failure:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_ops\20260403\real\orders_submit_log.csv`
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_ops\20260403\real\orders_state_timeline.csv`
  - both `Test-Path=False`
- State DB:
  - `D:\xtquant-mcp\instance\prod\state\trade_ops\order_state_timeline.sqlite3`
  - `LastWriteTime=2026-03-30 03:06:19`
  - `order_states` table contained no fresh rows for this run

## Host-Side Snapshot

- `XtMiniQmt_20260403.log` showed the owner session `1111` remained readable:
  - `2026-04-03 13:15:48.121` `quant session 1111 connected`
  - `2026-04-03 13:16:27.428-13:16:27.443` repeated account/positions/orders queries for tag `1111`
- The connect-gate candidate `2111` was unstable in the same window:
  - `2026-04-03 13:15:51.161` `quant session 2111 connected`
  - `2026-04-03 13:15:54.881` heartbeat timeout `ssid:2111`
  - `2026-04-03 13:16:01.223` heartbeat timeout `ssid:2111`
  - `2026-04-03 13:16:10.286` heartbeat timeout `ssid:2111`
  - `2026-04-03 13:16:19.348` heartbeat timeout `ssid:2111`
- Queue-file state:
  - `lock_down_queue_win_1111` last write `2026-04-03 13:13:48`
  - `lock_down_queue_win_2111` last write `2026-04-03 13:15:51`
  - `down_queue_win_1111` last write `2026-04-03 13:16:21`
  - `down_queue_win_2111` last write `2026-04-03 13:16:24`

## Classification Notes

- Environment:
  - market window was open
  - MiniQMT login and owner-session reuse were healthy
  - the write path failed because the same-attempt pretrade connect gate for `session_id=2111` was unstable
  - no `broker_order_id` or broker-side state chain was produced
- Governance/control-plane:
  - this run used `1` real order attempt
  - the first attempt is conclusive, so no second live order is justified in this session
- Design/contract:
  - no fresh `fail_design` signal was observed
  - the governed write path preserved truthful failure reporting instead of emitting a fake broker ack

## Snapshot Summary

This snapshot captures the full same-session Round 3 governed-write outcome for `VAL-003` on 2026-04-03 Beijing afternoon. The run recovered a temporary listener-level `G1` stop, completed the required Round 3 preflight, and then executed one real `order.place` with the fixed packet. That live write became conclusive without needing more budget: the service-side write path truthfully returned `connect_gate_failed`, no `broker_order_id` was created, and the connect gate on `session_id=2111` degraded from one initial `connect_code=0` to four subsequent `connect_code=-1` results in the same attempt. Post-failure runtime truth still showed owner-session read readiness on `1111`, but no broker-side order chain or persistence artifacts materialized. The correct test-role classification for this snapshot is therefore `fail_env` with `attempt_count=1` and no further live attempts in the current session.

## Recommended Next State

- Recommended next state: `Blocked`
- Reason: the same-session governed write already produced conclusive `fail_env` evidence, so the task should not stay in an active live-write posture until broker/session connect-gate stability is independently re-established.
