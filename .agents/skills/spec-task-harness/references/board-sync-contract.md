# Board Sync JSON Contract

This contract defines the write-side payload for syncing controller decisions back to an external board / RunLedger.

Board sync is controller-owned work.

Board sync is not role substitution.

The controller may sync the board only when the update is justified by existing role-owned artifacts such as:

- `ChangePack`
- `EvidencePack`
- `ReviewPack`
- `EnvSnapshot`

The controller must not invent missing role-owned artifacts first and then sync the board as if execution had happened.

## Minimal accepted shape

Preferred shape:

```json
{
  "target_ledger": "notion://xtquant-mcp-board",
  "mode": "upsert_tasks",
  "updates": [
    {
      "task_id": "DG-001",
      "status": "Accepted",
      "owner_role": "review",
      "current_role": "review",
      "blocking_reason": "",
      "review_result": "pass",
      "change_package_link": "docs/change_packages/DG-001.md",
      "evidence_pack_link": "docs/evidence_packs/DG-001-test-202603292240.md",
      "review_pack_link": "docs/reviews/DG-001-review-202603300706.md",
      "env_snapshot_link": "docs/env_snapshots/DG-001-test-202603292240.md",
      "reason": "VAL-001 closed the live G2 gap and the superseding review passed."
    }
  ]
}
```

## Preferred envelope fields

- `target_ledger`
- `mode`
- `sync_run_id`
- `source_mode`
- `source_board_export`
- `updates`

Recommended values:

- `mode`: `upsert_tasks`
- `source_mode`: `board_reconcile` or `repo_only_recovery`

## Preferred update fields

- `task_id`
- `status`
- `owner_role`
- `current_role`
- `blocking_reason`
- `review_result`
- `change_package_link`
- `evidence_pack_link`
- `review_pack_link`
- `env_snapshot_link`
- `reason`

## Controller write rules

The controller may write:

- board status
- owner and current role
- blocking reason
- review result
- artifact links
- a short sync reason

The controller must not write these fields unless the underlying spec or task docs were separately changed and reviewed:

- `Title`
- `Type`
- `Priority`
- `Acceptance Gate`
- `Depends On`
- `Scope In`
- `Scope Out`

## Safe sync rules

- Sync by `task_id`, never by row position.
- Prefer idempotent upsert behavior.
- Use existing artifact links as the source of truth for link fields.
- If the board integration supports compare-and-set, the controller should preserve a copy of the prior board export before writing.
- If the board integration is unavailable, the controller should still emit a payload in this shape or a checklist derived from it.

## Sample file

See:

- `examples/board_sync.sample.json`
