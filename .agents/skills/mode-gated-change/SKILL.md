---
name: mode-gated-change
description: Prepare shared or cross-boundary changes under explicit review, CI, and policy gates. Use when a task has been routed to `gated_change`, especially for shared-code changes, public APIs, cross-module refactors, auth or security work, infra changes, or any change that cannot stop at local TDD evidence.
---

# Mode Gated Change

Use this mode when the change must be reviewable, reproducible, and bounded by explicit gates before it can be accepted.

This mode is stricter than `fast_loop` but still short of live rollout. It focuses on preparing a clean shared change with the right evidence for CI, reviewers, code owners, and policy gates.

## Default Workflow

1. Confirm the task still belongs in `gated_change`.
2. Load the `acceptance_contract`.
3. Scope the change to the shared boundary actually under review.
4. Where practical, add the smallest failing boundary check before or alongside the change.
5. Implement only what is needed for the contract.
6. Gather reviewable evidence: tests, contract updates, CI expectations, and known risks.
7. Stop short of release authority and hand off to `evidence-gate` or repo-native review.

## What This Mode May Do

- edit code and tests needed for the shared change
- update public or internal contracts when the task requires it
- prepare evidence for CI, review, and gate evaluation
- document explicit known risks and next required authority

## What This Mode Must Not Do

- do not bypass required reviewers, code owners, or CI gates
- do not collapse review preparation into rollout approval
- do not treat local success as final acceptance
- do not hide contract changes inside unrelated implementation work

## Typical Tasks

- public API changes
- shared library refactors
- infra-as-code or workflow policy changes
- auth, security, or permission changes
- agent/tool routing changes that affect shared behavior

## Trigger Phrases

- `Use $mode-gated-change. Prepare a reviewable shared change under explicit gates.`
- `Use $mode-gated-change. Gather the evidence needed for CI and independent review.`
- `Use $mode-gated-change. Stop short of release authority.`

## References

- Read [references/README.md](./references/README.md) for gate expectations and escalation boundaries.
- Read [examples/README.md](./examples/README.md) for example prompts and expected behavior.

## Handoff

- Hand off to `$evidence-gate` once the shared change evidence is ready.
- Hand off back to `$acceptance-analysis` if a required gate is still unclear.
- Escalate to `$mode-live-rollout` if the work crosses into real external mutation or rollout behavior.
