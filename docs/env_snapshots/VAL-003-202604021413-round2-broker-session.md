# EnvSnapshot

Task ID: VAL-003
Date: 2026-04-02T14:13:59.9154226+08:00
Role: test

## Host

- Working Directory: `D:\xtquant-mcp\repo`
- EvidencePack: [VAL-003-test-202604021413-round2-broker-session.md](../evidence_packs/VAL-003-test-202604021413-round2-broker-session.md)
- TaskCard: [VAL-003.md](../task_cards/VAL-003.md)
- ChangePack: [VAL-003.md](../change_packages/VAL-003.md)
- Controller Judgment Input:
  - `.tmp/spec-task-harness/VAL-003-controller-judgment-20260402T132558+0800.md`
  - `.tmp/spec-task-harness/VAL-003-dispatch-20260402T132558+0800-round2.md`

## Runtime Scope

- Intended governed-write packet:
  - side: `BUY`
  - symbol: `515880.SH`
  - qty: `100`
  - price_mode: `l1_protect`
  - cancel_timeout: `30s`
- Execution posture in this snapshot:
  - Round 2 only
  - non-write broker/session targeted recheck
  - `order.place` not executed
  - `order.status` governed-write chain not executed
  - `orders.list` governed-write followup chain not executed
  - `order.cancel` not executed
  - `fills.list` governed-write chain not executed

## Wall Clock

- Resource re-read snapshot: `2026-04-02T14:13:59.9154226+08:00`
- Gateway-side Round 2 chain server timestamps:
  - `miniqmt.ensure_logged_in`: `2026-04-02T13:26:43`
  - `session.warm`: `2026-04-02T13:26:43`
  - `session.status`: `2026-04-02T13:26:50`
  - `probe.connection`: `2026-04-02T13:26:50`
- Native direct broker/session probe timestamps:
  - `session_id=100`: `2026-04-02T14:13:31-14:13:32 +08`
  - `session_id=101`: `2026-04-02T14:13:32-14:13:33 +08`
- Trading-window assessment:
  - `market_window_closed=false` for the observed Round 2 runtime window

## Gateway-Side Session State

- `session.warm`:
  - `trace_id=aad1e634-887f-4393-9d08-547ceb84d272`
  - `ready=true`
  - `account_id=8883884325`
  - `session_id=1111`
  - `owner_generation=1`
  - `owner_started_reason=initial_warm`
- `session.status`:
  - `trace_id=a1c5ba00-1a4f-497e-8800-764c5cd7b8bd`
  - `ready=true`
  - `session_id=1111`
  - `last_error=""`
- `probe.connection`:
  - `trace_id=75cf6a40-1a5c-4bed-a7c6-33f8cc11287d`
  - `ok=true`
  - `reason=ok`
  - `session_id=1111`
  - `probe_mode=owner_managed_session_reuse`
  - `read_only_ready=true`
  - `write_permission_ready=true`
  - `overall_trade_ready=true`

## Resource Snapshot

- `trade://session/current`:
  - `ready=true`
  - `account_id=8883884325`
  - `session_id=1111`
  - `warmed_at=2026-04-02T13:26:50`
  - `last_check_at=2026-04-02T14:13:59`
- `diag://probe/latest`:
  - `ok=true`
  - `reason=ok`
  - `session_id=1111`
  - `read_only_ready=true`
  - `write_permission_ready=true`
  - `overall_trade_ready=true`
- `diag://login/latest`:
  - `ok=true`
  - `status=already_logged_in`
  - `port_ready=true`

## Native Probe Snapshot

- `session_id=100`:
  - `connect_code=0`
  - `query_account_infos` returned one account
  - `subscribe_code=0`
  - `query_stock_asset` succeeded
  - `query_stock_positions` count `1`
  - `query_stock_orders` count `2`
  - result: `query_chain_ok`
- `session_id=101`:
  - `connect_code=0`
  - `query_account_infos` returned one account
  - `subscribe_code=0`
  - `query_stock_asset` succeeded
  - `query_stock_positions` count `1`
  - `query_stock_orders` count `2`
  - result: `query_chain_ok`
- `any_connect_minus_1=false`

## Host-Log Snapshot

- `XtMiniQmt_20260402.log` around the gateway-side owner session:
  - `13:26:44` quant session `1111` connected
  - `13:26:50` asset / positions / orders queries observed for `1111`
- `XtMiniQmt_20260402.log` around the direct native probes:
  - `14:13:31` quant session `100` connected
  - `14:13:36` `ssid:100` heartbeat timeout, disconnected, `lock_down_queue_win_100 file lock not held, offline`
  - `14:13:32` quant session `101` connected
  - `14:13:37` `ssid:101` heartbeat timeout, disconnected, `lock_down_queue_win_101 file lock not held, offline`
- Supporting filesystem facts:
  - `down_queue_win_100` last write `2026/4/2 14:13:31`
  - `down_queue_win_101` last write `2026/4/2 14:13:32`
  - persistent owner lock `lock_down_queue_win_1111` last write `2026/4/2 13:26:50`

## Classification Notes

- Environment:
  - current host/login/session state is sufficiently ready for Round 2 broker/session closure
  - no fresh `xttrader connect=-1` reproduction in this packet
- Governance/control-plane:
  - task remains under manual gate until a new Round 3 controller judgment
- Design/contract:
  - endpoint-contract drift remains resolved
  - live runtime readiness now matches the intended Round 2 closure shape

## Snapshot Summary

This Round 2 snapshot captures the first current-day broker/session closure for `VAL-003` under a live Beijing trading window. The owner-managed gateway session is now established and healthy as `session_id=1111`, `trade://session/current.ready=true`, and `diag://probe/latest.ok=true`. The higher-gate native broker/session probe also succeeds on both bounded candidates `100` and `101` without reproducing `xttrader connect=-1`. This snapshot does not execute any governed write, but it is sufficient to support a fresh controller judgment on whether Round 3 may begin.
