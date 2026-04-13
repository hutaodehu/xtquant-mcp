# Evidence Gate References

Read this file when you need the canonical decision vocabulary for comparing evidence against a contract.

## Decision Vocabulary

- `provisional_pass_for_local_iteration`
- `ready_for_independent_validation`
- `gated_pass`
- `blocked`
- `not_authoritative_due_to_missing_contract`

## Blocker Classes

- `none`
- `fail_env`
- `fail_design`
- `policy_missing`
- `approval_missing`
- `evidence_missing`

## Core Rules

- A local green run is not a release pass by itself.
- missing contract should use `not_authoritative_due_to_missing_contract`.
- unsatisfied validation or release authority blocks release-level success.
- Missing runtime health evidence blocks live-rollout success.
- Missing or weak evidence should not be replaced with narrative summaries.
- runtime-state or live-risk tasks need freshness metadata, not only artifact paths.

## Related Docs

- `docs/universal_skills/contracts/GATE_RESULT_SCHEMA.md`
- `docs/universal_skills/contracts/ACCEPTANCE_CONTRACT_SCHEMA.md`
- `docs/universal_skills/contracts/AUTHORITY_MATRIX.md`
