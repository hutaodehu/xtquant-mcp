# `OPERATIONS_RUNBOOK`

关联协作规则：[../AGENTS.md](../AGENTS.md)  
当前状态入口：[CURRENT_STATUS.md](./CURRENT_STATUS.md)  
验收标准：[ACCEPTANCE_STANDARD.md](./ACCEPTANCE_STANDARD.md)  
执行与工件规范：[EXECUTION_AND_ARTIFACT_STANDARD.md](./EXECUTION_AND_ARTIFACT_STANDARD.md)  
设计规范：[MCP_DESIGN.md](./MCP_DESIGN.md)  
关键任务卡：[OPS-002](./task_cards/OPS-002.md) | [VAL-003](./task_cards/VAL-003.md) | [VAL-004](./task_cards/VAL-004.md)

## 文档状态

- 文档类型：formal operations runbook
- 主要受众：主控、测试 agent、需要执行 live rerun 或 blocker recovery 的操作者
- 适用范围：live 启动顺序、最小 preflight、`G0/G1/G3/G4` 硬停止条件、higher-gate broker/session 恢复判断、证据采集清单、环境与设计分类
- 非目标：
  - 不替代 [README.md](../README.md) 的功能介绍
  - 不替代任务卡、EvidencePack、ReviewPack
  - 不宣称当前 `connect_gate_failed` / higher-gate blocker 已解除
  - 不宣称 `VAL-003` / `G4` 或 live 写路径已可放行

## 当前入口与历史工件边界

本手册负责定义当前 operator 应遵循的读取顺序与 stop rules。为避免旧工件误导，固定边界如下：

1. 当前执行判断优先级：本手册 > [MCP_DESIGN.md](./MCP_DESIGN.md) > [CURRENT_STATUS.md](./CURRENT_STATUS.md) > 历史 formal artifact。
2. `EvidencePack` / `EnvSnapshot` / `ReviewPack` 会保留当时现场 payload，不因后续 contract 演进而回写。
3. 因此，较早历史工件里若仍看到旧字段语义，例如：
   - `probe.connection.session_id` 仍表示 probe 观测 session
   - `write_permission_ready=true` 仍接近 precheck success
   - `orders.list` 尚未显式区分 `truth_scope`
   - `order.place` 尚未显式返回 `broker_submission_attempted` / `local_gate_intercepted`
   这些都只表示“当时的记录形态”，不表示当前 contract 仍如此。

## 何时使用本手册

出现以下任一情况时，先读本手册，再执行命令或派发角色任务：

1. 需要在 Windows 本机启动或重启 Trade/Data Gateway 做 live 验证。
2. 需要判断当前问题属于 `G0`、`G1`、`G3` 还是 `G4` 的硬停止。
3. 需要处理 `VAL-003` 当前的 `connect_gate_failed` / higher-gate 阻断，而不是继续依赖聊天上下文回忆历史。
4. 需要把一次 rerun 的结论整理成正式 EvidencePack / ReviewPack 所需的最小证据链。

## 入口阅读顺序

live 操作不要直接从聊天或临时评论开始。标准入口顺序如下：

1. 读取当前任务卡，确认 `Task ID`、目标 gate、`Blocking Reason`、`Scope In` / `Scope Out`。
2. 读取 [CURRENT_STATUS.md](./CURRENT_STATUS.md)，确认当前 accepted posture 与 higher-gate blocker。
3. 读取 [ACCEPTANCE_STANDARD.md](./ACCEPTANCE_STANDARD.md)，以 gate 和 verdict 词汇校准口径。
4. 读取本手册，按启动顺序、preflight、硬停止和证据清单执行。
5. 若当前问题涉及 trade `G3/G4`，补读最新正式材料：
   - [VAL-002-review-20260330-143606-live-gateway-rerun-orders-fallback.md](./reviews/VAL-002-review-20260330-143606-live-gateway-rerun-orders-fallback.md)
   - [VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md](./evidence_packs/VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md)
   - [VAL-003.md](./task_cards/VAL-003.md)
   - [VAL-003_G4_EXECUTION_PLAN.md](./VAL-003_G4_EXECUTION_PLAN.md)
   - [VAL-004.md](./task_cards/VAL-004.md)

## Startup Order

以下顺序用于 live 验证、fresh rerun 和 blocker recovery。不要跳步。

1. 确认本次目标是 `G1` 环境确认、`G3` 只读 rerun、还是 `G4` 写路径验证。
  - 若目标任务是 [VAL-003](./task_cards/VAL-003.md) 且当前状态仍为 `Blocked / connect_gate_failed`，先停在 higher-gate recovery 分支，不得直接执行 `order.place`。
   - 若当前目标是 [VAL-003](./task_cards/VAL-003.md) 的 `G4`，执行细节以 [VAL-003_G4_EXECUTION_PLAN.md](./VAL-003_G4_EXECUTION_PLAN.md) 的固定 packet、三轮顺序和工件要求为准。
2. 确认当前实例与工件边界。
   - 使用 `D:\xtquant-mcp\instance\prod` 作为本次实例目录。
   - 确认本次配置路径和目标 gateway。
   - 确认当前任务已有 TaskCard 与 ChangePack 回链。
3. 做宿主最小 preflight。
   - `XtMiniQmt.exe` 进程存在。
   - `xtdata` 运行时端口可达。
   - 若目标涉及 trade/data gateway，确认对应监听端口当前可观测，或明确处于待唤起状态。
4. 按支持路径启动或重启 gateway。
   - Trade Gateway：`scripts/wake_trade_gateway.ps1`
   - Data Gateway：`scripts/wake_data_gateway.ps1`
   - 若是 rerun，先记录旧 listener 的 PID、启动时间、命令行和 `/healthz`，再执行受控 stop+wake。
   - 对 `VAL-003` 的主控亲测，默认只允许无 `-ForceRestart` 的受控恢复；若端口已被占用但 `/healthz` 不匹配，正确动作是停在 no-go judgment，而不是自动强制替换 listener。
5. 校验 fresh runtime truth。
   - 记录新 listener PID、进程启动时间、命令行、`/healthz`、最近日志文件。
   - 确认 `/healthz` 反映的是当前实例真相，而不是 fake backend。
6. 只在 preflight 完成后执行目标 gate 的 ordered chain。
   - `G3`：按 [ACCEPTANCE_STANDARD.md](./ACCEPTANCE_STANDARD.md) 的顺序跑完整交易只读链。
   - `G4`：只在 `G0 -> G3` 已闭合、交易窗口允许、人工 gate 明确授权时执行。
   - 对 `Controller Test Policy: controller_direct_required` 的 live test 卡，主控入口统一使用 `scripts/run_controller_direct_test.ps1`。

## Minimum Preflight

最小 preflight 不等于完整验收，但它决定是否允许继续进入 live 链路。缺一项就不要继续。

| Area | 必须确认的事实 | 最小证据 |
| --- | --- | --- |
| Task 边界 | 当前任务卡、目标 gate、ChangePack 已明确 | TaskCard 路径 + ChangePack 路径 |
| 宿主进程 | `XtMiniQmt.exe` 可见 | 进程查询结果 |
| `xtdata` | 运行时端口可达 | `Test-NetConnection` 结果 |
| Gateway 健康 | 目标 gateway 监听与 `/healthz` 可读 | listener 查询 + `/healthz` 响应 |
| 实例真相 | 配置路径、命令行、实例目录对得上当前 rerun | 进程命令行 + config 路径 |
| 新鲜工件 | 当前窗口有新日志或新 artifact 可回链 | 最新日志文件路径 / artifact 路径 |
| 污染隔离 | fake/test 状态未混入本次正式 evidence | 实例目录检查结论 |
| Write safety | prod trade config 的 `kill_switch_file` 非空，且 `/healthz` 没有 `kill_switch_unconfigured` release blocker | config 路径 + `/healthz.write_safety` |

若任一项拿不到最小证据，只能写 `blocked` / `fail_env` / `fail_design`，不能写“先继续试”。

## G0 Hard Stops

出现以下任一情况时，不得进入 live 验证：

1. 当前任务没有正式 TaskCard、没有 `Repo Spec Link`、或没有稳定 ChangePack 路径。
2. [AGENTS.md](../AGENTS.md)、[MCP_DESIGN.md](./MCP_DESIGN.md)、[ACCEPTANCE_STANDARD.md](./ACCEPTANCE_STANDARD.md)、[CURRENT_STATUS.md](./CURRENT_STATUS.md) 的口径冲突到足以误导执行顺序或 verdict。
3. 实例目录中 fake 状态、测试残留和真实产物无法区分。
4. 当前 operator 无法说明本次使用的配置路径、实例目录和 gateway 进程来自哪里。

默认分类：

- 文档或契约冲突：`fail_design`
- 状态目录污染、路径拿不准、实例来源不清：`blocked` 或 `fail_env`

## G1 Hard Stops

出现以下任一情况时，不得推进到 `G2/G3/G4`：

1. `XtMiniQmt.exe` 不存在。
2. `xtdata` 运行时端口不可达。
3. 目标 gateway `/healthz` 不可用。
4. `/healthz` 可用但明显返回 fake/backend 占位状态，而非当前实例真相。
5. 交互桌面不可用，导致登录窗口、唤醒流程或 host-side 观察无法执行。

默认分类：

- 进程、端口、权限、桌面、路径问题：`fail_env` 或 `blocked`
- `/healthz` 语义错误、把假状态冒充真状态：`fail_design`

## G3 Hard Stops

`G3` 的目标是交易侧只读闭环。以下任一情况出现，都不能把结果写成 `G3 pass`：

1. `miniqmt.ensure_logged_in` 没有得到可追溯成功结果，例如：
   - `miniqmt_not_logged_in`
   - `login_window_not_found`
   - `desktop_not_interactive`
2. `session.warm` 不能建立 owner-managed session。
3. `session.status.ready != true`。
4. `probe.connection.ok != true`，或其结果无法区分 read-only 与 write-permission。
5. `account.show`、`positions.list`、`orders.list`、`snapshot.l1` 任一步 public tool 失败，导致 ordered chain 未闭合。
6. `xttrader connect=-1` 直接导致 public `orders.list` 或上游步骤失败。

当前操作口径里，以下情况可以判定为 `G3 pass`，但不得外推到 `G4`：

1. ordered chain 完整完成。
2. public `orders.list` 返回 `ok=true`。
3. 若 public `orders.list` 使用 degraded fallback，则同一 payload 内必须显式保留：
   - `degraded=true`
   - `fallback_used=true`
   - `fallback_reason=broker_connect_failed`
   - `truth_scope=shadow_fallback`
   - `broker_truth_confirmed=false`
   - `broker_read.ok=false`
   - `broker_read.error=xttrader connect failed: -1 ...`
4. fallback 成功只能说明 truthful degraded read contract 成立，不能说明 broker fresh connect 或写权限已恢复；只有 `truth_scope=broker_truth` 且 `broker_truth_confirmed=true` 时，public `orders.list` 才能被当作 broker truth 消费。

这正是 [VAL-002-review-20260330-143606-live-gateway-rerun-orders-fallback.md](./reviews/VAL-002-review-20260330-143606-live-gateway-rerun-orders-fallback.md) 的当前 accepted 口径：`G3 pass` 与 higher-gate blocked 可以同时成立。

## G4 Hard Stops

`G4` 代表受控最小真单验证。以下任一情况出现，都必须停止，不得执行或继续解释 `order.place`：

1. `G0 -> G3` 没有正式闭合。
2. 当前任务仍是 [VAL-003](./task_cards/VAL-003.md) 的 `Blocked / connect_gate_failed`。
3. 交易窗口未开放，即 `market_window_closed`。
4. `up_queue_xtquant` 或其他写权限前置条件未满足。
5. 任何 broker subpath 仍出现 `xttrader connect=-1`，即使 `G3` 已靠 degraded read contract 通过。
6. 不能证明当前账户、最小数量、撤单策略和审计路径已明确。
7. 无法为本次 `G4` 执行创建新的 EvidencePack 与 EnvSnapshot。
8. 对 `controller direct test execution` 卡，gateway recovery 未通过或 listener `/healthz` 不匹配。
9. prod trade config 的 `kill_switch_file` 仍为空，或 `/healthz.write_safety.release_blockers` 非空。

关键规则：

1. `G3 pass` 不是 `G4 ready`。
2. `probe.connection` 中 `write_permission_precheck_ok=true`、`write_permission_ready=true`、`write_authority_ready=true` 都只是 runtime 层信号；它们最多说明当前 packet 具备尝试 governed write 的 same-session runtime 条件，不能单独等价于 `trade_write_authority`、`G4 pass` 或 release authority。
3. 任何残留的 `broker_read.error=xttrader connect failed: -1 ...` 都继续阻断 `VAL-003`。
4. `controller direct test execution` 不是绕过 hard stop 的快捷键；它只是把真实 `test` 执行人固定为主控，仍必须先过 recovery 和 preflight。
5. 对 `VAL-003/G4`，Round 2 gateway-side fresh authority 与 Round 3 write `MUST` 使用同一套 session 解析语义；若 `session.warm`、`session.status`、`probe.connection`、same-call `connect_gate` 不能回链同一 resolved write session，则直接停止。
6. formal authority green 不发生在 Round 3 前置 gate；`scripts/run_controller_direct_test.ps1` 只负责 fresh packet、runtime capture 与 typed authority source。只有 fresh packet 完成、独立 `ReviewPack` 产出、并完成 state truth refresh 后，才允许核对 `trade_write_authority_latest.json`、`ter_execution_gate_latest.json`、`CURRENT_STATUS.md`、任务卡等 formal truth 是否同步转绿。
7. state truth refresh 后，只有 `same_plan_verdict=true`、`probe_complete_verdict=true`、`fresh_connect_verified=true`、`formal_trade_write_closed=true` 同时满足时，才允许把 `trade_write_authority` 或 formal authority 视为转绿。

## `connect_gate_failed` / Higher-Gate Recovery Flow

`connect_gate_failed` 不是“已经确认是代码问题”，也不是“只差点一下重试”。它表示任务已经跨入 governed write，但 same-call pretrade connect gate 仍未闭合。旧的 `broker_blocked` 叙事可以看作 pre-write 阶段的上层占位词；当前正式 posture 以 `connect_gate_failed` 为准。

官方 `xttrader` 语义只要求会话编号彼此不冲突、同一策略通常只维护一个 API 实例、同一 `session_id` 的重连要遵守冷却；它没有把 `100/101/1111/2111` 这类数字定义成官方模板。因此仓库里的任意 session 数字都只能被视为实例 seed、本地候选或派生 fallback，不能把某个固定值写成“官方推荐 session 模板”。

### 支持确认口径（2026-04-08，用户提供客服答复）

本小节记录 `2026-04-08` 用户提供的官方客服答复，用于当前仓库的 operator-facing 判断。它是 support-confirmed guidance，不替代公开 SDK 文档，也不把客服口径直接升格成通用公开 contract。

适用前提：

1. 当前执行路径不是纯原生单实例 `XtQuantTrader(PATH, SESSION_ID)` 脚本。
2. 服务端存在 `session_resolution`、candidate plan、以及可选 derived fallback。

支持确认的关键点如下：

1. resolver/derived fallback 可以存在，但会话稳定性、唯一性和重连纪律全部由用户侧承担，不由底层自动兜底。
2. `session.warm/session.status=1111`、native probe=`100/101`、write-side `connect_gate=2111` 这类 warm/probe/write 跨层不一致，按当前 support 口径应视为异常会话不一致，而不是“多会话都可用”的正常形态。
3. 一旦写路径实际落到新的 session，新的 session 必须重新完成自己的 `connect -> subscribe -> order` 链；不得继承旧 session 的 warm/probe 成功状态。
4. 当前 machine-readable local gate 字段若已明确给出 `broker_submission_attempted=false`、`local_gate_intercepted=true`，应优先据此判定本地 gate 层拦截、未进入券商柜台；`connect_gate_failed + broker_order_id=""` 只作为历史工件 fallback 佐证，不再作为首选解释入口。

### 问题总结与对应解决办法

当前 `VAL-003` 的典型故障形态，不是“不会下单”，而是“真实 `order.place` 已发起，但最后一道本地交易连接门禁没有通过”。operator 必须按下表处理：

| 观察到的现象 | 当前应如何理解 | 对应动作 |
| --- | --- | --- |
| `session.warm` / `session.status` 可读，asset / positions / public orders 也可读，但真实 `order.place` 返回 `connect_gate_failed` | 读侧成功，不等于写侧 ready；写路径门禁仍未闭合 | 停止继续试单，保留 formal evidence，不得把当前窗口解释成“基本恢复” |
| `order.place` 返回 `broker_submission_attempted=false` 且 `local_gate_intercepted=true` | 机器可读地确认订单停在本地 gate / pre-submit 阶段，没有进入 broker 提交链 | 直接按 local intercept 处理，不再依赖空 `broker_order_id` 的人工推理 |
| 历史工件只看到 `connect_gate_failed` 且 `broker_order_id=""` | 仅可作为 fallback 佐证当前 no-go 形态；优先级低于 machine-readable local gate 字段 | 不写 broker 受理成功，不写 broker reject；按历史 fallback 证据收口 |
| owner session 与 write-side session 不一致 | 会话语义未收口，warm/probe 成功不能外推写 readiness | 回到 session 解析收口分支，不得进入新的 governed write |
| `probe.connection.session_id` 与 `observed_probe_session_id` 不一致，且 `write_session_alignment.same_plan_verdict=false` | 顶层已明确暴露 write-path session truth，观测到的 probe session 只是 read-only / supplemental observation | 以顶层 `session_id=session_resolution.resolved_session_id` 作为写路径主真相；必须按 resolved session 重做 same-session verify |
| native probe 只验证了 legacy session（如 `100/101`），但写路径落到 derived 或其他 session（如 `2111`） | Round 2 证据不足，same-plan verdict 为 `false` | 必须用 write-side 实际 session 重做 native `connect -> subscribe -> read-only query` 链 |
| 切换到新 session 或 resolver 选中了新 session | 旧 session 的 subscribe / probe 结果全部失效 | 在新 session 上重新完成 `connect -> subscribe -> order` 前，不得放行写路径 |
| 同一 `userdata` 下可能存在 session 残留、重复 connect、冷却期冲突 | 写侧 connect 稳定性可能被污染，哪怕只读仍有结果 | 检查 queue / lock / heartbeat / disconnect 痕迹；同号重连前满足 `>= 3 秒` 间隔；避免复用不确定残留 session |

### 1. 先判定当前属于哪一类阻断

1. 若当前连 `G3` 都没有正式通过，按 `VAL-002` / `G3` 问题处理，不进入当前 higher-gate 恢复流。
2. 若 `G3` 已正式通过，且最新 governed-write 或 host-side evidence 仍保留 same-call connect gate 失败 / broker fresh connect 不稳定，则按当前 higher-gate blocker 处理。
3. 若当前问题只是文档口径、schema、session 语义冲突，且与 broker fresh connect 无关，则不要滥用当前 higher-gate blocker；应回到 `fail_design` 分支。

### 2. 固定当前操作真相

进入当前 higher-gate 恢复流前，先固定以下事实：

1. [VAL-002](./task_cards/VAL-002.md) 当前已是 `Accepted/pass`，但只覆盖 `G3`。
2. [VAL-003](./task_cards/VAL-003.md) 当前仍是 `Blocked / connect_gate_failed`。
3. [VAL-004](./task_cards/VAL-004.md) 是当前 higher-gate blocker 的隔离取证卡，不是写路径实现卡。

### 3. 恢复阶段允许做什么

允许做：

1. 重跑 gateway-side live `G3` evidence 以确认 blocker 形状是否变化。
2. 做 native broker/session probe，确认 `xttrader connect=-1` 是否仍在宿主侧复现。
3. 做 bounded host-log 提取，增强对 session/heartbeat/lock 丢失现象的解释。
4. 显式固定并记录本轮 session plan，包括 gateway owner session、native probe candidate list、write-path candidate list 与是否启用 derived fallback。
5. 对 `VAL-003/G4`，native probe 的 `--user-data-path` 必须来自 `TaskCard.Trade Config Path` 对应实例配置中的 `qmt_userdata`，或同窗 `miniqmt.ensure_logged_in` / `diag://login/latest` 暴露的 `evidence.qmt_userdata`；不得在 harness 中写死宿主路径。
6. 生成新的 EvidencePack / EnvSnapshot / ReviewPack，决定继续 `blocked` 还是新开更具体的 trade refactor follow-up。

补充要求：

- 当前 contract 下，`probe.connection` / `order.place` 等 write-adjacent payload 的顶层 `session_id` 应视为 write-path resolved session；观测到的 probe/read-only session 通过 `observed_probe_session_id`、`read_only_probe.session_id` 等 additive 字段单独暴露。
- 进入 higher-gate 恢复或 `VAL-003/G4` 前，`session.warm`、`session.status`、`trade://session/current`、`probe.connection`、`order.place` 的 payload 都应回链同一个 `session_resolution.effective_session_plan`。
- `session.warm` 现在也应经过 explicit session resolution；若它仍表现成单纯复用配置 seed，而 `probe.connection` / `order.place` 落到另一套 session plan，应直接按 session 语义未收口处理。
- 若 resolver / derived fallback 最终让 write-path 落到新的 session，该 session 必须重新完成自己的 `connect -> subscribe -> order` 链，不得继承旧 session 的 warm/probe 成功状态。
- `probe.connection` 当前还必须同时检查：`write_permission_precheck_ok`、`write_permission_ready` / `write_authority_ready`、`write_session_alignment.same_plan_verdict`；只要 `same_plan_verdict=false`，即使 `ok=true` / `read_only_ready=true`，也不得把当前窗口解释成 write-ready。即使 `same_plan_verdict=true` 且 runtime ready 字段转绿，这也仍只是 fresh packet 的 runtime go/no-go，不等于 formal authority 已转绿。
- `probe.connection` 若仅复用现存 owner-managed session，当前 contract 会明确保留 read-only success，但必须把 write-side 结论停在 `reuse_only_not_sufficient`；只有 fresh connect/subscribe verify 才能形成 write authority。
- `scripts/run_controller_direct_test.ps1` 的 Round 2 现在固定包含 `session.close -> cooldown -> native probe` 的 clean-window 步骤；若首次 fresh native probe 仍失败，才允许进入受控 host recovery（停 gateway、停 MiniQMT、清理匹配 session residue、重启后再 probe）。
- operator 应把 runner 的职责限制在 fresh packet 执行与 runtime capture；formal closeout 还必须等待新的 `ReviewPack` 与 state truth refresh，之后再核对 `trade_write_authority_latest.json`、`ter_execution_gate_latest.json`、`CURRENT_STATUS.md` 与任务卡是否一致。只有 `same_plan_verdict=true`、`probe_complete_verdict=true`、`fresh_connect_verified=true`、`formal_trade_write_closed=true` 同时成立时，formal truth 才允许视为转绿。
- `trade_write_authority_latest.json` 的机器输入现在固定为 `trade_write_authority_source_latest.json + diag_probe_latest.json`。`CURRENT_STATUS.md` 只保留 operator-readable 镜像角色，不再作为 authority 机器输入主来源。

不允许做：

1. 不执行 `order.place`。
2. 不启动 `VAL-003`。
3. 不把 degraded read success 改写成 broker fresh connect success。
4. 不把“暂时看起来恢复”写成“写路径已可放行”。
5. 不得用一套 session plan 上的 native probe pass 去放行另一套 session plan 上的真实写路径。

### 4. 恢复阶段的标准取证组合

按 [VAL-004.md](./task_cards/VAL-004.md) 的当前定义，higher-gate 恢复至少要对齐三类证据：

1. gateway rerun
   - fresh listener PID
   - `/healthz`
   - ordered MCP chain
   - 相关 `trace_id`
2. native probe
   - 宿主侧 `xttrader.connect()` 或等价 broker/session 探针现象
   - 与 gateway 结果的同窗对比
3. bounded host-log
   - MiniQMT / QMT 日志里的 session、heartbeat、lock、disconnect 现象
   - 只写已证实的宿主现象，不把根因假设写成结论
4. session plan alignment
   - `session.warm` / `session.status` 的 owner session
   - `session_resolution.resolved_base_session_id`
   - `session_resolution.effective_session_plan`
   - native probe 实际覆盖的 session 列表
   - native probe `user_data_path`、解析来源与 `path_exists` 结果
   - write-path 解析后的 candidate plan 与 same-call `connect_gate` session
   - 是否启用了 derived fallback，以及它是否参与本轮验证
5. freshness / authority
   - `/healthz.server_ts`
   - `/healthz.process_identity`
   - `/healthz.latest_audit_log`
   - 相关资源的 `freshness_status`
   - 相关资源的 `state_age_seconds`
   - 相关资源是否仅为 `cached_last_known_state`

### 5. 何时继续保持当前 higher-gate block

出现以下任一情况时，继续保持 `Blocked / connect_gate_failed`：

1. broker fresh connect 仍失败。
2. `xttrader connect=-1` 仍只被隔离到“剩余 higher-gate blocker”，没有新的 write-path closure 证据。
3. 当前只有 `G3` degraded read success，没有新的 broker write readiness 证据。
4. 仍然无法确定是宿主环境、session 锁、broker heartbeat 还是别的更细分根因。
5. gateway owner session、native probe session 集和 same-call `connect_gate` session 之间仍不是同一套可比较的 session plan。
6. `order.place` 若已返回 `broker_submission_attempted=false` 且 `local_gate_intercepted=true`，说明 machine-readable local gate 已确认本轮停在 broker 提交前，本轮已不具备继续消费 live retry 的证据增量价值；历史工件中的 `connect_gate_failed + broker_order_id=""` 只作为 supplemental fallback 佐证同一 no-go 形态。

### 6. 何时可以离开当前 higher-gate block

只有在新的正式工件同时证明以下事实时，才允许主控考虑把 [VAL-003](./task_cards/VAL-003.md) 从 `Blocked` 移走：

1. higher-gate broker fresh connect 前置条件已独立闭合。
2. 写权限 gate、交易窗口、最小数量、撤单策略、审计路径都已具备。
3. 该结论来自新的 EvidencePack / EnvSnapshot / ReviewPack，而不是沿用旧的 `VAL-002/G3` 结果。
4. Round 2 probe 与 Round 3 write 已按同一套 session 解析语义执行，并且 formal 工件已经把 owner session、native probe session plan、write-path session plan 明确回链。

在这些条件闭合前，正确动作不是“继续试一单”，而是继续保留 `connect_gate_failed` / higher-gate block。

## Evidence Collection Checklist

每次 live rerun、blocker recovery 或 gate 验收，至少采集以下内容：

1. 任务上下文
   - `Task ID`
   - `Acceptance Gate`
   - 当前角色
   - ChangePack 路径
   - 配置路径
2. 时间与宿主
   - 执行时间
   - 主机名
   - shell
   - 实例目录
3. 进程与端口
   - `XtMiniQmt.exe` 进程状态
   - `xtdata` 运行时端口连通性
   - gateway listener PID、启动时间、命令行
4. gateway 健康
   - `/healthz` 原始响应
   - 最近日志文件路径
5. ordered chain 原始结果
   - 每一步工具名
   - `ok` / `reason`
   - `trace_id`
   - `server_ts`
   - `duration_ms`
6. resource 回读
   - 至少包括相关 `diag://...` 或 `trade://...` / `xtdata://...` 资源
   - 记录这些资源的 `freshness_status`、`state_age_seconds`、`resource_path`、`resource_server_ts`
7. artifact 路径
   - calls.jsonl
   - state 文件
   - 日志文件
   - 必要时的截图、host-log、queue 证据
8. 阻断说明
   - 第一处 hard stop 在哪里
   - 为什么它属于 `blocked` / `fail_env` / `fail_design`
   - 是否阻断更高 gate

若本次是 trade `G3` 的 degraded success，还必须额外保留：

1. `degraded=true`
2. `fallback_used=true`
3. `fallback_reason`
4. `broker_read.ok=false`
5. `broker_read.error`

否则后续 review 无法判断这是 truthful degraded success，还是静默掩盖失败。

## Environment vs Design Classification

分类时先问一个问题：当前失败是宿主/券商/端口/时段事实导致的，还是契约、语义、状态输出本身错误导致的。

| 观察到的现象 | 首选分类 | 说明 | 下一步 |
| --- | --- | --- | --- |
| `XtMiniQmt.exe` 不存在、`xtdata` 端口未开、交易窗口关闭、桌面不可交互 | `fail_env` 或 `blocked` | 宿主条件不满足，先停，不要继续解释成设计通过 | 修环境，重跑 |
| `xttrader connect=-1` 让 public tool 直接失败，ordered chain 未闭合 | `fail_env` 或 `blocked` | 当前证据优先指向 broker/session 环境硬停止 | 保持阻断，补 host-side 取证 |
| public `orders.list` 以 `ok=true` degraded fallback 成功，且同一 payload 保留 `broker_read.error=xttrader connect=-1 ...` | `G3 pass` + `G4 higher-gate blocked` | 这是 truthful degraded read success，不是设计失败，也不是写路径恢复 | `VAL-002` 可收口；`VAL-003` 继续阻断 |
| 文档或状态输出把配置值冒充 runtime truth，例如把 `xtdata` 端口、`session_id` 写成稳定常量 | `fail_design` | 语义模型错误，会直接误导 agent | 修正文档或实现，再 rerun |
| read-only readiness 与 write permission 被混成单一 ready 口径 | `fail_design` | 契约边界错误，不只是环境噪声 | 修契约与输出，再补证据 |
| fake/test 状态被当成正式 evidence | `blocked`，必要时 `fail_design` | 先停用该证据；若规范或实现让两者不可区分，则上升为设计问题 | 清理污染并修隔离 |
| 同一问题既有宿主现象也有契约矛盾 | 分开写 | 不允许混写成单一“不可用” | 分别记录 environment 与 design 结论 |

## Operator Output Rules

1. 开发只能写“自测通过”，不能写“验收通过”。
2. 测试只能写测试结论，不能代替审查宣布放行。
3. 审查在正式 `ReviewPack` 中只能基于正式工件给出 `pass` / `partial` / `blocked` / `fail_env` / `fail_design`，不能回到聊天口头结论。
4. 若外部看板或任务卡的 `Review Result` 字段需要写 `needs_fix`，必须明确它只属于 board/ledger 字段语义，不属于正式 `ReviewPack` 或其他 formal artifact 的结论词汇。
5. 任何角色都不得把 `VAL-002/G3` 的成功外推成 `VAL-003/G4` 可启动。
6. 任何正式结论都必须区分 `设计问题` 和 `环境问题`。

## 当前操作基线

截至 [CURRENT_STATUS.md](./CURRENT_STATUS.md) 当前快照，本仓库 live 操作的正式基线是：

1. Data lane 已正式闭合到 `G2`。
2. Trade lane read 已正式闭合到 `G3`。
3. `VAL-002` 已接受 `public orders.list` 的 truthful degraded fallback 作为 `G3 pass`。
4. `VAL-003` 仍为 `Blocked / connect_gate_failed`。
5. 在新的 higher-gate formal evidence 出现前，不得把 trade write path 解释为已 ready。
