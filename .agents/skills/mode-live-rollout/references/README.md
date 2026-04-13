# Live Rollout References

Read this file when you need the default safeguards for production or production-adjacent changes.

## Use This Mode When

- the task mutates real external state
- rollout approval is required
- runtime health must be observed during or after execution
- rollback readiness is material to safety

## Required Discipline

- confirm approval authority before execution
- prefer the smallest safe rollout surface
- require fresh runtime evidence, not stale readiness claims
- stop immediately if health or rollback confidence weakens
- keep freshness metadata and environment identity with each live evidence artifact

## Fail-Closed Conditions

- approval missing
- live health signal missing
- rollback path missing or untrusted
- acceptance contract unclear for a high-risk action
