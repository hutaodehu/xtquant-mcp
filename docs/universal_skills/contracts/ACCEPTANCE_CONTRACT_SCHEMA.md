# `ACCEPTANCE_CONTRACT_SCHEMA`

## 目的

`acceptance_contract` 用于回答“什么才算通过”，其内容来自外部权威来源，而不是模型自创标准。

它既要表达平面的 gate，也要表达 ATDD / BDD 风格的场景层，以区分：

- 开发内环 TDD
- 独立验证
- 最终 release acceptance

## 最小结构

```yaml
acceptance_contract:
  version: 1
  authoritative_sources:
    - string
  task_type: [docs, bugfix, refactor, feature, migration, rollout, investigation]
  risk_level: [low, medium, high]
  required_checks:
    - string
  non_waivable_gates:
    - string
  human_review_required: boolean
  environment_approval_required: boolean
  pass_thresholds:
    key: value
  evidence_required:
    - string
  acceptance_scenarios:
    - scenario_id: string
      goal: string
      stage: [local_iteration, independent_validation, release_gate]
      required_checks:
        - string
      required_evidence:
        - string
      required_authority:
        - string
  gate_definitions:
    - gate: string
      stage: [local_iteration, independent_validation, release_gate]
      threshold: string
      evidence:
        - string
      authority:
        - string
  gate_ladder:
    - gate: string
      stage: [local_iteration, independent_validation, release_gate]
      hard_stop_on_fail: boolean
  hard_stop_conditions:
    - string
  scope_limited_success_rules:
    - string
  runtime_truth_rules:
    - string
  required_authorities:
    execution_authority:
      - string
    validation_authority:
      - string
    release_authority:
      - string
  evidence_freshness: [stale_ok, fresh_required]
  missing_contract_policy: [fail_closed]
```

## 来源优先级

1. 任务级 acceptance
2. repo policy
3. branch / environment / CI gate
4. API/data/protocol contract
5. 安全与合规规则
6. 套件默认建议

## 固定规则

- `authoritative_sources` 为空时，不得生成 authoritative contract。
- 若高优先级来源和低优先级来源冲突，必须返回 `contract_ambiguous`。
- `missing_contract_policy` 默认应为 `fail_closed`。
- `human_review_required=true` 时，仅靠模型或本地 tests 不足以形成 release pass。
- `human_review_required=true` 时，`required_authorities.validation_authority` 或 `required_authorities.release_authority` 不得同时为空。
- `environment_approval_required=true` 时，`required_authorities.release_authority` 不得为空。
- `task_type` 为 `feature`、`migration`、`rollout` 或任务涉及跨角色/用户可见行为时，`SHOULD NOT` 只保留平面 `required_checks`；`SHOULD` 提供 `acceptance_scenarios`。
- 若 docs / runbook / template / policy 任务会改变 safety、approval、release、permission 或 handoff boundary，`SHOULD` 同样提供 `acceptance_scenarios`、`gate_definitions` 与 `scope_limited_success_rules`。
- 若任务涉及 agent/tool routing、permission hint 或 multi-agent handoff，`required_checks` 与 `evidence_required` `SHOULD` 包含 eval、trace review 或 permission-boundary evidence，而不应只保留普通文档检查。
- `required_authorities.release_authority` 为空时，不得对需要人工评审或环境批准的任务形成正式放行结论。
- `evidence_freshness=fresh_required` 时，后续 `gate_result` 必须能证明证据的新鲜度与来源。
- 若任务存在严格 gate 顺序、scoped success 或 runtime truth 约束，`gate_ladder`、`hard_stop_conditions`、`scope_limited_success_rules`、`runtime_truth_rules` `SHOULD` 被明确填充，而不是留给执行者自行脑补。
- 若任务存在严格 gate 顺序或 scoped success，`SHOULD` 使用 `gate_ladder` 与 `scope_limited_success_rules` 明确 lower gate pass 不代表 higher gate ready。
