# Workflow Router Examples

Use example prompts like these:

- `Use $workflow-router. Classify a docs-only change and choose the base mode.`
- `Use $workflow-router. This task changes a shared API and CI workflow. Produce a route_decision.`
- `Use $workflow-router. The task enables real external writes. Escalate conservatively.`
- `Use $workflow-router. Decide whether this plugin-packaging request is execution work or analyze-only.`

Expected behavior:

- docs-only or pure local deterministic changes usually route to `fast_loop`
- shared API or cross-module changes usually route to `gated_change`
- missing authority or missing contract usually routes to `analyze_only`
- conflicting authority or conflicting contract usually routes to `analyze_only` with `contract_ambiguous`
- live-risk external writes usually route to `live_rollout`
