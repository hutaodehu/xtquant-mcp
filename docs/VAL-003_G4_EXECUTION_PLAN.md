# `VAL-003 / G4` 执行计划

关联任务卡：[task_cards/VAL-003.md](./task_cards/VAL-003.md)  
关联 ChangePack：[change_packages/VAL-003.md](./change_packages/VAL-003.md)  
当前状态入口：[CURRENT_STATUS.md](./CURRENT_STATUS.md)  
运维手册：[OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md)  
验收标准：[ACCEPTANCE_STANDARD.md](./ACCEPTANCE_STANDARD.md)  
执行与工件规范：[EXECUTION_AND_ARTIFACT_STANDARD.md](./EXECUTION_AND_ARTIFACT_STANDARD.md)  
协作模板：[TEMPLATES.md](./TEMPLATES.md)  
协作规则：[../AGENTS.md](../AGENTS.md)

## 文档状态

- 文档类型：formal execution plan
- 编制时间：2026-04-02
- 最近 reconcile：2026-04-11T00:34:08+08:00
- 主要受众：controller、test、review
- 当前任务 posture：`Blocked / data_gateway_port_conflict_nonrepo_listener_8766`
- 当前目标：不是继续沿用旧的 same-day retry 思路，而是把 `VAL-003` 固化为“只有在 fresh 环境恢复 formal truth 出现后，才允许重新进入 Round 1 -> Round 3”的 reopen plan
- 最新 reviewed no-go baseline：
  - `2026-04-11 00:30:25 +08` 的 fresh controller-direct packet 在 gateway recovery 即停止：trade wake `started` 且 health 正常，但 data wake 返回 `status=port_conflict`
  - `2026-04-11 00:34:08 +08` 的独立 `ReviewPack` 已正式把当前唯一 blocker 收口为 `data_gateway_port_conflict_nonrepo_listener_8766`；本轮 `order.place` 未执行，因此 current truth 只能写成 fresh blocked，而不是继续沿用旧 `connect_gate_failed`
  - `2026-04-09 14:13:01 +08` 的 raw runtime capture 提供了当前最新一轮“已显式收口 canonical session plan”的 machine-readable 基线：preflight effective session plan=`2111,2100,2101`，preflight same-plan verdict=`True`，native probe same-plan verdict=`True`，但 `fresh_connect_verified=false`、native probe `overall_ok=false`
  - `2026-04-08 10:13 +08` 的独立 `ReviewPack` 仍保留为 reopen authority 的历史 design baseline：`1111 / 100,101 / 2111` 的 session-plan split 不能被解释成写路径 ready
  - 当前仓内已新增独立 `scripts/check_packet_readiness.ps1`；packet readiness 的正式 stop/go 入口为该脚本输出的 machine-readable `go/no_go`，并由 `scripts/run_controller_direct_test.ps1` 在 Round 1/2 hard-stop 后消费，再由当轮 `Controller Judgment` / `EvidencePack` / `ReviewPack` 收口 formal truth
- 非目标：
  - 不替代正式 `EvidencePack`、`EnvSnapshot`、`ReviewPack`
  - 不宣称当前已经 `G4 ready`
  - 不允许在计划文档里越权宣布 `order.place` 可以直接执行

## 固定执行参数

- 默认 controller mode：`controller-only`
- TaskCard policy：`Controller Test Policy: controller_direct_required`
- 执行轮次：`3`
- 测试标的包：
  - side：`BUY`
  - symbol：`515880.SH`
  - qty：`100`
  - price_mode：`l1_protect`
  - cancel_timeout：`30s`
- 运行宿主：Windows 本机 `D:\xtquant-mcp\repo`
- live 实例目录：`D:\xtquant-mcp\instance\prod`
- trade config：`D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- gateway 入口：
  - trade gateway：`http://127.0.0.1:8765/mcp`
  - trade `/healthz`：`http://127.0.0.1:8765/healthz`
  - data `/healthz`：`http://127.0.0.1:8766/healthz`
- 原则：
  - 不经 WSL
  - 不在 WSL 直接 `import xtquant`
  - 不扩大单量
  - 不在没有 fresh recovery evidence + manual gate 的情况下自动追加任何 live order

## 当前 canonical session plan / readiness 口径

1. 当前正式文档中的 canonical session plan 主真相固定为 `session_resolution.effective_session_plan`，不是 legacy `100/101` probe，也不是单个 observed session。
2. 以目前仓内已落盘的 machine-readable packet 看，最近一轮完整记录该主真相的是 `2026-04-09 14:13:01 +08` 的 controller-direct runtime capture：
   - preflight effective session plan：`2111,2100,2101`
   - preflight same-plan verdict：`True`
   - native probe same-plan verdict：`True`
   - native probe overall_ok：`False`
   - `fresh_connect_verified`：`False`
3. 因此当前能成立的正式结论是“canonical session plan 语义已收口到 `2111,2100,2101` 这一套计划文本，但 fresh native probe / fresh connect 尚未闭合”；这不是 write authority，也不是 `G4 pass`。
4. 对 `2026-04-11 00:30 +08` 这轮 fresh blocked packet，runner 在 gateway recovery 就停止，所以本轮没有 current-round `probe_complete_verdict`，也没有 current-round write-path verdict。
5. 当前仓内已新增独立 `scripts/check_packet_readiness.ps1`；凡提到 packet readiness，都应回链到该脚本输出、`scripts/run_controller_direct_test.ps1`、对应 controller judgment 与正式 `EvidencePack / ReviewPack`。

## `2026-04-13` 最新 runtime 进展（non-formal）

1. 当前这轮推进没有生成新的 formal packet / ReviewPack，因此 `2026-04-11` 的 fresh blocked truth 继续保持不变。
2. 但 runtime 层已经完成三项关键收口：
   - `check_packet_readiness.ps1` 与 `run_controller_direct_test.ps1` 当前已优先消费 gateway-side fresh authority，而不是把旧 external native probe 当作唯一主 gate。
   - `session.warm / session.status` 已能在 live 环境中稳定 realign 到 `resolved_session_id=2101`。
   - `probe.connection` 现在会在 owner shadow 仍停在旧 session、但该 session 仍属于 `effective_session_plan` 时继续尝试 broker fresh verify。
3. 最新 clean recovery + UI 登录已证明：
   - 凭据 target、密码填充、`up_queue_xtquant`、warm/status session split 已不再是当前主 blocker。
   - 当前 runtime 层唯一剩余 blocker 已缩小为 broker fresh connect 本身。
4. 最新顺序化 live 结果是：
   - `session.warm.session_id=2101`
   - `session.status.session_id=2101`
   - `probe.connection.session_id=2101`
   - 但 `probe.connection.reason=write_connect_failed`
   - `fresh_connect_verified=false`
   - `write_authority_ready=false`
5. 因此当前 reopen 目标必须继续收敛：不是再回头修登录、session 解析或 packet gate，而是直接证明 `2101` 上的 broker fresh connect 可以从 `-1` 变成 `0`。

## 使用的技能与标准

### 技能

- repo-local controller skill：`.agents/skills/spec-task-harness/SKILL.md`
- 默认使用方式：`controller-only`
- 对本卡的真实 live test，主控不再依赖一次性 override 口头约定，而是按 TaskCard 里的 `Controller Test Policy: controller_direct_required` 手动触发 `scripts/run_controller_direct_test.ps1`
- controller 允许做：
  - reconcile 当前 repo truth
  - render bounded dispatch
  - 检查工件是否齐备
  - 基于既有 role-owned artifact 同步 ledger
- controller 对本卡额外允许做：
  - 作为真实执行者运行 `scripts/run_controller_direct_test.ps1`
  - 产出带 `Executor: controller direct test execution` metadata 的正式 `Role: test` 工件
- controller 不允许做：
  - 代做 `dev` / `review`
  - 在不满足 TaskCard policy 或 gateway recovery 失败时继续写路径
  - 亲自补写 `ReviewPack` 或伪装成子代理结果
  - 在 no-go 条件下直接发起 `order.place`

### 标准源

执行时必须同时满足以下标准源：

1. [AGENTS.md](../AGENTS.md)
2. [CURRENT_STATUS.md](./CURRENT_STATUS.md)
3. [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md)
4. [ACCEPTANCE_STANDARD.md](./ACCEPTANCE_STANDARD.md)
5. [EXECUTION_AND_ARTIFACT_STANDARD.md](./EXECUTION_AND_ARTIFACT_STANDARD.md)
6. [TEMPLATES.md](./TEMPLATES.md)
7. [task_cards/VAL-003.md](./task_cards/VAL-003.md)

## 开盘前准备

### 1. 入口阅读顺序

1. 读取 [task_cards/VAL-003.md](./task_cards/VAL-003.md)。
2. 读取 [CURRENT_STATUS.md](./CURRENT_STATUS.md)。
3. 读取 [ACCEPTANCE_STANDARD.md](./ACCEPTANCE_STANDARD.md) 的 `G4` 与 hard-stop 规则。
4. 读取 [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md)。
5. 读取本文，确认固定 packet、轮次、工件与停点。

### 2. controller 准备

1. 用 `$spec-task-harness, controller-only` 先做一次 reconcile。
2. 确认 `VAL-003` 仍是唯一待推进的 `G4` 卡。
3. 本卡在 `select_next_safe_tasks.py` 中应继续停留在 `manual_resume_required`，不会进入普通 `dispatchable`；这不是异常，而是主控亲测策略的正式行为。
4. 只有在当前 formal posture 允许、且 operator 显式触发 `scripts/run_controller_direct_test.ps1 -TaskId VAL-003` 时，才进入真实 `test` 执行。
5. 当前若 formal posture 不允许、或 controller runner 在 gateway recovery 停止，则 controller 只给 no-go judgment / repo-only sync，不得继续推动写路径。

### 3. 环境准备

1. 确认 `XtMiniQmt.exe`、`miniquote.exe`、`xtdata` 运行端口和 gateway listener 可观测。
2. 确认 `up_queue_xtquant` 等写权限前置条件在当前实例上存在。
3. 确认当前窗口是允许交易的专用时间窗口。
4. 确认账户权限、最小数量、撤单策略、审计路径已明确。
5. 确认 fake/test 状态未污染 `prod` 实例 evidence。

### 4. 工件准备

controller direct runner 每次真实执行都必须新建正式工件，不复用旧文档：

1. 主控 judgment：
   - `.tmp/spec-task-harness/VAL-003-controller-judgment-<timestamp>-controller-direct-test.md`
2. raw recovery / probe / runtime capture：
   - `.tmp/spec-task-harness/val-003-*.json`
3. 正式 `test` 工件：
   - `docs/evidence_packs/VAL-003-test-<YYYYMMDDHHMM>-controller-direct-live.md`
   - `docs/env_snapshots/VAL-003-<YYYYMMDDHHMM>-controller-direct-live.md`
4. 最终 review：
   - `docs/reviews/VAL-003-review-<YYYYMMDDHHMM>.md`

## Round 1：Fresh Preflight + Go/No-Go

### 目的

确认当前开盘窗口是否具备进入更高 gate 的最低宿主事实；本轮只允许采集 preflight 证据，不执行 `order.place`。

### 必做检查

1. 任务与标准确认：
   - `Get-Content docs\task_cards\VAL-003.md`
   - `Get-Content docs\CURRENT_STATUS.md`
   - `Get-Content docs\ACCEPTANCE_STANDARD.md`
   - `Get-Content docs\OPERATIONS_RUNBOOK.md`
2. 时间、进程、端口：
   - `Get-Date -Format o`
   - `Get-Process XtMiniQmt,miniquote -ErrorAction SilentlyContinue | Select-Object ProcessName,Id,StartTime,Path`
   - `Test-NetConnection 127.0.0.1 -Port 58610 | Select-Object ComputerName,RemotePort,TcpTestSucceeded`
   - `Test-NetConnection 127.0.0.1 -Port 8765 | Select-Object ComputerName,RemotePort,TcpTestSucceeded`
   - `Test-NetConnection 127.0.0.1 -Port 8766 | Select-Object ComputerName,RemotePort,TcpTestSucceeded`
3. gateway 健康：
   - `Invoke-RestMethod http://127.0.0.1:8765/healthz | ConvertTo-Json -Depth 8`
   - `Invoke-RestMethod http://127.0.0.1:8766/healthz | ConvertTo-Json -Depth 8`
4. 最小 runtime probe：
   - 用 `D:\xtquant-mcp\venv313\Scripts\python.exe` 的 inline HTTP client 对 `http://127.0.0.1:8765/mcp` 调用：
     - `initialize`
     - `tools/call probe.connection {}`
     - `resources/read diag://probe/latest`
5. artifact back-link：
   - `Select-String -Path D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\<YYYYMMDD>\trade_gateway_calls.jsonl -Pattern '<trace_id>'`

### Round 1 停止条件

出现以下任一情况，本轮结论直接写 `blocked` 或 `fail_env`，并停止进入 Round 2：

1. `market_window_closed`
2. `XtMiniQmt.exe` 不存在
3. `xtdata` 端口不通
4. trade/data `/healthz` 不可用
5. formal posture 仍明确禁止继续
6. fake/prod evidence 无法区分

### Round 1 通过条件

只有同时满足以下条件，才允许进入 Round 2：

1. 市场已开盘
2. 端口、listener、`/healthz`、实例路径都可观测
3. `probe.connection` 返回可解释的当前 readiness 形态
4. 当前没有新的文档/契约冲突

## Round 2：Broker / Session 定点复核

### 目的

在仍不下单的前提下，确认 higher-gate broker/session 前置条件是否真实闭合，避免把 precheck 误写成 write authorization。

### 必做检查

1. fresh gateway-side non-write chain：
   - `initialize`
   - `tools/call miniqmt.ensure_logged_in {"login_timeout_seconds": 20}`
   - `tools/call session.warm {}`
   - `tools/call session.status {}`
   - `tools/call probe.connection {}`
   - `resources/read trade://session/current`
   - `resources/read diag://probe/latest`
   - `resources/read diag://login/latest`
2. direct native broker/session probe：
   - 使用 `D:\xtquant-mcp\venv313\Scripts\python.exe`
   - `--user-data-path` 必须先从 `TaskCard.Trade Config Path` 指向的 trade config 中解析 `trade.qmt_userdata` / `login.qmt_userdata` / `qmt.qmt_userdata`；若该链路缺失，才允许退回 `miniqmt.ensure_logged_in` 或 `diag://login/latest` 暴露的 `evidence.qmt_userdata`
   - 不允许在 harness 内写死宿主 `userdata_mini` 路径
   - 每个 candidate 只跑一个 `XtQuantTrader` 实例和一个 connect lifecycle
   - 先记录 gateway-side owner session，以及 `session.warm` / `session.status` / `trade://session/current` 返回的 `session_resolution`
   - 同时记录 `probe.connection.session_id`、`observed_probe_session_id`、`write_session_alignment.same_plan_verdict`、`write_permission_precheck_ok`、`write_permission_ready`
   - 再按与 Round 3 写路径相同的 resolver 生成或校验 `effective_session_plan`
   - native probe 必须覆盖 `effective_session_plan` 中会被写路径实际使用的 session；若启用了 derived fallback，则对应 derived session 也必须显式纳入或明确说明为什么本轮不适用
   - 若额外保留 `100/101` 这类 legacy probe，只能作为 supplemental observation，不能单独作为 Round 3 放行依据
   - 若 resolver / derived fallback 最终让 write-path 落到新的 session，本轮必须在该 session 上重新完成 `connect -> subscribe -> read-only query`，不得继承旧 session 的 warm/probe 状态
   - `write_permission_ready=true` / `write_authority_ready=true` 只可用作 Round 2/3 runtime go-no-go 判断，不能单独等价于 `trade_write_authority`、`G4 pass` 或 release authority
   - 只有 `connect()==0` 时才允许继续做 `query_account_infos`、`subscribe`、read-only query
3. bounded host-log 提取：
   - 提取当前同窗内的 MiniQMT / QMT 日志
   - 只记录 session、heartbeat、lock、disconnect 等已观测事实

### Round 2 停止条件

出现以下任一情况，本轮结论直接写 `blocked` / `fail_env`，并停止进入 Round 3：

1. native probe 仍复现 `xttrader connect=-1`
2. broker/session 形态仍无法唯一解释
3. write-permission 仍只停留在 precheck 层，没有更高 gate closure
4. host-log 与 runtime probe 相互矛盾
5. gateway owner session、native probe session 集与 Round 3 预期 write-path session plan 仍不一致
6. `probe.connection` 顶层 `session_id` 已对齐 resolved write session，但 `observed_probe_session_id` / native probe 实际命中的 session 与之不一致，且 `write_session_alignment.same_plan_verdict=false`

### Round 2 通过条件

只有同时满足以下条件，才允许进入 Round 3：

1. 没有新的 `fail_design`
2. broker/session higher-gate blocker 不再表现为 connect 级失败
3. `up_queue_xtquant` 与写权限前置条件满足
4. 当前窗口仍在允许交易时段内
5. controller judgment 明确允许进入 governed write
6. Round 2 已把 owner session、native probe session plan、Round 3 write-path session plan 显式收口到同一套可比较语义

## Round 3：正式 `G4` Governed Write 链

### 前提

只有在 Round 1、Round 2 都通过，且主控触发的 `run_controller_direct_test.ps1` 在同一执行中保持 go 状态后，本轮才允许开始。

### 固定测试包

- `code="515880.SH"`
- `side="BUY"`
- `qty=100`
- `price_mode="l1_protect"`

### 必做链路

1. preflight 复核：
   - `initialize`
   - `tools/call miniqmt.ensure_logged_in {"login_timeout_seconds": 20}`
   - `tools/call session.warm {}`
   - `tools/call session.status {}`
   - `tools/call probe.connection {}`
   - 记录 owner session、`session_resolution.resolved_base_session_id`、`session_resolution.effective_session_plan`、derived fallback 开关，以及 `Round 2 -> Round 3` 的 same-plan verdict
2. 正式写路径：
   - `tools/call order.place {"code":"515880.SH","side":"BUY","qty":100,"price_mode":"l1_protect"}`
3. 从 `order.place` 响应中提取：
   - `broker_order_id`
   - `trace_id`
   - `server_ts`
   - `session_resolution`
4. 后续状态链：
   - `tools/call order.status {"broker_order_id":"<broker_order_id>"}`
   - `tools/call orders.list {}`
   - 若订单状态允许撤单：
     - `tools/call order.cancel {"broker_order_id":"<broker_order_id>"}`
   - 无论是否成交：
     - `tools/call fills.list {"trading_day":"<当天交易日>","broker_order_id":"<broker_order_id>"}`
5. resource 回读：
   - `resources/read trade://session/current`
   - `resources/read diag://probe/latest`
   - `resources/read diag://login/latest`
6. artifact back-link：
   - `trade_gateway_calls.jsonl`
   - 相关 state 文件
   - 最新 trade gateway 日志
   - 必要时的 host-side 辅助证据

### Round 3 特殊规则

1. 若 `order.place` 没有拿到 `broker_order_id` 或等价 broker 标识，直接停止并按 `fail_env` / `fail_design` 分类。
2. 若订单立即成交，`order.cancel` 记为 `N/A`，但必须写明原因并保留对应状态证据。
3. 本轮任何追加 live order 都必须来自当轮 fresh controller judgment + manual gate，不允许沿用历史 packet 命名里的 `override` 预算或结论。
4. 若本轮 packet 里的 owner session、native probe session plan 与 same-call `connect_gate` session 仍然不一致，必须把该现象写成 formal evidence，并停止继续消费 live retry。
5. 若 `session.warm`、`probe.connection`、`order.place` 返回的 `session_resolution.effective_session_plan` 不一致，直接回到 session 解析收口分支，不得解释为单纯环境抖动。
6. 若 write-path 实际使用的 session 与 Round 2 已验证 session 不同，必须先在该新 session 上完成 `connect -> subscribe -> order` 的完整链路；没有这个 same-session closure，直接 no-go。
7. 若 `order.place` 返回 `broker_submission_attempted=false` 且 `local_gate_intercepted=true`，按 machine-readable local gate definitive no-go 处理，直接停止，不得写成 broker 已受理或 broker-side reject。
8. 若本轮只能从历史工件看到 `connect_gate_failed + broker_order_id=""`，该 tuple 仅可作为 fallback / supplemental evidence 佐证同一 no-go 形态；不得与 machine-readable local gate 语义并列为现行主规则。

## 下个开盘窗口待执行

1. 直接使用已更新的 `scripts/run_controller_direct_test.ps1`，不再手填 native probe session 或 `userdata_mini` 路径。
2. Round 2 当前以 gateway-side fresh authority 为第一入口：runner 先执行 `session.warm -> session.status -> probe.connection -> orders.list`，并以 `same_plan_verdict / probe_complete_verdict / fresh_connect_verified / write_authority_ready` 作为 pre-write go/no-go 主依据。
3. 只有当上述 gateway-side fresh authority 没有形成可消费 truth 时，runner 才退回 clean-window / host recovery / legacy native probe 诊断分支；legacy native probe 继续保留为补充证据，但不再是唯一主 gate。
4. 真正进入 Round 3 前，`session.warm`、`session.status`、`probe.connection`、`trade://session/current` 必须都对齐同一 resolved write session；若 warm/status 仍停在 owner shadow session 而 probe 已 realign 到另一 write session，必须先修正 session plan 收口，再谈 write。
5. runner 的职责只到 fresh packet 执行与 runtime capture 为止；它不会在 Round 3 前置 gate 或 packet 结束时直接宣布 formal authority green。
6. fresh Round 1 / Round 2 只有在以下条件同时满足时才允许继续进入 Round 3：
   - `preflight same-plan verdict = true`
   - `native probe same-plan verdict = true`
   - `native_probe_user_data.path_exists = true`
   - trade/data wake 都回到当前 repo 期望 listener，且 `8766` 不再被非 repo listener 占用
7. 若 fresh live packet 仍未拿到 `broker_order_id`，或 same-call `connect_gate` 继续落在与 Round 2 不一致的 session plan，上述现象必须直接写入 EvidencePack / EnvSnapshot，并停止继续消耗当轮 live retry。
8. 只要 fresh packet 形成新的 formal truth，就必须立即补独立 `ReviewPack`；没有新的 review，不得改写 task-level reviewed baseline。

## Packet 后 formal authority refresh

Round 3 结束后，无论结果是 pass 还是 no-go，都必须把 runtime packet 与 formal authority refresh 明确拆层：

1. fresh packet / runner 只负责产出当轮 `EvidencePack`、`EnvSnapshot`、runtime capture 和 back-link。
2. 独立 `ReviewPack` 必须先对 fresh packet 做 formal verdict，确认是否存在新的 `fail_design`、session-plan split 或 local gate 拦截结论。
3. 只有在 review 认可 packet 已形成可闭合的 formal truth 后，才允许刷新 state truth，并核对以下文件是否同步：
   - `trade_write_authority_latest.json`
   - `ter_execution_gate_latest.json`
   - `CURRENT_STATUS.md`
   - `task_cards/VAL-003.md`
4. `trade_write_authority` 只有在 state truth refresh 后仍同时满足 `same_plan_verdict=true`、`probe_complete_verdict=true`、`fresh_connect_verified=true`、`formal_trade_write_closed=true` 时才允许视为 formal green。
5. `write_permission_ready=true` / `write_authority_ready=true` 即使在 fresh packet 中转绿，也只表示 runtime 条件允许尝试 governed write；没有 review 和 state truth refresh，不得把它写成 `trade_write_authority`、`G4 pass` 或 release authority。
6. 若 `order.place` 返回 `broker_submission_attempted=false` 且 `local_gate_intercepted=true`，应优先按 machine-readable local gate no-go 收口；`connect_gate_failed + broker_order_id=""` 仅作为历史工件 fallback。

## 测试与验收标准

### 每轮要执行的测试

1. Round 1：host preflight + gateway health + `probe.connection`
2. Round 2：fresh gateway-side non-write chain + direct native broker/session probe + bounded host-log
3. Round 3：完整 `G4` ordered chain

### 正式验收标准

最终只有满足以下全部条件，`VAL-003` 才能写 `pass`：

1. `order.place` 真实进入 broker 写路径。
2. 返回值包含 `broker_order_id` 或等价 broker 标识。
3. `order.status` 与 `orders.list` 能观测到该单状态链。
4. 若订单可撤，`order.cancel` 有明确结果。
5. 无论是否成交，`fills.list` 已检查并纳入记录。
6. `trace_id`、`server_ts`、calls.jsonl、日志、状态文件和时间窗证据完整回链。
7. review 未发现新的 `fail_design`。
8. fresh packet 之后已完成 formal authority refresh，且 `trade_write_authority_latest.json`、`ter_execution_gate_latest.json`、`CURRENT_STATUS.md`、`task_cards/VAL-003.md` 对同一轮 truth 口径一致。

### 结论词汇

每一轮和最终审查都只能使用以下正式结论词：

- `pass`
- `partial`
- `blocked`
- `fail_env`
- `fail_design`

### 失败分类规则

1. `blocked` / `fail_env`：
   - 市场关闭
   - 端口不通
   - 桌面不可交互
   - 券商权限未开
   - `xttrader connect=-1`
   - formal posture 不允许继续
2. `fail_design`：
   - 写路径绕过 gate
   - 返回契约错误
   - 状态语义与实现冲突
   - fake/prod truth 混淆

## 工件闭环要求

1. test 角色：
   - 每一轮至少一个正式 `EvidencePack`
   - 每一轮至少一个正式 `EnvSnapshot`
2. review 角色：
   - 在最终 round 结束后产出一个正式 `ReviewPack`
3. controller：
   - 只在现有 role-owned artifact 足够时同步 ledger
   - 不制造 `EvidencePack`、`EnvSnapshot`、`ReviewPack`

## 当前默认结论

在新的 formal artifact 产出前，当前正确动作仍然是：

1. 把 [task_cards/VAL-003.md](./task_cards/VAL-003.md) 保持为 `Blocked / data_gateway_port_conflict_nonrepo_listener_8766`
2. 把 `2026-04-11 00:30 +08` 这轮 current truth 写成 fresh blocked；本轮没有 `order.place`、没有 current-round `probe_complete_verdict`，因此不得回退为旧 `connect_gate_failed`
3. 在 trade/data wake 都恢复到 repo 期望 listener、并形成新的 fresh formal packet 前，controller 只做 no-go judgment / repo-only sync，不自动进入 controller direct runner 的 live write 段
4. 若未来要重开，必须从 Round 1、Round 2 重新开始，而不是沿用 `2026-04-03` 的历史命名、旧 live budget 或旧 write verdict
