# Acceptance Analysis Examples

Use example prompts like these:

- `Use $acceptance-analysis. Load the acceptance contract for this public API change.`
- `Use $acceptance-analysis. Normalize repo policy, CI, and schema rules into required checks.`
- `Use $acceptance-analysis. The contract is unclear; identify the missing gates and stop.`

Expected behavior:

- produce a structured `acceptance_contract`
- cite authoritative sources
- identify required checks and non-waivable gates
- derive scenario-level acceptance when the task crosses roles or user-visible behavior
- stop on missing or contradictory standards instead of inventing pass criteria
