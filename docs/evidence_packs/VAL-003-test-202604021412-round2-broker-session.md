# EvidencePack

Task ID: VAL-003
Role: test
Date: 2026-04-02T14:12:59.6999037+08:00
Acceptance Gate: G4
Conclusion: pass

## Env Snapshot

- Link: [VAL-003-202604021412-round2-broker-session.md](../env_snapshots/VAL-003-202604021412-round2-broker-session.md)

## Scope

1. Execute the formal Round 2 broker/session targeted recheck for the current 2026-04-02 Beijing-time live trading window.
2. Confirm whether the live-window `session_not_ready` blocker from Round 1 still reproduces after the required non-write broker/session chain.
3. Run the required direct native broker/session probe for candidate `session_id=100` then `session_id=101`, without entering any governed write path.

## Required Sources Re-Read First

1. [VAL-003.md](../task_cards/VAL-003.md)
2. [ACCEPTANCE_STANDARD.md](../ACCEPTANCE_STANDARD.md)
3. [OPERATIONS_RUNBOOK.md](../OPERATIONS_RUNBOOK.md)
4. [VAL-003_G4_EXECUTION_PLAN.md](../VAL-003_G4_EXECUTION_PLAN.md)
5. [VAL-003-test-202604021307-round1-preflight.md](./VAL-003-test-202604021307-round1-preflight.md)
6. [VAL-003-202604021307-round1-preflight.md](../env_snapshots/VAL-003-202604021307-round1-preflight.md)
7. [VAL-003-review-202604021313.md](../reviews/VAL-003-review-202604021313.md)
8. `.tmp/spec-task-harness/VAL-003-controller-judgment-20260402T132558+0800.md`
9. `.tmp/spec-task-harness/VAL-003-dispatch-20260402T132558+0800-round2.md`

## Commands

1. Gateway-side Round 2 non-write chain via `http://127.0.0.1:8765/mcp`:
   - `initialize`
   - `tools/call miniqmt.ensure_logged_in {"login_timeout_seconds": 20}`
   - `tools/call session.warm {}`
   - `tools/call session.status {}`
   - `tools/call probe.connection {}`
2. Current-day gateway call-log verification:
   - `Get-Item D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260402\trade_gateway_calls.jsonl | Select-Object FullName,Length,LastWriteTime`
   - `Get-Content D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260402\trade_gateway_calls.jsonl | Select-Object -Last 20`
3. Direct native broker/session probe, one lifecycle each:
   - `D:\xtquant-mcp\venv313\Scripts\python.exe -` with `XtQuantTrader(session_id=100)` -> `connect -> query_account_infos -> subscribe -> query_stock_asset -> query_stock_positions -> query_stock_orders`
   - `D:\xtquant-mcp\venv313\Scripts\python.exe -` with `XtQuantTrader(session_id=101)` -> `connect -> query_account_infos -> subscribe -> query_stock_asset -> query_stock_positions -> query_stock_orders`
4. Bounded host-side log extraction:
   - `Get-ChildItem D:\lh\国金证券QMT交易端\userdata_mini -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 40 FullName,LastWriteTime,Length`
   - `Select-String -Path D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260402.log -Pattern '13:26|14:11|14:12|1111|100|101|disconnect|heartbeat|lock' | Select-Object -Last 40`
   - `Select-String -Path D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQuote_20260402.log -Pattern '13:26|14:11|14:12|1111|100|101|disconnect|heartbeat|lock' | Select-Object -Last 40`

## Raw Results

- Formal posture before runtime checks:
  - [VAL-003 task card](../task_cards/VAL-003.md) still records `Status: Blocked` and `Blocking Reason: broker_blocked`.
  - The active controller judgment for this round explicitly authorizes Round 2 only and does not authorize Round 3 or any write-path action yet.

- Gateway-side Round 2 non-write chain:
  - `miniqmt.ensure_logged_in`
    - trace `c3106f76-1a88-49bf-ae91-32d414843251`
    - server time `2026-04-02T13:26:43`
    - `ok=true`, `status=already_logged_in`, `port_ready=true`
  - `session.warm`
    - trace `aad1e634-887f-4393-9d08-547ceb84d272`
    - server time `2026-04-02T13:26:43`
    - `ok=true`
    - `ready=true`
    - `session_id=1111`
    - `owner_generation=1`
    - `owner_started_reason=initial_warm`
    - warm-health trace reached:
      - `account.show ok=true`
      - `positions.list ok=true`
      - `orders.list ok=true`, `read_scope=warm_health_only`, `count=2`, `source=xttrader_shadow`
  - `session.status`
    - trace `a1c5ba00-1a4f-497e-8800-764c5cd7b8bd`
    - server time `2026-04-02T13:26:50`
    - `ready=true`
    - `session_id=1111`
    - `owner_generation=1`
  - `probe.connection`
    - trace `75cf6a40-1a5c-4bed-a7c6-33f8cc11287d`
    - server time `2026-04-02T13:26:50`
    - `ok=true`
    - `reason=ok`
    - `overall_trade_ready=true`
    - `probe_mode=owner_managed_session_reuse`
    - `read_only_ready=true`
    - `write_permission_ready=true`
    - `session_reused=true`
    - reused shadow `session_id=1111`

- Direct native probe A, `session_id=100`:
  - observed at `2026-04-02T14:11:52.292009+08:00`
  - `XtQuantTrader.start()`: `ok`
  - `XtQuantTrader.connect()`: `0`
  - `query_account_infos`: `ok`, count `1`
  - selected account: `8883884325`
  - `subscribe`: `ok`, code `0`
  - `query_stock_asset`: `ok`
  - `query_stock_positions`: `ok`
  - `query_stock_orders`: `ok`
  - no `connect=-1`

- Direct native probe B, `session_id=101`:
  - observed at `2026-04-02T14:12:36.114804+08:00`
  - `XtQuantTrader.start()`: `ok`
  - `XtQuantTrader.connect()`: `0`
  - `query_account_infos`: `ok`, count `1`
  - selected account: `8883884325`
  - `subscribe`: `ok`, code `0`
  - `query_stock_asset`: `ok`
  - `query_stock_positions`: `ok`
  - `query_stock_orders`: `ok`
  - no `connect=-1`

- Host-side QMT log facts:
  - `XtMiniQmt_20260402.log` recorded for `session_id=100`:
    - `14:11:52` `quant session 100 connected`
    - `14:11:53` account infos / subscribe / asset / positions / orders all completed
    - `14:11:58` heartbeat timeout and disconnect after the bounded lifecycle
  - `XtMiniQmt_20260402.log` recorded for `session_id=101`:
    - `14:12:36` `quant session 101 connected`
    - `14:12:36-14:12:37` account infos / subscribe / asset / positions / orders all completed
    - `14:12:41` heartbeat timeout and disconnect after the bounded lifecycle
  - `XtMiniQuote_20260402.log` remained live during the same `14:12` window and continued logging market-status / whole-quote activity.

- Host-side file facts:
  - `D:\lh\国金证券QMT交易端\userdata_mini\down_queue_win_100` updated at `2026-04-02 14:11:52`
  - `D:\lh\国金证券QMT交易端\userdata_mini\down_queue_win_101` updated at `2026-04-02 14:12:36`
  - gateway-side owner-managed session file state still included `lock_down_queue_win_1111` and `down_queue_win_1111` updated at `2026-04-02 13:26:50`

## Hard-Stop Assessment

1. Native probe still reproduces `xttrader connect=-1`: does not apply in this run.
   - Both direct native candidates `100` and `101` returned `connect()==0`.

2. Broker/session shape still cannot be uniquely explained: does not apply in this run.
   - Gateway-side chain and direct native probes both converge on the same explanation: broker/session readiness is currently available, not blocked at connect level.

3. Write-permission still only remains at precheck layer with no higher-gate closure: does not block Round 2.
   - `probe.connection` reports `write_permission_ready=true` and `overall_trade_ready=true`.
   - This still does not authorize governed write by itself; it closes the Round 2 readiness check only.

4. Host-log and runtime probe contradict each other: does not apply in this run.
   - QMT logs for `100` and `101` align with the bounded native query chain and only show heartbeat timeout after the intentionally short lifecycle ended.

## Separation Of Notes

- Environment-side findings:
  - current host/login/session state is sufficient for `session.warm` and `probe.connection` to succeed
  - direct native broker/session probes for `100` and `101` both complete the bounded read-only chain

- Governance and control-plane findings:
  - `VAL-003` still remains formally `Blocked / broker_blocked` until controller issues a separate Round 3 judgment
  - this packet stays within Round 2 only and does not execute `order.place`

- Design and contract findings:
  - the previously observed endpoint-contract drift remains resolved
  - the earlier live-window `session_not_ready` blocker no longer reproduces after the required Round 2 chain

## Execution Boundary

- `order.place` was not executed.
- `order.status` was not executed in governed-write scope.
- `orders.list` write-followup for the governed packet was not executed.
- `order.cancel` was not executed.
- `fills.list` was not executed.

## Verdict

`pass`. This Round 2 packet closes the broker/session targeted recheck. The gateway-side non-write chain now succeeds end-to-end in a live trading window: `miniqmt.ensure_logged_in.ok=true`, `session.warm.ok=true`, `session.status.ready=true`, and `probe.connection.ok=true` with `overall_trade_ready=true`. The required direct native broker/session probe also no longer reproduces `xttrader connect=-1`; both `session_id=100` and `session_id=101` complete `connect -> query_account_infos -> subscribe -> query_stock_asset -> query_stock_positions -> query_stock_orders` in one bounded lifecycle. Under the Round 2 pass conditions, the correct result for this rerun is therefore `pass`, and control should return to the controller for a separate Round 3 governed-write judgment.
