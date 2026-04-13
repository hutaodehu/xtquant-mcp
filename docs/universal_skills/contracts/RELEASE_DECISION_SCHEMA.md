# `RELEASE_DECISION_SCHEMA`

## 目的

`release_decision` 用于表达最终放行、拒绝放行、限制性放行等正式决定。

它与 `gate_result` 不同：

- `gate_result` 回答“当前证据是否满足当前 gate”
- `release_decision` 回答“哪一位 authority 基于哪些前提，是否允许进入下一发布边界”

## 最小结构

```yaml
release_decision:
  decision_scope: [local_iteration, independent_validation, release_gate]
  decision_type: [approved, rejected, deferred, limited_release]
  authority_role: [reviewer, approver, environment_owner, resource_owner, product_owner]
  authority_actor: string
  source_artifact: string
  decided_at: string
  constraints:
    - string
  rollback_preconditions:
    - string
  notes:
    - string
```

## 固定规则

- `release_decision` 必须来自外部 authority，而不是执行该变更的同一模型自封。
- `limited_release` 时，`constraints` 不得为空。
- `decision_scope=release_gate` 时，`source_artifact` `SHOULD` 指向正式 review、approval 或 environment gate 记录。
- 没有对应 authority artifact 时，不得伪造 `release_decision`。
