# Adaptive Delivery Suite 使用手册

关联设计文档：[ADAPTIVE_DELIVERY_SUITE_DESIGN.md](./ADAPTIVE_DELIVERY_SUITE_DESIGN.md)  
关联二轮复审：[ADAPTIVE_DELIVERY_SUITE_REVIEW_20260330.md](./ADAPTIVE_DELIVERY_SUITE_REVIEW_20260330.md)  
关联 schema 与契约目录：[contracts/](./contracts/)  
关联 golden examples：[examples/](./examples/)

## 文档状态

- 文档类型：操作手册
- 主要受众：技能使用者、主控编排者、repo policy 维护者、泛 quant 与 agent/tooling 团队
- 当前状态：可作为首版通用技能组的正式使用说明；repo adapter 与运行时落地仍需单独 follow-up
- 非目标：
  - 不替代具体 repo 的执行规范或权限系统
  - 不直接定义运行时脚本或平台插件实现
  - 不把当前仓库的 `TaskCard`、`ChangePack`、`EvidencePack` 命名强行推广成跨项目标准

## 一句话心智模型

这套技能不是让模型“直接开干”的快捷键集合，而是一条受控链路：

1. 先判断任务该走哪种模式
2. 再明确什么才算通过
3. 再进入对应执行模式
4. 最后用证据对 gate 做判断

推荐默认顺序：

1. `workflow-router`
2. `acceptance-analysis`
3. 某个 `mode-*`
4. `evidence-gate`

## 为什么不是一个大一统重型技能

这套设计刻意没有把任务路由、开发执行、测试验收、发布放行、账本同步塞进一个巨型 skill，原因有三点：

1. 风险模式和执行动作不是同一个问题。`workflow-router` 负责回答“该走哪条路”，而不是“现在就改什么代码”。
2. TDD 与最终验收不是同一个问题。`mode-fast-loop` 可以用 TDD 驱动开发，但 authoritative acceptance 必须来自 `acceptance-analysis` 提取的外部契约。
3. 不同项目的 truth carrier 不同。GitHub PR、OpenSpec、TaskCard/ChangePack/EvidencePack 都只是 adapter，不应污染通用抽象层。

## 先用什么 skill

### 默认起点：`workflow-router`

几乎所有非纯聊天任务都应先走 `workflow-router`，尤其是：

- 只知道业务目标，不知道该走快内环还是重 gate
- 任务可能跨模块、跨接口或跨环境
- 任务涉及 agent 权限、联网工具、runtime state 或真实外部写操作
- 用户要求多 agent 并行，但尚未明确写集边界和 handoff 契约

推荐触发语：

- `Use $workflow-router. Classify the task and choose the base mode.`

### 什么时候紧接着用 `acceptance-analysis`

以下情况 `SHOULD` 紧跟 `workflow-router` 之后使用：

- 任务没有清晰的 acceptance standard
- 任务进入 `gated_change` 或 `live_rollout`
- 已有测试不少，但不清楚“绿了哪些才算过”
- 任务涉及 agent prompt/tool routing/permissions，需要把行为要求转成 eval 场景
- 任务涉及 quant runtime state，需要明确 runtime smoke、env snapshot 和 fresh evidence 边界

推荐触发语：

- `Use $acceptance-analysis. Load the acceptance contract and identify missing gates.`

### 什么时候只做 `mode-analyze-only`

适用：

- `contract_missing`
- `contract_ambiguous`
- 风险级别尚不稳定
- 任务混合了低风险开发和高风险 rollout，当前不可直接执行
- 只需要方案澄清、风险澄清、权责澄清

进入后应该输出：

- 当前未解决问题
- 不能继续自动执行的原因
- 需要谁补充 authority 或 policy
- 下一步应该回到哪个 skill

### 什么时候进入 `mode-fast-loop`

适用：

- 局部 bugfix
- 纯说明性 docs-only，且不改变 safety / approval / release / permission boundary
- 纯逻辑修复
- 小范围、可逆、确定性可验证改动
- 离线 quant 研究逻辑、小型 factor/feature 变更

默认工作法：

1. 先把需求改写成行为
2. 先找 failing test 或最小 deterministic check
3. 做最小实现
4. 再跑本地检查
5. 只停在 `provisional_pass_for_local_iteration` 或 `ready_for_independent_validation`

不应该做：

- 宣称最终 release pass
- 跳过 repo 现有 review/CI gate
- 把本地自测外推成 live readiness
- 把 runbook、template、policy、permission boundary 的修改误当成普通 docs-only

### 什么时候进入 `mode-gated-change`

适用：

- 共享代码
- 公共 API 或协议变化
- 跨模块 refactor
- auth/security/infra/schema 变化
- agent prompt/tool routing/permission 边界变化
- runbook、template、policy 文档改变 safety、approval、release 或 permission boundary
- runtime state 行为变化但尚未进入真实 live write

默认工作法：

1. 先确认任务仍然属于 shared change，而非 live rollout
2. 读取 `acceptance_contract`
3. 只实现本次 contract 涉及的 shared boundary
4. 补齐 review、CI、contract、integration 所需证据
5. 把 release authority 留给独立 reviewer、branch policy 或其他外部 gate

### docs-only 不是天然 `fast_loop`

如果文档修改满足以下任一项，就不应再按普通 docs-only 处理：

- 文档会改变 operator 的动作边界
- 文档会改变 reviewer / approver 的放行边界
- 文档会改变 prompt、tool routing、permission hint 或 handoff 规则
- 文档会成为新的 authoritative acceptance source

这类任务至少应进入 `mode-gated-change`，并配套：

- policy conflict check
- scenario-level acceptance
- independent review
- 必要时的 permission / handoff eval

### 什么时候进入 `mode-live-rollout`

适用：

- 生产或生产邻近写路径
- schema/data migration
- secrets、权限、真实账户、真实订单、真实资金
- 需要 live approval、rollback readiness、fresh runtime health

默认工作法：

1. 确认该任务无法停留在 `gated_change`
2. 读取 `acceptance_contract`
3. 验证 approver、environment owner、resource owner 等 authority
4. 先做 readonly / paper / sandbox / pre-live 证据
5. 只在批准边界内执行最小 blast radius 的 live 动作
6. 用 fresh evidence 再交给 `evidence-gate`

## 多 Agent 使用手册

推荐默认采用“单主控 + 多子代理”：

- 主控负责路由、契约、统一 vocabulary、派单、去重、冲突收敛
- 子代理负责边界清晰且写集不重叠的子任务
- 主控不应冒充 `dev`、`test`、`review` 的正式工件生产者

可以并发的典型切分：

- 设计草案与手册分开
- contract/schema 与 examples 分开
- 核心 skill 文案与 repo-specific adapter 文档分开
- 实现工作与验证工作分开

不应该并发的典型切分：

- 两个子代理同时写同一份主设计文档
- contract 还没稳定就并发写多个执行模式
- 让一个子代理同时承担实现、独立测试、最终放行

只有满足以下条件时，`workflow-router` 才应输出 `multi_agent_allowed`：

- 子任务输入输出边界已经定义
- 写集不重叠，或串行顺序已明确
- handoff 词汇和 schema 已统一
- 主控不会绕过 authority boundary

## TDD、ATDD、BDD 和验收契约怎么配合

### TDD 的正确位置

TDD 主要属于开发内环，尤其适合：

- `fast_loop`
- 一部分 `gated_change`
- 有稳定 fixture、稳定接口和确定性检查的 quant 离线逻辑

TDD 的价值：

- 让行为要求先落成可验证检查
- 压缩回归面
- 逼出更小 diff 和更清晰接口

TDD 不负责：

- 决定最终 release pass
- 替代 reviewer 或 approver
- 替代 live health signal
- 替代环境级 gate

### 什么时候需要 ATDD / BDD 风格场景

以下情况只靠 TDD 往往不够：

- 任务跨角色交接
- 任务改变用户可见行为
- 任务改变 agent 路由、tool selection、approval boundary
- 任务依赖 runtime state、broker session、subscription lease

这时 `acceptance-analysis` 应把需求转换为 `acceptance_scenarios`，每个 scenario 至少要回答：

- 哪个行为必须成立
- 由哪些 checks 证明
- 需要哪些 evidence carrier
- evidence 是否必须 fresh
- 哪些 authority 才能宣布该 scenario 通过

### 模型可以判断什么，不能判断什么

模型可以辅助：

- 先写哪些测试
- 哪些 suite 成本最低且最能证明行为
- 哪些 acceptance 场景尚未被测试覆盖
- 怎样把模糊需求改写为可执行场景

模型不能擅自决定：

- authoritative acceptance standard
- 非豁免 gate 是否可跳过
- 谁拥有最终 release authority
- 缺少 fresh evidence 时是否“默认也算过”

## 产品验收视角下的落地要求

从产品验收和 agent 交付视角看，这套技能至少要回答以下问题：

1. 任务为什么进入这个模式，而不是更轻或更重的模式
2. 当前 acceptance contract 从哪里来
3. 哪些 gate 是非豁免 gate
4. 哪些结果只是开发内环自测，哪些结果可以进入独立验证
5. 若失败，是 `fail_env`、`fail_design` 还是 authority/policy/evidence 缺口
6. 用户可见行为或公共接口变化是否还需要 product owner / consumer signoff

推荐把输出分成四层阅读：

### 第 1 层：`risk_profile`

看它是否回答了：

- 有无真实外部状态变化
- 失败的 blast radius
- 回滚是否可信
- 是否依赖 stateful runtime 或 fresh probe
- 是否需要 background/long-running 执行

### 第 2 层：`acceptance_contract`

看它是否回答了：

- authoritative sources 是谁
- required checks 是什么
- 哪些 scenario 必须成立
- 哪些 authority 必须独立出现
- 哪些 evidence 必须 fresh

### 第 3 层：`mode-*` 执行输出

看它是否回答了：

- 这次工作实际只推进到哪一 gate
- 哪些证据已经准备好
- 哪些风险留给后续独立验证
- 是否越权宣称 release-level pass

### 第 4 层：`gate_result`

看它是否回答了：

- 当前 decision 是什么
- blocker_class 是什么
- 哪些 gate 已满足
- 哪些 gate 未满足
- 下一步最安全动作是什么

## 泛 quant 场景使用手册

### 场景 1：因子研究、特征工程、离线回测

推荐：

- 默认 `fast_loop`
- 若影响共享研究框架、共享数据 schema、公共信号接口，升格到 `gated_change`

推荐证据：

- unit tests
- deterministic fixture tests
- baseline / benchmark diff 摘要
- 数值边界测试

### 场景 2：行情数据接入、订阅、缓存、lease、重连逻辑

推荐：

- 默认 `gated_change`
- 若只改纯解析逻辑且有稳定 fixture，可退回 `fast_loop`
- 若需要真实实例探测，叠加 `fresh_env_snapshot_required`

推荐证据：

- contract tests
- integration tests
- controlled runtime smoke
- env snapshot

注意事项：

- 不要把端口、会话、订阅未就绪误写成设计通过
- 不要把一次历史成功截图当成 fresh readiness 证明

### 场景 3：交易网关、broker session、订单写路径、真实资金动作

推荐：

- 默认 `live_rollout`
- `manual_gate` 通常是默认 overlay

推荐证据：

- local unit / contract / integration
- paper / sandbox / readonly smoke
- live approval
- live health metrics
- rollback readiness
- approver authority

硬边界：

- 模型不得自封通过
- 无 rollback plan 不得继续
- 无 fresh evidence 不得外推 readiness

### 场景 4：agent prompt、tool schema、tool routing、多 agent handoff

推荐：

- 默认 `gated_change`
- 若影响联网工具、background agent、shell 权限、审批边界，可按接近 `live_rollout` 的审慎级别处理

推荐证据：

- prompt / tool selection eval
- handoff eval
- permission boundary tests
- failure-mode replay
- trace review

### 场景 5：runbook、模板、操作标准

推荐：

- 默认 `fast_loop`
- 若文档改变高风险流程、安全边界、发布边界，升格到 `gated_change`

补充判断：

- 纯措辞澄清、排版、低风险示例补充，可保持在 `fast_loop`
- 一旦文档会影响 operator / reviewer / approver 的正式动作，`SHOULD` 升格到 `gated_change`
- 若文档口径会被用于真实外部写操作的批准或执行前置，后续还应由 `acceptance-analysis` 明确非豁免 gate

推荐证据：

- link check
- command freshness
- consistency review
- 与当前 repo policy 的冲突检查

## 常见反模式

以下做法应明确避免：

1. 一开始就直接选 `mode-fast-loop`，完全跳过路由和契约
2. 把 `acceptance-analysis` 变成“帮我合理化为什么现在能过”
3. 让 `evidence-gate` 只看聊天摘要，不看证据载体
4. 让 orchestrator 同时扮演 `dev`、`test`、`review`
5. 对所有任务都施加同样重型的文书负担
6. 把环境失败写成设计通过
7. 没有 fresh evidence 仍然宣称 live readiness

## 是否需要打包为 Codex 插件

当前建议：先保持 skill-first / adapter-first，不把这套设计立即打包成 Codex plugin。

原因：

1. 这套通用技能的核心价值在于技能职责、契约结构和 adapter 抽象，本质上已经可以在当前 Codex CLI 下直接使用。
2. 当前仓库尚未形成稳定的 repo-agnostic adapter 实现，也没有可复用的 plugin surface 约束；此时 pluginize 很容易把尚未稳定的设计提前冻结。
3. Codex plugin 对终端用户来说更适合承载稳定入口、参数面和安装分发，而不是承载仍在演进中的架构实验。

什么时候再考虑插件化：

- 这 7 个 skill 的输入输出格式在两个及以上项目中稳定复用
- adapter contract 至少已有 1 到 2 个成熟实现
- 有明确的 `plugin.json`、入口命令、示例和兼容约束
- 当前 Codex CLI 对 plugin surface 已稳定公开，而不是实验性能力

现阶段更合适的落地方式：

- 继续维护 `.agents/skills/*`
- 继续维护 `docs/universal_skills/*`
- 等输入输出和适配器稳定后，再把“稳定入口层”包装成 plugin

## FAQ

### Q1：如果没有 acceptance contract 怎么办

不要让模型拍脑袋补一个 authoritative contract。正确做法是：

- 进入 `analyze_only`
- 输出 `contract_missing` 或 `contract_ambiguous`
- 列出缺失 authority、缺失 scenario、缺失 gate

### Q2：如果用户明确要求“快一点”，能不能直接走 `fast_loop`

不能用“快一点”覆盖风险边界。速度只能在当前允许的模式内优化，而不能跳过模式选择。

### Q3：所有任务都要写大量工件吗

不用。工件负担应与模式匹配：

- `fast_loop`：最小本地证据
- `gated_change`：reviewable diff + CI/contract/integration evidence
- `live_rollout`：approval + live health + rollback evidence

### Q4：多 agent 一定比单 agent 快吗

不一定。只有在 contract 稳定、写集不重叠、handoff vocabulary 明确时，多 agent 才会真正提效。否则只会把冲突和收口成本放大。
