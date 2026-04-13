---
name: acceptance-analysis
description: Load authoritative acceptance sources and normalize them into an `acceptance_contract` with required checks, evidence, thresholds, and authority boundaries. Use when Codex needs to determine what counts as done for a task, reconcile multiple policy sources, identify contract gaps, or plan a risk-appropriate test portfolio before execution or release decisions.
---

# Acceptance Analysis

Use this skill after routing whenever the acceptance boundary is not already explicit and machine-readable.

This skill answers a different question from routing: not "which mode should we use?" but "what exact contract must be satisfied?" It is the canonical place to fail closed when standards are missing, conflicting, or too vague to justify a later verdict.

## Load Order

Read sources in this order:

1. task-level acceptance statements
2. repo policy files such as `AGENTS.md` and acceptance docs
3. branch, CI, environment, or deployment gates
4. API, schema, protocol, or data contracts
5. security, compliance, or release policies
6. suite defaults only when higher-order sources do not speak

If a higher-priority source conflicts with a lower-priority source, do not resolve it implicitly. Mark the contract as ambiguous and stop.

## Output

Produce an `acceptance_contract` that includes:

- authoritative sources
- task type and risk level
- required checks
- non-waivable gates
- pass thresholds
- evidence requirements
- acceptance scenarios
- gate definitions
- required authorities
- evidence freshness requirements
- whether human review or environment approval is required
- the missing-contract policy

Also produce explicit gap markers when needed, such as `contract_missing` or `contract_ambiguous`.

## Test Portfolio Planning

Use risk and boundary type to scale the test burden:

- Prefer unit and small deterministic checks for local logic.
- Require contract or integration checks when APIs, schemas, or persistent boundaries change.
- Require runtime smoke, health, or staged evidence when the task approaches live rollout.
- Require agent/tool evals when the task changes prompt logic, tool routing, permissions, or multi-agent handoff.
- When behavior crosses roles or user-visible outcomes, derive ATDD / BDD-style `acceptance_scenarios` instead of only flat check lists.

Do not default to top-heavy E2E suites when lower-level checks can prove the requirement more cheaply and more reliably.

## Hard Stops

Stop and return a gap instead of continuing when:

- no authoritative source defines what "pass" means
- policy sources disagree about a required gate
- release authority is required but undefined
- the only available evidence is an existing passing test suite with no matching acceptance source
- a high-risk task would have to rely on model judgment alone
- a feature, migration, rollout, or agent-routing task lacks scenario-level acceptance despite cross-role behavior

## Forbidden Actions

- Do not invent authoritative pass/fail standards.
- Do not treat existing green tests as sufficient if they are not tied to the requirement.
- Do not waive human review, environment approval, or non-waivable gates.
- Do not convert an ambiguous contract into a permissive contract.
- Do not declare release readiness.

## Trigger Phrases

- `Use $acceptance-analysis. Load the acceptance contract and identify missing gates.`
- `Use $acceptance-analysis. Normalize the policy sources into required checks and evidence.`
- `Use $acceptance-analysis. Fail closed if the contract is missing or ambiguous.`

## References

- Read [references/README.md](./references/README.md) for source priority, contract fields, and test-portfolio heuristics.
- Read [examples/README.md](./examples/README.md) for example prompts and expected `acceptance_contract` shapes.

## Handoff

- Hand off to a `mode-*` skill only after the contract is stable enough to justify execution.
- Hand off to `$evidence-gate` after execution or validation evidence exists and you need a gate decision.
- Hand off back to `$mode-analyze-only` if the task cannot obtain a stable contract.
