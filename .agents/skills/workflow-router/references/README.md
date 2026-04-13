# Workflow Router References

Read this file when you need the canonical routing vocabulary without reopening the larger design pack.

## Core Terms

- `base_mode`: one of `analyze_only`, `fast_loop`, `gated_change`, `live_rollout`
- `overlays`: additional constraints such as `contract_missing`, `contract_ambiguous`, `manual_gate`, `human_review_required`, `multi_agent_allowed`, `background_agent_allowed`, `fresh_env_snapshot_required`
- `route_decision`: the structured routing output for a task
- `risk_profile`: the structured risk input that explains why the route was chosen

## Primary Signals

Classify by:

- external state mutation
- blast radius
- rollback quality
- production exposure
- security or privacy sensitivity
- validation difficulty
- cross-boundary change
- human or financial impact
- execution topology
- runtime dependency and volatility
- privilege surface

## Conservative Escalation

- Unknown authority should escalate, not relax.
- Unknown rollback should escalate, not relax.
- Missing contracts should route to `analyze_only`.
- Conflicting contracts should route to `analyze_only` with `contract_ambiguous`.
- Real external writes or production-adjacent writes should route to `live_rollout`.

## Overlay Derivation

- `fresh_env_snapshot_required`: fresh probe or runtime evidence is mandatory
- `multi_agent_allowed`: write sets are disjoint and handoff contracts are explicit
- `background_agent_allowed`: background execution is explicitly approved and auditable
- `manual_gate` / `human_review_required`: external authority is required to continue

## Related Docs

- `docs/universal_skills/contracts/RISK_PROFILE_SCHEMA.md`
- `docs/universal_skills/contracts/ROUTE_DECISION_SCHEMA.md`
- `docs/universal_skills/ADAPTIVE_DELIVERY_SUITE_DESIGN.md`
