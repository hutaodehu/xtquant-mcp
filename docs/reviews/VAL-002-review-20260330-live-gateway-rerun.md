# ReviewPack

Task ID: VAL-002
Role: review
Date: 2026-03-30T13:05:00+08:00
Change Package Link: [VAL-002.md](../change_packages/VAL-002.md)
Evidence Pack Link: [VAL-002-test-20260330-124617-live-gateway-rerun.md](../evidence_packs/VAL-002-test-20260330-124617-live-gateway-rerun.md)
Env Snapshot Link: [VAL-002-test-20260330-124617-live-gateway-rerun.md](../env_snapshots/VAL-002-test-20260330-124617-live-gateway-rerun.md)
Prior Review Link 1: [VAL-002-review-20260330-native-query-chain.md](./VAL-002-review-20260330-native-query-chain.md)
Prior Review Link 2: [VAL-002-review-20260330-full-postpatch-rerun.md](./VAL-002-review-20260330-full-postpatch-rerun.md)
Prior Evidence Link: [VAL-002-test-20260330-full-postpatch-rerun.md](../evidence_packs/VAL-002-test-20260330-full-postpatch-rerun.md)

## Findings

1. High: `VAL-002` 仍然不能放行，正式 release decision 继续是 `blocked`，`VAL-003` 仍不得启动。
   - [ACCEPTANCE_STANDARD.md](../ACCEPTANCE_STANDARD.md) 的 `G3` 要求按顺序完成 `miniqmt.ensure_logged_in -> session.warm -> session.status -> probe.connection -> account.show -> positions.list -> orders.list -> snapshot.l1`。
   - 本轮 fresh gateway-side rerun 中，第 1 步 `miniqmt.ensure_logged_in` 失败为 `desktop_not_interactive`，第 4 步 `probe.connection` 失败为 `connect_failed`，第 7 步 `orders.list` 失败为 `xttrader connect failed: -1 after 3 attempts (...)`。
   - 因此本轮最多只能承接测试结论 `partial`，不能改写成 `pass`，也不能解除 `VAL-002` 的任务级 `blocked`。

2. High: 相比上一轮正式 blocker narrative，本轮变化是实质性的，旧的“`session.warm` 后整体 `session_not_ready`”叙事已经不再准确。
   - 上一轮 [VAL-002-test-20260330-full-postpatch-rerun.md](../evidence_packs/VAL-002-test-20260330-full-postpatch-rerun.md) 的正式结论是：`miniqmt.ensure_logged_in=already_logged_in`，但 `session.warm` 以 `orders.list_exception -> xttrader connect failed: -1` 失败，随后 `session.status`、`probe.connection`、`account.show`、`positions.list`、`orders.list`、`snapshot.l1` 全部停在 `session_not_ready`，`trade://session/current` 为 `ready=false`。
   - 本轮 fresh gateway-side rerun 则明确显示：gateway 从 `8765 down` 状态被 repo-supported 路径重新拉起，`session.warm=ready`，`session.status=ready`，`trade://session/current=ready`，并且 `account.show`、`positions.list`、`snapshot.l1` 已成功。
   - 所以 blocker narrative 已经从“owner-managed session 根本未建立”收缩为“owner-managed session 已建立，但登录探测与公开 connect-based 读路径仍失败”。

3. High: 纯 `fail_env` 已不再是充分解释，但本轮仍不足以正式证明 `fail_design`；当前最准确 posture 是 `blocked`，且属于 mixed but not-yet-proven explanation。
   - 仍然存在明确 environment blockers：
     - `miniqmt.ensure_logged_in=desktop_not_interactive`
     - `probe.connection` 对 `101/100/111` 全部返回 `connect_code=-1`
     - 公开 `orders.list` 继续返回 `xttrader connect failed: -1 after 3 attempts (...)`
   - 同时，本轮也出现了不能继续被“纯环境不可用”完整覆盖的新事实：
     - 同一 fresh gateway process 已把 `trade://session/current` 写成 `ready=true`
     - `session.status=ready`
     - `account.show`、`positions.list`、`snapshot.l1` 可成功返回
   - 这意味着旧的“环境层完全不可用，所以 gateway 自然全链路失败”解释已经不足。更强的假设变成：gateway 的 session readiness、shadow-backed 成功路径、以及公开 connect-based 读路径之间存在 design 或实现边界不一致。
   - 但由于本轮仍伴随 `desktop_not_interactive` 和 `connect=-1` 这两个 `G3` 环境硬停止，本包还不能把矛盾收敛成单一已证实 contract break，因此正式 `fail_design` 仍然是 `no`。

4. Medium: 本轮对 design-mismatch 假设的补强是明确的，但它仍然只是 hypothesis strengthening，不是 formal proof。
   - `diag://probe/latest` 在本轮链路结束后仍为 `ok=false`、`reason=connect_failed`、`readiness_layers.read_only.ok=false`，而 `trade://session/current` 同时为 `ready=true`。
   - `session.warm` 成功时记录的是 `warm_health_only` / `xttrader_shadow` 成功路径，而公开 `orders.list` 仍然要求真实 connect 并失败。
   - 这个组合足以要求后续 dev/test 明确拆开“session 已 ready 的定义”和“公开读工具可用的定义”，但还不足以由 review 直接宣布某一条具体设计契约已经被正式证伪。

## Severity

- highest: high

## Impact

本轮 review 改变的是正式解释口径，不改变正式放行结果。

已确认的 gateway-side progress 是：

1. repo-supported wake 路径在 `8765 down` 的前置状态下仍能拉起 fresh gateway process，并返回健康 `/healthz`。
2. owner-managed session 不再停在 `session_not_ready`，而是已经达到 `session.warm=ready`、`session.status=ready`、`trade://session/current=ready`。
3. `account.show`、`positions.list`、`snapshot.l1` 已能在本轮 fresh gateway-side rerun 中成功。

仍然存在的 environment blockers 是：

1. `miniqmt.ensure_logged_in=desktop_not_interactive`。
2. `probe.connection` 对 `101/100/111` 仍是 `connect=-1`。
3. 公开 `orders.list` 仍然落在 `xttrader connect failed: -1 after 3 attempts (...)`。

被补强但尚未正式证明的 design-mismatch hypothesis 是：

1. gateway 对“session ready”的判定，与公开 connect-based 读路径是否真实可用之间，可能存在契约或生命周期边界不一致。
2. shadow-backed 成功路径与公开 connect-based 失败路径可能被混写进同一 `G3` readiness 口径。

因此，当前不能再把 `VAL-002` 简化写成纯 `fail_env`，但也不能越级写成已证明的 `fail_design`。最准确的正式 posture 仍然是 `blocked`。

## Required Fix

1. 后续 dev/test 必须在同一 host、同一 bundle、同一实例目录条件下，单独对齐以下三类事实，不能再合并叙述：
   - `miniqmt.ensure_logged_in` 的桌面交互状态
   - gateway owner-managed session 的 ready 判定
   - 公开 connect-based 读工具的真实可用性
2. 后续证据必须明确区分 shadow-backed 成功与真实 connect-based 成功，避免把前者误写成完整 `G3` 恢复。
3. 在没有新 EvidencePack 证明完整 `G3 pass` 前，不得解除 `VAL-002` 的 `blocked`，不得推进 `VAL-003`。
4. 在没有新证据把当前矛盾收敛到明确 contract break 前，不得把本卡正式改判为 `fail_design`。

## Release Decision

- Decision: `blocked`
- Evidence Conclusion Carried Forward: `partial`
- Prior Pure `fail_env` Explanation Still Adequate: `no`
- Formal `fail_design` Proven By This Rerun: `no`
- Correct Current Posture: `blocked`
- Summary: 本轮 fresh gateway-side rerun 证明 gateway 侧已有实质进展，旧的“`session.warm` 后整体 `session_not_ready`” blocker narrative 已经失效；但由于 `desktop_not_interactive` 与 `xttrader connect=-1` 仍在同一 `G3` 链路内出现，正式结论不能从 `blocked` 提升，也不能从 review 侧直接改判为 `fail_design`。当前正确口径是 `blocked` with mixed but not-yet-proven explanation。
- Release Recommendation: 不放行，`VAL-003` 继续阻断

## State Suggestion

- Target Status: `Blocked`
- Reason: 新 EvidencePack 已证明 gateway-side progress，但 `G3` 仍未完整通过；纯 `fail_env` 已不足以完整解释，正式 `fail_design` 又尚未被证明，因此任务级 posture 仍应保持 `Blocked`，等待后续把 environment blockers 与 design-mismatch hypothesis 继续拆分取证。
