# EvidencePack
Task ID: VAL-003
Role: test
Date: 2026-04-03T14:41:33+08:00
Acceptance Gate: G4
Conclusion: fail_env

## Scope

1. Execute one commanded pre-close override run for `VAL-003` using the unchanged governed write packet.
2. Stop after the first additional live `order.place` if the result is already conclusive and does not produce broker-side progress.
3. Record any extra same-window live attempts that are observed in the authoritative host call log after the commanded run, so cumulative live budget is not undercounted.

## Fixed Packet

- side: `BUY`
- symbol: `515880.SH`
- qty: `100`
- price_mode: `l1_protect`
- cancel_timeout: `30s`
- override-round budget authorized by user: `3` additional real orders
- commanded attempts used in this run: `1`
- broker-side progress obtained in this commanded run: `no`

## Command Source

1. Exact commanded runtime capture:
   - `.tmp/spec-task-harness/val003-preclose-runtime-20260403T144133+0800.json`
2. Authoritative gateway call log:
   - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260403\trade_gateway_calls.jsonl`

## Commanded Run Results

- Commanded run wall clock start: `2026-04-03T14:41:33.6956429+08:00`
- Trade `/healthz`: `ok=true`
- Data `/healthz`: `ok=true`
- `miniqmt.ensure_logged_in`
  - `trace_id=0bbfb228-aedf-4a2d-9374-24a0806db8be`
  - `server_ts=2026-04-03T14:41:33+08:00`
  - `status=already_logged_in`
- `session.warm`
  - `trace_id=df629765-6511-4081-bdae-26d7f2e1738c`
  - `server_ts=2026-04-03T14:41:33+08:00`
  - `ready=true`
  - `session_id=1111`
- `session.status`
  - `trace_id=6893b7a9-1749-42f5-87f9-f68952af2d77`
  - `server_ts=2026-04-03T14:41:34+08:00`
  - `ready=true`
  - `session_id=1111`
- `probe.connection`
  - `trace_id=388d78f6-ebca-4988-a98a-aeeda2de9d98`
  - `server_ts=2026-04-03T14:41:34+08:00`
  - `overall_trade_ready=true`
  - `write_permission_ready=true`
  - `write_permission_probe.implies_write_permission=false`
- `orders.list` before write
  - `trace_id=d67ba88a-f932-42b7-a454-4b4302e46e5d`
  - `server_ts=2026-04-03T14:41:34+08:00`
  - `degraded=true`
  - `fallback_used=true`
  - `fallback_reason=broker_missing`
  - `rows=[]`

## Commanded `order.place`

- `trace_id=3a4abce7-7132-4210-8fb5-4d382cd13fba`
- `server_ts=2026-04-03T14:41:34+08:00`
- command wall clock finished: `2026-04-03T14:42:13.5892748+08:00`
- `ok=false`
- `status=risk_rejected`
- `code=connect_gate_failed`
- `broker_order_id=""`
- `intent_id=INT-CLI-20260403144134`
- `governed_write_path=true`
- `write_path=governed_service_order_place`

`connect_gate` details for the commanded run:

- `attempts=5`
- `ok_count=1`
- `success_rate=0.2`
- `threshold=0.9`
- `reason=connect_gate_failed`
- samples on `session_id=2111`:
  - `2026-04-03T14:41:34+08:00 -> -1`
  - `2026-04-03T14:41:43+08:00 -> 0`
  - `2026-04-03T14:41:49+08:00 -> -1`
  - `2026-04-03T14:41:58+08:00 -> -1`
  - `2026-04-03T14:42:07+08:00 -> -1`

Test judgment for the commanded run:

1. The first additional live attempt again reached the real governed write path.
2. It still failed before broker submission and did not produce `broker_order_id`.
3. That result was already conclusive enough to stop the commanded run after one additional order instead of burning more manually.

## Observed Post-Command Host Truth

During post-command inspection of the authoritative call log, an extra same-window background sequence was observed:

- fresh preflight traces at `2026-04-03T14:43:27+08:00`:
  - `miniqmt.ensure_logged_in=deac02fa-1337-420a-b29b-f2d497445059`
  - `session.warm=5e5563d8-9b0f-424b-8c89-b0b1c5d3ddee`
  - `session.status=3d172113-4891-4003-a256-456678a031ff`
  - `probe.connection=879dd4f1-8b7f-4598-b1b9-08d561ed794b`
  - `orders.list=da917d63-8190-4f5f-8f92-e86e8f30c2c6`
- extra observed `order.place`:
  - `trace_id=0a3397e0-ca96-4ea6-8f74-7bf7a7770c04`
  - `server_ts=2026-04-03T14:43:27+08:00`
  - `ok=false`
  - `status=risk_rejected`
  - `code=connect_gate_failed`
  - `broker_order_id=""`
  - `connect_gate success_rate=0.0`
  - samples for `session_id=2111`: `-1, -1, -1, -1, -1`

This extra sequence was not part of the commanded shell script captured in `.tmp/spec-task-harness/val003-preclose-runtime-20260403T144133+0800.json`, and it is therefore treated as separately observed host truth, likely from an earlier interrupted unified exec process that continued in the background. It still matters for live-budget accounting.

## Attempt Accounting

- real `order.place` attempts already known before this run: `2`
- additional attempts directly used by the commanded pre-close override run: `1`
- host-observed additional attempt after the commanded run in the same override window: `1`
- host-observed cumulative total real `order.place` attempts today by `2026-04-03T14:44:09+08:00`: `4`

## Conclusion

- Final Conclusion: `fail_env`
- Failure Layer: `environment`
- Recommended Next State: `Blocked`

Reasoning:

1. The fresh commanded run again hit the real governed write path but still produced no `broker_order_id`.
2. `probe.connection` remained optimistic at the top level while `write_permission_probe.implies_write_permission=false` stayed unchanged.
3. The commanded run already reproduced the same `connect_gate_failed` blocker with insufficient broker/session stability.
4. Independent of the commanded run, the host call log then showed one more same-window `order.place` also failing with the same blocker and an even worse `0/5` connect profile.
5. Further live attempts in the current session would spend budget without increasing broker-side truth.
