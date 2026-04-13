# Gated Change Examples

Use example prompts like these:

- `Use $mode-gated-change. Update this shared API contract and gather the review evidence.`
- `Use $mode-gated-change. Refactor this cross-module behavior without bypassing CI or reviewer gates.`
- `Use $mode-gated-change. Prepare this auth-related change for independent review and evidence-gate judgment.`

Expected behavior:

- shared-boundary implementation only
- explicit evidence preparation for CI and review
- no rollout claim and no release authority claim
