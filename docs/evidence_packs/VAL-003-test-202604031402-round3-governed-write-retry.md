# EvidencePack: VAL-003 Round 3 Governed Write Retry

## 1. Metadata

- Task ID: `VAL-003`
- Role: `test`
- Acceptance Gate: `G4`
- Conclusion: `fail_env`
- Run Type: `second real live retry today`
- Retry Context: `post-review retry under the same fixed packet`
- Fixed Packet: `BUY 515880.SH qty=100 price_mode=l1_protect cancel_timeout=30s`
- Test Date: `2026-04-03`
- Timezone: `Asia/Shanghai (UTC+08:00)`

## 2. Test Scope

This EvidencePack records the second real live retry of `VAL-003` on `2026-04-03` under the unchanged governed write packet:

- Symbol: `515880.SH`
- Side: `BUY`
- Quantity: `100`
- Price Mode: `l1_protect`
- Cancel Timeout: `30s`
- Governed Write Path: `true`

The purpose of this retry was to verify whether the previously identified write-lane environment blocker had cleared after review, not to change packet shape, loosen gates, or reinterpret acceptance authority.

## 3. Attempt Budget and Consumption

- Real-order budget authorized today: `3`
- Attempts already used before this run: `1`
- Attempts actually used in this run: `1`
- Cumulative real-order attempts today after this run: `2`
- Remaining real-order budget after this run: `1`

## 4. Preflight Chain

Preflight chain executed at `2026-04-03 13:54:37 +08:00`:

- `miniqmt.ensure_logged_in`
  - trace_id: `7fb86f79-b2b8-44ab-aedd-625032719994`
- `session.warm`
  - trace_id: `f882e70a-e684-4ff4-8b2b-b4f5117059a3`
- `session.status`
  - trace_id: `8af762ba-0805-49f5-a010-24c0ae150a66`
- `probe.connection`
  - trace_id: `9c3e8844-42bf-4b94-b450-2895acfeb7eb`
- `orders.list`
  - trace_id: `1e568bf7-cfae-4853-91ec-04d90b619065`

Observed preflight status remained internally inconsistent in the same direction as prior environment-side failures:

- `overall_trade_ready=true`
- `write_permission_ready=true`
- `write_permission_probe.implies_write_permission=false`

Test judgment at preflight stage: the runtime continued to expose a degraded write-readiness signal even though top-level readiness booleans remained optimistic.

## 5. Governed Write Execution

Real `order.place` was executed at `2026-04-03T13:56:17+08:00` with the following authoritative result:

- trace_id: `d03a7fd5-e314-47f7-a3da-fc46604fa8f3`
- intent_id: `INT-CLI-20260403135617`
- governed_write_path: `true`
- duration_ms: `42326`
- ok: `false`
- status: `risk_rejected`
- code: `connect_gate_failed`
- broker_order_id: `""`

Test interpretation: the governed write path executed as designed, but the environment-side connect gate rejected the live order before any broker order identifier was produced.

## 6. Connect Gate Evidence

Authoritative `connect_gate` runtime truth for `session_id=2111`:

- attempts: `5`
- ok_count: `0`
- success_rate: `0.0`
- threshold: `0.9`
- reason: `connect_gate_failed`

Five sampled connect attempts all returned `-1` at:

- `2026-04-03 13:56:17 +08:00`
- `2026-04-03 13:56:26 +08:00`
- `2026-04-03 13:56:35 +08:00`
- `2026-04-03 13:56:44 +08:00`
- `2026-04-03 13:56:53 +08:00`

Test judgment: this retry does not indicate an order-packet defect or governed-write policy defect. It reinforces the existing environment blocker because the write lane failed the repeated broker connection gate with a `0/5` success profile.

## 7. Post-Failure Runtime Truth

Post-failure verification executed at `2026-04-03 13:56:59 +08:00`:

- `session.status`
  - trace_id: `a0a38150-7dc1-4f35-b5b6-26dda9553d83`
- `probe.connection`
  - trace_id: `1a75dda2-c253-48ef-9ef0-09c15f5ba6a1`
- `orders.list`
  - trace_id: `cc5ac0eb-90d6-4ab4-8fee-3e35c8074e0d`
  - degraded: `true`
  - fallback_used: `true`
  - fallback_reason: `broker_missing`
  - rows: `[]`

Post-failure interpretation: after the retry, runtime truth still showed degraded broker visibility and no broker-side order rows, consistent with an environment-side connectivity/session blocker rather than a successful live write.

## 8. Evidence Source

Authoritative source for this EvidencePack:

- [instance/prod/artifacts/trade_gateway/20260403/trade_gateway_calls.jsonl](../../instance/prod/artifacts/trade_gateway/20260403/trade_gateway_calls.jsonl)

This file is the controlling evidence source for the timestamps, trace IDs, gate results, and governed write outcome recorded above.

## 9. Result Classification

- Final Conclusion: `fail_env`
- Failure Layer: `environment`
- Acceptance Position: `G4 not passed`

Reasoning:

1. Preflight continued to expose `write_permission_probe.implies_write_permission=false` despite optimistic top-level readiness flags.
2. The governed live write failed with `status=risk_rejected` and `code=connect_gate_failed`.
3. The connect gate recorded `5` attempts, `0` successes, and `success_rate=0.0`, far below the `0.9` threshold.
4. Post-failure runtime truth remained degraded, used broker-missing fallback, and returned no broker order rows.

## 10. Test Conclusion

This second real live retry strengthens the conclusion that `VAL-003` remains blocked by an environment-side write-lane failure. The retry does not provide evidence that the broker connection gate has recovered, and it does not justify spending the last remaining real-order attempt for today.

Recommended test-side disposition:

- Keep current result at `fail_env`
- Preserve `G4` as not passed
- Require environment recovery evidence before any further real-order retry
