# ReviewPack

Task ID: VAL-002
Role: review
Date: 2026-03-30T14:36:06+08:00
Change Package Link: [VAL-002.md](../change_packages/VAL-002.md)
Evidence Pack Link: [VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md](../evidence_packs/VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md)
Env Snapshot Link: [VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md](../env_snapshots/VAL-002-test-20260330-142745-live-gateway-rerun-orders-fallback.md)
Prior Review Link 1: [VAL-002-review-20260330-135658-live-gateway-rerun-followup.md](./VAL-002-review-20260330-135658-live-gateway-rerun-followup.md)
Prior Evidence Link 1: [VAL-002-test-20260330-134330-live-gateway-rerun.md](../evidence_packs/VAL-002-test-20260330-134330-live-gateway-rerun.md)
Design Context Link: [TG-004.md](../change_packages/TG-004.md)

## Findings

1. High: `VAL-002` 现在可以通过 review gate，正式 release decision 应改为 `pass`，目标状态可从 `Blocked` 进入 `Accepted`。
   - [ACCEPTANCE_STANDARD.md](../ACCEPTANCE_STANDARD.md) 对 `G3` 的要求是按顺序完成 `miniqmt.ensure_logged_in -> session.warm -> session.status -> probe.connection -> account.show -> positions.list -> orders.list -> snapshot.l1`。
   - 新 EvidencePack 显示整条链路已按顺序完成，且 public `orders.list` 不再是 `ok=false`，而是 `ok=true`、`count=5`、`source=active_owner_shadow`、`read_scope=public_fallback`。
   - 这次 public `orders.list` 没有把 broker failure 伪装成 broker success，而是在同一 payload 内显式保留：
     - `degraded=true`
     - `fallback_used=true`
     - `fallback_reason=broker_connect_failed`
     - `broker_read.source=broker`
     - `broker_read.ok=false`
     - `broker_read.fresh_connect_attempted=true`
     - `broker_read.fresh_connect_ok=false`
     - `broker_read.error=xttrader connect failed: -1 after 3 attempts (...)`
   - 对 `G3` 而言，这已经满足“交易侧只读验收”的 operational truth 要求：public `orders.list` 成功返回当前账户的可读委托结果，同时明确声明它是 degraded read，不把 broker subpath 失败静默掩盖掉。

2. High: `VAL-003` 目前仍不应从 review-governance 视角启动，原因是 higher gate hard stop 仍然存在。
   - [ACCEPTANCE_STANDARD.md](../ACCEPTANCE_STANDARD.md) 明确把 `xttrader connect=-1` 列为“必须停止继续推进更高 gate”的硬停止条件。
   - 本轮 rerun 虽然已把该 failure 从 public `orders.list` 的 task-level blocker 降为 payload 内显式保留的 broker subpath failure，但 `broker_read.error=xttrader connect failed: -1 ...` 仍然存在。
   - 因此这次 review 的正确拆分是：
     - `VAL-002/G3`: `pass`
     - `VAL-003/G4`: 仍不得启动，继续按 higher-gate `blocked` 处理
   - 不能把 degraded read success 外推成 broker write path ready，也不能把它外推成 `order.place` 前置 gate 已闭合。

3. Medium: 相比 prior rerun，本轮 improvement 是实质性 closure，而不是仅仅换了一种叙事。
   - prior rerun 中，public `orders.list` 仍是 formal blocker：`ok=false`，错误为 `xttrader connect failed: -1 after 3 attempts (...)`。
   - current rerun 中，`miniqmt.ensure_logged_in`、`session.warm`、`session.status`、`probe.connection`、`account.show`、`positions.list`、`snapshot.l1` 均保持成功，同时 public `orders.list` 改为显式 degraded fallback success。
   - 这次 improvement 不是把失败藏进 warm trace，也不是只在内部 shadow path 成功；而是 public contract 本身已经改为 truthful degraded success，并把 broker failure 作为 machine-readable metadata 原样保留。
   - 受控 stop 旧 listener 再执行 repo-supported wake path 后，fresh gateway process、post-restart `/healthz`、新日志文件和 `trade_gateway_calls.jsonl` 一起证明这次结论来自新的 live gateway-side rerun，而不是旧进程残留。

4. Medium: formal `fail_design` 仍然没有被这次 rerun 证明。
   - 这次 rerun 证明的是 `TG-004` public `orders.list` fallback contract 已在真实运行态生效，并且 contract 没有损坏 operational truth。
   - 这次 rerun 没有证明 schema、session 契约或探测语义在 `G3` 边界仍然自相矛盾。
   - 因此，正确表述是：`fail_design` not proven；当前设计侧结论是 contract 已经满足 `G3` 的 read-only truthfulness 要求。

5. Low: session identifier split 仍是 residual observation，但不是本轮 blocker。
   - `session.status` / `trade://session/current` 报告 `session_id=100`。
   - `probe.connection` / `diag://probe/latest` 以及 `orders.list.shadow_fallback` 报告复用 shadow `session_id=111`。
   - 本轮里该 split 没有破坏 ordered chain，也没有让 public `orders.list` 的 degraded contract 失真；当前应继续记为 observation，而不是 blocker。

## Severity

- highest: high

## Impact

这次 review 需要把两个判断拆开：

1. 对 `VAL-002` 本身，目标 gate 是 `G3`。本轮已经形成 formal `pass`，因为 public `orders.list` 现在以 truthful degraded result 完成了先前缺失的公开只读能力闭环。
2. 对 `VAL-003`，本轮没有提供 broker fresh connect 已恢复的证据，反而继续在 `orders.list.broker_read` 中保留了 `xttrader connect=-1`。这意味着 higher gate 的阻断并未解除。

换句话说，本轮 improvement 既不是“环境完全恢复”，也不是“broker path 已 ready”；它是更精确的 contract closure：

1. `G3` 公开只读链路已成立。
2. broker subpath failure 仍被保留并可追溯。
3. 因为 failure 没有被掩盖，所以当前 public `orders.list` 的 success 可以被接受为 `G3 pass`。
4. 也正因为 failure 没有被掩盖，所以 `VAL-003/G4` 仍不能被误写成可启动。

## Required Fix

1. 对 `VAL-002` 本卡范围：无新的 blocking fix。`G3` review gate 可收口。
2. 对 downstream `VAL-003`：在进入 `G4` 前，仍需单独满足 higher-gate broker/write path 前置条件，不能复用本次 degraded `orders.list` 结果来代替。

## Release Decision

- Decision: `pass`
- Evidence Conclusion Carried Forward: `pass`
- `G3` Satisfied By This Rerun: `yes`
- Public `orders.list` Degraded Fallback Accepted For `G3`: `yes`
- Why Accepted: public tool now returns a truthful read-only result while preserving broker failure inside the same payload, so operational truth is preserved rather than masked
- Formal `fail_design` Proven By This Rerun: `no`
- `VAL-002` May Move Out Of `Blocked`: `yes`
- `VAL-003` May Proceed: `no`
- Summary: 本轮 live gateway-side rerun 关闭了上一轮仅剩的 public `orders.list` formal blocker。该工具现在以 broker-first、explicit degraded fallback 的方式完成公开只读返回，并在同一 payload 内保留 broker connect failure，因此 `VAL-002/G3` 可以正式 `pass`。但保留下来的 `xttrader connect=-1` 仍是 higher gate hard stop，故 `VAL-003/G4` 不得据此启动。

## State Suggestion

- Target Status: `Accepted`
- Reason: `VAL-002` 的目标 gate 是 `G3`，而本轮已经给出完整 ordered chain 的 formal `pass` 证据，且 public `orders.list` 的 explicit degraded fallback 保持了 operational truth。该卡可以离开 `Blocked`。
- Downstream Note: `VAL-003` 继续保持 `Blocked`，建议阻断原因记为 `broker_blocked`，直到 higher-gate broker/write path 前置条件得到独立闭合。
