# ReviewPack

Task ID: TG-004
Role: review
Date: 2026-03-30T12:33:22.2413773+08:00
Change Package Link: [TG-004.md](../change_packages/TG-004.md)
Evidence Pack Link: [TG-004-test-20260330-followup-2-warm-health.md](../evidence_packs/TG-004-test-20260330-followup-2-warm-health.md)
Prior Review Link: [TG-004-review-20260330-followup.md](./TG-004-review-20260330-followup.md)
Broader Posture Link: [VAL-002-review-20260330-native-query-chain.md](./VAL-002-review-20260330-native-query-chain.md)
Scope: bounded `Follow-up Patch 2 (2026-03-30)` warm-health read patch only

## Findings

1. No code, design, or test finding was identified inside this bounded warm-health patch scope.
   - `xtqmt_mcp/trade_gateway/session_manager.py:39-45` routes the session health-check `orders.list` step through `getattr(context.service, "warm_health_orders_list", None) or context.service.orders_list`, so the warm/status health path prefers the dedicated warm-only reader when present.
   - `xtqmt_mcp/trade_ops.py:483-522` implements `warm_health_orders_list()` on `self.shadow.get_orders()` and marks the payload with `source="xttrader_shadow"` plus `read_scope="warm_health_only"`.
   - `xtqmt_mcp/trade_ops.py:671-697` keeps public `orders.list()` on `self.broker.query_open_orders(self.cfg.account_id)`, so the bounded patch does not rewrite the public broker-backed contract.
   - `tests/test_trade_gateway_session_manager.py:104-128` and `tests/test_trade_ops_warm_health.py:87-118` cover the intended split, and the independent test artifact records focused unittest `OK`, compile success, and no bounded-scope `fail_env` / `fail_design` in `docs/evidence_packs/TG-004-test-20260330-followup-2-warm-health.md:20-24`, `docs/evidence_packs/TG-004-test-20260330-followup-2-warm-health.md:39-55`, and `docs/evidence_packs/TG-004-test-20260330-followup-2-warm-health.md:66-75`.

## Severity

- highest: none in this bounded patch scope

## Impact

Within the bounded patch, the reviewed implementation is internally consistent with the stated goal: `session.warm` / `session.status` health checks can read order visibility from the shadow path without silently changing the public `orders.list` contract.

This does not change the overall release posture of `TG-004`. The current bounded evidence is local-only and explicitly does not claim live `G3` recovery or `VAL-002` recovery. As the broader posture review states in `docs/reviews/VAL-002-review-20260330-native-query-chain.md:14-18` and `docs/reviews/VAL-002-review-20260330-native-query-chain.md:57-68`, live `G3` remains formally `blocked`; that broader blocker is still outside the acceptance boundary closed by this patch.

Design and environment remain separated here:

1. Bounded patch scope: no new `fail_design` finding identified.
2. Bounded local independent test: no `fail_env` observed in the provided evidence pack.
3. Overall TG-004 release posture: still `blocked` because live `G3` / `VAL-002` is not cleared by this bounded local patch.

## Required Fix

1. None within this bounded warm-health patch.
2. Outside this patch, the existing release blocker remains: test must still rerun live `G3` / `VAL-002` and produce new gateway-side evidence before `TG-004` can move out of `blocked`.
3. Do not use this bounded patch to claim `G3 pass`, `VAL-002` recovery, or live broker-backed `orders.list` validation beyond the local evidence boundary.

## Release Decision

- Decision: `blocked`
- Bounded Patch Review Status: `review-clean`
- Bounded Patch `fail_design`: `none identified`
- Bounded Patch `fail_env`: `none observed in provided local independent test`
- Explicit Statement: This bounded warm-health patch is review-clean within its local evidence boundary, but it does not clear the overall `TG-004` task for release. `TG-004` remains formally `blocked` because live `G3` is still not closed, and `VAL-002` remains blocked in the broader posture review.
- Release Recommendation: do not treat this patch alone as sufficient to clear live `G3` or `VAL-002`

## State Suggestion

- Target Status: `Blocked`
- Reason: keep the task in blocked release posture for live acceptance. The bounded follow-up patch can stay review-clean without being promoted to overall task pass, because the remaining blocker is broader live validation rather than a newly found defect in this patch.

## Residual Risks

1. Coverage remains focused and local. This patch does not prove that live owner-managed `session.warm -> session.status -> probe.connection -> account.show -> positions.list -> orders.list -> snapshot.l1` now succeeds end-to-end.
2. The bounded patch intentionally leaves public `orders.list` broker-backed, so live broker query health is still an open acceptance question rather than something this review can clear.
