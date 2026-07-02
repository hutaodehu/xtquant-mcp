# xtquant MCP 验收标准

本文件定义 `xtqmt-mcp` 的统一验收标准。开发、测试、审查必须使用同一套 gate、结论词汇和硬停止条件，避免“开发觉得可以、测试觉得不行、审查又按另一套标准判断”。

与 [EXECUTION_AND_ARTIFACT_STANDARD.md](./EXECUTION_AND_ARTIFACT_STANDARD.md) 的关系如下：

- 本文件定义验收 gate 和 verdict。
- 执行与工件规范定义 TaskCard、ChangePack、EvidencePack 和 EnvSnapshot 如何进入这些 gate。

## 结论词汇

统一使用以下结果：

- `pass`
- `partial`
- `blocked`
- `fail_env`
- `fail_design`

解释如下：

- `pass`
  达到当前任务定义的正式通过标准。
- `partial`
  部分 gate 通过，但未达到最终放行标准。
- `blocked`
  当前无法继续推进，需要等待环境、券商、时段或文档前置条件。
- `fail_env`
  主要失败原因是环境或实例问题，设计口径本身未被证明错误。
- `fail_design`
  主要失败原因是接口契约、状态机、验收定义或实现边界本身错误。

## 通用证据要求

每次正式验收都必须记录以下内容：

- 任务编号
- 验收时间
- 验收人或 agent 角色
- 代码版本或提交标识
- 配置路径
- ChangePack 路径
- EvidencePack 路径
- 执行步骤
- 原始结果
- 错误码或失败分类
- artifact 路径
- 最终结论

必须保留的最小证据包括：

- gateway `/healthz` 响应
- 相关 MCP 工具原始响应
- `trace_id`
- `server_ts`
- 审计 artifact 路径
- 需要时的 `EnvSnapshot`

## Gate 顺序

验收必须按 `G0 -> G1 -> G2 -> G3 -> G4` 的顺序执行。前一层未通过，后一层不得宣告通过。

### G0 文档与实例洁净度

目的：确保当前任务不是在脏状态或错误口径上推进。

通过条件：

1. 任务卡已建立，且包含 `Repo Spec Link`。
2. 当前任务已绑定明确的 `Acceptance Gate`。
3. 任务已有 ChangePack 路径，正式验收前可追溯到对应变更边界。
4. `README.md`、`AGENTS.md`、相关 `docs/*.md` 没有明显口径冲突。
5. 实例状态目录中不存在被误当成生产状态的 fake 记录。

失败结论：

- 口径冲突导致无法定义真实标准，记 `fail_design`。
- 状态目录污染但可清理，记 `blocked` 或 `fail_env`。

### G1 环境与服务就绪

目的：确认本机 MiniQMT、xtdata 和 MCP gateway 具备基本可测条件。

通过条件：

1. `XtMiniQmt` 进程存在。
2. `xtdata` 实际服务端口可达。
3. Trade/Data gateway 均能启动并返回 `/healthz`。
4. gateway `health` 返回的是当前真实状态，不是 fake backend 回应。

建议检查项：

```powershell
Get-Process -Name XtMiniQmt
Test-NetConnection -ComputerName 127.0.0.1 -Port <resolved_xtdata_port>
Test-NetConnection -ComputerName 127.0.0.1 -Port 8765
Test-NetConnection -ComputerName 127.0.0.1 -Port 8766
```

`<resolved_xtdata_port>` 必须来自配置、环境变量、QMT 日志探针、当前 `xtquant.xtdatacenter.listen` 默认签名或 gateway current endpoint。`58610` 可以是当前有效实例端口，但不能被写死成协议常量。`Test-NetConnection` 只证明连接层可达；Data Gateway 的 `G1 pass` 还必须看到 `gateway.health.readiness.layers.basic_query.ready=true`，也就是原生 `xtdata` 只读探针已通过。

失败结论：

- 端口、进程、桌面交互、路径问题，记 `fail_env` 或 `blocked`。
- health 明明正常但状态语义错误，记 `fail_design`。

### G2 数据侧只读验收

目的：确认 Data Gateway 的只读能力符合 agent 消费预期。

必须覆盖的工具：

1. `xtdata.status`
2. `xtdata.history.get_bars`
3. `xtdata.snapshot.batch`

建议附加工具：

1. `xtdata.calendar.query`
2. `xtdata.instruments.search`

通过条件：

1. `xtdata.status` 返回真实 endpoint 状态，不把静态配置值冒充运行时事实。
2. `xtdata.history.get_bars` 对小范围标的和时间窗口查询成功。
3. `xtdata.snapshot.batch` 对至少一个实际标的返回有效快照。
4. 如果执行 `xtdata.instruments.search`，必须确认其前置元数据条件已满足；若未满足，只能标记为 `blocked`，不能伪装成“服务 ready”。

失败结论：

- 真实 `xtdata` 不可达或端口未就绪，记 `fail_env`。
- 返回结构、状态语义、元数据前置条件定义错误，记 `fail_design`。

### G3 交易侧只读验收

目的：确认 Trade Gateway 的登录、预热、探测和只读查询链条成立。

必须按以下顺序执行：

1. `miniqmt.ensure_logged_in`
2. `session.warm`
3. `session.status`
4. `probe.connection`
5. `account.show`
6. `positions.list`
7. `orders.list`
8. `snapshot.l1`

通过条件：

1. 登录与预热可成功完成，且结果可追溯。
2. `session.status` 返回的会话状态与实际可用会话一致。
3. `probe.connection` 的结果能区分登录、端口、会话、快照层面的失败。
4. 账户、持仓、委托和 L1 读取结果与当前账户状态一致。
5. 如果系统声明支持多账户，则显式账户调用和默认账户调用必须契约一致；如果只支持单账户，则 schema 必须明确不支持显式账户切换。

失败结论：

- `xttrader connect=-1`、路径、权限、会话冲突，记 `fail_env` 或 `blocked`。
- schema、会话契约、探测语义与实现不一致，记 `fail_design`。

### G4 受控最小真单验收

目的：在受控风险下证明真实写路径成立，并能被完整追踪。

前置条件：

1. 已通过 `G0` 到 `G3`。
2. 处于允许交易的专用时间窗口。
3. 使用专用账户或专用验证标的。
4. 已确认 `up_queue_xtquant` 等写权限前置条件满足。
5. 已明确最小数量和撤单策略。
6. prod trade config 的 `kill_switch_file` 已配置为非空路径。

当前 formal standard 对写路径真相固定采用以下口径：

1. `session_resolution.effective_session_plan` 是 `G4` 的单一主真相；warm、probe、write、审查都必须回链到同一套 plan。
2. `observed_probe_session_id`、`read_only_probe.session_id` 等字段只表示观测到的 probe/read-only session，不能替代 write-path truth。
3. 任意 legacy / native probe pass，包括固定 `100/101` 这类 session 的 pass，只能证明观测链或 supplemental probe 成功，不能单独升格为 write-ready 证据。
4. `write_permission_ready=true` / `write_authority_ready=true` 只表示当前 packet 具备尝试 governed write 的 runtime 条件，不能单独等价于 `trade_write_authority`、`G4 pass` 或 release authority。

必须执行的链路：

1. `order.place`
2. `order.status`
3. `orders.list`
4. `order.cancel`，若订单状态允许撤单
5. `fills.list`

通过条件：

1. `order.place` 真实进入 broker 写路径，而不是模拟结果或假响应。
2. 返回值包含可追踪的 `broker_order_id` 或等价 broker 侧标识。
3. `order.status` 和 `orders.list` 能观测到该单的状态链。
4. 若订单可撤，`order.cancel` 有明确结果。
5. 无论是否成交，`fills.list` 都必须被检查并纳入记录。
6. 所有审计 artifact、trace、时间戳和状态证据完整留档。
7. 若使用 `trade_write_authority` 或等价 formal authority 结论，只有在 `same_plan_verdict=true`、`probe_complete_verdict=true`、`fresh_connect_verified=true`、`formal_trade_write_closed=true` 同时满足时才允许转绿；缺任一项都不得写成 write-ready / release-ready。

说明：

- 第一版正式通过不强制要求订单一定成交。
- 如果订单立即成交，撤单步骤记为 `N/A`，但必须写明原因并保留证据。
- 若 `order.place` 返回 `broker_submission_attempted=false` 且 `local_gate_intercepted=true`，正式语义固定为本地 gate 层拦截、未进入券商柜台。
- 若历史工件只保留了 `connect_gate_failed + broker_order_id=""`，可作为 fallback 佐证同一 no-go 结论；但当前 operator 判断应优先锚定 machine-readable local gate 字段，不再依赖空 `broker_order_id` 做人工猜测。
- `flow_smoke` 只可证明 MCP 写路径生命周期壳子存在，不能替代 live governed write，也不能升格为 `G4 pass`、write authority 或 release authority。
- `scripts/run_controller_direct_test.ps1` 负责 fresh packet 执行与 runtime capture；formal authority green 只允许出现在 fresh packet 完成后、独立 `ReviewPack` 产出并完成 state truth refresh 之后。

### `VAL-003 / G4` 术语收口

以下口径用于把 live packet 的 session-plan / readiness / current truth 统一到一套正式文档语义：

1. `session_resolution.effective_session_plan` 是 canonical session plan 的唯一主真相；当前 runtime payload 已显式暴露 `session_plan_version`，若后续再补 `canonical_session_plan_version`，它们都只能表示该主真相的 contract/version 元数据，不能替代实际 plan 文本或覆写当前 packet 解析出的 session 集。
2. `probe_complete_verdict` 在文档中专指“当前 packet 的 Round 2 bounded native probe 是否在 canonical session plan 上完成”的正式结论。若当前轮在 gateway recovery 或 Round 1 就停止，则必须明确写“本轮未产生 current-round probe verdict”，不得继承上一轮的 probe 结果或 write-path no-go。
3. 当前仓内正式 packet readiness 入口是 `scripts/check_packet_readiness.ps1` 产出的 machine-readable `go/no_go`，并由 `scripts/run_controller_direct_test.ps1` 在 Round 1/2 hard-stop 后消费。若后续讨论沿用“packet readiness”称呼，必须同时回链到该脚本输出、当轮 `Controller Judgment` 与正式 `EvidencePack / ReviewPack`。
4. 若 fresh packet 在 Round 2 前就停止，当前 formal truth 必须收口为 fresh blocked truth，而不是继续沿用旧 `connect_gate_failed`、旧 native probe failure 或其他历史 baseline 充当本轮结论。

失败结论：

- 因市场关闭、券商权限、环境不稳导致无法执行，记 `blocked` 或 `fail_env`。
- 写路径绕过服务端 gate、风险证据缺失、返回契约错误，记 `fail_design`。

## 硬停止条件

出现以下任一情况时，必须停止继续推进更高 gate：

- `xtdata_port_not_ready`
- `xttrader connect=-1`
- session 冲突或 session 无法唯一判定
- warm / probe / write 的 `session_resolution.effective_session_plan` 不一致，或 `write_session_alignment.same_plan_verdict != true`
- gateway `/healthz` 不可用
- prod trade `/healthz.write_safety.release_blockers` 非空，或 `kill_switch_file` 仍为空
- `up_queue_xtquant` 缺失且当前验收涉及写路径
- `market_window_closed`
- 实例目录中发现 fake 状态污染生产证据
- 把 `observed_probe_session_id`、legacy probe pass、单次 cached `write_permission_ready=true` / `write_authority_ready=true` 或 `flow_smoke` 结果解释为 formal green / write-ready / release-ready
- 文档口径与实现口径冲突，足以误导 agent

## 失败分类规则

### 环境失败

以下场景优先归类为 `fail_env`：

- MiniQMT 未启动
- 端口未打开
- 交互桌面不可用
- 券商权限未开
- 市场时段不允许
- 本机路径、进程或权限异常

### 设计失败

以下场景优先归类为 `fail_design`：

- 工具 schema 与实际语义矛盾
- 状态输出把配置值冒充运行时事实
- 会话或账户契约前后不一致
- 写路径绕过设计宣称的 gate
- 测试与生产状态无法区分

## 当前版本的放行门槛

在本仓库当前阶段，任务是否可以对外宣告“可供 agent 使用”，至少满足：

1. 对应任务要求的最高 gate 已通过。
2. 没有未关闭的 `fail_design`。
3. 所有证据已归档。
4. 审查结论为可放行。
5. 若结论涉及 trade 写路径或 `G4`，单一主真相必须仍是 `session_resolution.effective_session_plan`，不能退回到观测字段或固定 probe session。
6. 若结论涉及 trade 写路径或 `G4`，`trade_write_authority` 只有在 `same_plan_verdict=true`、`probe_complete_verdict=true`、`fresh_connect_verified=true`、`formal_trade_write_closed=true` 同时满足时才允许视为绿灯。
7. `write_permission_ready=true` / `write_authority_ready=true` 只能证明 runtime packet 可尝试 governed write，不能单独充当 formal green、`trade_write_authority` 或 release authority。
8. `flow_smoke`、`write_permission_precheck_ok=true`、`observed_probe_session_id` 命中、或 `100/101` 这类 probe pass，均不能单独充当写路径放行证据。

如果缺少任一项，只能写 `partial` 或 `blocked`，不能写 `pass`。
