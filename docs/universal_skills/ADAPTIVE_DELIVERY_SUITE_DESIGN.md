# Adaptive Delivery Suite 设计基线

关联索引：[README.md](./README.md)  
关联使用手册：[ADAPTIVE_DELIVERY_SUITE_MANUAL.md](./ADAPTIVE_DELIVERY_SUITE_MANUAL.md)  
关联二轮复审：[ADAPTIVE_DELIVERY_SUITE_REVIEW_20260330.md](./ADAPTIVE_DELIVERY_SUITE_REVIEW_20260330.md)  
关联研究文档：[../research/UNIVERSAL_AGENT_DELIVERY_ROUTING_RESEARCH_20260330.md](../research/UNIVERSAL_AGENT_DELIVERY_ROUTING_RESEARCH_20260330.md)

## 文档状态

- 文档类型：设计基线
- 主要受众：技能设计者、主控编排者、repo policy 维护者
- 当前状态：Phase 1 core contract baseline 已稳定，repo adapter 与运行时落地仍待后续阶段单独收口
- 非目标：
  - 不实现当前仓库 adapter
  - 不引入运行时脚本
  - 不替代当前仓库已生效执行规范
  - 不在当前阶段直接打包为 Codex plugin

## 设计目标

`Adaptive Delivery Suite` 的目标不是取代所有 repo 的现有流程，而是在不同项目上统一回答四个问题：

1. 当前任务应该进入哪一种执行模式
2. 当前任务的验收标准从哪里来
3. 当前已有证据是否足以支撑下一步 gate
4. 当前 repo 的本地工件、PR/CI、spec 文件或 board 如何映射到统一抽象

本套件的关键原则是：

- `policy-driven routing`
- `policy-derived, model-assisted acceptance`
- `evidence before verdict`
- `mode-specific artifact burden`
- `adapters over repo-specific core concepts`
- `authority separation over agent optimism`

## 核心对象

通用层统一只定义以下对象：

- `task_spec`
- `risk_profile`
- `acceptance_contract`
- `change_evidence`
- `validation_evidence`
- `release_decision`
- `route_decision`
- `gate_result`

当前仓库或其他项目中的任何本地工件，都必须通过 adapter 映射到这些对象，而不是直接把本地命名提升为通用协议。

## 套件组成

### 核心技能

1. `workflow-router`
2. `acceptance-analysis`
3. `evidence-gate`

### 模式技能

1. `mode-analyze-only`
2. `mode-fast-loop`
3. `mode-gated-change`
4. `mode-live-rollout`

### 配套文档对象

- `RISK_PROFILE_SCHEMA`
- `ACCEPTANCE_CONTRACT_SCHEMA`
- `ROUTE_DECISION_SCHEMA`
- `GATE_RESULT_SCHEMA`
- `RELEASE_DECISION_SCHEMA`
- `AUTHORITY_MATRIX`
- `ADAPTER_CONTRACT`

## Phase 边界

### Phase 1：core contract baseline

本阶段只收口以下内容：

- `route_decision`、`risk_profile`、`acceptance_contract`、`gate_result`、`release_decision`
- `AUTHORITY_MATRIX`
- 手册中的 mode / authority / evidence vocabulary
- 能体现风险分界的 golden examples，尤其是 docs-only 与 safety-boundary docs 的对照样例

本阶段的完成条件不是“已经可以插件化”或“已经有运行时 adapter”，而是：

1. schema、design、manual、examples 对核心 contract 的表达一致
2. `docs-only` 与“改变 safety / approval / release / permission boundary 的文档任务”被清晰区分
3. `authority`、`evidence freshness`、`scope-limited success` 不再只停留在散文描述，而是进入 contract 结构

### Phase 2：adapter 与运行时后续

以下内容明确不属于本阶段：

- 当前仓库 `TaskCard/ChangePack/EvidencePack/ReviewPack/EnvSnapshot` adapter 映射
- `.agents/skills/*` 的真实运行逻辑、prompt、tool 选择或权限边界实现
- CI / eval runner / runtime hooks
- Codex plugin packaging 与分发载体

## 模式模型

### Base Modes

```yaml
base_mode:
  - analyze_only
  - fast_loop
  - gated_change
  - live_rollout
```

### Overlays

```yaml
overlays:
  - contract_missing
  - contract_ambiguous
  - manual_gate
  - human_review_required
  - multi_agent_allowed
  - background_agent_allowed
  - fresh_env_snapshot_required
```

### 设计说明

- `base_mode` 用于回答“这项任务本质上属于哪一种工作流”
- `overlays` 用于回答“这项任务额外叠加了哪些限制或升级条件”
- `controller-only` 与 `controller-with-delegation` 不属于通用层主模式，它们是 specialized controller skill 的运行方式

### `multi_agent_allowed` overlay

`multi_agent_allowed` 不是默认能力，而是显式升级。

只有同时满足以下条件时，才应叠加该 overlay：

- 任务已经被切分成边界清晰的子任务
- 子任务写集不重叠，或顺序关系已经定义清楚
- 每个子任务的输入契约和输出契约可独立检查
- 主控只负责编排、汇总、去重和一致性检查，不越权代做子任务
- 多 agent 带来的收益大于上下文、合并和验证成本

若以上条件不满足，`SHOULD` 保持单线程执行，即使任务本身属于 `gated_change`。

## 技能职责边界

## `workflow-router`

职责：

- 读取 `task_spec`、repo policy、已知风险输入
- 生成 `risk_profile`
- 生成 `route_decision`
- 说明升级原因、required gates、forbidden actions、required artifacts、authority requirements、required handoff

不得：

- 实现业务代码
- 发出最终验收或发布 verdict
- 用聊天上下文替代 policy sources

## `acceptance-analysis`

职责：

- 读取权威标准来源
- 生成 `acceptance_contract`
- 标注缺失项、冲突项、不可自动化项
- 规划测试组合、scenario 层验收和 gate 组合

不得：

- 自行发明权威验收标准
- 在 contract 缺失时默认“可继续”
- 用“现有测试都过了”代替 acceptance contract

## `evidence-gate`

职责：

- 汇总当前 `change_evidence` 与 `validation_evidence`
- 将证据映射到 `acceptance_contract`
- 判断哪些 gate 已满足、哪些 gate 未满足
- 输出带 authority、freshness、provenance 的 `gate_result`

不得：

- 让 evidence 缺口被聊天总结掩盖
- 把 blocker 与 verdict 混为一谈
- 在 authority 不满足时发正式 `pass`

## 模式技能

### `mode-analyze-only`

职责：

- 做只读分析、差异评估、风险识别、契约补全前置工作

适用：

- `contract_missing`
- 需求歧义
- 方案比较
- 不宜立即改动的复杂 repo

### `mode-fast-loop`

职责：

- 以 TDD / deterministic local checks 驱动开发内环

适用：

- 局部逻辑修复
- docs-only
- 可逆、小范围、低副作用变更

### `mode-gated-change`

职责：

- 组织受控 shared change，准备 reviewable diff 与受控 validation

适用：

- 共享代码
- 公共 API
- 跨模块 refactor
- auth/security/infra

### `mode-live-rollout`

职责：

- 组织高副作用动作的 rollout plan、approval、live evidence 与 rollback readiness

适用：

- 生产或生产邻近写操作
- schema/data migration
- feature flag 暴露
- secrets、资金、交易、支付等高后果变更

## 路由策略

## 风险画像驱动

所有模式选择 `MUST` 基于 `risk_profile`，而不是模型主观“感觉安全”。

最低要求字段见 [RISK_PROFILE_SCHEMA.md](./contracts/RISK_PROFILE_SCHEMA.md)。

## 固定路由优先级

1. 若缺少足够 `authoritative_sources`，返回：
   - `base_mode=analyze_only`
   - overlay `contract_missing`
2. 若存在权威来源但互相冲突，返回：
   - `base_mode=analyze_only`
   - overlay `contract_ambiguous`
3. 若 `external_state_mutation=true` 且满足任一高后果条件，返回：
   - `base_mode=live_rollout`
4. 若满足共享变更、高验证难度、低回滚信心、跨边界变化条件，返回：
   - `base_mode=gated_change`
5. 否则返回：
   - `base_mode=fast_loop`

## 高后果条件

满足任一项应直接升格到 `live_rollout`：

- `prod_exposure` 不为 `none`
- `human_harm_or_financial_impact=high`
- `external_state_mutation=true` 且 `reversibility` 不是 `easy`
- 涉及真实资金、交易、支付、账户权限、secrets
- 涉及 schema/data migration
- 需要 background agent 且运行于联网或远端环境

## 升格到 `gated_change` 的条件

满足任一项即可升格到 `gated_change`：

- `cross_boundary_change` 非空
- `rollback_quality` 为 `weak` 或 `unknown`
- `validation_difficulty=high`
- `security_privacy_sensitivity` 不为 `low`
- `runtime_dependency` 不为 `none`
- `runtime_volatility=high`
- 需要独立 reviewer 或 code owner
- 影响 shared branch 或公共 artifact

## docs-only 边界

`docs-only` 不是天然 `fast_loop`。

只有同时满足以下条件时，文档任务才可以保持在 `fast_loop`：

- 不改变 safety、approval、release 或 permission boundary
- 不改写 prompt / tool routing / handoff contract
- 不把文档本身变成新的 authoritative acceptance source
- 不要求 operator、reviewer 或 approver 依据该文档执行高风险动作

满足以下任一项时，文档任务 `SHOULD` 至少升格到 `gated_change`：

- runbook、template、policy 文档改变了 safety / approval / release boundary
- prompt、tool schema、tool routing、permission hint 的文档口径发生变化
- 文档将被当作 operator、reviewer 或 approver 的正式行动依据
- 文档修订会改变非豁免 gate 的定义或通过口径

## 硬停止条件

以下情况 `MUST` 返回只读分析或阻断，不得继续自动推进：

- `acceptance_contract` 无法可靠生成
- 缺少 deterministic checks
- 缺少 live health signal
- 缺少 environment approval path
- 缺少 rollback path
- evidence 来源不可信或无法复现

## 验收契约模型

`acceptance_contract` 由 `acceptance-analysis` 生成，来源优先级为：

1. 任务级 acceptance
2. repo 级 policy
3. branch / environment / CI / release gate
4. API/data/protocol contract
5. 安全与合规要求
6. 套件默认建议

### 冲突策略

若高优先级来源与低优先级来源冲突：

- `MUST NOT` 由模型自行裁定
- `MUST` 输出 `contract_ambiguous`
- `SHOULD` 回退到 `analyze_only`

### 场景层表达

对于 feature、migration、rollout、agent routing，以及会改变 safety / approval / release 边界的 docs/policy 任务，`acceptance_contract` 不应只保留平面的 checks 列表。

`SHOULD` 同时提供：

- `acceptance_scenarios`
- `gate_definitions`
- `required_authorities`
- `evidence_freshness`

这样才能把 TDD 内环、独立验证和最终放行分开表达。

## Authority Matrix

统一把 authority 分为三层：

- `execution_authority`
- `validation_authority`
- `release_authority`

详细定义见 [AUTHORITY_MATRIX.md](./contracts/AUTHORITY_MATRIX.md)。

### 原则

- 模型可以拥有受限的 execution authority
- 模型可以辅助 validation，但不能单独拥有最终 release authority
- 风险越高，release authority 越必须外部化到 reviewer、environment owner、resource owner 或明确 approver
- controller 可以编排 authority 流转，但不能代替正式 authority 角色

## Evidence 模型

所有 verdict 必须基于 evidence，而不是聊天描述。

### `change_evidence` 可能来源

- diff
- commit
- PR 描述
- 变更日志
- spec delta

### `validation_evidence` 可能来源

- unit/integration/contract test logs
- CI status checks
- eval results
- trace/logs
- rollout health metrics
- approval records
- env snapshot

### 证据要求

- 证据必须带来源与 artifact 路径
- 运行态证据 `SHOULD` 带时间信息和 environment 标识
- `fresh_env_snapshot_required` 出现时，不得用历史成功记录替代 fresh evidence

`gate_result` 结构见 [GATE_RESULT_SCHEMA.md](./contracts/GATE_RESULT_SCHEMA.md)。

正式放行结论不应和 `gate_result` 混写，最终放行对象见 [RELEASE_DECISION_SCHEMA.md](./contracts/RELEASE_DECISION_SCHEMA.md)。

## Adapter Contract

通用层不强行规定 repo 如何存储 truth，但 `adapter` 必须能回答以下问题：

- 哪些文件或对象承载 `task_spec`
- 哪些文件或对象承载 `change_evidence`
- 哪些文件或对象承载 `validation_evidence`
- 哪些系统或工件承载 `release_decision`
- 哪些来源承载 runtime health 与 approvals

详细契约见 [ADAPTER_CONTRACT.md](./contracts/ADAPTER_CONTRACT.md)。

## 多 Agent 编排原则

本套件默认支持“单主控 + 多子代理”的工作方式，但必须满足以下硬边界：

1. 主控 `MUST` 先通过 `workflow-router` 和 `acceptance-analysis` 把模式与契约稳定下来。
2. 子代理 `MUST` 在共享 schema、共享 authority vocabulary、共享结论词汇之下工作。
3. 主控 `MUST NOT` 让多个子代理同时改写同一组文件。
4. 子代理结果 `MUST` 回到主控统一收口，不能把多个子代理输出并列视为最终真相。
5. 若子代理之间产生冲突，主控 `MUST` 以通用契约和权威 policy 为准，而不是以“哪份稿件写得更像样”为准。
6. `multi_agent_allowed` 与 `background_agent_allowed` 只表示可受控编排，不改变 validation / release authority。

推荐切分方式：

- 按 write set 切分
- 按 mode 切分
- 按 contract / manual / examples 切分

不推荐切分方式：

- 多个子代理同时编辑同一份主设计文档
- 在 contract 尚未稳定前就并发执行实现型任务
- 让一个子代理同时承担实现、验收、放行三种责任

## 泛 quant 与 agent 开发适配

## 泛 quant

### 因子 / 研究 / 回测

- 默认倾向 `fast_loop`
- 若涉及共享研究框架、公共数据 schema、离线基准对账，升格到 `gated_change`

### 行情数据接入 / 订阅 / 缓存 / runtime state

- 默认倾向 `gated_change`
- 若需要真实运行态探测，应叠加 `fresh_env_snapshot_required`

### 交易、下单、broker session、资金写路径

- 默认 `live_rollout`
- 常与 `manual_gate` 组合出现

## Agent / Tooling

### prompt / tool routing / tool schema

- 默认 `gated_change`
- 若影响权限边界、联网工具或 background agent，则继续升格

### 多代理 handoff

- `MUST` 用显式 contract 和 evidence 检查 handoff 质量
- `SHOULD` 以 repo-specific evals 验证 instruction following 与 tool selection

## 反模式

本套件明确反对以下做法：

1. 把 orchestrator 变成全能执行者
2. 让模型自己发明 authoritative acceptance standard
3. 让 `fast_loop` 直接宣布 release pass
4. 用 board、ledger、聊天摘要替代证据本体
5. 对所有任务施加相同重型工件负担
6. 把 environment failure 写成 design pass
7. 把 background/remote/internet-enabled agent 当默认模式

## 实现顺序建议

1. 先稳定 core contract：schema、manual、examples、authority vocabulary
2. 再实现 `workflow-router`
3. 然后实现 `acceptance-analysis`
4. 再实现 `evidence-gate`
5. 最后实现 4 个模式技能
6. 等通用抽象稳定后，再为具体仓库补 adapter

## Plugin Readiness Gates

当前设计结论是：先维持 `repo-local skills + contracts`，不立即插件化。

只有同时满足以下条件时，才应重新评估是否包装成 Codex plugin：

1. 已有稳定的 packaging target，与当前 Codex CLI 的公开 plugin surface 对齐
2. 至少一个 repo adapter 和最小运行入口已经稳定
3. manifest ownership、versioning、compatibility policy 已明确
4. runtime hooks、artifact 路径、失败边界可被安装后稳定发现
5. plugin 只作为分发载体，而不拥有 release authority 或绕过 repo policy
