# EnvSnapshot

Task ID: VAL-003
Date: 2026-04-02T14:12:59.6999037+08:00
Role: test

## Host

- Working Directory: `D:\xtquant-mcp\repo`
- EvidencePack: [VAL-003-test-202604021412-round2-broker-session.md](../evidence_packs/VAL-003-test-202604021412-round2-broker-session.md)
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
  - `order.place` not executed
  - `order.status` not executed in governed-write scope
  - `orders.list` write-followup chain for this packet not executed
  - `order.cancel` not executed
  - `fills.list` not executed

## Wall Clock

- Gateway-side Round 2 chain:
  - `miniqmt.ensure_logged_in` / `session.warm` start: `2026-04-02T13:26:43+08:00`
  - `session.status` / `probe.connection` finish: `2026-04-02T13:26:50+08:00`
- Direct native probe A, `session_id=100`:
  - `2026-04-02T14:11:52.292009+08:00` to `2026-04-02T14:11:53.938505+08:00`
- Direct native probe B, `session_id=101`:
  - `2026-04-02T14:12:36.114804+08:00` to `2026-04-02T14:12:37.759360+08:00`
- Trading-window assessment:
  - all observed runtime steps remained inside the `2026-04-02` afternoon live Beijing trading window

## Gateway-side Session State

- `miniqmt.ensure_logged_in`
  - trace `c3106f76-1a88-49bf-ae91-32d414843251`
  - `ok=true`
  - `status=already_logged_in`
  - `port_ready=true`
- `session.warm`
  - trace `aad1e634-887f-4393-9d08-547ceb84d272`
  - `ready=true`
  - `session_id=1111`
  - `owner_generation=1`
  - `owner_started_reason=initial_warm`
- `session.status`
  - trace `a1c5ba00-1a4f-497e-8800-764c5cd7b8bd`
  - `ready=true`
  - `session_id=1111`
- `probe.connection`
  - trace `75cf6a40-1a5c-4bed-a7c6-33f8cc11287d`
  - `ok=true`
  - `overall_trade_ready=true`
  - `probe_mode=owner_managed_session_reuse`
  - reused shadow `session_id=1111`
  - `read_only_ready=true`
  - `write_permission_ready=true`

## Direct Native Probe Snapshot

- Candidate `session_id=100`
  - `connect()==0`
  - `query_account_infos ok`
  - `subscribe ok`
  - `query_stock_asset ok`
  - `query_stock_positions ok`
  - `query_stock_orders ok`
- Candidate `session_id=101`
  - `connect()==0`
  - `query_account_infos ok`
  - `subscribe ok`
  - `query_stock_asset ok`
  - `query_stock_positions ok`
  - `query_stock_orders ok`

## Host-side File And Log Facts

- `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260402\trade_gateway_calls.jsonl`
  - exists
  - latest relevant traces:
    - `c3106f76-1a88-49bf-ae91-32d414843251`
    - `aad1e634-887f-4393-9d08-547ceb84d272`
    - `a1c5ba00-1a4f-497e-8800-764c5cd7b8bd`
    - `75cf6a40-1a5c-4bed-a7c6-33f8cc11287d`
- `D:\lh\国金证券QMT交易端\userdata_mini\down_queue_win_100`
  - updated at `2026-04-02 14:11:52`
- `D:\lh\国金证券QMT交易端\userdata_mini\down_queue_win_101`
  - updated at `2026-04-02 14:12:36`
- `D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260402.log`
  - session `100` connected, queried, then heartbeat timeout/disconnect after the bounded lifecycle
  - session `101` connected, queried, then heartbeat timeout/disconnect after the bounded lifecycle
- `D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQuote_20260402.log`
  - continued logging market-status / whole-quote activity during the same `14:12` window

## Classification Notes

- Environment:
  - the earlier live-window `session_not_ready` blocker no longer reproduces in this Round 2 packet
  - direct native broker/session probes for both `100` and `101` do not reproduce `connect=-1`
- Governance/control-plane:
  - Round 2 is closed, but Round 3 still requires a new explicit controller judgment
- Design/contract:
  - endpoint contract remains healthy and broker/session higher-gate blocker is no longer a connect-level failure

## Snapshot Summary

This Round 2 snapshot closes the broker/session targeted recheck for `VAL-003`. In the live `2026-04-02` afternoon window, the gateway-side non-write chain now succeeds through `session.warm`, `session.status`, and `probe.connection`, and the direct native broker/session probes for both `session_id=100` and `session_id=101` complete the bounded read-only query chain without reproducing `connect=-1`. The packet remains non-write only, but it is sufficient to support a fresh controller judgment on whether to enter Round 3 governed write.
