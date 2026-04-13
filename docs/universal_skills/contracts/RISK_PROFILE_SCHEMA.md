# `RISK_PROFILE_SCHEMA`

## 目的

`risk_profile` 用于回答“当前任务为什么进入某个模式”，而不是回答“模型是否有信心”。

它不仅要覆盖常规代码风险，还要覆盖 quant / agent 常见的 runtime state、权限边界、执行拓扑和证据新鲜度需求。

## 最小结构

```yaml
risk_profile:
  side_effect_surface: [none, local_edit, shared_code, external_read, external_write]
  external_state_mutation: boolean
  blast_radius: [low, medium, high]
  reversibility: [easy, partial, hard]
  rollback_quality: [strong, medium, weak, unknown]
  prod_exposure: [none, production_adjacent, production]
  security_privacy_sensitivity: [low, medium, high]
  validation_difficulty: [low, medium, high]
  cross_boundary_change:
    - [api, persistence, auth, infra, workflow, runtime_state, ui, docs]
  human_harm_or_financial_impact: [low, medium, high]
  execution_topology: [single_agent, multi_agent, background_agent, remote_agent]
  runtime_dependency: [none, env_snapshot, session_state, live_service, external_tooling]
  runtime_volatility: [low, medium, high]
  fresh_evidence_required: boolean
  privilege_surface: [none, local_fs, shell, network, secret, external_account]
  data_integrity_risk: [low, medium, high]
  long_running: boolean
  resume_sensitive: boolean
  recovery_class: [rollback, cancel_or_compensate, rebuild, forward_fix_only]
```

## 字段解释

- `side_effect_surface`
  - 当前改动的副作用面
- `external_state_mutation`
  - 是否会改变 repo 外的真实状态
- `blast_radius`
  - 一旦出错，影响范围的预估
- `reversibility`
  - 出错后是否容易撤回
- `rollback_quality`
  - 是否存在可信回滚路径
- `prod_exposure`
  - 是否会暴露到生产或生产邻近环境
- `security_privacy_sensitivity`
  - 是否涉及权限、认证、隐私、安全
- `validation_difficulty`
  - 是否难以通过 deterministic checks 验证
- `cross_boundary_change`
  - 是否跨 API、持久化、auth、infra、runtime state 等边界
- `human_harm_or_financial_impact`
  - 是否会带来明显人身、财务、交易或合规后果
- `execution_topology`
  - 执行拓扑是否涉及多 agent、后台 agent、远端 agent
- `runtime_dependency`
  - 是否依赖环境快照、会话状态、live service 或外部工具链
- `runtime_volatility`
  - runtime 状态是否波动明显，例如 broker session、lease、端口、订阅态
- `fresh_evidence_required`
  - 是否必须依赖 fresh probe / env snapshot，而不能复用旧证据
- `privilege_surface`
  - 是否触及 shell、network、secret、外部账户等权限面
- `data_integrity_risk`
  - 即使不直接外写，也是否存在数据污染、漂移或账实不一致风险
- `long_running`
  - 是否属于长时任务、durable job 或需要后台执行/轮询的流程
- `resume_sensitive`
  - 中断后是否必须显式 resume / cancel / rebuild，而不能简单重跑
- `recovery_class`
  - 恢复语义属于普通回滚、取消/补偿、重建，还是只能前向修复

## 固定约束

- `risk_profile` 不得缺失 `external_state_mutation`、`blast_radius`、`rollback_quality`、`execution_topology`、`runtime_dependency`。
- 任一字段无法确定时，`SHOULD` 使用保守值而不是乐观值。
- `external_state_mutation=true` 且 `human_harm_or_financial_impact=high` 时，`MUST` 触发 `live_rollout`。
- `fresh_evidence_required=true` 时，`SHOULD` 叠加 `fresh_env_snapshot_required`。
- `execution_topology` 为 `background_agent` 或 `remote_agent` 且存在非本地副作用时，`MUST NOT` 默认停留在 `fast_loop`。
- `runtime_dependency` 不为 `none` 且 `runtime_volatility=high` 时，`SHOULD` 至少升格到 `gated_change`。
- `long_running=true` 且 `resume_sensitive=true` 时，`SHOULD` 明确 durable job / resume / cancel 语义，而不是只写成普通本地循环。
