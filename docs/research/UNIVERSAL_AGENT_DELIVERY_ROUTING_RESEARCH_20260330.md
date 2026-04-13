# 通用 Agent 交付路由与验收分析研究

关联当前仓库执行规范：[../EXECUTION_AND_ARTIFACT_STANDARD.md](../EXECUTION_AND_ARTIFACT_STANDARD.md)  
关联协作规范：[../WORKFLOW_AND_BOARD.md](../WORKFLOW_AND_BOARD.md)  
关联验收标准：[../ACCEPTANCE_STANDARD.md](../ACCEPTANCE_STANDARD.md)  
关联现状快照：[../CURRENT_STATUS.md](../CURRENT_STATUS.md)  
关联当前设计：[../MCP_DESIGN.md](../MCP_DESIGN.md)

## 文档状态

- 文档类型：研究与方案建议
- 主要受众：设计通用技能的维护者、agent 编排者、泛 quant 与 agent 开发团队
- 快照时间：2026-03-30
- 结论状态：建议稿，默认不直接替代当前仓库已生效规范
- 研究范围：
  - 通用任务路由模型
  - TDD 与验收标准的关系
  - 风险分级与模式升级
  - GitHub 上类似项目的可复用模式
  - 泛 quant 与 agent 开发工作的场景适配

## 一句话结论

可跨项目复用的技能体系不应把“任务路由、开发执行、测试验收、发布放行、账本同步”全部塞进一个巨型技能。更合理的架构是：

1. 一个负责模式选择的 `workflow-router`
2. 一个负责验收契约与测试组合的 `acceptance-analysis`
3. 一个负责证据判断与 gate 汇总的 `evidence-gate`
4. 一组按模式运行的执行技能，例如 `analyze_only`、`fast_loop`、`gated_change`、`live_rollout`
5. 针对具体仓库或平台的 adapter，例如 `TaskCard/ChangePack/EvidencePack` adapter、PR/CI adapter、OpenSpec adapter

## 研究问题

本轮研究聚焦以下问题：

1. 通用技能是否应该默认走“重型 harness 流”
2. 任务应该如何按风险级别路由到不同模式
3. TDD 驱动时，测试与验收标准是否可以交给模型自己判断
4. 是否需要把风险分析和验收分析拆成配套技能
5. 泛 quant 与 agent 开发场景下，什么任务适合快内环，什么任务必须升格到严格 gate

## 核心判断

### 1. 模式选择必须是 policy-driven，而不是 model-improvised

成熟工程组织和头部 agent 产品虽然表面形态不同，但底层原则一致：工作模式不是由模型“感觉”出来的，而是由预先定义的策略、权限和发布边界决定。

更准确地说：

- Google、GitHub、Microsoft 更偏向把模式选择写进分支、环境、审批、CI、发布流程
- OpenAI、Anthropic、Cursor 更偏向把模式选择写进 agent permissions、tool approval、sandbox、eval 规则

这两条路的共同点是：

- 模式选择必须外部化
- 风险越高，门禁越强
- 高风险任务的批准权必须与执行权分离
- “是否已经通过”不能由执行模型自己裁定

### 2. TDD 是开发内环，不是最终验收权威

TDD 非常适合作为默认内环，原因是：

- 反馈快
- 强迫开发者把接口、边界条件、失败路径想清楚
- 更贴近 small change / fast review / deterministic checks 的工程实践

但 TDD 只解决一部分问题：

- 代码层局部正确性
- 回归风险的早期暴露
- 公共 API 或内部接口的行为约束

TDD 不自动解决以下问题：

- 是否满足跨团队或跨角色验收标准
- 是否满足安全、权限、环境、上线、可回滚要求
- 是否可以对真实外部状态执行写操作
- 是否可以代替独立 reviewer 或资源 owner 的批准

因此，TDD 应该是 `fast_loop` 的默认工作法，但不应该被误用成“最终放行机制”。

### 3. 验收标准必须来自契约，模型只能辅助解释和执行

这轮研究最重要的结论之一是：

> 在通用技能里，模型不应该为自己发明 authoritative 的测试标准或验收标准。

正确的边界是：

- 规范性判断来自 policy、contract、CI、评审规则、环境审批规则
- 策略性判断可以由模型辅助，例如补哪些测试、先跑哪些测试、怎样把需求改写为可执行场景

如果仓库缺少明确验收契约，安全做法不是让模型“合理化通过”，而是返回：

- `contract_missing`
- `contract_ambiguous`
- `proposed_not_authoritative`

### 4. 工件要求应该随模式升级，而不是所有任务一刀切

重型工件不是没有价值，而是不应该成为所有任务的默认负担。

更合理的做法是：

- 低风险任务：最小证据即可
- 中风险共享变更：需要 review + CI + gate evidence
- 高风险 live 变更：需要 rollout、approval、health、rollback evidence

也就是说，工件策略要与模式耦合，而不是与“是否用了 agent”耦合。

## 外部实践综述

## Google

Google 的公开工程实践呈现出非常清晰的结构：

- 日常变更追求 small CL、快速 review、自动化 presubmit
- 代码评审的标准是“提升代码库健康度”，不是“追求完美而长期阻塞”
- 测试金字塔强调大量小测试，较少集成与 E2E
- 风险更高的变更进入 staged rollout / canary 路径

对通用技能的启发是：

- 默认模式应该偏向快内环，而不是默认重流程
- 真正需要重 gate 的是发布风险，而不是所有代码变更
- acceptance 应尽量以可执行检查为主，而不是叙述性总结

## GitHub 与 Microsoft

GitHub 和 Microsoft 的公开实践更像“强门禁、轻文书”：

- PR review、CODEOWNERS、status checks、branch policies、merge queue 负责 shared change gate
- environment approvals、safe deployment、tier-based rollout 负责 live gate
- 变更作者不能静默篡改环境级审批
- 自动化优先吸收大部分机械检查

对通用技能的启发是：

- 通用技能不要自己再复制一套平台已经提供的门禁逻辑
- 通用技能应该优先读取现有 repo / CI / environment policy
- 如果平台已有权威 gate，技能只需要做 adapter 和 evidence mapping

## OpenAI、Anthropic、Cursor

头部 agent 产品的公开实践同样没有走“所有任务默认超重流程”路线。

它们更重视：

- 只在真正需要时使用 agent，而不是能脚本化还要 agent 化
- 权限模式分层，例如只读分析、受限编辑、需要审批的命令执行
- sandbox 与 approval，避免高风险操作无边界自动执行
- evals、trace、logs、review 来提供可审计证据

对通用技能的启发是：

- agent 相关能力要先分模式，再分权限
- background agent、远程 agent、联网 agent 不应该被视为普通默认模式
- LLM grader 可以辅助，但不能代替权威验收标准

## 开源项目对比

以下项目提供了有价值的模式，但都不适合原样照搬。

### `gstack`

定位倾向：

- 面向 coding agent 的一套 workflow pack
- 强调角色化命令，例如 planning、engineering、review、QA、ship

可借鉴之处：

- review / QA / ship 的工作流建模
- 根据改动类型调整 QA 路线，而不是一套固定 checklist
- 更贴近 agent 使用体验的命令面

主要问题：

- 命令与 surface area 偏大
- 状态管理容易散在 repo 外
- 一旦加入很多角色流，复杂度会迅速上升

### `OpenSpec`

定位倾向：

- 更偏 repo-resident specs
- 用 `specs/` 与 `changes/` 分离“稳定规范”和“当前变更”

可借鉴之处：

- canonical spec 与 change pack 分离
- `propose / apply / verify / sync / archive` 这种显式生命周期
- 对 brownfield 仓库也能较自然接入

主要问题：

- 文件负担明显
- 容易让轻量任务也背上规范同步成本
- `/verify` 更偏一致性检查，不天然等于严肃验收 gate

### `get-shit-done`

定位倾向：

- 薄 orchestrator + specialized subagents
- 更强调执行波次、验证回路与人机协作

可借鉴之处：

- thin orchestrator
- worker 专职化
- 验证失败后不重开整条流程，而是返回 focused debug/fix loop

主要问题：

- 编排与状态的隐性复杂度很高
- 如果验证边界不够硬，容易出现“流程结束但验证没真正成立”
- manager 越权和 worktree/状态同步问题会被放大

### `Kiro`

定位倾向：

- 更明确地区分 `Specs` 与轻量开发流
- 对复杂 feature、复杂 bug 走 requirements / design / tasks 的规范化路径

可借鉴之处：

- 不是所有任务都默认走 spec flow
- feature 与 bugfix 可以使用不同 spec 颗粒度
- steering 与 spec 的角色区分相对清晰

主要问题：

- 如果团队把所有任务都升格成 spec，仍然会走向过重
- 若缺少 adapter，可能与既有 repo 规范脱节

## 统一抽象：不要把仓库本地工件名当成通用协议

如果目标是做跨项目技能，抽象层不应该直接使用：

- `TaskCard`
- `ChangePack`
- `EvidencePack`
- `ReviewPack`

这些名字可以继续在当前仓库使用，但通用协议更应使用中性对象：

- `task_spec`
- `risk_profile`
- `acceptance_contract`
- `change_evidence`
- `validation_evidence`
- `release_decision`

然后由 adapter 把这些抽象对象映射到不同项目的本地载体：

### 当前仓库 adapter

- `task_spec` -> `TaskCard`
- `change_evidence` -> `ChangePack`
- `validation_evidence` -> `EvidencePack`
- `release_decision` -> `ReviewPack`

### GitHub PR / CI adapter

- `task_spec` -> issue / PR description / repo instructions
- `change_evidence` -> diff / commit / PR metadata
- `validation_evidence` -> CI checks / test logs / deployment record
- `release_decision` -> review state / merge policy / environment approval

### OpenSpec adapter

- `task_spec` -> `specs/` + `changes/`
- `change_evidence` -> applied change artifacts
- `validation_evidence` -> `verify` outputs + CI
- `release_decision` -> `sync/archive` result + review approval

## 推荐的通用技能体系

## 1. `workflow-router`

职责：

- 读取风险输入、policy、task context
- 输出当前任务应进入哪一种 `base_mode`
- 说明为什么进入该模式
- 输出所需 gate、所需 evidence、禁止动作

不负责：

- 实现业务代码
- 写最终 review 结论
- 擅自放行高风险任务

建议输出结构：

```yaml
route_decision:
  base_mode: gated_change
  overlays:
    - human_review_required
  risk_level: medium
  reasons:
    - touches_public_api
    - cross_module_change
    - rollback_confidence_not_high
  required_gates:
    - unit
    - integration
    - ci_status_checks
    - independent_review
  forbidden_actions:
    - merge_without_review
    - background_agent
  required_artifacts:
    - change_evidence
    - validation_evidence
  acceptance_authority:
    - ci
    - reviewer
```

## 2. `acceptance-analysis`

职责：

- 加载权威标准来源
- 把需求、契约、CI、review policy 归一成 `acceptance_contract`
- 判断哪些要求是 hard gate，哪些是 advisory
- 当标准缺失或冲突时显式返回问题

不负责：

- 自行发明 authoritative 标准
- 在没有 contract 时直接宣布通过

建议子模块：

- `contract-loader`
- `risk-profiler`
- `test-portfolio-planner`
- `executable-spec-normalizer`
- `missing-contract-handler`

## 3. `evidence-gate`

职责：

- 汇总 tests、CI、logs、eval、review、deploy 健康信息
- 按 `acceptance_contract` 判断当前证据是否成立
- 输出结构化结论与缺口

不负责：

- 用聊天总结替代证据
- 把环境失败自动翻译成设计通过
- 绕过人类 reviewer 或资源 owner

建议输出结构：

```yaml
gate_result:
  decision: blocked
  blocker_class: fail_env
  satisfied_gates:
    - unit
    - integration
  unsatisfied_gates:
    - live_health_check
    - approver_signoff
  evidence:
    unit: reports/unit.xml
    integration: reports/integration.xml
    live_health_check: null
  notes:
    - deployment health signal not available
```

## 4. 模式执行技能

建议按模式拆开，而不是一个大技能兼容所有执行流。

### `analyze_only`

适用：

- 需求不清
- 验收契约缺失
- 风险识别阶段
- 只读调研与设计澄清

默认动作：

- 只读分析
- 不改代码
- 不宣称通过

### `fast_loop`

适用：

- 局部可逆改动
- 无外部副作用
- 无生产暴露
- 可以通过确定性本地测试验证

默认工作法：

- TDD / 小测试
- diff 小、反馈快
- 可由模型给出 `provisional_pass_for_local_iteration`

不允许：

- 直接发布
- 绕过共享仓库 gate
- 把本地自测当最终验收

### `gated_change`

适用：

- 共享分支变更
- 公共 API 变化
- 跨模块重构
- 安全、权限、基础设施、schema 等高协作任务

默认动作：

- 独立 review
- CI / status checks
- 明确 evidence
- 需要受控合并

### `live_rollout`

适用：

- 生产或生产邻近环境写操作
- feature flag 暴露
- schema / data migration
- secrets、权限、外部不可逆副作用
- 金融、支付、医疗、交易等高后果动作

默认动作：

- 环境批准
- staged rollout / canary
- bake time
- live health checks
- rollback 预案与回退条件

## 推荐的基础模式与 overlay

不建议把 `controller-only` 和 `controller-with-delegation` 作为通用模式主轴。它们更像控制器运行方式，而不是风险模式。

更通用的做法是：

```yaml
base_mode:
  - analyze_only
  - fast_loop
  - gated_change
  - live_rollout

overlays:
  - manual_gate
  - human_review_required
  - multi_agent_allowed
  - background_agent_allowed
  - contract_missing
  - fresh_env_snapshot_required
```

然后在具体仓库里再增加 controller 运行方式：

```yaml
controller_mode:
  - controller_only
  - controller_with_delegation
```

这样抽象更稳定，也更容易在不同项目上复用。

## 风险画像模型

任务路由的核心不应是“模型自信度”，而应是结构化的 `risk_profile`。

建议最少包含以下维度：

- `side_effect_surface`
- `external_state_mutation`
- `blast_radius`
- `reversibility`
- `rollback_quality`
- `prod_exposure`
- `security_privacy_sensitivity`
- `validation_difficulty`
- `cross_boundary_change`
- `human_harm_or_financial_impact`

示例：

```yaml
risk_profile:
  side_effect_surface: external_write
  external_state_mutation: true
  blast_radius: high
  reversibility: partial
  rollback_quality: weak
  prod_exposure: production_adjacent
  security_privacy_sensitivity: medium
  validation_difficulty: high
  cross_boundary_change:
    - api
    - persistence
  human_harm_or_financial_impact: high
```

## 推荐路由规则

建议通用技能采用 fail-closed 的升级逻辑：

1. 若 `acceptance_contract` 缺失，进入 `analyze_only + contract_missing`
2. 若涉及真实外部写状态、生产暴露、迁移、secrets、真实资金或安全边界，进入 `live_rollout`
3. 若涉及共享代码、公共 API、跨模块 refactor、低回滚信心、较高协作成本，进入 `gated_change`
4. 其余局部、可逆、确定性可验证任务进入 `fast_loop`

同时建议配置硬升级条件：

- `external_state_mutation=true`
- `prod_exposure` 不为 `none`
- `human_harm_or_financial_impact=high`
- `rollback_quality=weak`
- `validation_difficulty=high`
- 需要 background agent 或联网 agent

以及硬停止条件：

- 缺少 acceptance contract
- 缺少 rollback plan
- 缺少环境批准通道
- 缺少 deterministic checks
- 缺少可观察 health signal

## TDD、ATDD、BDD 与验收契约的关系

## TDD 该放在哪里

TDD 最适合放在 `fast_loop` 与部分 `gated_change` 的开发内环中。

TDD 能做的事：

- 用 failing test 迫使需求落地成行为
- 让模型优先围绕可验证行为编写实现
- 把回归风险压到小测试
- 改善接口设计

TDD 不应该承担的事：

- 代替环境级 gate
- 代替 reviewer / approver
- 代替发布决策
- 代替 live health signal

## ATDD / BDD 的位置

当任务跨角色、涉及业务行为或用户可见结果时，单纯 TDD 不够。

这时更适合引入：

- ATDD：预先定义 acceptance tests
- BDD：将行为要求写成协作式、可执行或半可执行的场景

对通用技能的价值是：

- 帮助 `acceptance-analysis` 把需求转成场景
- 帮助 `test-portfolio-planner` 识别哪些场景应进入 contract test、integration test、smoke test
- 减少模型把“实现细节”误当作“验收标准”的倾向

## 验收标准不该由模型拍脑袋

建议明确区分：

### Normative 决策

必须来自外部版本化契约：

- 什么行为必须成立
- 哪些 gate 不可豁免
- 谁拥有最终批准权
- 哪些证据是必须的
- 哪些阈值允许例外，谁可以批准例外

### Tactical 决策

可以由模型辅助：

- 哪些测试先写
- 哪些 suite 应先跑
- 哪些 case 需要补充
- 哪些 acceptance 场景当前未覆盖
- 怎样将模糊需求转成可执行场景

### 模型能说到什么程度

建议统一结论层级：

- `provisional_pass_for_local_iteration`
- `ready_for_independent_validation`
- `blocked`
- `fail_env`
- `fail_design`
- `not_authoritative_due_to_missing_contract`

不要让模型直接说：

- “已经验收通过”
- “可以发布”
- “默认视为没问题”

除非相应 authority 和 gates 已明确满足。

## 建议的验收契约模板

```yaml
acceptance_contract_version: 1
authoritative_sources:
  - AGENTS.md
  - docs/acceptance.md
  - .github/workflows/ci.yml
  - api/openapi.yaml
task_type: feature
risk_level: medium
required_checks:
  - unit
  - contract
  - integration
  - ci_status_checks
non_waivable_gates:
  - schema_compatibility
  - security_scan
human_review_required: true
environment_approval_required: false
pass_thresholds:
  unit: all_green
  contract: all_green
  integration: all_green
evidence_required:
  - test_logs
  - changed_contracts
  - review_record
missing_contract_policy: fail_closed
```

## 泛 quant 与 agent 开发场景适配

以下是本研究对泛 quant 与 agent 开发工作的落地建议。这里不是只针对本仓库，而是针对相近领域的常见工作类型。

## 场景 1：研究因子、特征工程、离线回测逻辑

典型特征：

- 多为离线代码与数据处理逻辑
- 主要风险是数值错误、数据泄漏、回测偏差
- 外部副作用相对低

建议模式：

- 默认 `fast_loop`
- 若影响公共研究框架或共享数据接口，可升格到 `gated_change`

推荐检查：

- unit tests
- deterministic fixture tests
- contract tests for factor / signal schema
- 与基准结果的差异摘要

不建议默认要求：

- 复杂人工审批
- live rollout 工件

## 场景 2：行情数据接入、订阅、缓存、lease、重连逻辑

典型特征：

- 运行时状态复杂
- 环境波动大
- 数据正确性受会话、端口、订阅状态影响

建议模式：

- 默认 `gated_change`
- 若变更只改纯解析逻辑，且有稳定 fixture，可先走 `fast_loop`
- 若需要真实实例或生产邻近探测，再叠加 `fresh_env_snapshot_required`

推荐检查：

- unit
- contract
- integration
- controlled runtime smoke
- env snapshot

风险提示：

- 环境失败与设计失败必须区分
- 不要把“端口没起来”误写成“功能设计失败”

## 场景 3：交易网关、下单路径、broker session、真实资金写路径

典型特征：

- 外部状态写入
- 财务影响高
- 环境依赖强
- 回滚常常不完美

建议模式：

- 默认 `live_rollout`
- `manual_gate` 通常应视为默认 overlay

推荐检查：

- local unit / contract / integration
- paper / sandbox / readonly smoke
- live approval
- live health metrics
- rollback readiness
- approver authority

强制要求：

- 模型不得自封通过
- 无 fresh evidence 不得外推 readiness
- 无 rollback plan 不得进入自动执行

## 场景 4：agent prompt、tool schema、tool routing、multi-agent handoff

典型特征：

- 代码改动不一定大，但行为不确定性高
- 容易影响工具选择、手工审批、权限边界

建议模式：

- 默认 `gated_change`
- 若涉及联网 agent、background agent、shell 权限放宽，可接近 `live_rollout` 的审慎级别

推荐检查：

- prompt / tool selection eval
- trace review
- handoff eval
- permission boundary tests
- failure-mode replay

额外建议：

- 对 agent 行为引入 repo-specific evals
- 不要用“跑通一次 demo”代替正式 acceptance

## 场景 5：文档、runbook、标准化模板

典型特征：

- 直接副作用低
- 但可能误导后续 agent 或人工操作

建议模式：

- 默认 `fast_loop`
- 若文档会改变高风险操作流程、发布流程或安全边界，则升格到 `gated_change`

推荐检查：

- link check
- command freshness
- consistency review
- 与当前 policy 的冲突检查

## 反模式清单

以下反模式在通用技能设计中应明确避免：

1. 让 orchestrator 自己代做 dev、test、review
2. 让模型自己定义“done”或“good enough”
3. 把 board、ledger、聊天摘要当作证据本体
4. 为所有任务强制同样的重型工件
5. 允许 `archive`、`complete`、`ship` 绕过验证
6. 把环境失败写成设计失败，或反之
7. 让 background / remote / internet-enabled agent 成为默认模式
8. 用单次手工 smoke 替代可重复证据
9. 把高层 E2E 变成默认主验证手段，而忽略低层可确定性验证
10. 让 repo 外隐藏状态成为 workflow 真相源，而 repo 只剩展示用文档

## 对当前仓库的直接启发

虽然本文讨论的是通用技能，但对当前仓库也有直接启发：

1. 当前 `spec-task-harness` 更适合作为 `gated_change` 与 `live_rollout` 的 adapter，而不是所有开发任务的默认主循环。
2. 当前仓库最值得保留的不是重工件本身，而是：
   - 角色边界清晰
   - `fail_env` 与 `fail_design` 区分
   - board 不是证据本体
   - 高副作用动作必须有 gate
3. 若要继续演进通用技能，建议先把本仓库的现有机制拆成：
   - 通用抽象层
   - 当前仓库 adapter
   - 交易/数据/validation 业务特有 gate

## 落地路线图

如果后续要把这一研究变成真正可复用的技能体系，建议按以下顺序落地：

### Phase 1：抽象层稳定

- 定义 `base_mode` 与 `overlays`
- 定义 `risk_profile` 与 `acceptance_contract` 数据结构
- 定义 `route_decision` 与 `gate_result` 统一输出

### Phase 2：拆技能

- 实现 `workflow-router`
- 实现 `acceptance-analysis`
- 实现 `evidence-gate`

### Phase 3：适配器

- 为当前仓库实现 `TaskCard/ChangePack/EvidencePack` adapter
- 为 GitHub PR / CI 仓库实现 PR adapter
- 如有需要，为 OpenSpec / Kiro 风格仓库实现 spec adapter

### Phase 4：先低风险试点

- 在 docs-only、pure logic、internal utility 上验证 `fast_loop`
- 在共享 API 或跨模块 refactor 上验证 `gated_change`
- 最后再接入 live-risk 任务

### Phase 5：引入 repo-specific evals

- 针对 agent/tool routing
- 针对 acceptance 场景覆盖
- 针对 handoff 质量
- 针对 reviewer summary 是否与证据一致

## 建议的最小文件集

如果要做成真正通用技能，建议最少有以下文件：

```text
.agents/skills/adaptive-delivery-router/SKILL.md
.agents/skills/acceptance-analysis/SKILL.md
.agents/skills/evidence-gate/SKILL.md
docs/policy/ACCEPTANCE_CONTRACT.md
docs/policy/RISK_ROUTING_POLICY.md
docs/templates/risk_profile.yaml
docs/templates/acceptance_contract.yaml
docs/templates/route_decision.yaml
docs/templates/gate_result.yaml
```

在具体仓库里，再决定是否补：

- board sync
- task cards
- change packs
- review packs
- env snapshots

## 参考资料

### 官方工程与产品资料

- Google Code Review Standard  
  https://google.github.io/eng-practices/review/reviewer/standard.html
- Google What to Look for in Review  
  https://google.github.io/eng-practices/review/reviewer/looking-for.html
- Google Speed of Code Reviews  
  https://google.github.io/eng-practices/review/reviewer/speed.html
- Google SRE: Reliable Product Launches  
  https://sre.google/sre-book/reliable-product-launches/
- Google SRE Workbook: Canarying Releases  
  https://sre.google/workbook/canarying-releases/
- GitHub Protected Branches  
  https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- GitHub Manage Environments  
  https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
- GitHub Merge Queue  
  https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/merging-a-pull-request-with-a-merge-queue?tool=webui
- GitHub Copilot Repository Instructions  
  https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions?tool=vscode
- GitHub Copilot Coding Agent  
  https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent
- GitHub Copilot Code Review  
  https://docs.github.com/en/copilot/concepts/agents/code-review
- Microsoft Branch Policies  
  https://learn.microsoft.com/en-us/azure/devops/repos/git/branch-policies?view=azure-devops
- Microsoft Approvals and Checks  
  https://learn.microsoft.com/en-us/azure/devops/pipelines/process/approvals?view=azure-devops
- Microsoft Safe Deployment Practices  
  https://learn.microsoft.com/en-us/devops/operate/safe-deployment-practices
- Microsoft Shift Testing Left  
  https://learn.microsoft.com/en-us/devops/develop/shift-left-make-testing-fast-reliable
- OpenAI Practical Guide to Building Agents  
  https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/
- OpenAI Evaluation Best Practices  
  https://platform.openai.com/docs/guides/evaluation-best-practices
- OpenAI Completion Monitoring  
  https://developers.openai.com/cookbook/examples/evaluation/use-cases/completion-monitoring
- OpenAI Eval-driven System Design  
  https://developers.openai.com/cookbook/examples/partners/eval_driven_system_design/receipt_inspection
- Anthropic Building Effective Agents  
  https://www.anthropic.com/engineering/building-effective-agents
- Anthropic Demystifying Evals for AI Agents  
  https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Claude Code Common Workflows  
  https://code.claude.com/docs/en/common-workflows
- Claude Code Security  
  https://code.claude.com/docs/en/security
- Cursor Modes  
  https://docs.cursor.com/agent/custom-modes
- Cursor Background Agents  
  https://docs.cursor.com/en/background-agents
- Cursor Agent Security  
  https://docs.cursor.com/account/agent-security
- Cursor Bugbot  
  https://docs.cursor.com/en/bugbot
- Cursor Building a Better Bugbot  
  https://cursor.com/blog/building-bugbot

### TDD / ATDD / BDD / 测试策略

- Agile Alliance: TDD  
  https://agilealliance.org/glossary/tdd/
- Agile Alliance: ATDD  
  https://agilealliance.org/glossary/atdd/
- Agile Alliance: Acceptance Testing  
  https://agilealliance.org/glossary/acceptance-testing/
- Cucumber BDD  
  https://cucumber.io/docs/bdd/
- Cucumber Documentation  
  https://cucumber.io/docs/
- Cucumber Better Gherkin  
  https://cucumber.io/docs/bdd/better-gherkin/
- Cucumber Examples  
  https://cucumber.io/docs/bdd/examples/
- Martin Fowler: The Practical Test Pyramid  
  https://martinfowler.com/articles/practical-test-pyramid.html
- Google Test Sizes  
  https://testing.googleblog.com/2010/12/test-sizes.html
- ISTQB CTAL-TA Syllabus v4.0  
  https://www.istqb.org/wp-content/uploads/sdm-uploads/ISTQB-CTAL-TA-Syllabus-v4.0-EN-4.pdf

### 类似项目与产品

- gstack  
  https://github.com/garrytan/gstack
- OpenSpec  
  https://github.com/Fission-AI/OpenSpec
- get-shit-done  
  https://github.com/gsd-build/get-shit-done
- Kiro Specs  
  https://kiro.dev/docs/specs/
- Kiro First Project  
  https://kiro.dev/docs/getting-started/first-project/
- Kiro Steering  
  https://kiro.dev/docs/cli/steering/
