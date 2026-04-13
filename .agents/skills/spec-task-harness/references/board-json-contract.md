# Board Export JSON Contract

The harness accepts an optional board export JSON file.

This file is a read-side snapshot of the external board / RunLedger.

If the board export is missing, the harness enters repo-only recovery mode.

## Minimal accepted shape

Preferred shape:

```json
{
  "tasks": [
    {
      "task_id": "DG-001",
      "status": "In Independent Test",
      "owner_role": "test",
      "current_role": "test",
      "blocking_reason": "",
      "review_result": "blocked",
      "change_package_link": "docs/change_packages/DG-001.md",
      "evidence_pack_link": "docs/evidence_packs/DG-001-test-202603292240.md",
      "review_pack_link": "docs/reviews/DG-001-review-202603292350.md"
    }
  ]
}
```

The harness also tolerates:

- a top-level array instead of `{ "tasks": [...] }`
- human-readable keys such as `Task ID`, `Status`, `Owner Role`

## Preferred envelope fields

- `board_name`
- `exported_at`
- `schema_version`
- `tasks`

These envelope fields are recommended, not required by the current scripts.

## Preferred task fields

- `task_id`
- `status`
- `owner_role`
- `current_role`
- `blocking_reason`
- `review_result`
- `claimed_by`
- `claim_run_id`
- `change_package_link`
- `evidence_pack_link`
- `review_pack_link`
- `env_snapshot_link`

## Normalization rules

- `task_id` is the stable primary key.
- `status` should use the board state machine defined in `docs/WORKFLOW_AND_BOARD.md`.
- Empty values should be represented as empty strings, not omitted, when practical.
- Relative artifact links should be repo-relative paths.
- Extra fields are allowed; the harness ignores unknown keys.

## Recommended freshness rules

- `exported_at` should reflect the actual board snapshot time.
- The controller should prefer a fresh export over a stale cached file before doing a formal board-vs-artifact reconcile.
- If the export is known stale, the controller should treat the result as advisory and may return `sync_runledger_first`.

## Sample file

See:

- `examples/board_export.sample.json`
