# `GATE_RESULT_SCHEMA`

## 目的

`gate_result` 用于回答“当前证据是否满足当前 gate”，并把 `decision`、`blocker_class`、authority 缺口、证据新鲜度明确分离。

## 最小结构

```yaml
gate_result:
  decision:
    - provisional_pass_for_local_iteration
    - ready_for_independent_validation
    - gated_pass
    - blocked
    - not_authoritative_due_to_missing_contract
  blocker_class:
    - none
    - fail_env
    - fail_design
    - policy_missing
    - contract_ambiguous
    - approval_missing
    - evidence_missing
  satisfied_gates:
    - string
  unsatisfied_gates:
    - string
  validation_authority_satisfied: boolean
  release_authority_satisfied: boolean
  evidence_freshness:
    status: [fresh, stale, unknown, stale_ok]
    observed_at: string
    stale_after: string
  evidence_items:
    - gate: string
      source: string
      artifact_path: string
      captured_at: string
      environment_id: string
  gate_statuses:
    - gate: string
      scope: [local_iteration, independent_validation, release_gate]
      status: [pass, blocked, fail_env, fail_design, evidence_missing]
  degraded_but_truthful: boolean
  next_safe_step: string
```

## 固定规则

- `fast_loop` 不得输出 `gated_pass`。
- `validation_authority_satisfied=false` 或 `release_authority_satisfied=false` 时，`decision` 不得是正式 release pass。
- `blocker_class=fail_env` 不等于设计问题已解决。
- `decision=blocked` 时，`unsatisfied_gates` 不得为空。
- `acceptance_contract` 缺失时，`SHOULD` 输出 `not_authoritative_due_to_missing_contract + policy_missing`，而不是把它和普通 gate 阻断混写。
- 涉及 `runtime_state`、`external_write` 或 `production_adjacent` 的任务，若缺少 freshness 元数据，不得输出 release-level pass。
- `gated_pass` 只代表当前 gate 已满足，不等于最终 release decision。
- lower gate `pass` 不得覆盖 higher gate `blocked`；若存在这种情况，`degraded_but_truthful` `SHOULD` 为 `true`。
