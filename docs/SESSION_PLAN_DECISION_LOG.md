# `VAL-003 / G4` Session Plan 决策日志

关联任务卡：[task_cards/VAL-003.md](./task_cards/VAL-003.md)  
关联执行计划：[VAL-003_G4_EXECUTION_PLAN.md](./VAL-003_G4_EXECUTION_PLAN.md)  
关联验收标准：[ACCEPTANCE_STANDARD.md](./ACCEPTANCE_STANDARD.md)  
关联当前状态：[CURRENT_STATUS.md](./CURRENT_STATUS.md)

## 文档状态

- 文档类型：formal decision log
- 编制时间：2026-04-13
- 当前 canonical session plan 负责人群：controller、test、review、docs/change
- 读取原则：先看“当前 canonical session plan”，再看“当前 blocker / latest formal truth”，最后看“下次交易窗口前置条件”

## 当前 canonical session plan

1. 当前正式文档中，canonical session plan 的单一主真相固定为 `session_resolution.effective_session_plan`。
2. 目前仓内最近一轮完整记录该主真相的 machine-readable packet 是 `2026-04-09 14:13:01 +08`：
   - 证据入口：[`VAL-003-test-202604091413-controller-direct-live.md`](./evidence_packs/VAL-003-test-202604091413-controller-direct-live.md)
   - 运行快照：`.tmp/spec-task-harness/val-003-controller-direct-runtime-20260409T141301+0800.json`
   - preflight effective session plan：`2111,2100,2101`
   - preflight same-plan verdict：`True`
   - native probe same-plan verdict：`True`
3. 这轮 packet 的正式 closeout 仍然是 no-go：
   - native probe `overall_ok=False`
   - host recovery `ok=False`
   - `fresh_connect_verified=False`
   - `order.place executed=False`
4. 因此当前正式结论只能写成：canonical session plan 语义已经收口到 `2111,2100,2101` 这一套计划文本，但 fresh native probe / fresh connect 尚未闭合；它不是 write authority，也不是 `G4 pass`。

## 当前 blocker / latest formal truth

1. 当前最新 formal truth 不是 `connect_gate_failed`，而是 `2026-04-11 00:30 +08` 形成的 fresh blocked：
   - 证据入口：[`VAL-003-test-202604110030-controller-direct-live.md`](./evidence_packs/VAL-003-test-202604110030-controller-direct-live.md)
   - 独立审查：[`VAL-003-review-202604110034.md`](./reviews/VAL-003-review-202604110034.md)
   - 当前唯一 blocker：`data_gateway_port_conflict_nonrepo_listener_8766`
2. 本轮 fresh packet 的停点在 gateway recovery，而不是 Round 2 或 Round 3：
   - trade wake：`started`，health 正常
   - data wake：`status=port_conflict`
   - `8766` 被非当前 repo 期望 listener 占用，`/healthz` 返回 `404 Not Found`
   - `order.place` 未执行
3. 因为本轮没有进入 Round 2，当前轮并未产生 `probe_complete_verdict`。正式文档只能写“本轮未产生 current-round probe verdict”，不能继承 `2026-04-09` 或更早 packet 的 probe/write no-go 来代替本轮结论。
4. `2026-04-11 00:30:25 +08` 的 pre-run artifact snapshot 仍指向 `2026-04-09` 的旧 formal 工件；它只说明 run 前 board 镜像，没有覆盖同窗 fresh packet 的最终 closeout。current truth 以 `2026-04-11` 的 EvidencePack / ReviewPack 为准。

## 术语对齐

1. `probe_complete_verdict`
   - 文档语义：当前 packet 的 Round 2 bounded native probe 是否在 canonical session plan 上完成。
   - 当前 `2026-04-11 00:30 +08`：未产生，因为 packet 在 gateway recovery 停止。
   - `2026-04-09 14:13 +08`：可等价理解为“same-plan 已成立，但 probe 未完成”，因为 `native probe same-plan verdict=True` 且 `native probe overall_ok=False`。
2. `session_plan_version` / `canonical_session_plan_version`
   - 当前 runtime payload 已经把 `session_plan_version` 落到 `probe.connection`、`order.place(connect_gate)`、`trade_write_authority` 与 `check_packet_readiness.ps1` 输出；但 reviewed formal artifacts 还没有在 fresh packet/ReviewPack 中完成这批字段的正式回收。
   - `canonical_session_plan_version` 仍未作为单独 machine-readable 字段落盘；在显式字段出现之前，正式文档必须直接引用 canonical plan 文本本身，以及其证据来源；不得臆造版本号。
   - 无论未来字段怎样扩展，它们都只能表示 canonical session plan contract/version 元数据，不能覆盖 `session_resolution.effective_session_plan` 的实际值。
3. `check_packet_readiness.ps1`
   - 当前仓内已新增这个独立脚本，产出 machine-readable `go/no_go`、`no_go_reason` 与 `session_plan_version`。
   - 现行正式入口是 `scripts/check_packet_readiness.ps1` 输出，加上 `scripts/run_controller_direct_test.ps1` 的 Round 1/2 readiness hard-stop 与同窗 `Controller Judgment`。
   - 任何“packet readiness”结论都必须同时回链到该脚本输出、当轮 judgment 与正式 `EvidencePack / ReviewPack`。

## 下次交易窗口前的前置条件

1. `8766` 必须先恢复为当前 repo 期望的 data listener；trade/data wake 都要回到 `ok=true`，且不再出现 `port_conflict`。
2. 必须形成新的 fresh controller judgment，明确 `gateway recovery did reach expected repo listeners`，并允许进入 test role work。
3. 新 packet 必须重新在 canonical session plan 上完成 Round 2 bounded native probe；不能沿用 `2026-04-09` 的 same-plan 结果，也不能沿用更早 `connect_gate_failed` 作为本轮判断。
4. 只有在 fresh packet 里同时重新形成 `same_plan_verdict=true`、fresh native probe 完成、并且 fresh review 认可 current truth 闭合后，才允许刷新 state truth 与 formal authority。

## `2026-04-13` runtime 经验（non-formal）

1. `session.warm / session.status / probe.connection` 现在必须被视作同一条 resolved write session truth 链，而不是三个彼此独立的只读检查。
2. clean recovery 之后，如果没有重新完成一次真实 UI 登录，`up_queue_xtquant` 很可能不会恢复；这会把 write-permission precheck 误打成新的环境 blocker。
3. `down_queue_win_*` / `lock_down_queue_win_*` / `__mutex` 残留确实会污染 fresh connect，但在当前环境里它们已经不是唯一根因：即便 residue 被清理并重新登录，broker fresh connect 仍可能继续 `-1`。
4. 最新 runtime 已经证明 `session.warm` / `session.status` 可以稳定 realign 到 `2101`；因此 reopen 时不应再把“warm/status 停在 2100”当作默认主 blocker。当前真正需要盯住的是 `2101` 上的 broker fresh connect 是否能从 `write_connect_failed` 转绿。
5. 在没有 fresh packet / ReviewPack 之前，以上经验只用于指导下一轮 reopen，不得回写 current formal truth。

## 当前不允许的写法

1. 不得把 `2026-04-11 00:30 +08` 这轮 fresh blocked 写成 `connect_gate_failed`。
2. 不得把 `2026-04-09 14:13 +08` 的 canonical session plan packet 写成 probe 已完成或 write authority 已恢复。
3. 不得把 `check_packet_readiness.ps1` 脱离 `run_controller_direct_test.ps1`、`Controller Judgment` 与 `ReviewPack` 单独解释成 formal green。
