# Policy Inputs

Use the repo policy files as the source of truth for scope and gating.

Read in this order:

1. `docs/MCP_DESIGN.md`
2. `docs/EXECUTION_AND_ARTIFACT_STANDARD.md`
3. `docs/WORKFLOW_AND_BOARD.md`
4. `docs/ACCEPTANCE_STANDARD.md`
5. `docs/FIRST_WAVE_TASK_BREAKDOWN.md`

Then load the task-specific artifacts:

- `docs/task_cards/<TaskID>.md`
- `docs/change_packages/<TaskID>.md`
- `docs/evidence_packs/*`
- `docs/reviews/*`
- `docs/env_snapshots/*`

When board integration is in scope, also load:

- `references/board-json-contract.md`
- `references/board-sync-contract.md`
- `examples/board_export.sample.json`
- `examples/board_sync.sample.json`

Do not duplicate or override these files inside the skill. The skill operationalizes them; it does not replace them.
