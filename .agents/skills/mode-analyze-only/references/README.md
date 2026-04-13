# Analyze Only References

Read this file when you need the explicit boundary for a read-only clarification pass.

## Use This Mode When

- the acceptance contract is missing or contradictory
- the correct execution mode is still unclear
- the task mixes incompatible risk levels
- the next safe step is more analysis, not implementation

## Stop Rules

- do not mutate repo-tracked files as implementation work
- do not run live or approval-requiring actions
- do not claim a release verdict

## Related Skills

- `$workflow-router`
- `$acceptance-analysis`
