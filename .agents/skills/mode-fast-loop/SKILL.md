---
name: mode-fast-loop
description: Run a TDD-style local delivery loop for low-risk, reversible, deterministic changes. Use when a task has been routed to `fast_loop`, especially for docs-only work, local bugfixes, pure logic changes, or small internal refactors that can be validated with local checks and do not require release authority.
---

# Mode Fast Loop

Use this mode to move quickly without pretending that local success equals release acceptance.

This mode is the default inner loop for safe local work. It prioritizes small diffs, fast feedback, deterministic checks, and behavior-first validation.

## Default Workflow

1. Restate the task in behavior terms.
2. Add or identify the smallest failing test or deterministic check.
3. Make the minimum change to satisfy the behavior.
4. Re-run local checks.
5. Stop at `provisional_pass_for_local_iteration` or `ready_for_independent_validation`.

## What This Mode May Do

- edit repo-tracked files in the local workspace
- add or update unit tests and other small deterministic checks
- run local test, lint, or typecheck commands that do not change the contract boundary
- prepare the task for independent validation if required later

## What This Mode Must Not Do

- do not declare `gated_pass`
- do not skip explicit repo review or CI gates when the repo requires them
- do not extend a low-risk task into live rollout work
- do not use broad E2E checks as the default proof when lower-level checks are enough
- do not stay in `fast_loop` once session state, permission boundaries, runtime freshness, or multi-agent coordination become material

## Typical Tasks

- docs-only adjustments
- pure logic bugfixes
- internal utility refactors
- local parsing or transformation fixes with stable fixtures
- low-risk research or analysis code in quant workflows

## Trigger Phrases

- `Use $mode-fast-loop. Follow TDD and do not claim release acceptance.`
- `Use $mode-fast-loop. Work in a small deterministic local loop.`
- `Use $mode-fast-loop. Stop at provisional local validation or ready-for-validation.`

## References

- Read [references/README.md](./references/README.md) for mode boundaries and common check types.
- Read [examples/README.md](./examples/README.md) for example prompts and expected outputs.

## Handoff

- Hand off to `$evidence-gate` when local evidence exists and you need a structured provisional result.
- Hand off to `$mode-gated-change` if shared-code or authority requirements emerge.
- Hand off to `$mode-live-rollout` if the task expands into live-risk external mutation.
