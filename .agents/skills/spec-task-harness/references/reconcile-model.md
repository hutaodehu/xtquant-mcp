# Reconcile Model

## Purpose

The harness starts with reconcile, not with dispatch.

This is required because repos may already contain:

- updated `ChangePack`
- one or more `EvidencePack`
- one or more `ReviewPack`
- stale `TaskCard.Status`
- stale or missing board state

## Local Stage

Infer `local_stage` from artifacts:

- `todo_local`
- `implemented_local`
- `tested_local`
- `reviewed_pass_local`
- `reviewed_needs_fix_local`
- `reviewed_blocked_local`
- `migration_exempt`

## Reconcile State

Compare `local_stage` with the board when a board export is available:

- `aligned`
- `board_stale`
- `artifact_incomplete`
- `conflict_needs_controller`
- `missing_board`

## Repo-Only Recovery Mode

If no board export is available:

- infer `local_stage`
- recommend the next controller action
- do not claim live board truth
- do not auto-dispatch high-risk or manual-gate tasks

This mode is for cold-start recovery and validation, not silent production orchestration.
