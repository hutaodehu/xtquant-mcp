---
name: spec-task-harness
description: Reconcile TaskCard-driven development workflows that use ChangePack, EvidencePack, ReviewPack, EnvSnapshot, and an external RunLedger. Use when Codex needs to assess current task reality from repo artifacts, compare it with a board export, choose the next safe controller action, render a dispatch, or validate that a repo follows a gated dev/test/review execution contract.
---

# Spec Task Harness

Use this skill as a controller harness, not as a business implementation skill.

This skill is for repos that already use:

- `TaskCard`
- `ChangePack`
- `EvidencePack`
- `ReviewPack`
- `EnvSnapshot`
- an external `RunLedger` / board

The skill exists to:

1. Reconcile repo artifacts against board state.
2. Recover the real current stage when local docs and board status drift apart.
3. Select the next safe controller action.
4. Render consistent dispatch text and artifact checks.

This skill must not be used as an unattended backlog-drain engine. It runs a bounded controller loop and then stops.

## Controller Modes

This skill supports exactly two modes:

1. `controller-only`
2. `controller-with-delegation`

This skill does not support generic role substitution.

The controller must never take over `dev`, `test`, or `review` work itself while using this skill. If the next step requires real role execution, the controller must either:

- stop after rendering the bounded dispatch, or
- delegate that bounded step to another agent when the user has explicitly authorized multi-agent delegation

The only repo-scoped exception is `controller direct test execution` on an eligible live test card. That exception:

- is not a third controller mode
- only applies when the TaskCard explicitly sets `Controller Test Policy: controller_direct_required`
- also requires `Automation Policy: manual_gate`, `Execution Class: test_only`, and `Risk Class: high`
- may only be triggered manually through `scripts/run_controller_direct_test.ps1`
- does not authorize controller-written `ReviewPack`
- does not make the task `dispatchable`

Controller responsibilities are limited to:

- reading policy inputs and task artifacts
- reconciling repo reality against board or repo-only state
- inferring the current local stage from artifacts
- selecting the next safe controller action
- rendering a bounded dispatch for another role
- dispatching a bounded child-agent task when delegation is explicitly authorized
- checking returned artifacts after a worker run
- recommending closeout, rollback, or validation preparation
- synchronizing external board / RunLedger state when that sync is derived from existing role-owned artifacts and an available board integration

In both controller modes, Codex must not:

- implement business code as `dev`
- execute validation, smoke, or acceptance work as `test`
- write a `ReviewPack` as `review`
- create a new `ChangePack`, `EvidencePack`, `EnvSnapshot`, or `ReviewPack` by performing that role's work itself
- mutate task state to imply a worker run happened when none did
- treat controller observations or chat text as substitutes for role-owned artifacts
- continue a worker task locally after delegating it to another agent

When the repo explicitly uses `controller direct test execution`, the controller may create `Role: test` artifacts only as the real executor of that run, and those artifacts must include:

- `Executor: controller direct test execution`
- `Authorization Basis`
- `Controller Judgment Link`
- `Raw Runtime Capture`
- `Gateway Recovery Output Link`

Board / RunLedger sync is controller-owned work, not role substitution.

If the current repo state and existing role-owned artifacts are already sufficient to determine the correct board update, the controller may:

- update external board status
- update board links to `ChangePack`, `EvidencePack`, `ReviewPack`, and `EnvSnapshot`
- mark closeout or blocked state in the RunLedger

The controller must not fabricate missing role-owned artifacts first and then sync the board as if execution had happened.

### `controller-only`

Use this mode when the goal is to reconcile, decide, render dispatch, and stop.

The correct loop is:

1. reconcile
2. select the next safe controller action
3. sync the board if a deterministic board update is already supported and justified by existing artifacts
4. render dispatch if needed
5. stop
6. wait for role-owned artifacts
7. reconcile again in a later turn or session

### `controller-with-delegation`

Use this mode only when the user has explicitly authorized multi-agent delegation for the current run.

In this mode, the controller may:

- reconcile current reality
- choose the next safe bounded step
- sync the external board / RunLedger when current artifacts already justify that update
- render the dispatch
- assign that bounded step to a delegated `dev`, `test`, or `review` agent
- wait for the delegated agent to return role-owned artifacts
- inspect returned artifacts and reconcile again

In this mode, the controller still must not do the delegated role's work itself.

When dispatching child agents for this repo, the controller must use a sub-agent configuration floor of:

- `model: gpt-5.4`
- `reasoning_effort: high`

Using any child agent below `gpt-5.4` with `high` reasoning is not allowed for this harness.

### Trigger Phrases

Use one of these short trigger phrases when invoking the skill:

- `Use $spec-task-harness, controller-only. Reconcile first, then give the next safe action. Do not do role work directly.`
- `Use $spec-task-harness, controller-with-delegation. Reconcile first, then dispatch the next safe bounded step to child agents. The controller must not substitute for dev, test, or review.`

For localized operator-facing trigger examples, see `docs/TEMPLATES.md`.

## Workflow

### 1. Load policy inputs first

Before making any decision, read the repo policy pack. For this repo, start with:

- `docs/MCP_DESIGN.md`
- `docs/EXECUTION_AND_ARTIFACT_STANDARD.md`
- `docs/WORKFLOW_AND_BOARD.md`
- `docs/ACCEPTANCE_STANDARD.md`
- `docs/FIRST_WAVE_TASK_BREAKDOWN.md`

Read [references/policy-inputs.md](./references/policy-inputs.md) when you need the exact order and purpose of each file.

### 2. Reconcile before dispatch

Never assume tasks start from `Ready`.

Always run reconcile first:

- If a board export is available, compare board state with local artifacts.
- If no board export is available, enter repo-only recovery mode and infer current local stage from artifacts.

Use:

- `scripts/reconcile_runledger.py`

Read [references/reconcile-model.md](./references/reconcile-model.md) before interpreting results.

### 3. Stop if state is not safe to automate

Do not dispatch new work when any of these are true:

- board state is stale relative to artifacts
- artifacts are incomplete for the board's claimed phase
- review says `needs_fix` or `blocked`
- task is marked `manual_gate`
- risk is `high`
- write scopes overlap
- controller would need to switch roles or personally perform role-owned work
- the only way forward is for the controller to create role-owned execution artifacts directly

For `Controller Test Policy: controller_direct_required` cards, the correct safe result is still to stop in the normal selection loop and surface `manual_resume_required`. The controller may only proceed if the operator explicitly triggers the controller-direct runner.

When this happens, stop and return a controller-facing recommendation instead of improvising.

### 4. Select only the next safe action

Use:

- `scripts/select_next_safe_tasks.py`

This script may return one of these controller outcomes:

- `sync_runledger_first`
- `controller_closeout`
- `prepare_validation`
- `dispatchable`
- `manual_gate_pending`
- `waiting_for_dependencies`
- `controller_review_required`

Only `dispatchable` tasks are safe to hand to implementation workers without extra controller judgment. In `controller-with-delegation`, non-`dispatchable` outcomes still require explicit controller judgment before any delegated run is started.

Cards that require `controller direct test execution` must remain outside `dispatchable_candidates`; they are resumed manually via `scripts/run_controller_direct_test.ps1`, not by ordinary dispatch rendering.

### 5. Render a bounded dispatch

When a task is safe to dispatch, render a controller message instead of freehanding it:

- `scripts/render_dispatch.py`

This keeps `In Scope`, `Out of Scope`, expected outputs, and artifact links consistent across runs.

In `controller-only`, do not continue past dispatch. After the bounded dispatch is rendered, stop and wait for the assigned role to produce artifacts.

In `controller-with-delegation`, the controller may hand that bounded dispatch to a child agent and then stop doing that role's work itself. The next controller step is to wait for returned artifacts, inspect them, and reconcile again.

If board integration is available, the controller may also perform the corresponding RunLedger sync before stopping, provided the update is supported by existing artifacts and does not require inventing missing role-owned outputs.

### 6. Check artifacts after each worker run

After a worker finishes, inspect artifacts before changing the board:

- `scripts/collect_artifacts.py`
- `scripts/validate_taskcard.py`

Do not treat chat text as completion. The minimum acceptable post-run evidence is:

- updated `ChangePack`
- relevant new or superseding `EvidencePack` / `ReviewPack` when applicable
- explicit risk and next-state recommendation

The controller may inspect these artifacts, but it must not manufacture missing role-owned artifacts just to advance state.

## Stop Rules

Stop and hand control back to the controller when:

- `reconcile_state` is `board_stale`
- `reconcile_state` is `artifact_incomplete`
- `reconcile_state` is `conflict_needs_controller`
- a task is `manual_gate`
- a task is `high` risk
- the board is missing and the decision would mutate live state
- the next step crosses from `dev` to `test`
- the next step crosses from `test` to `review`
- the task touches real write paths or other high-side-effect actions
- continuing would require the controller to substitute for `dev`, `test`, or `review`
- the only apparent next step is to create role-owned execution artifacts directly from controller observations

If the next step is an eligible controller-direct live test, stop the normal loop, preserve `manual_resume_required`, and wait for an explicit manual trigger of `scripts/run_controller_direct_test.ps1`.

## Repo-Specific Notes

For this repo:

- `TaskCard.Status` is a local mirror field, not the live board truth.
- `ReviewPack` is a first-class artifact under `docs/reviews/`.
- The harness must support repos where some cards are already partially or substantially completed before the skill is introduced.
- Cold-start validation should be done in a fresh session with minimal context, not in the same authoring thread.
- For this repo, the controller may orchestrate other agents, but it must never replace their role-owned execution work.

Read these only when needed:

- [references/policy-inputs.md](./references/policy-inputs.md)
- [references/reconcile-model.md](./references/reconcile-model.md)
- [references/board-json-contract.md](./references/board-json-contract.md)
- [references/board-sync-contract.md](./references/board-sync-contract.md)

Examples:

- `examples/board_export.sample.json`
- `examples/board_sync.sample.json`
