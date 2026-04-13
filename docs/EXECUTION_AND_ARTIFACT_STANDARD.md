# 执行与工件规范

关联协作规则：[../AGENTS.md](../AGENTS.md)  
看板与状态机：[WORKFLOW_AND_BOARD.md](./WORKFLOW_AND_BOARD.md)  
验收标准：[ACCEPTANCE_STANDARD.md](./ACCEPTANCE_STANDARD.md)  
模板入口：[TEMPLATES.md](./TEMPLATES.md)  
当前设计规范：[MCP_DESIGN.md](./MCP_DESIGN.md)

## 目的

本文定义 `xtqmt-mcp` 的执行与工件规范，用于回答四个问题：

1. spec 应如何拆成可执行任务卡。
2. 开发、测试、审查三类 agent 单次任务结束后必须交付什么。
3. 外部看板、仓库文档和运行态 artifact 各自承担什么职责。
4. 使用 Codex CLI 时，何时适合单主线，何时适合多 agent 编排。

本文不替代具体实现 spec，不定义功能语义；功能边界仍以 [MCP_DESIGN.md](./MCP_DESIGN.md) 等规范文档为准。

## 与其他文档的关系

- [MCP_DESIGN.md](./MCP_DESIGN.md) 定义目标契约。
- [WORKFLOW_AND_BOARD.md](./WORKFLOW_AND_BOARD.md) 定义看板字段和状态机。
- [ACCEPTANCE_STANDARD.md](./ACCEPTANCE_STANDARD.md) 定义验收 gate 和结果词汇。
- [TEMPLATES.md](./TEMPLATES.md) 提供任务卡、ChangePack、EvidencePack、ReviewPack 等模板。
- [AGENTS.md](../AGENTS.md) 定义角色边界和交接纪律。

如果这些文档之间发生冲突，优先级如下：

1. `MCP_DESIGN.md`
2. `AGENTS.md`
3. `ACCEPTANCE_STANDARD.md`
4. `EXECUTION_AND_ARTIFACT_STANDARD.md`
5. `WORKFLOW_AND_BOARD.md`
6. `TEMPLATES.md`

## 通用 adapter 到本仓库工件链的映射

本节把通用 suite 的 adapter 字段落到当前仓库已有 artifact chain。它不改变现有角色纪律，只回答“每类 truth/evidence/release source 在本仓库由谁承载”。

| 通用字段 | 当前仓库正式承载对象 | 边界说明 |
| --- | --- | --- |
| `policy_sources` | `AGENTS.md`、`docs/EXECUTION_AND_ARTIFACT_STANDARD.md`、`docs/WORKFLOW_AND_BOARD.md`、`docs/ACCEPTANCE_STANDARD.md` | 定义角色、工件、ledger、gate 规则 |
| `task_truth_carriers` | `docs/task_cards/<TaskID>.md`、`TaskCard` 的 `Repo Spec Link` 目标 | `TaskCard` 承担执行边界，spec 文档承担任务语义和目标契约 |
| `change_evidence_carriers` | `docs/change_packages/<TaskID>.md`、由 ChangePack 明确回链的修改文件或实现 artifact | 开发自测可以写入 ChangePack，但不替代独立测试证据 |
| `validation_evidence_carriers` | `docs/evidence_packs/<TaskID>-<Role>-<YYYYMMDDHHMM>.md`、必要时的 `docs/env_snapshots/<TaskID>-<YYYYMMDDHHMM>.md`、以及被 EvidencePack 回链的原始 artifact | 正式独立验证以 EvidencePack 为主，EnvSnapshot 只补环境事实 |
| `approval_sources` | `docs/reviews/<TaskID>-review-<YYYYMMDDHHMM>.md`、以及被 ReviewPack 回链的外部 approval artifact | 没有 ReviewPack 或等价外部 approval，不得宣称正式放行 |
| `runtime_health_sources` | 被 EvidencePack/EnvSnapshot 回链的 health probe、诊断输出、运行态检查结果 | 运行态原始信号不是 board comment，也不是 ChangePack 摘要 |
| `runtime_state_sources` | 被 EvidencePack/EnvSnapshot 回链的 state/resource readback、session/lease 状态 | 需要按任务 spec 和 lane 语义解释 |
| `resource_sources` | task spec、EvidencePack、EnvSnapshot 中引用的 repo runtime resource 输出 | 资源回读要有可追溯 artifact 路径 |
| `env_snapshot_sources` | `docs/env_snapshots/<TaskID>-<YYYYMMDDHHMM>.md` | 用于高副作用、跨宿主、端口/权限相关任务 |
| `staleness_sources` | EvidencePack、EnvSnapshot、原始 artifact 中的时间戳/TTL/recency 信息，以及 `docs/ACCEPTANCE_STANDARD.md` 或 task spec 中的 freshness 要求 | 只写“今天测过”不算稳定 freshness source |
| `final_release_sources` | `docs/reviews/<TaskID>-review-<YYYYMMDDHHMM>.md`、`docs/ACCEPTANCE_STANDARD.md` 中适用 gate、以及任务要求的外部 approval artifact | `RunLedger` 的 `Accepted` 仅镜像最终结果，不反向代替 release source |

与上表配套的硬规则如下：

- `ChangePack` 的自测记录属于开发 truth，不属于独立 `validation_evidence_carriers`。
- `EvidencePack` 可以回链 `EnvSnapshot`、实例目录日志、状态快照和运行态 probe；这些原始 artifact 仍以被正式文档引用后才进入可审计证据链。
- `ReviewPack` 是 release decision 的正式载体；若任务还要求 reviewer 之外的 environment owner 或 resource owner 批准，相关 artifact `MUST` 被 `ReviewPack` 明确回链。
- `TaskCard.Status` 与 board status 都不是 release authority；它们只能反映阶段，不生成 authority。

## 非 authority / 非工件对象

以下对象在当前仓库中有明确用途，但不属于角色工件本体，也不自动成为通用 adapter 的 truth carrier：

- `RunLedger` / 外部看板：live 状态账本，负责状态、角色和链接镜像。
- `Board Export`：用于主控 reconcile 的只读 ledger 快照。
- `Board Sync`：主控把既有工件结论写回 ledger 的控制面动作。
- controller judgment：主控基于现有工件做的调度或同步判断，不替代 `ChangePack`、`EvidencePack`、`ReviewPack`、`EnvSnapshot`。
- 聊天摘要：可以辅助解释上下文，但不得成为唯一 truth carrier 或 release source。

## Adapter 缺口纪律

- 若某类 `runtime_health_sources`、`runtime_state_sources`、`resource_sources` 还没有 repo-wide typed schema，执行者 `MUST` 在 spec、ChangePack、EvidencePack 或 ReviewPack 中显式写出当前采用的具体 carrier。
- 若某项 external approval 只存在于流程要求而没有 artifact 落点，结论 `MUST` 标记为 gap，而不是视为已经满足。
- 若 controller 只能拿到 board mirror 而拿不到底层 artifact，`MUST` 视为 adapter 映射未闭合，不能把 ledger 状态当作独立证据。

## 正式对象

### `TaskCard`

`TaskCard` 是执行单元，不是总设计文档。

- 一张任务卡 `MUST` 只有一个主目标。
- 一张任务卡 `MUST` 能被开发一次完成、被测试独立验证、被审查独立判定。
- 一张任务卡 `MUST NOT` 同时承载多个高耦合主题，例如“把 Trade Gateway 全部理顺”。
- `TaskCard` 的 scope、依赖、风险和 artifact 链接 `SHOULD` 在仓库中维护。
- `TaskCard.Status` `MAY` 作为本地镜像字段存在，但 live phase truth `MUST` 仍以 `RunLedger` 为准。

当任务需要使用主控亲测入口时，`TaskCard` 还承担 controller-runner 的结构化输入接口。此时必须满足：

- `Controller Test Policy: controller_direct_required`
- `Automation Policy: manual_gate`
- `Execution Class: test_only`
- `Risk Class: high`
- 结构化 packet 字段齐备：
  - `Execution Packet Side`
  - `Execution Packet Symbol`
  - `Execution Packet Qty`
  - `Execution Packet Price Mode`
  - `Execution Packet Cancel Timeout`
- 可选的 host/runtime 覆盖字段可以补充：
  - `Trade Config Path`
  - `Data Config Path`
  - `Trade Health URL`
  - `Data Health URL`

这些字段只让主控能够受控执行一张高风险 live test 卡，不会创建新的 board role，也不会放宽后续 review authority。

### `RunLedger`

`RunLedger` 是任务的状态账本，默认由外部看板承担。

- 看板 `MUST` 记录状态流转、责任角色、优先级、链接和最终 verdict。
- 看板 `MUST NOT` 代替 ChangePack 和 EvidencePack。
- 看板评论 `MAY` 解释状态变化，但 `MUST NOT` 成为唯一证据载体。
- `RunLedger` `MUST` 被视为 live 状态账本；本地 artifact 则承担执行证据 truth。

### `Board Export`

`Board Export` 是外部看板 / `RunLedger` 的只读 JSON 快照。

- 主控在做正式 board-vs-artifact reconcile 时 `SHOULD` 优先使用 `Board Export`。
- `Board Export` `MUST` 至少携带 `task_id` 与当前 board status。
- `Board Export` `SHOULD` 同时携带 owner/current role、review result 和 artifact links。
- 若缺少 `Board Export`，主控 `MAY` 退回 `repo_only_recovery`，但这不替代正式账本 truth。
- `Board Export` `MUST NOT` 被视为 `task_truth_carriers`、`change_evidence_carriers`、`validation_evidence_carriers` 或 `final_release_sources` 的替代。

最小 contract 与样例见：

- `.agents/skills/spec-task-harness/references/board-json-contract.md`
- `.agents/skills/spec-task-harness/examples/board_export.sample.json`

### `Board Sync`

`Board Sync` 是主控把既有工件结论写回外部看板 / `RunLedger` 的控制面动作。

- `Board Sync` 属于主控职责，不属于 `dev`、`test`、`review` 的角色工件。
- `Board Sync` `MUST` 以现有 `ChangePack`、`EvidencePack`、`ReviewPack`、`EnvSnapshot` 为依据。
- 主控 `MUST NOT` 先补造角色工件再伪装成可同步状态。
- 若外部看板暂时不可写，主控 `SHOULD` 至少生成结构化同步清单或 JSON payload。
- `Board Sync` 完成后更新的是 ledger 镜像，不会把 controller judgment 升格成 `final_release_sources`。

最小 contract 与样例见：

- `.agents/skills/spec-task-harness/references/board-sync-contract.md`
- `.agents/skills/spec-task-harness/examples/board_sync.sample.json`

### `ChangePack`

`ChangePack` 是本次变更边界的正式说明。

- 开发阶段 `MUST` 产出或更新 ChangePack。
- ChangePack `MUST` 说明“实现了什么”和“没有实现什么”。
- ChangePack `SHOULD` 为测试和审查提供稳定输入，而不是让后续角色去拼聊天上下文。
- ChangePack 中的自测与引用文件属于开发阶段 change truth；它们 `MUST NOT` 被误读为独立测试已经完成。

### `EvidencePack`

`EvidencePack` 是一次执行或验收的正式证据包。

- 测试阶段 `MUST` 产出独立 EvidencePack。
- 审查阶段 `SHOULD` 引用测试阶段的 EvidencePack，并补充审查所需证据。
- EvidencePack `MUST` 记录原始结果、artifact 路径和最终 verdict。
- 若引用运行态 probe、日志、状态回读或 EnvSnapshot，EvidencePack `MUST` 明确这些 artifact 的时间与路径，否则不能稳定承担 `validation_evidence_carriers`。
- 若该次测试由主控按 `controller direct test execution` 真实执行，EvidencePack 仍写 `Role: test`，但还必须补充：
  - `Executor: controller direct test execution`
  - `Authorization Basis`
  - `Controller Judgment Link`
  - `Raw Runtime Capture`
  - `Gateway Recovery Output Link`

### `ReviewPack`

`ReviewPack` 是 review 角色的正式放行工件。

- 审查阶段 `MUST` 产出独立 ReviewPack。
- ReviewPack `MUST` 记录 findings、required fix、release decision 和必要的状态回退建议。
- ReviewPack `MUST NOT` 被看板评论或聊天摘要替代。
- 需要 reviewer 之外 approval 的任务，ReviewPack `MUST` 明确回链这些 approval artifact；否则 `final_release_sources` 仍视为未闭合。

### `EnvSnapshot`

`EnvSnapshot` 用于记录执行宿主、权限、端口、配置和时间窗等环境事实。

- 跨 WSL / Windows、涉及外部端口或高副作用写路径的任务 `SHOULD` 记录 EnvSnapshot。
- 无 EnvSnapshot 时，测试或审查 `MUST` 谨慎区分 `fail_env` 与 `fail_design`。
- 若该次测试由主控按 `controller direct test execution` 真实执行，EnvSnapshot 也必须显式回链：
  - `Controller Judgment Link`
  - `Raw Runtime Capture`
  - `Gateway Recovery Output Link`

### `ReviewGate`

`ReviewGate` 表示人工或审查 agent 的正式放行门。

- `In Review` 阶段 `MUST` 有明确 findings、required fix 和 release decision。
- 高副作用路径 `MUST NOT` 跳过 ReviewGate 直接宣告 `Accepted`。

## 执行主线

默认执行顺序如下：

1. 从 spec 拆出任务卡。
2. 任务卡进入 `Ready`。
3. 开发 agent 实现并提交 ChangePack 与自测记录。
4. 测试 agent 基于任务卡、spec 和 ChangePack 做独立验证，提交 EvidencePack。
5. 审查 agent 基于 spec、ChangePack、EvidencePack 做放行判断。
6. 只有测试和审查都完成后，任务卡才能进入 `Accepted`。

若仓库中已经存在历史工件，主控在新一轮派单前 `MUST` 先执行 reconcile，而不是假设所有任务都从 `Ready` 开始。

这条主线的核心是：

- spec 是规范来源。
- TaskCard 是执行单元。
- 看板是账本。
- ChangePack 是变更说明。
- EvidencePack 是验证证据。
- ReviewPack 是审查放行证据。

## 任务拆分执行标准

### 必须拆卡的情况

以下情况 `MUST` 拆成多张任务卡，而不是作为一张总卡推进：

- 同时涉及交易写路径和数据状态模型。
- 同时涉及会话模型和订阅模型。
- 同时涉及实现收口和 live smoke。
- 同时修改多个高耦合子系统且无法在一次测试中独立验证。

### 适合单卡推进的情况

以下任务通常适合单卡推进：

- 收口唯一写路径
- 新增一个资源契约
- 重构一个状态输出
- 统一一组 schema 契约
- 清理一类测试污染并加验证

### 任务卡拆分判断标准

如果一张卡不能同时满足下面三条，就说明拆分还不够：

1. 开发 agent 可以在一次任务中完成。
2. 测试 agent 可以独立设计验收步骤。
3. 审查 agent 可以在不补需求决策的前提下给出 verdict。

### 当前仓库推荐的拆卡粒度

适合直接建卡的主题示例：

- `TG-001 order.place 唯一受控写路径收口`
- `DG-001 xtdata.status 分层 readiness 与 runtime endpoint`
- `DG-002 xtdata://leases/active 与 subscription lease 健康输出`
- `TG-002 session/account 单账户主契约统一`
- `TG-003 read-only preflight 与 write-permission preflight 拆层`

不推荐的任务标题示例：

- “实现 MCP spec”
- “把交易网关都改好”
- “把文档和代码全部理顺”

## 工件模型

### 最小交付组合

每张正式任务卡的最小交付组合如下：

1. 看板状态更新
2. 一个 ChangePack
3. 至少一个 EvidencePack

若任务已进入审查阶段，额外补：

4. 一个 ReviewPack

涉及跨宿主、外部端口或高副作用写路径时，额外补：

5. 一个 EnvSnapshot

### 推荐路径

本文不强制目录结构，但推荐如下命名方式：

- `docs/task_cards/<TaskID>.md`
- `docs/change_packages/<TaskID>.md`
- `docs/evidence_packs/<TaskID>-<Role>-<YYYYMMDDHHMM>.md`
- `docs/reviews/<TaskID>-review-<YYYYMMDDHHMM>.md`
- `docs/env_snapshots/<TaskID>-<YYYYMMDDHHMM>.md`

运行态原始 artifact `SHOULD` 继续落在实例目录下的 `logs`、`state`、`artifacts` 中，然后由 EvidencePack 回链。

### 角色交付要求

开发 agent 结束单次任务时 `MUST` 交付：

- 代码或文档变更
- ChangePack
- 开发自测记录
- 已知风险
- 待独立测试点

测试 agent 结束单次任务时 `MUST` 交付：

- 独立测试记录
- EvidencePack
- 失败分类
- 最终测试结论

审查 agent 结束单次任务时 `MUST` 交付：

- ReviewPack
- findings
- required fix
- release decision
- 必要的状态回退建议

## Reconcile First

当任务并非从零开始推进时，主控 `MUST` 先对账：

1. 扫描本地 `TaskCard`、`ChangePack`、`EvidencePack`、`ReviewPack`、`EnvSnapshot`
2. 与外部 `RunLedger` 当前状态比对
3. 先修正 `board_stale` / `artifact_incomplete` / `conflict_needs_controller`
4. 只有对账结果允许时，才继续派发下一张卡

## Codex CLI 编排规范

### 默认模式

默认推荐使用“单主控 + 多角色 agent”模式。

- 主控负责读取 TaskCard、分派角色任务、汇总工件链接和更新 RunLedger。
- 开发、测试、审查 agent 负责各自单次职责，不擅自改其他角色口径。
- 主控本身 `MAY` 由人工或一个独立窗口承担，但 `MUST NOT` 作为看板中的新角色枚举。

### 主控模式

本仓库的 harness 主控只支持两种模式：

1. `controller-only`
2. `controller-with-delegation`

另有一个任务卡级别的受控执行策略：

- `controller direct test execution`
- 它不是第三种主控模式
- 它只适用于 `manual_gate + test_only + high risk` 且 `Controller Test Policy: controller_direct_required` 的 live test 卡
- 它的入口是 `scripts/run_controller_direct_test.ps1`
- 它不会把此类任务放进普通 `dispatchable` 列表；repo-only reconcile 仍应返回 `manual_resume_required`

`controller-only` 的含义是：

- 主控先 reconcile 当前真实状态。
- 主控给出 next safe action。
- 若外部看板集成可用，且当前工件已经足以支撑账本更新，主控可直接同步 RunLedger。
- 如需继续，由主控渲染 bounded dispatch。
- 渲染完成后主控停止，不继续执行该角色工作。

`controller-with-delegation` 的含义是：

- 主控先 reconcile 当前真实状态。
- 主控选择下一步边界清晰的单步任务。
- 若外部看板集成可用，且当前工件已经足以支撑账本更新，主控可直接同步 RunLedger。
- 在用户显式授权多 agent 编排时，主控可以把该单步任务派给 `dev`、`test` 或 `review` 子代理。
- 子代理返回角色工件后，主控再做 artifact 检查与下一轮 reconcile。
- 只要派出子代理，其配置 `MUST` 不低于 `model=gpt-5.4` 且 `reasoning_effort=high`。

两种模式共同遵守以下硬规则：

- 主控 `MUST NOT` 自己代做 `dev`、`test`、`review` 的角色工作。
- 主控 `MUST NOT` 自己写 `ChangePack`、`EvidencePack`、`EnvSnapshot`、`ReviewPack` 来冒充子代理已执行。
- 主控 `MUST NOT` 在派出子代理后，又在本地继续完成同一个角色任务。
- 若下一步必须依赖真实角色执行，则 `MUST` 派对应子代理或切换到独立角色会话，而不是主控自己顶上。
- 子代理若低于 `gpt-5.4` / `high` 门槛，则 `MUST NOT` 用于本仓库的正式开发、测试、审查执行流。
- 外部看板 / RunLedger 的读写同步属于主控职责，不属于 `dev`、`test`、`review` 的角色工件。
- 若账本同步所需事实已经由现有工件闭合，主控 `SHOULD` 直接执行同步，而不是把该同步再拆成新的角色任务。
- 若缺少外部看板写入集成，主控 `SHOULD` 至少生成结构化同步清单，而不是把“是否应该同步”继续抛回用户。
- 若显式触发 `scripts/run_controller_direct_test.ps1`，主控是以真实执行者身份完成该张 `test` 卡，而不是冒充子代理；此时 formal artifact 仍必须满足 `Role: test` + executor metadata 契约，且后续独立 ReviewPack 仍不可省略。

常用触发词如下：

- `Use $spec-task-harness, controller-only. Reconcile first, then give the next safe action. Do not do role work directly.`
- `Use $spec-task-harness, controller-with-delegation. Reconcile first, then dispatch the next safe bounded step to child agents. The controller must not substitute for dev, test, or review.`

### 适合多 agent 的条件

只有同时满足以下条件时，才推荐并行多 agent：

1. 子任务切分已经明确。
2. 写集不重叠或合并责任人明确。
3. 共享账本存在。
4. verifier 或验收标准已经定义。

### 不适合多 agent 并行的场景

以下场景默认 `SHOULD` 采用单主线或显式审批：

- 最终写路径提交
- 高副作用交易动作
- 强依赖连续上下文的单点判断
- 尚未拆卡清楚的总任务
- 主控需要自己代做角色工件才能“看起来推进”

### 不推荐的工作方式

不推荐主要依靠“人工多开窗口、口头协调职责”的方式长期推进，因为这会削弱：

- 工件一致性
- 状态可追溯性
- 角色纪律
- 失败分类准确性

## 结果与放行纪律

- 开发完成 `MUST NOT` 等于正式通过。
- 测试完成 `MUST NOT` 等于设计放行。
- 审查未通过前，任务卡 `MUST NOT` 进入 `Accepted`。
- 缺少 ChangePack 或 EvidencePack 的任务 `MUST NOT` 宣称正式完成。

## 与实现无关但必须执行的纪律

- 所有结论继续使用 `pass`、`partial`、`blocked`、`fail_env`、`fail_design`。
- 所有工件 `MUST` 回链到 `Task ID`。
- 所有正式结论 `MUST` 区分设计问题与环境问题。
- 高副作用路径 `SHOULD` 保留审批与恢复语义，不依赖口头约定。
