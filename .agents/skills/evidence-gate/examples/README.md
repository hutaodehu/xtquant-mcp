# Evidence Gate Examples

Use example prompts like these:

- `Use $evidence-gate. Compare current CI and review evidence against the acceptance contract.`
- `Use $evidence-gate. Determine whether this fast-loop task is ready for independent validation.`
- `Use $evidence-gate. Report why this live rollout remains blocked.`

Expected behavior:

- return a structured `gate_result`
- separate `decision` from `blocker_class`
- list satisfied and unsatisfied gates
- refuse to infer a release pass when authority or evidence is missing
