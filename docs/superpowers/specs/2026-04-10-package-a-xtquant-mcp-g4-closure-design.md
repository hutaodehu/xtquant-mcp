# Package A 设计：xtquant-mcp G4 真写闭环与 Canonical Session Plan 收口

> 目标仓：`D:\xtquant-mcp\repo`
> package_id：`pkg-a-xtquant-mcp-g4`
> 日期：`2026-04-10`
> 状态：repo-local draft v1

## 1. 目标与终态

本包只处理新交易 MCP 的 `VAL-003 / G4` 真写闭环，不处理 data MCP，不处理 Package B，也不修改 `/home/yun/qlib/trade_execution_runtime`。

允许终态只有两种：

1. `G4 pass`
2. `fresh blocked`

本包的交付目标不是“把状态写得更像 ready”，而是把 `VAL-003` 的当前结论刷新为一轮新的 formal truth，并让 `trade_write_authority_latest.json`、`ter_execution_gate_latest.json`、`CURRENT_STATUS.md`、`task_cards/VAL-003.md` 口径一致。

## 2. 本轮已确认事实

### 2.1 文档与状态事实

1. 目标仓当前没有 `docs/superpowers/`，必须补齐 repo-local `spec` 与 `plan`。
2. `docs/CURRENT_STATUS.md` 的最新镜像快照时间仍是 `2026-04-08T10:15:37+08:00`，明确 Trade Lane Write 唯一未闭环项是 `VAL-003`，当前真实卡点为 `connect_gate_failed`。
3. `docs/task_cards/VAL-003.md` 已把 `2026-04-08 10:13 +08` 的 review 定义为 reopen authority 的当前基线：`1111 / 100,101 / 2111` 的 session-plan split 已被升级为 material design/contract blocker。
4. `instance/prod/state/trade_resources/trade_write_authority_latest.json` 生成时间是 `2026-04-09T11:09:21+00:00`，当前为：
   - `status=fail`
   - `blocking_reason=formal_trade_write_lane_not_closed`
   - `same_plan_verdict=true`
   - `fresh_connect_verified=false`
   - `formal_trade_write_closed=false`
5. `instance/prod/state/trade_resources/trade_session_current.json` 生成时间是 `2026-04-09T19:21:25+08:00`，当前 `session_resolution.effective_session_plan=[2111,2100,2101]`，但 `ready=false`，失败原因为 `account.show_exception`，说明运行态已经在使用新的 session 解析语义，但 formal closeout 尚未刷新到同一轮 truth。

### 2.2 代码事实

1. `xtqmt_mcp/trade_ops.py` 已经暴露：
   - `session_resolution.effective_session_plan`
   - `write_session_alignment.same_plan_verdict`
   - `observed_probe_session_id`
   - `fresh_connect_verified`
   - `broker_submission_attempted`
   - `local_gate_intercepted`
2. `scripts/run_controller_direct_test.ps1` 已经包含 canonical session plan 检查，并会在 Round 2 阶段对 `session_resolution.effective_session_plan` 和 native probe same-plan 做 hard-stop。
3. `xtqmt_mcp/trade_write_authority.py` 已能读取 `diag_probe_latest.json` 与 `CURRENT_STATUS.md`，但当前测试只覆盖两种场景：
   - formal truth 未闭合时 fail
   - runtime/formal 全绿时 pass
4. 现有 targeted tests 还没有完整冻结以下语义：
   - same-plan 成立但正式 write 仍未闭合时必须 fail
   - same-plan 不成立时必须 hard-stop
   - `observed_probe_session_id` 只能是观测字段，不能替代 write-path truth
   - `connect_gate_failed + broker_order_id=""` 的本地 gate 拦截语义必须持续可测

### 2.3 环境前提事实

1. `/mnt/d/xtquant-mcp/repo` 当前未发现 `.git` 元数据，因此后续 `using-git-worktrees` 无法直接对该路径执行标准 `git worktree add`。
2. 这不阻断当前 repo-local `spec/plan` 落地，但会阻断实现阶段的规范化 worktree 流程。
3. 本设计因此显式把“切换到 git-backed working copy 或确认无 worktree 例外”定义为实现前置条件，而不是在执行时临时绕过。

## 3. 当前 draft plan 的缺口

当前上游 draft 方向正确，但还缺四个必须显式落盘的点：

1. 没有把“目标目录无 `.git`，无法直接执行 worktree”写成实现前置条件。
2. 没有把 `trade_write_authority` 的绿灯条件冻结为 formal authority 语义，只是笼统描述了 same-plan / fresh packet。
3. 没有把 targeted tests 扩充到四类强约束场景。
4. 没有把 “formal artifacts -> state json -> CURRENT_STATUS/task card” 的刷新顺序写成单向收口链，容易再次出现 stale truth 充当当前结论。

## 4. 设计决策

### 4.1 单一 SoT 固定为 `session_resolution.effective_session_plan`

以下四段必须共享同一 canonical session plan：

1. `session.warm`
2. `session.status`
3. `probe.connection` 与 native probe
4. governed `order.place`

允许保留 `observed_probe_session_id`、`read_only_probe.session_id` 一类观测字段，但它们只能表达“实际观测到了哪个 probe session”，不能替代顶层 write-path truth。顶层 write-path truth 固定由：

1. `session_resolution.resolved_session_id`
2. `session_resolution.effective_session_plan`
3. `write_session_alignment.same_plan_verdict`

共同表达。

### 4.2 `trade_write_authority` 只认 formal closeout

`trade_write_authority` 转绿必须至少同时满足：

1. `same_plan_verdict=true`
2. `fresh_connect_verified=true`
3. `formal_trade_write_closed=true`

补充约束：

1. `write_permission_ready` 保留为 runtime 诊断字段，但不能替代 formal closeout，也不能单独把 authority 变绿。
2. `observed_probe_session_id` 只允许出现在观测字段里，不能参与 authority 的主判定。
3. `CURRENT_STATUS.md` 未明确把 Trade Lane Write 关闭前，authority 必须保持 fail。

### 4.3 `connect_gate_failed + broker_order_id=""` 语义冻结

若 fresh formal packet 中 `order.place` 返回：

1. `code=connect_gate_failed`
2. `broker_order_id=""`

则正式语义固定为：

1. 本地 gate 层拦截
2. 未进入券商柜台

因此 payload 必须继续稳定暴露：

1. `broker_submission_attempted=false`
2. `local_gate_intercepted=true`

文档、ReviewPack、CURRENT_STATUS 与 task card 都不得把这类结果写成 broker-side reject，也不得写成“基本 ready”。

### 4.4 `flow_smoke` 继续降级为生命周期壳子证明

`flow_smoke` 只能证明 MCP 写路径生命周期壳子存在，不能作为：

1. write-ready 证据
2. broker 已提交证据
3. release authority

所有与 `VAL-003 / G4` 相关的 formal truth 必须来自 live `controller_direct` packet，而不是 `flow_smoke`。

### 4.5 不兼容旧 MCP，不保留旧契约回退

本包直接按“新数据 MCP / 新交易 MCP 已拆分”处理：

1. 不保留旧 MCP 的兼容桥接语义
2. 不用 legacy `100/101` probe pass 继续替代 write-path readiness
3. 不引入第三条 change 主线

## 5. 代码与文档边界

### 5.1 优先改动范围

1. `D:\xtquant-mcp\repo\xtqmt_mcp\session_resolution.py`
2. `D:\xtquant-mcp\repo\xtqmt_mcp\trade_ops.py`
3. `D:\xtquant-mcp\repo\xtqmt_mcp\trade_write_authority.py`
4. `D:\xtquant-mcp\repo\xtqmt_mcp\trade_gateway\bootstrap.py`
5. `D:\xtquant-mcp\repo\xtqmt_mcp\trade_gateway\server.py`
6. `D:\xtquant-mcp\repo\scripts\run_controller_direct_test.ps1`
7. `D:\xtquant-mcp\repo\tests\test_trade_write_authority.py`
8. `D:\xtquant-mcp\repo\tests\test_trade_probe_readiness_split.py`
9. `D:\xtquant-mcp\repo\tests\test_trade_order_submission_contract.py`
10. `D:\xtquant-mcp\repo\docs\task_cards\VAL-003.md`
11. `D:\xtquant-mcp\repo\docs\VAL-003_G4_EXECUTION_PLAN.md`
12. `D:\xtquant-mcp\repo\docs\CURRENT_STATUS.md`
13. `D:\xtquant-mcp\repo\docs\ACCEPTANCE_STANDARD.md`
14. `D:\xtquant-mcp\repo\docs\OPERATIONS_RUNBOOK.md`
15. `D:\xtquant-mcp\repo\docs\MCP_DESIGN.md`

### 5.2 明确不做

1. 不扩大到多账户、多标的、多手数
2. 不处理 data MCP
3. 不处理 Package B
4. 不把 blocked 包装成 ready
5. 不把 warm / probe pass 包装成 broker write success
6. 不沿用旧 evidence 充当当前结论
7. 不修改 `/home/yun/qlib/trade_execution_runtime`

## 6. 验证与产物设计

### 6.1 Targeted tests 先行

最小必须覆盖四类场景：

1. same-plan 成立且 authority 可放行
2. same-plan 成立但 write 仍失败
3. same-plan 不成立直接 hard-stop
4. `observed_probe_session_id` 不能替代 write-path truth

### 6.2 live packet 进入条件

只有在以下条件全部满足时，才允许用 `pwsh` 执行 controller-direct formal packet：

1. repo-local spec/plan 已落盘
2. targeted tests 本轮 fresh 通过
3. 当前交易窗口允许
4. `CURRENT_STATUS.md` 与 `task_cards/VAL-003.md` 仍指向本轮要推进的 `VAL-003`
5. preflight 已暴露 canonical `session_resolution.effective_session_plan`
6. `run_controller_direct_test.ps1` 的 Round 2 same-plan 检查未被绕过

### 6.3 fresh artifacts 与 truth 刷新顺序

无论 pass 还是 blocked，都必须按以下顺序收口：

1. 生成新的 `docs/evidence_packs/VAL-003-*.md`
2. 生成新的 `docs/env_snapshots/VAL-003-*.md`
3. 生成新的 `docs/reviews/VAL-003-*.md`
4. 刷新 `trade_write_authority_latest.json`
5. 刷新 `ter_execution_gate_latest.json`
6. 同步 `CURRENT_STATUS.md`
7. 同步 `docs/task_cards/VAL-003.md`

最后只允许输出两种 posture：

1. `G4 pass`
2. `fresh blocked`

## 7. 对 Package B 的唯一输出契约

本包完成后，只向 Package B 输出四样东西：

1. 最新 `VAL-003 posture`
2. 最新 `ReviewPack` 路径
3. 最新 `trade_write_authority_latest.json` 路径
4. 最新 `ter_execution_gate_latest.json` 路径

除此之外，不额外扩散 Package B 所需的解释性上下文。
