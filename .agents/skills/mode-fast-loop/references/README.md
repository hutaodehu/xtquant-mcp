# Fast Loop References

Read this file when you need the default boundaries for low-risk local execution.

## Use This Mode When

- the task is local, reversible, and low-risk
- deterministic local checks are enough for the next step
- no release authority is being claimed

## Preferred Validation Style

- failing test first when practical
- small deterministic checks
- small diffs
- explicit stop at provisional local validation

## Escalate Out Of This Mode When

- shared-code or reviewer gates become required
- external mutation appears
- rollout or approval work appears
- session state, runtime freshness, or environment volatility becomes material
- permission boundaries, secrets, or external accounts enter the task surface
- multi-agent or background-agent coordination becomes part of the execution plan
