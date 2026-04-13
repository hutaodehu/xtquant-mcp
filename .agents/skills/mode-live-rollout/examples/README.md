# Live Rollout Examples

Use example prompts like these:

- `Use $mode-live-rollout. Prepare this schema migration with approval, live health checks, and rollback readiness.`
- `Use $mode-live-rollout. Evaluate whether this real trade write path is ready for a controlled rollout.`
- `Use $mode-live-rollout. Fail closed if the runtime evidence or approval chain is incomplete.`

Expected behavior:

- explicit approval and authority handling
- fresh runtime or environment evidence
- bounded rollout reasoning
- blocked result when safety conditions are incomplete
