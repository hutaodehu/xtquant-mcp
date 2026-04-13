# ReviewPack

Task ID: VAL-002
Role: review
Date: 2026-03-30T14:05:00+08:00
Change Package Link: [VAL-002.md](../change_packages/VAL-002.md)
Evidence Pack Link: [VAL-002-test-20260330-134330-live-gateway-rerun.md](../evidence_packs/VAL-002-test-20260330-134330-live-gateway-rerun.md)
Env Snapshot Link: [VAL-002-test-20260330-134330-live-gateway-rerun.md](../env_snapshots/VAL-002-test-20260330-134330-live-gateway-rerun.md)
Prior Review Link: [VAL-002-review-20260330-live-gateway-rerun.md](./VAL-002-review-20260330-live-gateway-rerun.md)
Prior Fresh Rerun Baseline: [VAL-002-test-20260330-124617-live-gateway-rerun.md](../evidence_packs/VAL-002-test-20260330-124617-live-gateway-rerun.md)

## Findings

1. High: `VAL-002` 仍不得放行，正式 release decision 继续是 `blocked`，`VAL-003` 仍不得启动。
   - [ACCEPTANCE_STANDARD.md](../ACCEPTANCE_STANDARD.md) 的 `G3` 明确要求按顺序完成 `miniqmt.ensure_logged_in -> session.warm -> session.status -> probe.connection -> account.show -> positions.list -> orders.list -> snapshot.l1`。
   - 本轮 fresh live gateway-side rerun 中，`miniqmt.ensure_logged_in`、`session.warm`、`session.status`、`probe.connection`、`account.show`、`positions.list`、`snapshot.l1` 已成功，但 public `orders.list` 仍返回 `xttrader connect failed: -1 after 3 attempts (...)`。
   - 因此本轮只能承接测试结论 `partial`，不能改写成 `pass`，也不能解除任务级 `blocked`。

2. High: 相比上一轮 fresh rerun，正式 blocker 已明显收窄；当前剩余正式 blocker 已缩到 public `orders.list` only。
   - 对比 [VAL-002-test-20260330-124617-live-gateway-rerun.md](../evidence_packs/VAL-002-test-20260330-124617-live-gateway-rerun.md)：
   - 上一轮仍有三处正式失败：`miniqmt.ensure_logged_in=desktop_not_interactive`、`probe.connection=connect_failed`、public `orders.list=xttrader connect failed: -1 after 3 attempts (...)`。
   - 本轮已把前两处失败清掉：
     - `miniqmt.ensure_logged_in=already_logged_in`
     - `diag://login/latest=already_logged_in`
     - `probe.connection=ok`
     - `probe_mode=owner_managed_session_reuse`
     - `readiness_layers.read_only.ok=true`
     - `fresh_connect_attempted=false`
   - 本轮仍保留且仅保留的正式失败项是 public `orders.list=xttrader connect failed: -1 after 3 attempts (...)`。
   - 旧的“`login + probe + public orders.list` 同时失败”的 blocker narrative 已不再准确；本轮准确表述应是：remaining formal blocker narrowed to public `orders.list` only。

3. Medium: 本轮已确认明确的 design-side progress，但这些进展不等于 formal `fail_design` 已被证明。
   - 已确认的 design-side progress：
     - `TG-004` 的 probe 语义修补已在真实运行态生效。
     - `probe.connection` 现已能用 `owner_managed_session_reuse` 表达 read-only readiness，而不再把失败统一塌缩成 `connect_failed`。
     - `diag://login/latest`、`diag://probe/latest`、public `orders.list` 仍保持分离可见，没有把失败路径静默掩盖成“整体 ready”。
   - 这些都属于设计与可观测性改进已经成立。
   - 但 formal `fail_design` 需要证明接口契约、状态机或实现边界本身错误；本轮并没有给出这样的正式证据闭环。

4. Medium: 剩余 blocker 目前仍应按 environment blocker 处理，formal `fail_design` 仍然是 `no`。
   - 当前唯一未通过的正式项是 public `orders.list`，其错误类别仍是 `environment`，且核心失败文本仍是 `xttrader connect failed: -1 after 3 attempts (...)`。
   - [ACCEPTANCE_STANDARD.md](../ACCEPTANCE_STANDARD.md) 已将 `xttrader connect=-1` 列为 `G3` 硬停止条件，并优先归类为 `fail_env` 或 `blocked`。
   - EnvSnapshot 中记录的 session identifier observation 目前只是一条 observation，不足以把本轮正式改判成 `fail_design`。
   - 因此，当前正确 posture 是：有明确 design-side progress；剩余 formal blocker 仍是 environment-scoped public `orders.list`；formal `fail_design` not proven。

## Severity

- highest: high

## Impact

本轮 review 改变的是 blocker 宽度判断，不改变正式放行结果。

现在可以确认的 improvement 是：

1. `miniqmt.ensure_logged_in` 已从 `desktop_not_interactive` 恢复为 `already_logged_in`。
2. `probe.connection` 已从 `connect_failed` 恢复为 `ok`，并返回分层 readiness 语义。
3. fresh gateway process 仍是 repo-supported wake path 拉起，`session.warm`、`session.status`、`trade://session/current` 继续维持 `ready`。
4. `account.show`、`positions.list`、`snapshot.l1` 继续成功。

现在仍然阻断放行的 only formal blocker 是：

1. public `orders.list=xttrader connect failed: -1 after 3 attempts (...)`

因此，本轮不能写 `pass`，也不能把任务改判成已证明的 `fail_design`。

## Required Fix

1. 后续 dev/test 只需继续围绕 public `orders.list` 做正式取证，不应再沿用“`login + probe + orders.list` 三处并列失败”的旧叙事。
2. 后续证据若要推进 `VAL-002` 放行，必须证明 public `orders.list` 在同类 fresh live gateway-side rerun 中通过，形成完整 `G3 pass`。
3. 在没有新 EvidencePack 证明 public `orders.list` 恢复前，不得解除 `VAL-002` 的 `blocked`，不得推进 `VAL-003`。
4. 在没有新证据把剩余 blocker 收敛为明确契约错误前，不得把本卡正式改判为 `fail_design`。

## Release Decision

- Decision: `blocked`
- Evidence Conclusion Carried Forward: `partial`
- Improvement Versus Prior Fresh Rerun: `login` and `probe` recovered; blocker narrowed materially
- Exact Narrowed Blocker Statement: remaining formal blocker narrowed to public `orders.list` only
- Remaining Blocker Type: `environment blocker`
- Formal `fail_design` Proven By This Rerun: `no`
- `VAL-003` May Proceed: `no`
- Summary: 本轮 fresh live gateway-side rerun 已把 formal blocker 从“`login + probe + public orders.list` 三处失败”收窄为“仅 public `orders.list` 失败”。这证明了明确的 design-side progress，但尚未形成 `G3 pass`，也未形成 formal `fail_design` proof。
- Release Recommendation: 不放行，`VAL-003` 继续阻断

## State Suggestion

- Target Status: `Blocked`
- Blocking Reason: `env_blocked`
- Reason: 本轮已确认 design-side progress 和 blocker 收窄，但 `G3` 仍被 public `orders.list` 的 `xttrader connect=-1` 硬停止条件阻断；当前 formal `fail_design` 仍未证明，故任务级 posture 应继续保持 `Blocked`。
