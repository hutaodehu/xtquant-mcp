---
name: mode-live-rollout
description: Plan and execute controlled high-risk work that mutates production or production-adjacent external state under explicit approval, health, and rollback gates. Use when a task has been routed to `live_rollout`, especially for migrations, feature exposure, real external writes, secrets, or financial and safety-critical operations.
---

# Mode Live Rollout

Use this mode only when the task truly belongs near live state. It is intentionally slower, stricter, and more explicit than the other modes.

This mode exists to protect high-consequence systems from accidental optimism. It requires visible authority, live health signals, and rollback readiness before any success claim can be made.

## Default Workflow

1. Confirm the task cannot remain in `gated_change`.
2. Load the `acceptance_contract` and verify required approvals.
3. Verify runtime health and rollback prerequisites before execution.
4. Limit the rollout surface as much as possible.
5. Gather fresh runtime evidence during or after the controlled action, including freshness metadata.
6. Stop if approval, health, or rollback readiness becomes weak.

## What This Mode May Do

- prepare a rollout plan
- verify approvals and authority paths
- verify runtime health or live-signal readiness
- gather fresh environment or runtime evidence
- execute only within the approved operational boundary

## What This Mode Must Not Do

- do not proceed without explicit approval where the contract requires it
- do not reuse stale evidence as proof of fresh readiness
- do not execute high-impact writes without rollback readiness
- do not infer release success from local or pre-live checks alone

## Typical Tasks

- schema or data migrations
- real trade, payment, or account-affecting write paths
- feature-flag exposure to real users
- secret rotation or permission changes with live effect
- runtime configuration changes with external consequences

## Trigger Phrases

- `Use $mode-live-rollout. Prepare a controlled rollout with approvals, health checks, and rollback readiness.`
- `Use $mode-live-rollout. Fail closed if authority or live evidence is missing.`
- `Use $mode-live-rollout. Keep the blast radius bounded and explicit.`

## References

- Read [references/README.md](./references/README.md) for the live-risk gate expectations.
- Read [examples/README.md](./examples/README.md) for example prompts and expected blocked or gated outputs.

## Handoff

- Hand off to `$evidence-gate` after live evidence is gathered and must be judged against the contract.
- Hand off back to `$acceptance-analysis` if the rollout gate or approval model is still unclear.
- Hand off back to `$mode-analyze-only` if the task cannot be executed safely with the information available.
