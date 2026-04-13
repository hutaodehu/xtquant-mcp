# Fast Loop Examples

Use example prompts like these:

- `Use $mode-fast-loop. Fix this local parsing bug with TDD.`
- `Use $mode-fast-loop. Update these setup docs and run a consistency check.`
- `Use $mode-fast-loop. Refactor this internal helper and stop at local validation.`
- `Use $mode-fast-loop. Keep this quant factor transform in a deterministic fixture-driven loop.`

Expected behavior:

- small scoped implementation
- local deterministic validation
- no release-level pass claim
- explicit escalation when runtime state, permissions, or multi-agent coordination becomes relevant
