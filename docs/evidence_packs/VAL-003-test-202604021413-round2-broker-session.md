# EvidencePack

Task ID: VAL-003
Role: test
Date: 2026-04-02T14:13:59.9154226+08:00
Acceptance Gate: G4
Conclusion: pass

## Env Snapshot

- Link: [VAL-003-202604021413-round2-broker-session.md](../env_snapshots/VAL-003-202604021413-round2-broker-session.md)

## Scope

1. Execute Round 2 broker/session targeted recheck for the current 2026-04-02 Beijing-time live trading window only.
2. Confirm whether the `session_not_ready` blocker from the live-window Round 1 packet still reproduces after the formal non-write chain and direct native broker/session probe.
3. Decide whether the repo now has sufficient broker/session evidence to justify a Round 3 governed-write judgment.

## Go/No-Go Packet

- side: `BUY`
- symbol: `515880.SH`
- qty: `100`
- price_mode: `l1_protect`
- execution result in this run: `ROUND 2 PASS / NO WRITE EXECUTED`
- `order.place` executed: `no`

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

1. Gateway-side non-write chain observed from same-day trade gateway call log:
   - `tools/call miniqmt.ensure_logged_in {"login_timeout_seconds": 20}`
   - `tools/call session.warm {}`
   - `tools/call session.status {}`
   - `tools/call probe.connection {}`
2. Resource re-read after owner-managed session was established:
   - `initialize`
   - `resources/read trade://session/current`
   - `resources/read diag://probe/latest`
   - `resources/read diag://login/latest`
3. Direct native broker/session probe:
   - `D:\xtquant-mcp\venv313\Scripts\python.exe D:\xtquant-mcp\repo\.tmp\round2_native_probe_20260402.py`
4. Bounded host-log extraction:
   - `Select-String -Path D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260402.log -Pattern '1111| 100 | 101 |onConnected|onDisconnected|heartbeat|lock_down_queue' | Select-Object -Last 80`
   - `Get-ChildItem D:\lh\国金证券QMT交易端\userdata_mini -Filter 'lock_down_queue_win_*' | Select-Object Name,LastWriteTime,Length`
   - `Get-ChildItem D:\lh\国金证券QMT交易端\userdata_mini -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 40 FullName,LastWriteTime,Length`
5. Wall clock:
   - `Get-Date -Format o`

## Raw Results

- Formal posture before runtime checks:
  - [VAL-003 task card](../task_cards/VAL-003.md) still records `Status: Blocked`, `Blocking Reason: broker_blocked`, `Risk Class: high`, and `Automation Policy: manual_gate`.
  - The controller judgment for `2026-04-02T13:25:58+08:00` authorized only Round 2 broker/session targeted recheck and did not authorize Round 3 or any write-path action.

- Live-window facts:
  - current wall clock after this Round 2 packet capture: `2026-04-02T14:13:59.9154226+08:00`
  - all observed runtime actions in this packet remained inside the 2026-04-02 afternoon Beijing trading session

- Gateway-side non-write chain facts from `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260402\trade_gateway_calls.jsonl`:
  - `miniqmt.ensure_logged_in`
    - `trace_id=c3106f76-1a88-49bf-ae91-32d414843251`
    - `server_ts=2026-04-02T13:26:43`
    - `ok=true`
    - `status=already_logged_in`
    - `port_ready=true`
  - `session.warm`
    - `trace_id=aad1e634-887f-4393-9d08-547ceb84d272`
    - `server_ts=2026-04-02T13:26:43`
    - `ok=true`
    - `account_id=8883884325`
    - `session_id=1111`
    - `ready=true`
    - `owner_generation=1`
    - `owner_started_reason=initial_warm`
    - warm health steps all `ok=true`:
      - `account.show`
      - `positions.list`
      - `orders.list` with `read_scope=warm_health_only`, `count=2`
  - `session.status`
    - `trace_id=a1c5ba00-1a4f-497e-8800-764c5cd7b8bd`
    - `server_ts=2026-04-02T13:26:50`
    - `ready=true`
    - `session_id=1111`
    - `last_error=""`
  - `probe.connection`
    - `trace_id=75cf6a40-1a5c-4bed-a7c6-33f8cc11287d`
    - `server_ts=2026-04-02T13:26:50`
    - `ok=true`
    - `reason=ok`
    - `session_id=1111`
    - `probe_mode=owner_managed_session_reuse`
    - `read_only_ready=true`
    - `write_permission_ready=true`
    - `write_permission_blocked=false`
    - `overall_trade_ready=true`
    - `up_queue_xtquant_exists=true`

- Resource re-read after the Round 2 chain:
  - `trade://session/current`
    - `ready=true`
    - `account_id=8883884325`
    - `session_id=1111`
    - `warmed_at=2026-04-02T13:26:50`
    - `last_check_at=2026-04-02T14:13:59`
  - `diag://probe/latest`
    - `ok=true`
    - `reason=ok`
    - `session_id=1111`
    - `read_only_ready=true`
    - `write_permission_ready=true`
    - `overall_trade_ready=true`
  - `diag://login/latest`
    - `ok=true`
    - `status=already_logged_in`
    - `port_ready=true`

- Direct native broker/session probe from `D:\xtquant-mcp\repo\.tmp\round2_native_probe_20260402.py`:
  - `session_id=100`
    - `connect_code=0`
    - furthest step: `query_stock_orders`
    - `query_account_infos` returned one account: `8883884325`
    - `subscribe_code=0`
    - `query_stock_asset` succeeded
    - `query_stock_positions` count `1`
    - `query_stock_orders` count `2`
    - result: `query_chain_ok`
  - `session_id=101`
    - `connect_code=0`
    - furthest step: `query_stock_orders`
    - `query_account_infos` returned one account: `8883884325`
    - `subscribe_code=0`
    - `query_stock_asset` succeeded
    - `query_stock_positions` count `1`
    - `query_stock_orders` count `2`
    - result: `query_chain_ok`
  - `any_connect_minus_1=false`

- Bounded host-log extraction:
  - active owner-managed session trace in `XtMiniQmt_20260402.log`:
    - `2026-04-02 13:26:44-13:26:50` shows quant session `1111` connected and read-only queries for asset / positions / orders
  - direct native probe traces in `XtMiniQmt_20260402.log`:
    - `2026-04-02 14:13:31` quant session `100` connected
    - `2026-04-02 14:13:36` quant session `100` heartbeat timeout, disconnected, `lock_down_queue_win_100 file lock not held, offline`
    - `2026-04-02 14:13:32` quant session `101` connected
    - `2026-04-02 14:13:37` quant session `101` heartbeat timeout, disconnected, `lock_down_queue_win_101 file lock not held, offline`
  - supporting file facts from `userdata_mini`:
    - `down_queue_win_100` last write `2026/4/2 14:13:31`
    - `down_queue_win_101` last write `2026/4/2 14:13:32`
    - persistent owner lock remains `lock_down_queue_win_1111` last write `2026/4/2 13:26:50`

## Hard-Stop Assessment

1. `xttrader connect=-1`: does not apply in this run.
   - both native candidates `100` and `101` returned `connect_code=0`
   - the gateway-side owner-managed session also established successfully as `session_id=1111`

2. broker/session shape cannot be uniquely explained: does not apply in this run.
   - gateway-side owner session, resource state, and native probes all point to the same broker/session picture: login ready, owner-managed session established, read-only query chain available

3. write-permission still only at precheck layer: does not apply as a Round 2 stop.
   - `diag://probe/latest` now shows `write_permission_ready=true`
   - `probe_scope_note` still correctly warns that this is not itself governed-write authorization

4. host-log and runtime probe contradiction: does not apply in this run.
   - QMT host log confirms `1111` owner session query activity for the gateway-side chain
   - QMT host log also confirms bounded native `100/101` connect lifecycles instead of `connect=-1`

## Separation Of Notes

- Environment-side findings:
  - host login is ready
  - owner-managed session warm succeeded
  - direct native broker/session probe no longer reproduces `connect=-1`
- Governance and control-plane findings:
  - task remains formally `Blocked / broker_blocked` until controller issues a new Round 3 judgment
  - this packet itself remains strictly non-write
- Design and contract findings:
  - prior endpoint-contract drift remains resolved
  - current runtime state now meets the intended Round 2 broker/session closure shape

## Execution Boundary

- `order.place` was not executed.
- `order.status` in governed-write scope was not executed.
- `orders.list` as write-followup for the governed packet was not executed.
- `order.cancel` was not executed.
- `fills.list` in governed-write scope was not executed.

## Verdict

`pass`. This Round 2 packet closes the broker/session targeted recheck for the current live Beijing trading window. The earlier live-window Round 1 blocker `probe.connection -> session_not_ready` no longer reproduces after the formal non-write chain: `session.warm` now succeeds, `session.status.ready=true`, `trade://session/current.ready=true`, and `diag://probe/latest.ok=true` with `overall_trade_ready=true`. The higher-gate direct native broker/session probe also no longer reproduces `xttrader connect=-1`: both `session_id=100` and `session_id=101` complete `connect -> query_account_infos -> subscribe -> query_stock_asset -> query_stock_positions -> query_stock_orders` in one bounded lifecycle. Under the repo's execution plan, this is sufficient for a fresh controller judgment on Round 3 governed write.
