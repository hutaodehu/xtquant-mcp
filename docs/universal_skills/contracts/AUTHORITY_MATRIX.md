# Authority Matrix

## 目的

该矩阵用于明确谁可以执行、谁可以验证、谁拥有最终 release authority。

## 三层 authority

- `execution_authority`
- `validation_authority`
- `release_authority`

## 按模式定义

### `analyze_only`

- execution authority：只读分析者
- validation authority：不适用
- release authority：不适用

### `fast_loop`

- execution authority：模型或工程师，在 repo 允许的本地编辑范围内
- validation authority：deterministic local checks
- release authority：不在技能内满足

### `gated_change`

- execution authority：模型或工程师，在 shared change policy 下执行
- validation authority：CI、required checks、独立验证者、必要时产品/消费者签收
- release authority：reviewer、branch policy、code owner、product owner 或等价 gate owner

### `live_rollout`

- execution authority：受控 operator path
- validation authority：CI、runtime evidence、live health signal
- release authority：approver、environment owner、resource owner 或明确授权人

## 固定规则

- execution authority 不得自动推导出 release authority。
- release authority 不得由执行该变更的同一模型隐式获得。
- `live_rollout` 需要外部 authority；没有外部 authority 时只能输出 `blocked`。
- `multi_agent_allowed` 只表示允许并行协作，不表示任何 authority 自动提升。
- controller 可以编排 authority 流转，但不能替代 `dev`、`test`、`review`、`approver` 的正式 authority。
- `gated_change` 与 `live_rollout` 的 validation / release authority `SHOULD` 与当前执行者分离。
- docs / runbook / template / policy 任务若重定义 safety、approval、release 或 permission boundary，`SHOULD` 继承 `gated_change` 级别的 validation / release authority 分离，而不是按普通 docs self-check 视为完成。
- 文档作者、prompt 作者或 controller 可以提出 contract 变更，但不得因为“只是改文档”就自动满足 reviewer / approver authority。
