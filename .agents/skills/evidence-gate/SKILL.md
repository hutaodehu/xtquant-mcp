---
name: evidence-gate
description: Compare existing `change_evidence` and `validation_evidence` against an `acceptance_contract` and report a structured `gate_result` without collapsing blocker type into a release verdict. Use when Codex needs to determine whether current evidence is sufficient for the next gate, whether authority is satisfied, or why a task remains blocked.
---

# Evidence Gate

Use this skill only after evidence exists and an `acceptance_contract` is already available or can be loaded from an authoritative source.

This skill is the final comparison layer between contract and evidence. It does not create missing evidence, relax authority requirements, or translate weak signals into a release pass.

## Inputs

Load:

- the current `acceptance_contract`
- current `change_evidence`
- current `validation_evidence`
- any review, approval, or runtime-health records needed by the contract

Ignore chat-only claims that are not tied to evidence carriers.

## Output

Produce a `gate_result` with:

- `decision`
- `blocker_class`
- `satisfied_gates`
- `unsatisfied_gates`
- `validation_authority_satisfied`
- `release_authority_satisfied`
- `evidence_freshness`
- `evidence_items`
- `next_safe_step`

Keep blocker classification and release decision separate. For example, `blocked` because of `fail_env` is not the same thing as `fail_design`.

## Decision Rules

- `fast_loop` evidence may support `provisional_pass_for_local_iteration` or `ready_for_independent_validation`, but never `gated_pass`.
- `gated_change` may support `gated_pass` only when required checks and the required independent authority are satisfied.
- `live_rollout` may support `gated_pass` only when approvals, live health evidence, and rollback readiness are all satisfied.
- Missing contracts should map to `not_authoritative_due_to_missing_contract`, not a normal `blocked` result.
- If evidence is missing, classify the blocker explicitly instead of inferring success.

## Hard Stops

Stop and return a blocked result when:

- the acceptance contract is missing
- required evidence carriers are missing
- approval is required but absent
- runtime health is required but absent
- the only evidence is a narrative claim with no artifact path or source

## Forbidden Actions

- Do not create or rewrite missing evidence just to advance the gate.
- Do not treat authority gaps as documentation gaps.
- Do not infer release approval from local test success.
- Do not compress `fail_env`, `fail_design`, and `blocked` into one value.
- Do not declare release readiness when validation or release authority is unsatisfied.

## Trigger Phrases

- `Use $evidence-gate. Compare the current evidence against the acceptance contract.`
- `Use $evidence-gate. Report satisfied gates, unsatisfied gates, and authority status.`
- `Use $evidence-gate. Keep blocker classification separate from the release decision.`

## References

- Read [references/README.md](./references/README.md) for the decision vocabulary and evidence handling rules.
- Read [examples/README.md](./examples/README.md) for example prompts and expected `gate_result` patterns.

## Handoff

- Hand off back to the active `mode-*` skill when more evidence must be gathered.
- Hand off back to `$acceptance-analysis` if the contract is too weak to judge the current evidence.
- Hand off to a repo-specific release process only after the required gate and authority conditions are actually met.
