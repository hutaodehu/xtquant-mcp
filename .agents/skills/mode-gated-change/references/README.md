# Gated Change References

Read this file when you need the default boundaries for shared or cross-boundary changes.

## Use This Mode When

- shared code or shared workflows are affected
- public or semi-public APIs change
- a change crosses module, schema, auth, security, or infra boundaries
- rollback confidence is not strong enough for a pure local loop

## Required Discipline

- keep the change reviewable and scoped
- align evidence with the `acceptance_contract`
- preserve explicit reviewer, CI, and policy gates
- stop before rollout approval
- preserve handoff contracts and agent-eval evidence when prompt, tool routing, or permissions change

## Escalate Out Of This Mode When

- the change mutates live or production-adjacent external state
- environment approvals become mandatory
- fresh runtime health or rollback evidence becomes required
