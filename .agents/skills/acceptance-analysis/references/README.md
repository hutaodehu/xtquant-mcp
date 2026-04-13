# Acceptance Analysis References

Read this file when you need the contract-loading order and the default test-planning heuristics.

## Source Priority

Use this priority order:

1. task-level acceptance requirements
2. repo policy and `AGENTS.md`
3. repo adapter docs when truth carriers or runtime/resource sources are already defined
4. branch, CI, environment, or deployment gates
5. API, schema, or protocol contracts
6. security, compliance, and release policies
7. suite defaults

## Contract Rules

- High-priority sources win over low-priority sources.
- If sources conflict materially, return `contract_ambiguous`.
- If no authoritative source exists, return `contract_missing`.
- Use `fail_closed` by default for high-risk tasks.
- For feature, migration, rollout, or cross-role behavior, prefer scenario-level acceptance instead of only flat check lists.

## Test Portfolio Heuristics

- Favor unit and small deterministic tests for local logic.
- Add contract tests for API, schema, or protocol changes.
- Add integration tests for cross-boundary behavior.
- Add runtime smoke or health checks only when the task approaches live systems.
- Add agent/tool evals when prompt, routing, permissions, or handoff behavior changes.
- Map each business scenario to checks, evidence, and authority so TDD inner-loop proof is not confused with final acceptance.

## Related Docs

- `docs/universal_skills/contracts/ACCEPTANCE_CONTRACT_SCHEMA.md`
- `docs/universal_skills/contracts/AUTHORITY_MATRIX.md`
- `docs/universal_skills/ADAPTIVE_DELIVERY_SUITE_DESIGN.md`
