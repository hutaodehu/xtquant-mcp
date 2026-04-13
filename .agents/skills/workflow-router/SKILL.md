---
name: workflow-router
description: Classify engineering tasks into `analyze_only`, `fast_loop`, `gated_change`, or `live_rollout` using explicit repo policy, task context, and risk signals. Use when Codex needs to choose the correct delivery mode before implementation, testing, or release work, especially for cross-boundary changes, unclear risk, missing contracts, shared-code changes, or live-risk operations.
---

# Workflow Router

Use this skill first when the correct delivery mode is not already fixed by the repo or the user.

This skill exists to answer one question only: what mode should this task enter, and why. It does not implement the task, define acceptance criteria on its own, or declare that any release gate has passed.

## Inputs

Load only the minimum sources needed to classify the task:

- task request, issue, ticket, spec, or diff summary
- repo policy files such as `AGENTS.md`, acceptance docs, CI config, or environment gate docs
- repo adapter docs when the project already defines truth carriers or runtime/resource sources
- any existing runtime or rollout constraints that affect safety
- any prior `acceptance_contract` or `risk_profile` already present for the task

If the task is already bound to a higher-order policy gate, do not override it locally.

## Outputs

Produce a structured `route_decision` with:

- one `base_mode`
- any required `overlays`
- the full `risk_profile`
- a concise `risk_level`
- explicit `reasons`
- explicit `required_gates`
- explicit `forbidden_actions`
- explicit `required_artifacts`
- explicit `authority_requirements`
- explicit `handoff_required_roles`
- explicit `next_skill`

If the contract is missing or contradictory, route to `analyze_only` rather than guessing.

## Base Modes

- `analyze_only`
  Use when scope, authority, or acceptance inputs are not stable enough to execute safely.
- `fast_loop`
  Use for local, low-risk, deterministic work that can stop at provisional local validation.
- `gated_change`
  Use for shared-code, cross-boundary, public-interface, infra, auth, or rollback-sensitive work that needs explicit review and CI-style gates.
- `live_rollout`
  Use for production or production-adjacent writes, migrations, secrets, feature exposure, or any high-consequence external mutation.

## Routing Rules

Apply these rules in order:

1. If authoritative acceptance sources are missing, output `analyze_only` with `contract_missing`.
2. If authoritative acceptance sources exist but conflict materially, output `analyze_only` with `contract_ambiguous`.
3. If the task mutates live or production-adjacent external state, affects real money or human-impact domains, or lacks a trustworthy rollback path, output `live_rollout`.
4. If the task touches shared code, public APIs, cross-module contracts, auth, security, infra, session/runtime state, or has weak rollback confidence, output `gated_change`.
5. Otherwise, use `fast_loop`.

Then derive overlays explicitly:

- add `fresh_env_snapshot_required` when fresh runtime evidence is required
- add `multi_agent_allowed` only when write sets are separated and handoff contracts are explicit
- add `background_agent_allowed` only when the execution topology is intentionally approved and auditable
- add `human_review_required` or `manual_gate` when repo policy or risk level requires external authority

Escalate conservatively. When a field is unknown, prefer the safer mode instead of the faster mode.

## Hard Stops

Stop and return a routing result instead of continuing execution when any of these are true:

- no authoritative acceptance source can be found
- authoritative acceptance sources conflict materially
- release authority is required but not discoverable
- live health signals are required but undefined
- the task mixes low-risk local work with high-risk rollout work in one unit
- the user asks for implementation before the correct mode is chosen

## Forbidden Actions

- Do not implement business code as part of routing.
- Do not invent acceptance authority or repo policy.
- Do not declare `gated_pass`, merge approval, or rollout readiness.
- Do not compress blocker type and decision into one label.
- Do not downgrade `live_rollout` to `fast_loop` just to keep work moving.
- Do not let `multi_agent_allowed` or `background_agent_allowed` imply authority elevation.

## Trigger Phrases

- `Use $workflow-router. Classify the task and choose the base mode.`
- `Use $workflow-router. Produce a route_decision with required gates and forbidden actions.`
- `Use $workflow-router. Escalate conservatively if the contract or authority is unclear.`

## References

- Read [references/README.md](./references/README.md) when you need the canonical mode vocabulary, routing signals, or cross-domain examples.
- Read [examples/README.md](./examples/README.md) when you need example prompts and expected routing outcomes.

## Handoff

- If the result is `analyze_only`, hand off to `$mode-analyze-only`.
- If the result is `fast_loop`, hand off to `$mode-fast-loop`.
- If the result is `gated_change`, hand off to `$mode-gated-change`.
- If the result is `live_rollout`, hand off to `$mode-live-rollout`.
- If the task lacks a stable acceptance source, ask `$acceptance-analysis` to normalize the contract before any implementation mode starts.
