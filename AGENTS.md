# Repository Guidelines

本仓库面向 Windows 本机 `xtquant` / MiniQMT MCP 网关协作开发。默认目标不是单人脚本式推进，而是让开发、测试、审查 agent 按统一规则交接、复核和放行。

## 文档入口

- live 运维与 blocker 恢复：`docs/OPERATIONS_RUNBOOK.md`
- 执行与工件规范：`docs/EXECUTION_AND_ARTIFACT_STANDARD.md`
- 协作与看板规则：`docs/WORKFLOW_AND_BOARD.md`
- 验收标准：`docs/ACCEPTANCE_STANDARD.md`
- 模板：`docs/TEMPLATES.md`
- 首轮任务拆分：`docs/FIRST_WAVE_TASK_BREAKDOWN.md`
- 当前设计：`docs/MCP_DESIGN.md`
- 当前状态：`docs/CURRENT_STATUS.md`
- 设计审查：`docs/DESIGN_REVIEW_20260327.md`

## 角色分工

### 开发 Agent

- 负责实现、重构、自测和提交实现说明。
- 不负责宣布最终通过。
- 必须输出：ChangePack、变更摘要、自测步骤、已知风险、待独立测试点、证据路径。

### 测试 Agent

- 负责按统一验收标准做独立验证。
- 不改需求口径，不替开发补设计决策。
- 必须输出：测试范围、执行步骤、EvidencePack、结果、证据路径、失败分类、最终结论。

### 审查 Agent

- 负责设计一致性、实现风险、文档一致性和放行判断。
- 主要关注：错误心智模型、回归风险、缺失测试、误导 agent 的接口契约。
- 必须输出：ReviewPack、findings、严重度、影响、 required fix、release decision、必要的回退状态建议。

## 主控与编排

- 主控负责读取任务卡、分派单卡、汇总 ChangePack 与 EvidencePack，并更新外部看板。
- 主控可以由人工或单独窗口承担，但不作为额外看板角色枚举；看板中的 `Owner Role` 和 `Current Role` 仍固定为 `dev`、`test`、`review`。
- 默认推荐使用“单主控 + 多角色 agent”模式，不推荐长期依赖人工多开窗口、口头协调职责。
- 主控只支持两种工作模式：`controller-only` 与 `controller-with-delegation`。
- `controller-only` 表示主控默认只做 reconcile、判断、派单文本和收口建议，不直接执行 `dev`、`test`、`review` 的角色工作。
- `controller-with-delegation` 表示主控在显式授权多 agent 编排时，可以把边界清晰的单步任务派给子代理执行，但主控自己仍不得代做该角色的工件。
- `controller direct test execution` 不是第三种主控模式，而是任务卡级别的受控执行策略；只在 `Controller Test Policy: controller_direct_required` 且同时满足 `Automation Policy: manual_gate`、`Execution Class: test_only`、`Risk Class: high` 时允许。
- 该受控策略只豁免 `test`，不豁免 `dev` / `review`；主控仍不得代做开发实现或独立审查。
- 主控亲测时，正式工件仍写 `Role: test`，但必须显式写出 `Executor: controller direct test execution`、`Authorization Basis`、`Controller Judgment Link`、`Raw Runtime Capture`、`Gateway Recovery Output Link`。
- 只要使用子代理，模型门槛 `MUST` 不低于 `gpt-5.4` 且 `reasoning_effort` 不低于 `high`；低于该门槛的子代理不得用于本仓库正式执行流。
- 外部看板 / RunLedger 同步属于主控职责，本身不视为 `dev`、`test`、`review` 的角色替代。
- 只要同步依据来自既有 `ChangePack`、`EvidencePack`、`ReviewPack`、`EnvSnapshot` 和明确的 controller judgment，主控 `SHOULD` 直接完成账本同步，而不是反复把“是否同步”抛回给用户。
- 主控 `MUST NOT` 亲自补写 `ChangePack`、`EvidencePack`、`EnvSnapshot`、`ReviewPack` 来冒充子代理已经执行；若属于受控 `controller direct test execution`，则必须由主控作为真实执行者产出带完整 metadata 的 `Role: test` 工件，而不是伪装成子代理结果。
- 本仓库不采用“主控自己临时代演 `dev` / `test` / `review`”作为通用机制；唯一例外是上述受控 live test 卡的 `controller direct test execution`，且该例外不改变独立 review authority。

## 通用协作规则

- Windows 命令优先使用 `pwsh`。
- WSL 或其他 agent 环境不直接 `import xtquant`，统一通过本机 MCP 网关访问能力。
- 所有结论必须区分 `设计问题` 和 `环境问题`，禁止混写。
- 没有证据就不能写“通过”。证据至少包括命令、时间、结果和 artifact 路径。
- 没有完成独立测试前，开发输出只能写“自测通过”，不能写“验收通过”。
- 没有完成审查前，测试输出只能写“测试通过”，不能写“设计放行”。
- `README.md`、`AGENTS.md`、`docs/**/*.md` 属于源文档，功能边界变更后要同步更新。
- 任务流转以外部看板为主，但规则和标准以仓库文档为准。
- 看板是 ledger，不是 artifact 本体；正式执行必须有 TaskCard、ChangePack 和 EvidencePack 的可追溯链路。
- `docs/reviews/*.md` 是正式 ReviewPack，不再把审查记录只当聊天摘要或看板评论。
- 高副作用或跨宿主任务应补充 `EnvSnapshot`，避免把环境问题误判成设计问题。
- 多 agent 并行只有在任务切分清晰、写集不重叠、共享账本明确时才允许；高副作用写路径默认串行推进。

## 通用 suite adapter 边界

- 当前仓库对通用 adapter 字段的 repo-local 映射，以 `TaskCard`、`ChangePack`、`EvidencePack`、`ReviewPack`、`EnvSnapshot` 和其显式回链 artifact 为正式 carrier。
- 外部看板 / `RunLedger`、`Board Export`、`Board Sync` 和 controller judgment 属于 ledger 或 control-plane，不替代上述角色工件。
- `TaskCard.Status`、board `Status`、board `Review Result` 只能镜像状态，不自动生成 `validation_authority` 或 `release_authority`。
- 若某类 runtime evidence、resource evidence 或 external approval 还没有稳定 carrier，必须在仓库文档或角色工件中显式登记 gap，不能默认为“后续自然补齐”。
- 通用 suite 的 `controller-only` / `controller-with-delegation` 相关描述，只能解释主控如何编排，不改变当前仓库 `dev`、`test`、`review` 的 authority 分工。
- `Controller Test Policy` 只决定某张高风险 live test 卡能否使用主控亲测入口，不会创建新的看板角色，也不会把 controller judgment 升格成 release authority。

## 任务交接要求

### 开发到测试

- 关联任务卡 ID。
- 附带 ChangePack 路径。
- 说明变更目标和范围。
- 标明是否触及交易写路径、会话模型、端口模型、订阅模型。
- 给出最小可复现验证步骤。
- 给出已知未覆盖风险。

### 测试到审查

- 关联任务卡 ID。
- 附带 EvidencePack 路径。
- 明确验收使用的标准版本。
- 明确结论：`pass`、`partial`、`blocked`、`fail_env`、`fail_design`。
- 附带所有证据路径。

### 审查到放行

- 明确是否可放行。
- 明确必须回流的修复项。
- 若为 `blocked`，必须说明是设计阻断还是环境阻断。
- 若需回退状态，明确回退到 `In Dev`、`In Independent Test` 或 `Blocked`。

## 结果词汇

统一使用以下结论词：

- `pass`
- `partial`
- `blocked`
- `fail_env`
- `fail_design`

禁止自行发明近义词替代，例如“基本通过”“大致可用”“差不多完成”。

## MCP 与 xtquant 特殊约束

- `xtdata` 端口不得在文档里被描述成稳定常量，只能写成实例状态或配置项。
- `session_id` 不得被描述成官方固定模板，只能写成服务端管理的冲突资源。
- 写路径必须明确标出所有前置 gate，不能把只读探测和写权限判断混为一谈。
- 实例目录中的 fake 状态、测试残留和真实产物必须可区分，不能混作验收证据。
