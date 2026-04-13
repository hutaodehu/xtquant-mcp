# Analyze Only Examples

Use example prompts like these:

- `Use $mode-analyze-only. The task has no clear acceptance contract. Clarify the gaps.`
- `Use $mode-analyze-only. Compare two safe approaches before implementation.`
- `Use $mode-analyze-only. The rollout authority is unclear; stop and explain what is missing.`
- `Use $mode-analyze-only. Decide whether this suite is ready for plugin packaging and fail closed if the packaging target is not stable.`

Expected behavior:

- read-only reasoning
- explicit missing inputs
- recommendation for the next safe skill
- recovery-oriented checklist for leaving `analyze_only`
