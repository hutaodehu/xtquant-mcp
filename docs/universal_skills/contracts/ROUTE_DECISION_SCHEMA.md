# `ROUTE_DECISION_SCHEMA`

## 目的

`route_decision` 用于说明任务为什么进入某种模式，以及进入该模式后有哪些 gates、authority 边界、禁止动作和 handoff 要求。

## 最小结构

```yaml
route_decision:
  base_mode: [analyze_only, fast_loop, gated_change, live_rollout]
  overlays:
    - [contract_missing, contract_ambiguous, manual_gate, human_review_required, multi_agent_allowed, background_agent_allowed, fresh_env_snapshot_required]
  risk_level: [low, medium, high]
  reasons:
    - string
  required_gates:
    - string
  forbidden_actions:
    - string
  required_artifacts:
    - string
  authority_requirements:
    execution_authority:
      - [model, engineer, controller, operator]
    validation_authority:
      - [local_checks, ci, independent_tester, reviewer, product_owner]
    release_authority:
      - [reviewer, approver, environment_owner, resource_owner, product_owner]
  handoff_required_roles:
    - [controller, dev, test, review, approver, environment_owner, resource_owner, product_owner]
  next_skill: [mode-analyze-only, mode-fast-loop, mode-gated-change, mode-live-rollout, acceptance-analysis]
```

## 固定规则

- `base_mode` 必须唯一。
- `overlays` 可为空，但不能与 `base_mode` 冲突。
- `fast_loop` 下不得只剩 `release_authority=approver` 这一类重 gate authority 来证明通过。
- 若 `contract_missing` 或 `contract_ambiguous` 出现，`base_mode` 必须是 `analyze_only`。
- 若 `base_mode` 为 `gated_change` 或 `live_rollout`，`authority_requirements.validation_authority` 与 `handoff_required_roles` 不得为空。
- 若出现 `human_review_required` 或 `manual_gate`，`authority_requirements.release_authority` 不得为空。
- docs-only 任务若改变 safety、approval、release、tool-routing 或 permission boundary，`base_mode` `MUST NOT` 继续停留在 `fast_loop`。
- 当 acceptance contract 仍未稳定时，`next_skill` `SHOULD` 指向 `acceptance-analysis`，而不是直接进入执行型 `mode-*`。
- `multi_agent_allowed` 或 `background_agent_allowed` 只代表允许受控编排，不代表 authority 自动升级。
- `release_authority` 不能由当前执行者自动满足。
