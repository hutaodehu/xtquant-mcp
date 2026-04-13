# EnvSnapshot
Task ID: VAL-003
Date: 2026-04-03T14:41:33+08:00
Role: test

## Host

- Working Directory: `D:\xtquant-mcp\repo`
- Runtime JSON: `.tmp/spec-task-harness/val003-preclose-runtime-20260403T144133+0800.json`
- Authoritative call log: `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260403\trade_gateway_calls.jsonl`
- Related ChangePack: [VAL-003.md](../change_packages/VAL-003.md)

## Intended Packet

- side: `BUY`
- symbol: `515880.SH`
- qty: `100`
- price_mode: `l1_protect`
- cancel_timeout: `30s`

## Budget Snapshot

- earlier real attempts already known today before this run: `2`
- additional attempts directly used in the commanded pre-close override run: `1`
- separately observed extra same-window attempt after the commanded run: `1`
- host-observed cumulative total real attempts today by `2026-04-03T14:44:09+08:00`: `4`

## Health Snapshot

- commanded run wall clock start: `2026-04-03T14:41:33.6956429+08:00`
- trade `/healthz`: `ok=true`
- data `/healthz`: `ok=true`

## Preflight Snapshot

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
  - `fallback_reason=broker_missing`
  - `rows=[]`

## Governed Write Snapshot

- `order.place`
  - `trace_id=3a4abce7-7132-4210-8fb5-4d382cd13fba`
  - `server_ts=2026-04-03T14:41:34+08:00`
  - command wall clock finished: `2026-04-03T14:42:13.5892748+08:00`
  - `ok=false`
  - `status=risk_rejected`
  - `code=connect_gate_failed`
  - `broker_order_id=""`
  - `intent_id=INT-CLI-20260403144134`
  - `governed_write_path=true`

`connect_gate`:

- `attempts=5`
- `ok_count=1`
- `success_rate=0.2`
- `threshold=0.9`
- `reason=connect_gate_failed`
- samples:
  - `2026-04-03T14:41:34+08:00 -> -1`
  - `2026-04-03T14:41:43+08:00 -> 0`
  - `2026-04-03T14:41:49+08:00 -> -1`
  - `2026-04-03T14:41:58+08:00 -> -1`
  - `2026-04-03T14:42:07+08:00 -> -1`

## Separately Observed Background Sequence

Post-command inspection of the authoritative call log showed a separate same-window background sequence that was not part of the commanded runtime JSON:

- `miniqmt.ensure_logged_in=deac02fa-1337-420a-b29b-f2d497445059`
- `session.warm=5e5563d8-9b0f-424b-8c89-b0b1c5d3ddee`
- `session.status=3d172113-4891-4003-a256-456678a031ff`
- `probe.connection=879dd4f1-8b7f-4598-b1b9-08d561ed794b`
- `orders.list=da917d63-8190-4f5f-8f92-e86e8f30c2c6`
- `order.place=0a3397e0-ca96-4ea6-8f74-7bf7a7770c04`
  - `server_ts=2026-04-03T14:43:27+08:00`
  - `broker_order_id=""`
  - `status=risk_rejected`
  - `code=connect_gate_failed`
  - `connect_gate success_rate=0.0`

## Environment Classification

- Classification: `fail_env`
- Blocking Layer: `broker/session connect gate`
- Design vs Environment: `environment blocker`

The commanded run itself was already conclusive enough to stop after one additional live order. The separately observed extra same-window background attempt only reinforced the same blocker and increased cumulative live-budget consumption.
