# MCP 设计规范

关联进度文档：[CURRENT_STATUS.md](./CURRENT_STATUS.md)  
关联审查文档：[DESIGN_REVIEW_20260327.md](./DESIGN_REVIEW_20260327.md)  
协作与验收入口：[../AGENTS.md](../AGENTS.md) | [WORKFLOW_AND_BOARD.md](./WORKFLOW_AND_BOARD.md) | [ACCEPTANCE_STANDARD.md](./ACCEPTANCE_STANDARD.md) | [TEMPLATES.md](./TEMPLATES.md)

## 文档状态

- 文档类型：规范性 spec
- 主要受众：消费本地 MCP 的 agent、开发 agent、测试 agent、审查 agent
- 当前状态：目标契约
- 当前实现差距：见本文末尾“Current Gaps”

本文不用于重复 README，也不用于罗列当前代码的所有细节。正文定义目标契约、消费边界与服务语义；当前实现偏差、实验能力与待修项统一放在“Current Gaps”中，避免现状与目标态混写。

## 当前契约优先级

为避免历史 formal artifact 的旧字段语义误导当前 operator / agent，当前 repo 固定采用以下读取优先级：

1. 当前 contract 与运行判断，以本文、[OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md)、[CURRENT_STATUS.md](./CURRENT_STATUS.md) 和对应 deterministic tests 为准。
2. 历史 `TaskCard` / `ChangePack` / `EvidencePack` / `EnvSnapshot` / `ReviewPack` 只用于保留当时现场真相，不自动升格为当前 contract。
3. 对 `2026-04-08` 之前形成的历史工件，若仍出现以下旧语义，应按“历史表述”理解，而不是按当前 contract 理解：
   - `probe.connection.session_id` 表示观测到的 probe session，而非 write-path resolved session
   - `write_permission_ready=true` 更接近 precheck success，而非当前意义上的 write authority closure
   - `connect_gate_failed + broker_order_id=\"\"` 没有 `broker_submission_attempted` / `local_gate_intercepted` 等机器可读字段
   - `orders.list ok=true` 但尚未显式区分 `truth_scope` / `broker_truth_confirmed`
4. 历史 formal artifact 原则上不回写重释现场，只在当前入口文档中标明其语义边界。

## 规范语言

本文使用以下规范词：

- `MUST`：必须满足的契约要求
- `MUST NOT`：明确禁止
- `SHOULD`：推荐采用，除非有充分理由偏离
- `MAY`：允许但非必需

## 目的与范围

`xtqmt-mcp` 的目标是在 Windows 本机提供面向 agent 的本地 MCP 能力面，只保留两类服务：

1. `xtqmtTradeGateway`
2. `xtqmtDataGateway`

这两个服务构成 agent 的正式消费面。WSL 或其他 agent 环境 `MUST NOT` 直接 `import xtquant`，而 `MUST` 通过本地 MCP 访问交易与数据能力。该边界与部署前提见 [README.md](../README.md)、[settings.py](../xtqmt_mcp/settings.py) 与 [http transport](../xtqmt_mcp/http_transport.py)。

本文当前 `MUST NOT` 扩展为第三类具体服务；未来扩展规则见“Extension Rules”。

## 设计原则

### 1. Agent-first

能力设计 `MUST` 以 agent 可稳定消费、可恢复推理、可追溯诊断为第一优先级，不以实现便利、脚本兼容或人工操作习惯为第一优先级。

### 2. Runtime truth over static defaults

服务对外暴露的状态 `MUST` 反映实例运行时真相，而不是配置默认值、示例值或历史习惯值。`xtdata` 端口、`session_id`、订阅活性、写权限状态都属于运行时事实，不属于协议常量。

### 3. Governed write path

写能力 `MUST` 走服务端受控路径。prompt 只能约束 agent 顺序，`MUST NOT` 代替服务端门禁。agent 看见“可写能力”时，默认理解应是“服务端已经执行强门禁”，而不是“只是把底层 submit 包了一层”。

### 4. Capability and state separation

文档 `MUST` 明确区分 capability、runtime state、resource、prompt、evidence artifact，避免将“存在某个工具”误解为“当前实例已经具备稳定执行条件”。

## 总体架构

整体链路为：

`vendor bundle -> Python 3.13 venv -> xtqmtTradeGateway / xtqmtDataGateway -> streamable HTTP`

运行时启动、bundle 校验与服务暴露的主入口见：

- [bootstrap_runtime.ps1](../scripts/bootstrap_runtime.ps1)
- [run_trade_gateway_http.py](../scripts/run_trade_gateway_http.py)
- [run_data_gateway_http.py](../scripts/run_data_gateway_http.py)
- [http transport](../xtqmt_mcp/http_transport.py)

目录分层 `MUST` 满足以下边界：

- 代码仓：`D:\xtquant-mcp\repo`
- 实例运行时：`D:\xtquant-mcp\instance\prod`
- vendor bundle：`D:\xtquant-mcp\vendor\xtquant_250807`
- Python venv：`D:\xtquant-mcp\venv313`

运行依赖 `MUST NOT` 散落到 QMT 安装目录、旧 `D:\lh\qlib` 目录或旧 `.venv311` 环境。该边界见 [README.md](../README.md) 与 [settings.py](../xtqmt_mcp/settings.py)。

## Shared Contract Model

### 能力对象模型

本文统一定义五类对象：

1. `capability`
   对外可调用的 MCP tool 或可消费的服务能力。
2. `runtime state`
   当前实例运行时真相，例如实际端点、当前会话状态、当前写权限状态。
3. `resource`
   最近一次稳定状态、缓存视图或诊断证据的只读读取面。
4. `prompt`
   对 agent 的推荐顺序、恢复流程和注意事项。
5. `evidence artifact`
   日志、状态快照、调用审计、下载工件等可追溯产物。

工具是否存在，不等于该能力当前可稳定执行；资源是否存在，也不等于对应 capability 当前可执行。

### 单账户优先契约

当前目标契约采用单账户优先模型：

- 服务端 `MUST` 拥有一个主账户上下文。
- agent `SHOULD` 以该主账户上下文消费 Trade Gateway。
- 多账户扩展 `MAY` 在后续版本引入，但 `MUST NOT` 在当前正文中与主契约混写。

### Readiness 与 capability flags

对外状态 `MUST NOT` 只暴露一个模糊的 `ready=true|false`。所有核心状态 `SHOULD` 至少拆为以下分层：

- import or bundle readiness
- endpoint connectivity readiness
- metadata readiness
- session or lease readiness
- write permission readiness

对 agent 有行为影响的能力 `SHOULD` 进一步以 capability flags 表达，例如：

- `can_connect`
- `can_query_readonly`
- `can_trade_write`
- `can_start_download`
- `can_hold_subscription_lease`

### 失败分类

正文中的失败语义 `MUST` 明确区分以下层次，不得将它们混成单一“不可用”：

- `environment`
- `connectivity`
- `permission`
- `metadata_missing`
- `risk`
- `contract_violation`
- `business_rejection`

## Trade Gateway Spec

### 职责边界

`xtqmtTradeGateway` `MUST` 负责以下能力族：

- MiniQMT 登录与登录证据
- 交易会话生命周期
- 只读连接诊断
- 账户、持仓、委托、成交、L1 快照读取
- 受控写路径下的下单与撤单
- 写路径审计与可追溯证据

其服务入口与配置边界见：

- [trade gateway server](../xtqmt_mcp/trade_gateway/server.py)
- [trade gateway config](../xtqmt_mcp/trade_gateway/config.py)
- [trade gateway resources](../xtqmt_mcp/trade_gateway/resources.py)
- [trade gateway prompts](../xtqmt_mcp/trade_gateway/prompts.py)

### 对外工具面

Trade Gateway 当前目标工具面 `SHOULD` 至少覆盖以下公共能力名：

- `miniqmt.ensure_logged_in`
- `session.warm`
- `session.status`
- `session.close`
- `probe.connection`
- `account.show`
- `positions.list`
- `orders.list`
- `fills.list`
- `snapshot.l1`
- `order.status`
- `order.cancel`
- `order.place`

该工具面见 [trade gateway config](../xtqmt_mcp/trade_gateway/config.py)。

### 账户模型

Trade Gateway 正文契约采用单账户优先模型：

- `account_id` `MUST` 被视为服务端上下文的一部分。
- 常规 agent 流程 `SHOULD NOT` 依赖在每次调用中显式选择账户。
- 若未来引入多账户，`MUST` 在 schema、resource、session、审计与执行路径上统一扩展，而不是局部补参。

### 会话模型

交易会话 `MUST` 由服务端 owner 管理。

- `session_id` `MUST` 被视为服务端管理的冲突资源。
- `session_id` `MUST NOT` 在文档中表现为固定模板或官方推荐值。
- 配置里的 `session_id` / `session_candidates` 只 `MAY` 作为实例 seed 或本地候选，不得被外推成官方稳定模板。
- 会话建立 `MUST` 明确区分“当前存在会话对象”和“当前会话已通过健康检查”。
- 断线恢复 `MUST` 被建模为显式重建，而不是透明自动恢复。

ThinkTrader 官方 `xttrader` 语义只要求会话编号不冲突、同一策略通常只维护一个 API 实例、同一 `session_id` 的重复 `connect()` 需要满足冷却；它没有把 `100/101/1111/2111` 这类数字定义成官方推荐模板。因此仓库内的固定数字只能被视为实例状态、本地候选或派生 fallback，不能作为对 agent 暴露的稳定契约。

`session.warm`、`session.status`、`session.close` 的目标职责是：

- 建立或回收服务端托管会话
- 对 agent 暴露当前会话健康状态与证据
- 为后续只读与写路径提供统一上下文

相关实现入口见 [trade gateway session manager](../xtqmt_mcp/trade_gateway/session_manager.py) 与 [trade gateway bootstrap](../xtqmt_mcp/trade_gateway/bootstrap.py)。

#### Session Resolution Contract

对 `G4` live validation packet，仓库目标契约 `MUST` 同时收口以下三个 session 层次：

1. gateway owner session：`session.warm` / `session.status` 暴露的当前托管会话
2. native probe session plan：宿主侧 direct `XtQuantTrader` probe 实际验证的 session 集
3. write-path session plan：真实 `order.place` / `order.cancel` / `order.status` 所解析出的 broker-side session 集，以及 same-call `connect_gate` 最终落到的 session

若实例启用了 derived fallback，服务端 `MUST` 把 base session 与 derived session 一并显式暴露；该 fallback 只是 repo-local 实现策略，不是官方 contract。Round 2 在一套 session plan 上的 probe success，`MUST NOT` 被拿去放行另一套 session plan 上的 Round 3 写路径。像 `session.warm=1111`、native probe=`100/101`、same-call `connect_gate=2111` 这类跨层不一致，必须先被建模为 session 解析语义未收口，而不是被误写成“环境大体恢复，可继续试单”。

当前实现中，`session.warm`、`session.status`、`trade://session/current`、`probe.connection`、`order.place`、`order.cancel`、`order.status` `MUST` 统一暴露 additive `session_resolution` 对象。该对象至少包含：

- `configured_session_id`
- `resolved_base_session_id`
- `resolved_session_id`
- `configured_session_candidates`
- `effective_session_plan`
- `derived_session_fallback_enabled`
- `explicit_session_resolution_applied`

自 `TG-007` 起，session-state 类载体还 `MUST` 明确区分 base truth 与 runtime override：

- `session_resolution`：bootstrap / base session truth，不再被 runtime health check 原地覆盖
- `effective_session_resolution`：base truth 与 runtime override 合成后的当前有效视图
- `runtime_session_override`：当前 runtime realign 事件元数据，至少包含 `event_source`、`reason`、`previous_resolved_session_id`、`resolved_session_id`

兼容约束：

- write-adjacent payload 可以继续保留兼容字段 `session_resolution`，但若存在 runtime override，必须同时暴露 `effective_session_resolution` 与 `runtime_session_override`。
- 对 `session.warm` / `session.status` / `trade://session/current` 这类长期状态载体，operator-facing summary `SHOULD` 以 base `session_resolution` + `effective_session_resolution` 双轨呈现，禁止再把 runtime 观测无痕写成 bootstrap 真相。

兼容策略也固定如下：

- 对 `probe.connection`、`order.place`、`order.cancel`、`order.status` 这类 write-adjacent payload，顶层 `session_id` `MUST` 对齐 `session_resolution.resolved_session_id`，作为 write-path 主真相。
- 观测层实际命中的只读 / probe session `MUST` 通过 additive 字段单独暴露，例如 `observed_probe_session_id`、`read_only_probe.session_id` 或等价子对象；不能再让 shadow/read-only session 占用顶层主语义。
- `session_resolution` 才是 service-side session resolver 的完整真相，单个 probe success 或单个 legacy session success 不能外推成完整 write readiness。
- `session.warm` 必须与后续 write-path 共用同一套 explicit session resolution，但仍保持 warm-health shadow-only 边界，不因收口 resolver 而提前构建 broker 写适配器。
- `probe.connection` `MUST` 额外暴露 machine-readable 的 `write_session_alignment.same_plan_verdict`、`write_permission_precheck_ok`、`write_permission_ready` / `write_authority_ready`；其中 `write_permission_precheck_ok=true` 只表示本地预检通过，只有 same-plan 成立且同 session `connect -> subscribe` verify 完成后，`write_permission_ready` 才允许为 `true`。

### Formal Authority Carrier

`trade_write_authority_latest.json` 的机器输入自 `OPS-008` 起 `MUST` 来自 packet-bound typed carrier，而不是 `CURRENT_STATUS.md` 的 Markdown 文本解析。当前最小 contract 固定如下：

- `trade_write_authority_source_latest.json` 是 authority 的 typed source latest pointer
- typed source `MUST` 至少包含：
  - `packet_id`
  - `trace_id`
  - `diag_probe_ref`
  - `controller_judgment_ref`
  - `formal_truth_snapshot_ref`
  - `formal_closeout_state`
- `review_ref` 对 close/pass packet 仍然是 `MUST`；对 fresh packet / reopen packet，若 `formal_closeout_state.trade_lane_write_closed=false`，typed source `MAY` 暂时留空，但 authority `MUST` 将其作为 warning 保留，且不得因缺 `review_ref` 覆盖更具体的 formal/runtime blocker
- `formal_closeout_state` `MUST` 至少包含：
  - `trade_lane_write_closed`
  - `trade_lane_write_state`
  - `task_id`
  - `status`
  - `gate`
  - `reason`
- 若 typed source 缺任一关键字段，或 `trace_id` 与 `diag_probe.resource_trace_id` 不一致，authority 生成逻辑 `MUST fail closed`，不得回退去猜测 `CURRENT_STATUS.md`。
- 当 `formal_closeout_state.trade_lane_write_closed=false` 时，`trade_write_authority_latest.json.blocking_reason` `SHOULD` 优先暴露 `formal_closeout_state.reason`，若该字段为空则回退到 runtime blocker，再回退到通用 blocker。

#### Support-Confirmed Operator Guidance

除公开官方文档外，当前仓库还采用 `2026-04-08` 用户提供的客服答复作为 operator-facing support-confirmed guidance。该 guidance 只用于当前 repo 的运行判断，不替代公开 SDK contract。

在该 support 口径下：

1. 带 `session_resolution` / derived fallback 的写路径允许存在，但稳定性责任、session 唯一性和重连纪律全部由用户侧承担。
2. `session.warm/session.status=1111`、native probe=`100/101`、write-side `connect_gate=2111` 这类 warm/probe/write 跨层不一致，属于异常会话不一致，而不是可接受的多会话成功形态。
3. 一旦 write-path 实际落到新的 session，该 session 必须重新完成自己的 `connect -> subscribe -> order` 链；旧 session 的 warm/probe 成功不得被继承到新 session。
4. `connect_gate_failed` 且 `broker_order_id=""` 的 operator 语义是“本地 gate 层拦截，订单未进入券商柜台”；这仍不改变执行分类与 review authority 需要独立 formal artifact 才能闭合的治理规则。
5. 当前 repo runtime 已把上述语义下沉为 machine-readable contract：`order.place` 在本地 gate 拦截时应返回 `broker_submission_attempted=false`、`local_gate_intercepted=true`、`submission_scope=local_gate`、`submission_stage=connect_gate`；不再只靠 runbook 解释空 `broker_order_id`。

### 只读能力与写能力分层

Trade Gateway `MUST` 将只读探测和写权限判断拆层建模：

- 只读探测：
  - 连接探测
  - 账户读取
  - 持仓读取
  - 委托读取
  - 成交读取
  - L1 快照读取
- 写权限：
  - 是否具备下单权限
  - 是否允许进入真实写路径

`up_queue_xtquant` 缺失 `MAY` 阻断真实写路径，但 `MUST NOT` 自动否定只读探测和账户诊断能力。相关前置检查逻辑见 [xttrader_precheck.py](../xtqmt_mcp/xttrader_precheck.py)。

对公共 `orders.list`，当前 runtime contract 也 `MUST` 明确区分 broker truth 与 shadow fallback truth：

- `truth_scope=broker_truth` + `broker_truth_confirmed=true`：表示当前结果来自 broker 读取面，可作为 broker open-orders 真相消费。
- `truth_scope=shadow_fallback` + `broker_truth_confirmed=false`：表示当前结果只是 public degraded fallback，不得外推成 broker truth。
- `truth_scope=shadow_warm_health` + `broker_truth_confirmed=false`：表示当前结果只用于 warm-health / owner-shadow 观察，不得拿去替代 public broker truth。
- `truth_scope=broker_unavailable` + `broker_truth_confirmed=false`：表示 broker truth 当前不可得，且没有可接受的 public fallback。

### 受控写路径契约

`order.place` 在目标契约中 `MUST` 被视为唯一受控写路径，而不是普通 thin capability。

服务端在执行真实写入前 `MUST` 至少完成以下 gate：

1. login gate
2. session gate
3. connectivity gate
4. write permission gate
5. risk gate
6. kill-switch gate
7. audit persistence gate

若任一 gate 未满足，服务端 `MUST` 拒绝写入，并返回明确失败分类，而不是仅依赖 prompt 告诉 agent“建议先预热再下单”。

对 prod scope 的 Trade Gateway，`kill_switch_file` `MUST` 为非空配置值。是否真正处于 kill-switch 状态仍由该文件是否存在决定，但“未配置 kill-switch 路径”本身必须被视为 write gate 未闭合，而不是被当作可忽略的默认值。

公共 MCP 入口 `order.place` `MUST` 进入 `TradeOpsService.place_order(...)` 所代表的受控服务端写路径。若保留 [capability_v2.py](../xtqmt_mcp/trade_gateway/capability_v2.py)，它 `MAY` 只作为兼容适配层存在，但 `MUST NOT` 再代表薄 broker 直通语义或重新引入平行未受控写路径。

`order.cancel` 与 `order.status` `SHOULD` 与该写路径共享同一会话与审计边界；`G4` 验证链也 `MUST` 用同一套 session resolution contract 贯穿 Round 2 probe 与 Round 3 write。相关实现边界见：

- [trade gateway server](../xtqmt_mcp/trade_gateway/server.py)
- [capability_v2.py](../xtqmt_mcp/trade_gateway/capability_v2.py)
- [trade_ops.py](../xtqmt_mcp/trade_ops.py)

补充：仓库现在允许一条显式的 non-prod `execution_mode=flow_smoke` 路径，用于盘后或 live gate 未闭合时验证 MCP 写路径生命周期本身。该模式 `MUST` 满足以下边界：

1. 只允许在 `non_prod` state/artifact scope 下运行，不得指向 `instance\prod\state`。
2. `order.place` / `order.status` / `orders.list` / `order.cancel` / `fills.list` 走本地 flow-smoke adapter，不产生真实 broker 委托。
3. payload 与 `/healthz` `MUST` 显式暴露 `execution_mode=flow_smoke`。
4. `orders.list` 在该模式下 `MUST` 标记 `truth_scope=flow_smoke_local`、`broker_truth_confirmed=false`。
5. `order.place` 在该模式下 `MUST NOT` 声称 broker 已提交；当前语义通过 `submission_scope=flow_smoke` 与 `broker_submission_attempted=false` 表达。
6. 该模式 `MUST NOT` 被当作 `VAL-003`、`G4`、broker readiness 或 release authority 证据。

### Trade Resources

Trade Gateway 的资源面 `SHOULD` 只承载最近稳定状态与诊断证据，例如：

- 当前 capability contract
- 当前托管会话摘要
- 最近账户快照
- 最近委托结果
- 最近探测证据
- 最近登录证据

资源 `MUST NOT` 暗示“资源可读 = 当前实例可写”。

Trade 资源当前还 `MUST` 显式暴露 freshness / authority 语义，至少能区分：

- `freshness_status=live_runtime_truth`
- `freshness_status=cached_last_known_state`
- `state_age_seconds`

当前 active 资源面至少应包含：

- `trade://capability/current`
- `trade://session/current`
- `trade://account/current`
- `trade://orders/today`
- `diag://probe/latest`
- `diag://login/latest`

其中 `trade://capability/current` `MUST` 作为 agent-first 读契约入口，至少暴露：

- `server_name`
- `server_version`
- `enabled_tools`
- `enabled_resources`
- `order_echo_fields`
- `write_contract_flags`
- `session_contract_version`

消费方 `MUST NOT` 再用 repo-local 硬编码“猜” Trade Gateway 是否支持严格写路径；若 `trade://capability/current` 缺失，执行侧应 fail closed。
- `resource_path`
- `resource_server_ts`
- `resource_trace_id`

若 payload 只是落盘缓存视图，它 `MUST NOT` 被表示成当前 listener 的 authoritative runtime truth；即使缓存内容本身可读，也只能作为 last-known-state 消费。

当前目标资源面 `SHOULD` 至少包括：

- `trade://session/current`
- `trade://account/current`
- `trade://orders/today`
- `diag://probe/latest`
- `diag://login/latest`

当前目标 prompt 面 `SHOULD` 至少包括：

- `trade-preflight`
- `trade-recovery`
- `order-followup`

### Trade Prompts

Trade prompt 的职责是：

- 指导 agent 正确顺序使用能力
- 提示恢复步骤
- 降低误用概率

Trade prompt `MUST NOT` 作为真实安全边界。相关入口见 [trade gateway prompts](../xtqmt_mcp/trade_gateway/prompts.py)。

### Trade Failure Taxonomy

Trade Gateway 的失败输出 `SHOULD` 至少区分：

- `environment`
- `connectivity`
- `permission`
- `risk`
- `business_rejection`
- `contract_violation`

## Data Gateway Spec

### 职责边界

`xtqmtDataGateway` `MUST` 负责以下能力族：

- 服务状态与诊断
- 标的目录与交易日历查询
- 批量快照、K 线与逐笔历史读取
- 异步数据下载作业
- 实时订阅租约
- 数据侧恢复流程提示

其服务入口与配置边界见：

- [data gateway server](../xtqmt_mcp/data_gateway/server.py)
- [data gateway config](../xtqmt_mcp/data_gateway/config.py)
- [data gateway service](../xtqmt_mcp/data_gateway/service.py)
- [data gateway jobs](../xtqmt_mcp/data_gateway/jobs.py)
- [data gateway resources](../xtqmt_mcp/data_gateway/resources.py)
- [data gateway prompts](../xtqmt_mcp/data_gateway/prompts.py)

### 对外工具面

Data Gateway 当前目标工具面 `SHOULD` 至少覆盖以下公共能力名：

- `xtdata.status`
- `xtdata.instruments.search`
- `xtdata.calendar.query`
- `xtdata.snapshot.batch`
- `xtdata.history.get_bars`
- `xtdata.history.get_ticks`
- `xtdata.download.submit`
- `xtdata.download.status`
- `xtdata.download.cancel`
- `xtdata.subscribe.start`
- `xtdata.subscribe.stop`

该工具面见 [data gateway config](../xtqmt_mcp/data_gateway/config.py)。

### Endpoint 契约

`xtdata` 端口 `MUST NOT` 被描述为协议常量。

Data Gateway 对外 `SHOULD` 同时表达两类信息：

- configured endpoint
- resolved runtime endpoint

其中 agent 决策 `MUST` 基于 resolved runtime endpoint，而不是示例值或配置默认值。`xtdata.status` `MUST` 输出当前实际解析到的 host/port、连通性与相关诊断，而不是只输出静态配置。

### Readiness 分层

Data Gateway 的 readiness `MUST` 至少拆为以下层：

1. bundle/import readiness
2. endpoint connectivity readiness
3. basic market-data query readiness
4. sector metadata readiness
5. download subsystem state
6. subscription lease state

单一 `ready=true|false` `MAY` 作为汇总字段存在，但 `MUST NOT` 取代分层状态。

### 元数据依赖

标的目录与板块分类能力 `MUST` 被视为元数据能力，而不是基础连接能力。

- `get_sector_list()` 与板块检索相关能力依赖 sector metadata。
- sector metadata 缺失 `MAY` 影响标的搜索与板块查询。
- sector metadata 缺失 `MUST NOT` 自动推出“xtdata 服务整体不可用”。

### 异步下载模型

长耗时数据下载 `MUST` 以 durable job 模型暴露，而不是同步阻塞调用。

`download.submit/status/cancel` 的目标契约是：

- `submit` 创建服务端持有的异步作业
- `status` 查询作业当前状态、进度、错误与工件路径
- `cancel` 终止仍可取消的作业

该模式是当前设计中应保留的部分，见 [data gateway jobs](../xtqmt_mcp/data_gateway/jobs.py)。

### 订阅租约模型

实时订阅在目标契约中 `SHOULD` 建模为 `subscription lease`，而不是稳定持久能力句柄。

租约健康状态 `SHOULD` 至少包含：

- callback loop 是否存活
- xtdata 连接是否仍存活
- 最近事件时间
- `lease_state`，至少可区分 `active`、`stale`、`stopped`
- 是否需要重建租约
- `rebuild_reason`
- 停止原因

当 `lease_state != active` 时，服务端输出 `SHOULD` 明确标出 `needs_rebuild=true`，并把 `callback_loop_alive`、`connection_alive` 与 `rebuild_reason` 一起暴露给 agent；该组合用于指导显式 rebuild，而不是暗示服务端已经完成透明自动恢复。

在真实 smoke 尚未证明订阅恢复模型前，订阅能力 `MUST` 标记为实验能力。agent 看见 `subscription_id` 时，默认理解 `MUST` 是“租约标识”，而不是“长期稳定订阅证明”。文档与输出 `MUST NOT` 把 reconnect / auto-rebuild 表述成已被 live 证明的稳定能力。

### Data Resources

Data Gateway 的资源面 `SHOULD` 保留：

- 最近服务状态
- 活动作业视图
- 标的目录缓存
- 活跃或最近租约状态

资源 `MUST NOT` 暗示“缓存目录可读 = 连接、元数据、订阅都已准备完成”。

与 Trade 资源相同，Data 资源 `MUST` 暴露 freshness / authority 语义，至少让 agent 能区分当前 payload 是 live runtime truth，还是仅仅来自 cache file 的 last-known-state。

当前目标资源面 `SHOULD` 至少包括：

- `xtdata://service/status`
- `xtdata://jobs/active`
- `xtdata://catalog/instruments`
- `xtdata://leases/active`

当前目标 prompt 面 `SHOULD` 至少包括：

- `data-backfill-plan`
- `data-download-triage`
- `xtdata-service-recover`

### Data Failure Taxonomy

Data Gateway 的失败输出 `SHOULD` 至少区分：

- `bundle_invalid`
- `connectivity`
- `metadata_missing`
- `job_failed`
- `lease_stale`
- `contract_violation`

## Shared Runtime, Security, and Evidence Model

### 传输与本机绑定

两个 HTTP 服务 `MUST` 默认只绑定 `127.0.0.1`，并使用 origin allowlist 约束本机访问。相关实现见：

- [http transport](../xtqmt_mcp/http_transport.py)
- [trade gateway config](../xtqmt_mcp/trade_gateway/config.py)
- [data gateway config](../xtqmt_mcp/data_gateway/config.py)

两个 gateway 的 `/healthz` 当前还 `SHOULD` 暴露可用于 freshness 判定的运行态字段，例如：

- `server_ts`
- `freshness_status`
- `process_identity`
- `latest_audit_log`

这些字段的目标不是替代正式 EvidencePack，而是避免 operator 把 stale process 或旧 cache 误认成当前 repo-backed listener。

### 资源落盘与状态目录

服务端 `MUST` 将状态、日志与工件分目录落盘，避免将缓存、审计与下载产物混在一起。默认目录边界见：

- [README.md](../README.md)
- [settings.py](../xtqmt_mcp/settings.py)
- [trade_gateway.example.yaml](../configs/trade_gateway.example.yaml)
- [data_gateway.example.yaml](../configs/data_gateway.example.yaml)

### 证据模型

可用于验收或审查的证据 `SHOULD` 包括：

- 命令与执行时间
- 调用结果
- 状态快照
- 审计日志
- 下载工件

fake 状态、测试污染、手工伪造缓存 `MUST NOT` 被当作生产运行证据。

## Extension Rules

当前正文只定义 `Trade Gateway` 与 `Data Gateway`。未来若新增服务族，新服务 `MUST` 满足以下扩展规则：

1. 继续采用 capability、runtime state、resource、prompt、evidence artifact 五分法。
2. 对外状态继续采用分层 readiness，而不是单一模糊 ready。
3. 写能力继续采用受控 gate 模型。
4. 继续满足 localhost、本机 allowlist、审计落盘和证据可追溯要求。

未来扩展 `MAY` 引入新服务名，但 `MUST NOT` 破坏当前 Trade/Data 主干契约。

## 明确不做的事

当前规范 `MUST NOT` 承诺以下内容：

- 兼容旧 `D:\lh\qlib` 路径、旧 `.venv311` 环境或旧脚本调用方式
- 在本文中扩展 README 式使用教程
- 将交易无关的通用能力纳入当前服务边界
- 将多账户直接写成当前主契约

## Current Gaps

以下内容只保留截至 2026-03-31 仍未闭合的真实差距。已经在代码、测试与正式工件中落地的项，例如单账户主契约、`xtdata.status` 分层 readiness、`resolved runtime endpoint`、`read_only vs write_permission` 拆层，以及 subscription lease 的恢复语义字段，不再继续列为当前 gap。

### 1. `G4` 受控写路径仍未获得正式 live 证明

- Target contract：
  在宣称 Trade Gateway 写路径可正式放行前，必须形成 `order.place -> order.status -> orders.list -> order.cancel -> fills.list` 的最小真单正式证据链。
- Current implementation shape：
  截至 `TG-001` 开发收口，公共 `order.place` 已在代码和 deterministic 测试中收口到受控服务端写路径；随后 [VAL-003.md](./task_cards/VAL-003.md) 已形成多轮正式 `EvidencePack` / `ReviewPack`，证明真实 governed write 确实被触发，但 `G4` 仍未闭合。最新 `2026-04-03 14:44/14:47 +08` formal truth 是：真实 `order.place` 仍在 same-call pretrade `connect_gate` 收口为 `connect_gate_failed`，没有 `broker_order_id`，因此任务级状态保持 reviewed `Blocked`，而不是 `G4 pass`。
- Impact on agent：
  agent 不应把 `G3` 的 truthful degraded read success 或 broker/session 只读恢复外推成 `order.place` 已 ready。
- Required follow-up：
  只有在 `2026-04-03` 之后出现新的环境恢复 formal truth，足以关闭 `connect_gate_failed` 对应的 higher-gate broker/session instability 时，才允许 [VAL-003.md](./task_cards/VAL-003.md) 重新从 Round 1 -> Round 3 进入独立验证；在那之前保持写路径未放行。

### 2. subscription live reconnect / auto-rebuild 仍未被正式证明

- Target contract：
  订阅应暴露为 experimental subscription lease，并且只有在独立验证后才能宣称 live reconnect / auto-rebuild 已成立。
- Current implementation shape：
  当前恢复语义模型已经落地，且 [DG-003-review-20260330174620.md](./reviews/DG-003-review-20260330174620.md) 已确认 `active` / `stale` / `stopped`、`needs_rebuild`、`rebuild_reason`、`resolved runtime endpoint` 等表达与 spec 一致；剩余差距只在“live reconnect / auto-rebuild 尚未被正式证明”。
- Impact on agent：
  agent 仍必须把 subscription 当作 experimental lease，对 `subscription_id` 的理解保持在“租约标识”而不是“已证明可自动恢复的长期订阅能力”。
- Required follow-up：
  继续维持“explicit rebuild required”的解释口径；若未来要宣称 live reconnect / auto-rebuild 成立，必须走新的独立验证卡，而不是复用现有 DG-003 结论。

## 参考来源

官方文档：

- <https://dict.thinktrader.net/nativeApi/start_now.html>
- <https://dict.thinktrader.net/dictionary/>
- <https://dict.thinktrader.net/nativeApi/xtdata.html>
- <https://dict.thinktrader.net/nativeApi/xttrader.html>
- <https://dict.thinktrader.net/nativeApi/code_examples.html?id=7zqjlm>
- <https://dict.thinktrader.net/nativeApi/question_function.html?id=TB5IbM>
- <https://dict.thinktrader.net/dictionary/question_answer.html>

本地代码与配置：

- [README.md](../README.md)
- [trade gateway server](../xtqmt_mcp/trade_gateway/server.py)
- [data gateway server](../xtqmt_mcp/data_gateway/server.py)
- [trade gateway config](../xtqmt_mcp/trade_gateway/config.py)
- [data gateway config](../xtqmt_mcp/data_gateway/config.py)
- [trade gateway session manager](../xtqmt_mcp/trade_gateway/session_manager.py)
- [data gateway service](../xtqmt_mcp/data_gateway/service.py)
- [trade_ops.py](../xtqmt_mcp/trade_ops.py)
