---
name: mode-analyze-only
description: Run read-only analysis when scope, authority, contracts, or risk are not stable enough for safe execution. Use when a task is routed to `analyze_only`, when acceptance criteria are missing or contradictory, when risk is unclear, or when execution would be premature without more policy or design clarity.
---

# Mode Analyze Only

Use this mode to reduce ambiguity, not to "make progress" by quietly starting implementation.

This mode exists to clarify tasks, contracts, options, and risks while keeping execution frozen. It is the safe default when the workflow lacks a trustworthy acceptance boundary.

## What This Mode May Do

- read specs, policy docs, schemas, CI config, and task context
- compare possible approaches
- identify missing contracts, missing authorities, and decision gaps
- produce a concise recommendation for the next safe step
- hand off back to `$workflow-router` or `$acceptance-analysis` when the missing information is known

## What This Mode Must Not Do

- do not edit repo-tracked files as execution work
- do not run release-impacting or external side-effect actions
- do not declare `gated_pass`
- do not bypass missing acceptance or missing authority by making assumptions look authoritative

## Typical Triggers

- `contract_missing`
- `contract_ambiguous`
- task mixes low-risk implementation with high-risk rollout work
- release authority is required but unknown
- the user asks for implementation before the task is classifiable

## Expected Output

Produce a short analysis package that includes:

- the unresolved questions
- the blocking policy or authority gaps
- the recommended next skill
- the minimum information needed to leave `analyze_only`

## Trigger Phrases

- `Use $mode-analyze-only. Clarify risk, gaps, and contracts before any changes.`
- `Use $mode-analyze-only. Stay read-only and identify the missing decision inputs.`
- `Use $mode-analyze-only. Do not start implementation until the contract is stable.`

## References

- Read [references/README.md](./references/README.md) for stop rules and typical outputs.
- Read [examples/README.md](./examples/README.md) for example prompts and expected behavior.

## Handoff

- Hand off to `$workflow-router` when the task can be reclassified.
- Hand off to `$acceptance-analysis` when the blocking issue is acceptance-related.
- Hand off to another `mode-*` skill only after the required inputs are explicit.
