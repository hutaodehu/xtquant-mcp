# EnvSnapshot: VAL-003 2026-04-03 13:54-13:56 +08 Round3 Governed Write Retry

## 1. Metadata

- Task ID: `VAL-003`
- Role: `test`
- Snapshot Type: `EnvSnapshot`
- Snapshot Time Window: `2026-04-03 13:54:37 +08` to `2026-04-03 13:56:59 +08`
- Host Working Dir: `D:\xtquant-mcp\repo`
- Host Instance Root: `D:\xtquant-mcp\instance\prod`
- Related TaskCard: `../task_cards/VAL-003.md`
- Related ChangePack: [VAL-003.md](../change_packages/VAL-003.md)
- Related Controller Inputs: `.tmp/spec-task-harness/VAL-003-controller-judgment-20260403T134842+0800-post-review-retry.md`
- Related EvidencePack: `../evidence_packs/VAL-003-test-202604031402-round3-governed-write-retry.md`

## 2. Retry Scope

This EnvSnapshot records the second real live retry for `VAL-003` on `2026-04-03` under the governed write flow. The intended packet was unchanged from the earlier approved write lane:

- Side: `BUY`
- Symbol: `515880.SH`
- Qty: `100`
- Price Mode: `l1_protect`
- Cancel Timeout: `30s`

The retry remained bounded to one additional governed live attempt and did not widen scope beyond the already authorized packet.

## 3. Session Budget

- Authorized Attempts: `3`
- Attempts Already Consumed Before This Retry: `1`
- Attempts Actually Used In This Retry: `1`
- Cumulative Attempts Used After Retry: `2`

## 4. Wall Clock And Trace Map

### 4.1 Preflight

- Time: `2026-04-03 13:54:37 +08`
- Trace IDs:
  - `7fb86f79-b2b8-44ab-aedd-625032719994`
  - `f882e70a-e684-4ff4-8b2b-b4f5117059a3`
  - `8af762ba-0805-49f5-a010-24c0ae150a66`
  - `9c3e8844-42bf-4b94-b450-2895acfeb7eb`
  - `1e568bf7-cfae-4853-91ec-04d90b619065`

### 4.2 Governed Write

- Time: `2026-04-03 13:56:17 +08`
- Trace ID: `d03a7fd5-e314-47f7-a3da-fc46604fa8f3`

### 4.3 Connect Gate Completion

- Time: `2026-04-03 13:56:59 +08`

### 4.4 Post-Failure Runtime Truth

- Time: `2026-04-03 13:56:59 +08`
- Trace IDs:
  - `a0a38150-7dc1-4f35-b5b6-26dda9553d83`
  - `1a75dda2-c253-48ef-9ef0-09c15f5ba6a1`
  - `cc5ac0eb-90d6-4ab4-8fee-3e35c8074e0d`

## 5. Preflight Runtime Truth

The preflight state remained permissive at the top-level readiness envelope, while the write-permission probe still did not prove effective broker-side write authority:

- `overall_trade_ready=true`
- `write_permission_ready=true`
- `write_permission_probe.implies_write_permission=false`

Interpretation:

- The retry entered governed write with the same previously observed mismatch between high-level readiness and actual write-lane proof.
- This mismatch remained an environment-side warning before the live packet was sent.

## 6. Governed Write Attempt Snapshot

- `ok=false`
- `status=risk_rejected`
- `code=connect_gate_failed`
- `broker_order_id=""`
- `intent_id=INT-CLI-20260403135617`
- `duration_ms=42326`

Observed outcome:

- The governed write consumed one additional real live order attempt.
- The write did not produce a broker order id.
- The failure remained pinned to the connect gate rather than to packet construction, symbol routing, or price-mode contract shape.

## 7. Connect Gate Detail

Per-attempt connect samples for this retry remained uniformly degraded:

- Session ID: `2111`
- Attempt Count Sampled By Connect Gate: `5`
- Per-Attempt Results: `-1, -1, -1, -1, -1`

Interpretation:

- The governed write lane reached the broker connect gate repeatedly and failed on every sampled attempt.
- This is stronger evidence of environment-side broker/session unavailability than a single-shot packet failure.

## 8. Post-Failure Runtime Truth

After the failed governed write, the runtime truth remained degraded on the orders surface:

- `orders.list` mode: `public_fallback`
- `rows=[]`
- `fallback_reason=broker_missing`

Interpretation:

- No broker-backed order row became visible after the retry.
- The runtime stayed on degraded public fallback rather than recovering to broker-backed truth.

## 9. Artifact Snapshot

Authoritative call-level evidence for this retry is the trade gateway call log:

- `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260403\trade_gateway_calls.jsonl`

Supporting artifact expectations:

- The call envelope declared `trade_ops` CSV outputs in the governed write path.
- Following the existing artifact pattern for this failure mode, those `trade_ops` CSVs were not materialized as authoritative runtime evidence for this retry.
- Where the envelope declared but did not materialize CSV artifacts, the JSONL call log remains the authoritative source of truth.

## 10. Environment Classification

- Classification: `fail_env`
- Blocking Layer: `broker/session connect gate`
- Design vs Environment: `environment blocker`

Judgment note:

- This retry consumed one additional real live order attempt under the approved governed write budget.
- The blocker remained environment-side and is stronger than the earlier `2026-04-03 13:15 +08` run because this retry carried a fresh live governed write through to a repeated `connect=-1` gate failure with no broker order creation and no broker-backed order visibility afterward.
- No evidence in this snapshot justifies reclassifying the outcome as `fail_design`.

## 11. Constraints For Follow-On Work

- Do not treat `overall_trade_ready=true` or `write_permission_ready=true` as sufficient proof of live write viability while `write_permission_probe.implies_write_permission=false` persists.
- Do not claim broker-side order creation without a non-empty `broker_order_id` or broker-backed order-list evidence.
- Subsequent decisions should use the JSONL gateway call artifact and the linked EvidencePack as the audit base for any further retry judgment.
