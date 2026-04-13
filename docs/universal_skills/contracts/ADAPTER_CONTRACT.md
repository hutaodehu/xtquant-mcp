# Adapter Contract

## 目的

`adapter` 的职责是把具体 repo 或平台中的本地 truth carriers 映射到通用对象。

## Adapter 必须回答的问题

1. 哪些对象承载 `task_spec`
2. 哪些对象承载 `change_evidence`
3. 哪些对象承载 `validation_evidence`
4. 哪些对象承载 `release_decision`
5. 哪些对象承载 `approval_sources`
6. 哪些对象承载 `runtime_health_sources`
7. 哪些对象承载 `runtime_state_sources`
8. 哪些对象承载 `resource_sources`
9. 哪些对象承载 `env_snapshot_sources`
10. 哪些对象承载 `staleness_sources`

## 最小结构

```yaml
adapter_contract:
  policy_sources:
    - string
  task_truth_carriers:
    - string
  change_evidence_carriers:
    - string
  validation_evidence_carriers:
    - string
  approval_sources:
    - string
  runtime_health_sources:
    - string
  runtime_state_sources:
    - string
  resource_sources:
    - string
  env_snapshot_sources:
    - string
  staleness_sources:
    - string
  final_release_sources:
    - string
```

## 示例 1：PR / CI adapter

- `task_truth_carriers`：issue、PR description、repo instructions
- `change_evidence_carriers`：diff、commit、PR metadata
- `validation_evidence_carriers`：CI checks、test logs、deploy previews
- `final_release_sources`：review state、branch policy、environment approvals

## 示例 2：OpenSpec-style adapter

- `task_truth_carriers`：`specs/`、`changes/`
- `change_evidence_carriers`：applied change artifacts
- `validation_evidence_carriers`：verify outputs、tests、CI
- `final_release_sources`：review + archive/sync gate

## 示例 3：TaskCard/ChangePack-style adapter

- `task_truth_carriers`：`TaskCard`
- `change_evidence_carriers`：`ChangePack`
- `validation_evidence_carriers`：`EvidencePack`、`EnvSnapshot`
- `runtime_state_sources`：runtime status、resource 回读、session / lease state
- `env_snapshot_sources`：`EnvSnapshot`
- `staleness_sources`：freshness timestamp、TTL、snapshot recency policy
- `final_release_sources`：`ReviewPack`、明确的外部 approval artifact 或 release gate owner artifact

说明：

- board、review state、Board Export、Board Sync 或 controller judgment 可以镜像 release 结论或驱动账本同步，但不应被泛化成 `final_release_sources` 本体。
- 若某个 repo 的 board workflow 同时承载了正式外部 approval artifact，adapter `MUST` 指向该 artifact 本身，而不是只写 board 状态字段。

## 当前仓库映射：`xtqmt-mcp` TaskCard/ChangePack adapter

当前仓库对通用 adapter 字段的 repo-local 映射如下。该映射用于回答“通用字段在本仓库由什么正式对象承载”，而不是替代仓库自身的执行规范。

```yaml
adapter_contract:
  policy_sources:
    - AGENTS.md
    - docs/EXECUTION_AND_ARTIFACT_STANDARD.md
    - docs/WORKFLOW_AND_BOARD.md
    - docs/ACCEPTANCE_STANDARD.md
  task_truth_carriers:
    - docs/task_cards/<TaskID>.md
    - Repo Spec Link target referenced by the TaskCard
  change_evidence_carriers:
    - docs/change_packages/<TaskID>.md
    - changed repo files or runtime artifacts explicitly cited by the ChangePack
  validation_evidence_carriers:
    - docs/evidence_packs/<TaskID>-<Role>-<YYYYMMDDHHMM>.md
    - docs/env_snapshots/<TaskID>-<YYYYMMDDHHMM>.md when the task requires env evidence
    - raw logs, state snapshots, and runtime artifacts linked from the EvidencePack
  approval_sources:
    - docs/reviews/<TaskID>-review-<YYYYMMDDHHMM>.md
    - explicit external approval artifacts linked by the ReviewPack when reviewer, environment owner, or resource owner approval is required
  runtime_health_sources:
    - runtime probes, health endpoints, and diagnostics linked from the EvidencePack or EnvSnapshot
  runtime_state_sources:
    - runtime state readbacks, session state, lease state, and resource readbacks linked from the EvidencePack or EnvSnapshot
  resource_sources:
    - repo-defined runtime resource outputs cited by the task spec, EvidencePack, or EnvSnapshot
  env_snapshot_sources:
    - docs/env_snapshots/<TaskID>-<YYYYMMDDHHMM>.md
  staleness_sources:
    - timestamps, TTL, and recency statements recorded in EvidencePack, EnvSnapshot, and linked raw artifacts
    - freshness rules defined by docs/ACCEPTANCE_STANDARD.md or the task-specific spec
  final_release_sources:
    - docs/reviews/<TaskID>-review-<YYYYMMDDHHMM>.md
    - release and gate requirements defined by docs/ACCEPTANCE_STANDARD.md
    - explicit external approval artifacts required by the task or environment
```

补充约束：

- `TaskCard` 是执行单元；`Repo Spec Link` 指向的设计或规范文档继续提供任务语义边界。两者共同构成当前仓库的 `task_truth_carriers`。
- `ChangePack` 负责描述变更范围、自测、已知风险和 handoff 输入；它可以引用修改文件或运行态 artifact，但不能替代独立 `EvidencePack`。
- `EvidencePack` 是独立验证的主载体；`EnvSnapshot` 是环境事实补充源，不因存在于 `validation_evidence_carriers` 中就自动等于正式通过。
- `ReviewPack` 是正式 release / rollback judgment 的主载体；board 上的 `Review Result`、`Accepted` 或其他状态字段只能镜像这个结果，不能反向代替它。
- `Board Export` 是 `RunLedger` 的只读快照，用于主控 reconcile；它不是 `task_truth_carriers`、`change_evidence_carriers` 或 `validation_evidence_carriers`。
- `Board Sync` 和 controller judgment 属于 control-plane 动作；它们可以根据既有工件更新账本，但不会因为“已经同步”就升级成角色工件或 `final_release_sources`。

## 当前未闭合缺口

- 当前仓库还没有单独落地一份 machine-readable adapter manifest；本映射目前由仓库文档共同承载，而不是单个 JSON/YAML 文件。
- `runtime_health_sources`、`runtime_state_sources`、`resource_sources` 的精确字段仍由 lane-specific 设计和证据文档决定，尚未统一成 repo-wide typed schema。
- `ReviewPack` 之外的外部 approval artifact 目前仍按任务逐案引用，尚未统一命名或统一落盘目录。
- repo-only 的 sync payload 或 board mirror 可以表达 ledger 状态，但它们不承载最终 release authority，也不构成 `final_release_sources` 的替代。

## 固定规则

- adapter 不能改变通用 schema 的语义，只能做映射。
- adapter 不能把 board 或聊天摘要当作唯一 truth carrier。
- adapter 若无法稳定映射某一类 authority 或 evidence，必须显式返回缺口。
- 若 repo 存在显式 runtime state 或 resource 回读，adapter `SHOULD` 优先映射它们，而不是把它们压缩进普通 health check 文本。
