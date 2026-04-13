# ReviewPack

Task ID: VAL-002
Role: review
Date: 2026-03-30T12:00:00+08:00
Evidence Pack Link: [VAL-002-test-20260330-broker-session-native-probe.md](../evidence_packs/VAL-002-test-20260330-broker-session-native-probe.md)
Env Snapshot Link: [VAL-002-test-20260330-broker-session-native-probe.md](../env_snapshots/VAL-002-test-20260330-broker-session-native-probe.md)
Prior Review Link: [VAL-002-review-20260330-full-postpatch-rerun.md](./VAL-002-review-20260330-full-postpatch-rerun.md)

## Findings

1. High: native broker/session probe does not change the `blocked` status of `VAL-002`; the `G3` hard stop still reproduces at native `xttrader.connect()` level outside the gateway.
   - The new probe kept the official-pattern envelope described in the test context: one `XtQuantTrader` instance, one `session_id` per lifecycle, direct `userdata_mini`, and read-only query steps only after successful connect.
   - Under that bounded native path, both tested session candidates `100` and `101` reached `start()` but failed `connect()` with `connect_code=-1`, with no callback events and no account/order query phase reached.
   - `docs/ACCEPTANCE_STANDARD.md` defines `xttrader connect=-1` as a `G3` hard stop and classifies broker/session connect failure first as `fail_env` or `blocked`, not as design pass-through evidence.
   - This means the native probe strengthens the prior review's blocker, but does not release it.

2. High: the native probe weakens the gateway-only bug narrative and keeps the current failure classified as environment-layer blocked, not proven `fail_design`.
   - The prior full rerun already showed `session.warm -> orders.list_exception -> xttrader connect failed: -1` while login state had recovered to `already_logged_in`.
   - The new native probe reproduced the same broker/session failure without MCP transport, without gateway session manager reuse, and before any `orders.list` logic could execute.
   - Therefore the current evidence is insufficient to assert that the remaining blocker is only a gateway query lifecycle defect or an `orders.list` implementation bug.
   - The design-vs-environment classification remains unchanged: `fail_env` is supported; `fail_design` is not proven by this probe.

3. Medium: session collision remains only a bounded hypothesis and cannot be promoted to the required fix until a separate dev/test cycle produces controlled evidence.
   - The official native guidance reflected in the task context says `session_id` must not collide and that one API instance is usually sufficient.
   - This probe tested two candidate ids, `100` and `101`, and both failed identically at `connect()=-1`.
   - That leaves open several environment-layer explanations, including unseen session ownership conflict or local runtime policy, but it does not validate a repository design defect in session allocation.
   - Any move toward dynamic session allocation or broader native session experiments needs a new dev card and a new independent test artifact, rather than a review-side reclassification.

## Severity

- highest: high

## Impact

The native probe improves stage isolation, but not release posture. It confirms that login recovery and `58610` reachability are real, while also showing that the remaining blocker survives outside the gateway in a minimal native lifecycle. As a result, the review baseline should now read: login recovered, broker/session still blocked at native connect stage. This changes diagnostic confidence, but it does not change `VAL-002` from `blocked`, and it does not move the issue from environment failure into proven design failure.

## Required Fix

1. Keep `VAL-002` in environment-blocked handling until a new EvidencePack shows `session.warm` can establish a real owner-managed session and no longer hits `xttrader connect=-1`.
2. For any next dev attempt, separate hypotheses explicitly:
   - environment/session ownership or broker runtime issue
   - repository session allocation strategy issue
   - gateway-only query lifecycle issue
3. Do not reclassify to `fail_design` unless a later bounded run shows the native path can connect successfully while the gateway path still fails under the same environment.
4. Do not use this probe to unblock `VAL-003` or any write-path validation; `G3` remains incomplete.

## Release Decision

- Decision: `blocked`
- Test Conclusion Carried Forward: `fail_env`
- Native Probe Changes Blocked Status: `no`
- Native Probe Changes Design-vs-Environment Classification: `no`
- Explicit Statement: this native probe does not change the formal `blocked` status of `VAL-002`, and it does not convert the current issue from environment-layer failure into proven design failure. The stronger supported conclusion is still `fail_env`, now with direct native evidence that the broker/session connect failure reproduces before gateway query logic.
- Release Recommendation: do not release, do not advance to `VAL-003`

## State Suggestion

- Target Status: `Blocked`
- Reason: `G3` remains blocked by native `xttrader connect=-1`, which is an acceptance hard stop and still classified as environment-side failure on current evidence.
