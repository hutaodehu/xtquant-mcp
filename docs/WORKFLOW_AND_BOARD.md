# 协作流程与任务看板规则

本文件定义 `xtqmt-mcp` 的任务协作机制。外部看板是主工作面，仓库文档是规则源。即使后续接入 Notion、Jira 或其他工具，字段语义、状态机和放行规则都应保持一致。

与 [EXECUTION_AND_ARTIFACT_STANDARD.md](./EXECUTION_AND_ARTIFACT_STANDARD.md) 的关系如下：

- 本文件定义看板字段、状态机和流转条件。
- 执行与工件规范定义 TaskCard、ChangePack、EvidencePack、ReviewPack、EnvSnapshot 和 Codex CLI 编排纪律。
- 看板负责 ledger，不替代 artifact 本体。

## 协作原则

1. 外部看板负责任务流转、责任归属和优先级排序。
2. 外部看板是 ledger，不是 ChangePack 或 EvidencePack 的替代品。
3. `TaskCard.Status` 是本地镜像字段，不是 live board truth。
4. 仓库文档负责定义规则、验收标准、模板和术语。
5. 每个任务都必须能从外部看板追溯到仓库内 spec、ChangePack、EvidencePack、ReviewPack 或审查记录。
6. 没有关联文档的任务不能进入正式开发。

## 看板字段与 adapter 边界

外部看板负责暴露 ledger 字段，但这些字段与 repo adapter 的正式 truth carriers 不是一回事。

| 看板字段 | 对应 repo adapter 对象 | 边界 |
| --- | --- | --- |
| `Repo Spec Link` | `task_truth_carriers` 中的 spec target | 只提供链接，不替代 `TaskCard` 本体 |
| `Change Package Link` | `change_evidence_carriers` 主入口 | 看板只保存入口，正式内容仍在 ChangePack |
| `Evidence Pack Link` | `validation_evidence_carriers` 主入口 | 看板不承载原始证据细节 |
| `Review Pack Link` | `approval_sources` / `final_release_sources` 主入口 | 没有 ReviewPack 时不能只靠 `Review Result` 宣称放行 |
| `Env Snapshot Link` | `env_snapshot_sources` | 只做索引，不代替 EnvSnapshot 内容 |
| `Status` / `Review Result` | ledger mirror | 只能反映当前阶段与结论，不能单独生成 authority |

配套硬规则：

- `Board Export` 只镜像这些字段及状态，不升级为 `task_truth_carriers`、`change_evidence_carriers`、`validation_evidence_carriers` 或 `final_release_sources`。
- 主控的 `Board Sync` 只负责把既有工件结果写回 ledger，不负责制造这些工件。
- 若看板字段与底层 artifact 不一致，应优先判定为 `board_stale` 或 `artifact_incomplete`，而不是默认信任看板状态。
- 若底层 artifact 缺失，`Accepted`、`pass`、`needs_fix` 等看板字段都不能单独作为 release authority 依据。

## 必填字段

所有外部任务卡必须包含以下字段：

| 字段 | 说明 |
| --- | --- |
| `Task ID` | 稳定任务编号，供代码、文档、证据互相引用 |
| `Title` | 简明任务标题 |
| `Type` | `feature`、`bug`、`refactor`、`governance`、`investigation` |
| `Priority` | `P0`、`P1`、`P2`、`P3` |
| `Owner Role` | 当前总负责角色，固定为 `dev`、`test`、`review` 之一 |
| `Current Role` | 当前执行角色，固定为 `dev`、`test`、`review` 之一 |
| `Status` | 使用本文件定义的状态机 |
| `Blocking Reason` | 若阻断，使用固定枚举 |
| `Repo Spec Link` | 指向仓库内设计、审查或标准文档 |
| `Acceptance Gate` | 任务对应的最高验收 gate，例如 `G2`、`G4` |
| `Change Package Link` | 指向本任务的 ChangePack |
| `Evidence Pack Link` | 指向本任务最近一次正式 EvidencePack |
| `Review Pack Link` | 指向本任务最近一次正式 ReviewPack |
| `Env Snapshot Link` | 指向环境快照；普通任务可留空，高风险任务必填 |
| `Review Result` | `pending`、`pass`、`needs_fix`、`blocked` |

## 建议附加字段

若外部看板工具支持，建议再补以下字段：

| 字段 | 说明 |
| --- | --- |
| `Verifier` | 本任务独立测试或审查使用的主要验证器 |
| `Merge Owner` | 最终收口、合并或状态确认责任人 |
| `Scope In` | 本卡明确包含的范围 |
| `Scope Out` | 本卡明确排除的范围 |
| `Lane` | `data`、`trade`、`ops`、`validation` |
| `Risk Class` | `low`、`medium`、`high` |
| `Write Scope` | 用于并行冲突判断的模块标签 |
| `Automation Policy` | `auto_safe`、`manual_gate` |
| `Execution Class` | `dev_only`、`test_only`、`review_only`、`handoff_required` |
| `Controller Test Policy` | `none`、`delegated_test_required`、`controller_direct_required` |

对 `Controller Test Policy: controller_direct_required` 的 repo-local 任务卡，还应在正文头部补充条件字段：

- `Execution Packet Side`
- `Execution Packet Symbol`
- `Execution Packet Qty`
- `Execution Packet Price Mode`
- `Execution Packet Cancel Timeout`
- 可选 `Trade Config Path` / `Data Config Path` / `Trade Health URL` / `Data Health URL`

## 状态机

统一状态如下：

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `Backlog` | 已记录但未排期 | 任务已建卡 | 进入 `Ready` |
| `Ready` | 规则、目标、验收标准已明确 | 有 `Repo Spec Link`、`Acceptance Gate`，且任务已拆到可执行粒度 | 进入 `In Dev` 或 `Blocked` |
| `In Dev` | 正在实现或修订文档/代码 | 当前责任角色为开发 | 进入 `In Self-Test`、`Blocked` |
| `In Self-Test` | 开发自测阶段 | 开发已提交自测记录 | 进入 `In Independent Test`、`Blocked` |
| `In Independent Test` | 测试 agent 独立验收 | 有自测记录和证据入口 | 进入 `In Review`、`Blocked`、回退 `In Dev` |
| `In Review` | 审查 agent 做放行判断 | 独立测试已有结论 | 进入 `Accepted`、回退 `In Dev`、`Blocked` |
| `Blocked` | 当前无法推进 | 明确写出阻断原因 | 阻断解除后回到前一执行状态 |
| `Accepted` | 达到定义好的通过标准 | 测试和审查都已完成且有证据 | 终态 |

## 阻断原因枚举

`Blocked` 必须填写以下固定枚举之一：

- `design_blocked`
- `env_blocked`
- `broker_blocked`
- `connect_gate_failed`
- `xtdata_blocked`
- `session_blocked`
- `docs_blocked`

补充说明要落在任务卡正文里，不能只写一个枚举值。

`connect_gate_failed` 只用于像 `VAL-003` 这类已经进入 governed write、且正式 runtime truth 明确显示 same-call pretrade connect gate 失败的任务；更细的 `session_id`、采样序列和 `fail_env` / `fail_design` 判断仍必须写在任务卡正文与正式工件里。

## 角色流转规则

### 主控编排模式

- 主控只支持 `controller-only` 与 `controller-with-delegation` 两种模式。
- `controller-only`：主控做 reconcile、判断、render dispatch，然后停止，等待角色工件返回。
- `controller-with-delegation`：主控在显式授权多 agent 编排时，可把边界清晰的单步任务派给子代理，再基于返回工件继续 reconcile。
- 使用子代理时，模型门槛固定为 `gpt-5.4` + `high` 或更高；低于该门槛不得进入正式执行流。
- 两种模式下，主控都不得直接代做 `dev`、`test`、`review` 的角色工作。
- 两种模式下，主控都不得亲自补写 `ChangePack`、`EvidencePack`、`EnvSnapshot`、`ReviewPack` 来推动状态流转。
- 两种模式下，主控都可以同步外部看板 / RunLedger；这属于账本维护，不属于角色代做。
- 只要同步依据已经被现有工件闭合，主控应直接完成账本更新，而不是重复征求“是否同步”的确认。
- 看板中的 `Owner Role` / `Current Role` 仍只允许 `dev`、`test`、`review`；主控模式不是新的看板角色。
- controller judgment 只决定 reconcile、dispatch 和 sync 行为，不会替代 repo adapter 所要求的 `TaskCard`、`ChangePack`、`EvidencePack`、`ReviewPack`、`EnvSnapshot`。
- `controller direct test execution` 不是新的主控模式，而是特定高风险 live test 卡的 task-level policy。
- 当 `Controller Test Policy: controller_direct_required` 且卡片满足 `manual_gate + test_only + high risk` 时，主控可在显式人工触发下运行 `scripts/run_controller_direct_test.ps1`。
- 这类卡在 `select_next_safe_tasks.py` 中仍应停留在 `manual_resume_required`，不能进入普通 `dispatchable_candidates`。
- 主控亲测后，board 的 `Owner Role` / `Current Role` 仍保持 `test` / `review` 流转语义；是否放行仍以独立 `ReviewPack` 为准。

### 对账优先

- 若本地已经存在 `ChangePack`、`EvidencePack` 或 `ReviewPack`，主控在新一轮派单前应先做 reconcile。
- reconcile 的目标是识别 `board_stale`、`artifact_incomplete`、`conflict_needs_controller`，而不是直接继续派单。
- 未完成 reconcile 时，不应假设任务仍停留在 `Ready`。
- reconcile 使用的 `Board Export`、board status 和 sync payload 都属于 ledger 侧信号；若底层 artifact 缺失，它们不能补足 adapter 缺口。

### 开发阶段

- 开发开始前，任务必须已有 `Repo Spec Link`。
- 开发开始前，任务应已保留 `Change Package Link`，即使初始内容仍为空模板。
- 涉及会话模型、端口模型、写路径和订阅语义的任务，必须先关联审查文档或新增设计文档。
- 开发完成后必须提交自测记录，才能进入独立测试。

### 测试阶段

- 测试必须按 `docs/ACCEPTANCE_STANDARD.md` 对应 gate 执行。
- 测试不能只写“通过”，必须写清测试范围和证据。
- 测试开始前应能读取稳定的 ChangePack，而不是依赖聊天上下文拼装变更范围。
- 测试发现设计级问题时，结论应标为 `fail_design` 或 `blocked`，不能只写环境失败。
- 测试若形成正式结论，应回链到对应 EvidencePack 与必要的 EnvSnapshot。
- 若测试由主控按 `controller direct test execution` 真实执行，formal artifact 仍记为 `Role: test`，并必须带齐 executor metadata；这不会免除后续独立 review。

### 审查阶段

- 审查以 findings 为中心，不做泛泛总结。
- 审查发现 agent 心智模型会被误导时，必须回退任务到开发。
- 只有审查写明可放行，任务才能进入 `Accepted`。
- 审查若要求回退，必须明确目标状态和所依据的工件链接。
- 审查阶段应形成独立 ReviewPack，而不是只把结论留在看板评论里。
- 主控即使已经派出 review 子代理，也不得自行补写 ReviewPack 或提前宣布放行。

## 任务与文档的关联规则

- `feature` 或 `refactor` 任务至少关联一个设计或审查文档。
- `bug` 任务至少关联一个复现记录或审查文档。
- `governance` 任务至少关联一个规范文档。
- `investigation` 任务完成后，必须产出结论文档或补充到既有文档，否则不能关闭。

## 任务拆分执行标准

### 必须满足的拆分条件

- 一张任务卡只能有一个主目标。
- 一张任务卡必须能由开发一次完成、由测试独立验证、由审查独立判定。
- 一张任务卡必须能被一个 ChangePack 清晰描述边界。

### 必须拆成多卡的情况

- 同时涉及交易写路径和数据状态模型。
- 同时涉及会话模型和订阅模型。
- 同时涉及实现收口和 live smoke。
- 同时修改多个高耦合子系统且无法在一次测试中独立验收。

### 不推荐的任务标题

- “实现 MCP spec”
- “把交易网关都改好”
- “把文档和代码一起全部理顺”

### 推荐的任务标题

- `TG-001 order.place 唯一受控写路径收口`
- `DG-001 xtdata.status 分层 readiness 与 runtime endpoint`
- `DG-002 xtdata://leases/active 与 subscription lease 健康输出`
- `TG-002 session/account 单账户主契约统一`

## 推荐的首批任务

基于 `DESIGN_REVIEW_20260327.md`，建议第一批任务卡直接建立为：

1. 统一 `order.place` 写路径，收口到唯一受控实现。
2. 将 `xtdata` endpoint 从静态配置改为动态解析与诊断输出。
3. 重构交易 session owner，避免双 trader 实例共用 session。
4. 拆分只读 preflight 与写权限 preflight。
5. 统一单账户/多账户契约和相关 schema。
6. 将订阅能力降级为实验能力，直到 live smoke 证明成立。
7. 隔离实例真实状态与测试 fake 状态。

## 工具映射建议

当前外部工具尚未确定，因此先采用工具无关设计：

- 如果用 Notion：
  将状态、角色、阻断原因、验收 gate、Change Package Link、Evidence Pack Link 做成明确属性。
- 如果用 Jira：
  将状态机映射为 workflow，将阻断原因、验收 gate、Change Package Link、Evidence Pack Link 做成必填字段。
- 如果暂未定工具：
  先按 `docs/TEMPLATES.md` 建立任务卡正文格式，后续再迁移。
