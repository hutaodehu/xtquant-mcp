# 当前开发进度

关联设计文档：[MCP_DESIGN.md](./MCP_DESIGN.md)  
关联审查文档：[DESIGN_REVIEW_20260327.md](./DESIGN_REVIEW_20260327.md)  
协作与验收入口：[../AGENTS.md](../AGENTS.md) | [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md) | [WORKFLOW_AND_BOARD.md](./WORKFLOW_AND_BOARD.md) | [ACCEPTANCE_STANDARD.md](./ACCEPTANCE_STANDARD.md) | [TEMPLATES.md](./TEMPLATES.md)

## 文档状态

- 文档类型：controller 入口快照
- 快照时间：2026-04-11T00:34:08+08:00
- 判定依据：
  - 仓库内正式 `TaskCard`、`ChangePack`、`EvidencePack`、`ReviewPack`、`EnvSnapshot`
  - 最新 controller direct judgment：[`VAL-003-controller-judgment-20260411T003025+0800-controller-direct-test.md`](../.tmp/spec-task-harness/VAL-003-controller-judgment-20260411T003025+0800-controller-direct-test.md)
  - 最新 formal truth snapshot：[`val-003-artifact-snapshot-20260411T003025+0800.json`](../.tmp/spec-task-harness/val-003-artifact-snapshot-20260411T003025+0800.json)
  - 最新 trade wake 结果：[`val-003-trade-wake-20260411T003025+0800.json`](../.tmp/spec-task-harness/val-003-trade-wake-20260411T003025+0800.json)
  - 最新 data wake 结果：[`val-003-data-wake-20260411T003025+0800.json`](../.tmp/spec-task-harness/val-003-data-wake-20260411T003025+0800.json)
  - 最新 systematic-debugging 进程取证：[`val-003-data-port-conflict-process-20260411T003408+0800.json`](../.tmp/spec-task-harness/val-003-data-port-conflict-process-20260411T003408+0800.json)
  - 最新 systematic-debugging health 取证：[`val-003-data-port-conflict-health-20260411T003408+0800.json`](../.tmp/spec-task-harness/val-003-data-port-conflict-health-20260411T003408+0800.json)
  - 最新 independent review：[`VAL-003-review-202604110034.md`](./reviews/VAL-003-review-202604110034.md)
  - 最新 formal test artifact：[`VAL-003-test-202604110030-controller-direct-live.md`](./evidence_packs/VAL-003-test-202604110030-controller-direct-live.md)
  - 最新 EnvSnapshot：[`VAL-003-202604110030-controller-direct-live.md`](./env_snapshots/VAL-003-202604110030-controller-direct-live.md)
  - `python .agents/skills/spec-task-harness/scripts/collect_artifacts.py --repo-root . --task-id VAL-003`
- 读取原则：
  1. `TaskCard.Status` 只是本地镜像字段，不是 live board 真相。
  2. 若任务卡回链与同 `Task ID` 的更晚正式工件冲突，以更晚的 `ReviewPack` / `EvidencePack` 为准。
  3. 若 `latest_review_decision=pass` 且脚本给出 `controller_closeout`，但更晚 `ReviewPack` 明确说明该 `pass` 只覆盖中间 round 而非 task-level closeout，则必须以 `ReviewPack` 的 state suggestion、residual risk 与 execution boundary 为准，不能直接把该卡视为已完成。
  4. 需要执行 live preflight、fresh rerun 或当前 higher-gate `connect_gate_failed` 恢复时，先读 [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md)，不要依赖聊天上下文回忆步骤。
  5. 对 `VAL-003/G4`，若同一 packet 中 `session.warm/session.status`、native probe 与 `order.place.connect_gate` 使用的 session plan 彼此不一致，则不得把较低层 probe 成功外推成写路径 readiness；必须先把 session 解析语义收口。
  6. `2026-04-08` 之前的历史 formal artifact 可能保留旧字段语义，例如 `probe.connection.session_id` 仍表示 probe 观测 session，或 `write_permission_ready=true` 仍接近 precheck success；当前读取必须以 [MCP_DESIGN.md](./MCP_DESIGN.md) 与 [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md) 的最新 contract 为准。
  7. `2026-04-11 00:30:25 +08` 的 `.tmp/spec-task-harness/val-003-artifact-snapshot-20260411T003025+0800.json` 仍是 run 前 artifact snapshot，它的 `latest_evidence_pack/latest_review_pack` 还指向 `2026-04-09` 的旧 formal 工件；当前 formal truth 必须以同窗生成的 `2026-04-11` EvidencePack / ReviewPack 为准，而不是把 pre-run snapshot 当成最终 closeout 结论。

## 总览

| 区域 | 当前结论 | 最高已闭合 Gate | 备注 |
| --- | --- | --- | --- |
| Shared Ops Mainline | 已闭环 | `G0` | [OPS-001](./task_cards/OPS-001.md) 已接受；fake/test 状态与正式实例证据已隔离 |
| Shared Ops Follow-up | 已闭环 | `G0` | [OPS-002](./task_cards/OPS-002.md)、[OPS-003](./task_cards/OPS-003.md)、[OPS-004](./task_cards/OPS-004.md)、[OPS-005](./task_cards/OPS-005.md)、[OPS-006](./task_cards/OPS-006.md)、[OPS-007](./task_cards/OPS-007.md) 均已接受 |
| Data Lane | 主线已闭环 | `G2` | [DG-001](./task_cards/DG-001.md)、[DG-002](./task_cards/DG-002.md)、[DG-003](./task_cards/DG-003.md)、[VAL-001](./task_cards/VAL-001.md) 均已接受 |
| Trade Lane Read | 已闭环 | `G3` | [TG-002](./task_cards/TG-002.md)、[TG-003](./task_cards/TG-003.md)、[TG-004](./task_cards/TG-004.md)、[VAL-002](./task_cards/VAL-002.md)、[VAL-004](./task_cards/VAL-004.md)、[TG-005](./task_cards/TG-005.md) 均已形成 formal closeout truth |
| Trade Lane Write | 未闭环 | `< G4` | [TG-001](./task_cards/TG-001.md) 已接受；当前仅剩 [VAL-003](./task_cards/VAL-003.md) 的 `G4` 真写验证仍未闭环 |

一句话版本：当前主线不是回到“全量设计阶段”，而是 `G3` 读侧 follow-up 已全部收口；真正还没落地的只剩 [VAL-003](./task_cards/VAL-003.md) 的 `G4` 真写验证。

## 已镜像 Accepted

| Task | Gate | 最新正式工件 |
| --- | --- | --- |
| [OPS-001](./task_cards/OPS-001.md) | `G0` | [OPS-001-review-202603300208.md](./reviews/OPS-001-review-202603300208.md) |
| [DG-001](./task_cards/DG-001.md) | `G2` | [DG-001-review-202603300706.md](./reviews/DG-001-review-202603300706.md) |
| [DG-002](./task_cards/DG-002.md) | `G2` | [DG-002-review-202603300815.md](./reviews/DG-002-review-202603300815.md) |
| [VAL-001](./task_cards/VAL-001.md) | `G2` | [VAL-001-review-202603300646.md](./reviews/VAL-001-review-202603300646.md) |
| [TG-002](./task_cards/TG-002.md) | `G3` | [TG-002-review-20260330150610.md](./reviews/TG-002-review-20260330150610.md) |
| [TG-003](./task_cards/TG-003.md) | `G3` | [TG-003-review-202603301506.md](./reviews/TG-003-review-202603301506.md) |
| [TG-004](./task_cards/TG-004.md) | `G3` | [TG-004-review-202603301510.md](./reviews/TG-004-review-202603301510.md) |
| [VAL-002](./task_cards/VAL-002.md) | `G3` | [VAL-002-review-20260330-143606-live-gateway-rerun-orders-fallback.md](./reviews/VAL-002-review-20260330-143606-live-gateway-rerun-orders-fallback.md) |
| [TG-001](./task_cards/TG-001.md) | `G4` | [TG-001-review-202603311528.md](./reviews/TG-001-review-202603311528.md) |
| [VAL-004](./task_cards/VAL-004.md) | `G3` | [VAL-004-review-202603311840.md](./reviews/VAL-004-review-202603311840.md) |
| [TG-005](./task_cards/TG-005.md) | `G3` | [TG-005-review-202603311920.md](./reviews/TG-005-review-202603311920.md) |
| [OPS-005](./task_cards/OPS-005.md) | `G0` | [OPS-005-review-202603311437.md](./reviews/OPS-005-review-202603311437.md) |
| [OPS-006](./task_cards/OPS-006.md) | `G0` | [OPS-006-review-202603311059.md](./reviews/OPS-006-review-202603311059.md) |
| [OPS-007](./task_cards/OPS-007.md) | `G0` | [OPS-007-review-202603311124.md](./reviews/OPS-007-review-202603311124.md) |

## 真实未落地项

| Task | 当前状态 | Gate | 当前真实卡点 | 说明 |
| --- | --- | --- | --- | --- |
| [VAL-003](./task_cards/VAL-003.md) | `Blocked` | `G4` | `data_gateway_port_conflict_nonrepo_listener_8766` | `2026-04-11 00:30:25 +08` 的 fresh controller-direct packet 在 gateway recovery 阶段即停止：trade wake 已 `started` 且 health 正常，但 data wake 返回 `status=port_conflict`。随后 `2026-04-11 00:34:08 +08` 的 systematic-debugging 取证确认 `8766` 被 `PID 26480` 占用，进程命令行为 `\\wsl.localhost\\Ubuntu-22.04\\home\\yun\\qlib\\scripts\\..\\scripts\\run_xtdata_gateway.py --transport streamable-http --host 127.0.0.1 --port 8766 --path /mcp`，且 `http://127.0.0.1:8766/healthz` 返回 `404 Not Found`，说明它不是当前 repo 期望的 `xtqmtDataGateway`。因此本轮 `order.place` 未执行，当前 formal truth 必须收口为 fresh blocked，而不能继续沿用旧 `connect_gate_failed` 作为本轮结论。 |

当前不再把以下内容记为“未落地项”：

- `xtdata.status` 的分层 readiness
- `resolved runtime endpoint` 的对外状态表达
- single-account primary contract
- `read_only` 与 `write_permission` 的显式拆层
- subscription lease 的恢复语义字段本身

这些能力已经在代码、测试或正式工件中闭合；剩余差距只在 write-path 和 live proof，而不是这些 contract handle 本身。

## `VAL-002` 现在为什么仍然只代表 `G3 pass`

最新正式工件：

- [VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md](./evidence_packs/VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md)
- [VAL-002-review-20260330-143606-live-gateway-rerun-orders-fallback.md](./reviews/VAL-002-review-20260330-143606-live-gateway-rerun-orders-fallback.md)

当前关键事实仍然是：

1. public `orders.list` 已经能返回 `ok=true` 的只读结果。
2. 同一结果明确标注了 `degraded=true`、`fallback_used=true`、`read_scope=public_fallback`。
3. 同一 payload 里仍保留 `broker_read.error=xttrader connect failed: -1 ...`。
4. 这份 accepted baseline 不会自动覆盖后续实现变化；但 [VAL-004](./task_cards/VAL-004.md) -> [TG-005](./task_cards/TG-005.md) 的 follow-up 链已经把 public `orders.list` 的历史 `NoneType.query_open_orders` blocker 收口并关闭。

因此它的真实含义仍是：

- `G3 pass`
- broker 子路径问题仍保留
- 不能外推为 `order.place` ready
- `G4` 继续阻断

## 控制面状态

当前可采信的最新控制面状态来自 `2026-04-11 00:30 +08` 的 fresh controller-direct packet：controller 进入了 gateway recovery，但没有到达 test role work。trade wake 已恢复到 repo 期望 listener，data wake 则因端口 `8766` 的非 repo listener 冲突而停止，controller judgment 明确给出 `gateway recovery did not reach expected repo listeners` 与 `Executed Test Role Work: no`。因此本轮 controller 的最终动作仍是 no-go，只是当前 no-go 的唯一 blocker 已切换为 `data_gateway_port_conflict_nonrepo_listener_8766`。

额外事实：

- `2026-04-11 00:30 +08` 这轮 fresh packet 的正式工件已前移到 [`VAL-003-test-202604110030-controller-direct-live.md`](./evidence_packs/VAL-003-test-202604110030-controller-direct-live.md)、[`VAL-003-202604110030-controller-direct-live.md`](./env_snapshots/VAL-003-202604110030-controller-direct-live.md) 与 [`VAL-003-review-202604110034.md`](./reviews/VAL-003-review-202604110034.md)。
- 当前 data side 的硬停点已由 systematic-debugging 落成 formal root cause：`8766` 上的 listener 不是 repo `xtqmtDataGateway`，而是外部 `\\wsl.localhost\\Ubuntu-22.04\\home\\yun\\qlib\\scripts\\..\\scripts\\run_xtdata_gateway.py` 进程；因此本任务只记录阻断，不处理进程。
- [TG-005](./task_cards/TG-005.md) 的 `G3` 收口、`2026-04-07` 的 `connect_gate_failed` write fail 与 `2026-04-09` 的 host recovery fail，都只能作为历史 baseline；它们不会覆盖本轮 current truth。
- 本轮 controller-direct packet 在 gateway recovery 就停止，因此当前 formal truth 明确不是 write-path verdict，也不是 broker-side verdict；唯一可用结论是 fresh blocked，主 blocker 为 `data_gateway_port_conflict_nonrepo_listener_8766`。

## `2026-04-13` 最新 runtime 进展（非 formal）

以下内容是 `2026-04-13` 北京时间下午的最新 live runtime 进展，用于指导下一轮 reopen / fresh packet；它们不是新的 formal truth，也不会覆盖 `2026-04-11` 的 reviewed blocked baseline。

1. 新 MCP 主线的执行层收口已经明显前移：
   - `check_packet_readiness.ps1` 与 `run_controller_direct_test.ps1` 当前已改为优先消费 gateway-side fresh authority，而不再只依赖旧 external native probe。
   - `session.warm` / `session.status` 现在会跟随 resolved write session realign；最新 live 运行里，这两者已经能稳定收口到 `session_id=2101`、`resolved_session_id=2101`。
   - `probe.connection` 在 owner shadow 仍停在旧 session、但该 session 仍属于当前 `effective_session_plan` 时，也会继续尝试 broker fresh verify，而不是过早停在 owner reuse 结论。
2. 最新 clean recovery 已经证明确认以下旧 blocker 不再是当前主问题：
   - 凭据 target 错位
   - UI 密码未填入
   - `up_queue_xtquant` 未建立
   - `session.warm` / `session.status` 长期停留在与 write-path 不一致的 session
3. 最新 live blocker 已收敛为单一 write-path 事实：
   - `probe.connection` 的 top-level `session_id` 与 `resolved_session_id` 现已对齐到 `2101`
   - 但同一轮 fresh broker verify 仍返回 `reason=write_connect_failed`
   - `fresh_connect_verified=false`
   - `write_authority_ready=false`
   - broker fresh connect 对 `2101 / 2100 / 2111` 三个 candidate 仍全部返回 `connect=-1`
4. 因此当前最准确的状态不是“已经只差下单”，而是：
   - 制度层 / 编排层 / session-plan 口径基本收口
   - 当前 runtime 层唯一剩余 blocker 是 broker fresh connect 本身
   - 在没有新一轮 fresh packet + ReviewPack 前，不得把这批 runtime 进展写成 formal green 或 release-ready

## 经验总结

1. 对 `VAL-003/G4`，`session.warm -> session.status -> probe.connection` 必须顺序执行；并发读取很容易把 `session_not_ready`、旧 owner summary 或旧 cached probe 混写成一轮 truth。
2. clean recovery 之后，不能只看“进程已起”或“端口已通”；若没有重新完成一次真实 UI 登录，`up_queue_xtquant` 与 write-permission precheck 可能不会恢复。
3. `down_queue_win_*` / `lock_down_queue_win_*` / `__mutex` 残留是真实干扰项，但它们不是全部根因；即便 residue 已清空，broker fresh connect 仍可能继续 `-1`。
4. 只要 `session.warm` / `session.status` 已经跟 `resolved write session` 收口，就不该再把 `owner shadow session != write session` 当作主 blocker；真正需要盯的是同一 resolved session 上的 fresh broker connect 能否成功。

## 下一步

1. 不要把这轮 fresh packet 误写成 `connect_gate_failed`；本轮没有执行 `order.place`，当前唯一 blocker 是 `data_gateway_port_conflict_nonrepo_listener_8766`。
2. 不要在本任务内处理 `8766` 端口上的外部 listener；该阻断已被明确归类为 out-of-scope 外部阻断。
3. 若未来要重开 [VAL-003](./task_cards/VAL-003.md)，前提至少是 trade/data wake 都恢复到 repo 期望 listener，并形成新的 fresh formal evidence，之后才谈 Round 2/3。

