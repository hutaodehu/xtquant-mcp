# ReviewPack

Task ID: VAL-002
Role: review
Date: 2026-03-30T13:56:58+08:00
Change Package Link: [VAL-002.md](../change_packages/VAL-002.md)
Evidence Pack Link: [VAL-002-test-20260330-134330-live-gateway-rerun.md](../evidence_packs/VAL-002-test-20260330-134330-live-gateway-rerun.md)
Env Snapshot Link: [VAL-002-test-20260330-134330-live-gateway-rerun.md](../env_snapshots/VAL-002-test-20260330-134330-live-gateway-rerun.md)
Prior Review Link 1: [VAL-002-review-20260330-live-gateway-rerun.md](./VAL-002-review-20260330-live-gateway-rerun.md)
Prior Evidence Link 1: [VAL-002-test-20260330-124617-live-gateway-rerun.md](../evidence_packs/VAL-002-test-20260330-124617-live-gateway-rerun.md)

## Findings

1. High: `VAL-002` 仍不能放行，正式 release decision 继续是 `blocked`，`VAL-003` 仍不得启动。
   - [ACCEPTANCE_STANDARD.md](../ACCEPTANCE_STANDARD.md) 的 `G3` 必须按顺序完成 `miniqmt.ensure_logged_in -> session.warm -> session.status -> probe.connection -> account.show -> positions.list -> orders.list -> snapshot.l1`。
   - 新 EvidencePack 中，`miniqmt.ensure_logged_in`、`session.warm`、`session.status`、`probe.connection`、`account.show`、`positions.list`、`snapshot.l1` 均成功，但 public `orders.list` 仍返回 `xttrader connect failed: -1 after 3 attempts (...)`。
   - `ACCEPTANCE_STANDARD.md` 同时把 `xttrader connect=-1` 列为硬停止条件，因此本轮最多只能承接测试结论 `partial`，不能提升为 `pass`。

2. High: 相比 prior fresh rerun，本轮 live `G3` 的正式 blocker 已明确收窄为 public `orders.list` only。
   - prior fresh rerun 中，失败桶是三处：`miniqmt.ensure_logged_in=desktop_not_interactive`、`probe.connection=connect_failed`、public `orders.list=xttrader connect failed: -1`。
   - 新 rerun 中，`miniqmt.ensure_logged_in` 已恢复为 `already_logged_in`，`diag://login/latest` 与工具结果一致；`probe.connection` 已恢复为 `ok`，并明确采用 `owner_managed_session_reuse`，`fresh_connect_attempted=false`。
   - 因此，上一轮“login + probe + public orders.list”三处失败的 blocker narrative 已不再成立；当前正式 blocker 只剩 public `orders.list` 这一条公开 connect-based 读路径。

3. Medium: 已确认的 design-side progress 是 probe 语义和可观测性修补在真实运行态生效，但这还不能被写成 `fail_design` 已证明。
   - `probe.connection` 从 prior run 的 `connect_failed` 变为 `ok`，并把 `readiness_layers.read_only.source=active_owner_shadow` 与 `readiness_layers.write_permission.source=userdata_precheck` 分开暴露。
   - `miniqmt.ensure_logged_in` 继续保持独立可见，没有被 `session.warm` 或 `probe.connection` 静默掩盖。
   - public `orders.list` 也继续保持独立失败可见，没有被 shadow 成功路径掩盖。
   - 这些都是已确认的 design-side progress，但它们证明的是语义拆分与可观测性更准确，不是新的正式 `fail_design`。

4. Medium: 剩余 blocker 目前仍应归为 environment blocker，正式 `fail_design` 仍然是 `no`。
   - 新 EvidencePack 里 public `orders.list` 明确标注 `error.category=environment`，错误文本仍是 `xttrader connect failed: -1 after 3 attempts (...)`。
   - `ACCEPTANCE_STANDARD.md` 对 `xttrader connect=-1` 的默认分类是 `fail_env` 或 `blocked`，除非有额外证据把问题收敛为会话契约、schema 或探测语义与实现不一致。
   - EnvSnapshot 记录了一个单独 observation: `session.status` / `trade://session/current` 为 `session_id=100`，而注记中提到 `diag://probe/latest` 复用 shadow `session_id=101`。当前证据把它记录为 observation only，而不是 formal blocker。
   - 因此，本轮不能把 `VAL-002` 正式改判为 `fail_design`；正确 posture 仍是 `blocked`，剩余 blocker 为 environment-scoped。

## Severity

- highest: high

## Impact

本轮 review 的核心变化是正式 blocker 形状继续收窄，但 release posture 不变。

已确认的 design-side progress：

1. repo-supported wake 路径再次证明可从 `8765 down` 状态拉起 fresh gateway process，并恢复 `/healthz`。
2. `miniqmt.ensure_logged_in` 已从 `desktop_not_interactive` 恢复为 `already_logged_in`，且 `diag://login/latest` 与工具结果一致。
3. `probe.connection` 已从 `connect_failed` 恢复为 `ok`，并在真实运行态证明 `owner_managed_session_reuse` 语义生效。
4. `probe.connection` 结果已明确区分 `read_only` 与 `write_permission`，没有再把两者混写成单一 ready 口径。
5. public `orders.list` 的失败仍保持独立可见，没有被 shadow 成功路径掩盖。

仍然存在的 environment blockers：

1. public `orders.list` 仍返回 `xttrader connect failed: -1 after 3 attempts (...)`。
2. `xttrader connect=-1` 仍是 `G3` 硬停止条件，因此本卡仍不能写成 `pass`，也不能进入 `G4`。

本轮没有新增被正式证明的 `fail_design`。当前最多只能说：此前的 blocker 叙事已经收窄，且 design-side progress 已经在真实运行态得到确认；但剩余 formal blocker 仍是 environment-scoped 的 public `orders.list`。

## Required Fix

1. 后续 dev/test 必须继续围绕 public `orders.list` 的 connect-based 路径取证，不能把 `probe.connection=ok` 或 warm trace 的 shadow `orders.list` 成功写成完整 `G3 pass`。
2. 若后续要主张 `fail_design`，必须补出直接证据，把问题从 `xttrader connect=-1` 环境硬停止收敛到明确的会话契约、schema 或探测语义错误；当前证据还不够。
3. 在 public `orders.list` 未恢复前，不得解除 `VAL-002` 的 `blocked`，不得推进 `VAL-003`。

## Release Decision

- Decision: `blocked`
- Evidence Conclusion Carried Forward: `partial`
- Remaining Formal Blocker Narrowed To Public `orders.list` Only: `yes`
- Exact Narrowed Blocker Statement: public `orders.list` is now the only remaining formal blocker in the live `G3` chain; it still fails as the explicit public connect-based read path with `xttrader connect failed: -1 after 3 attempts (...)`
- Confirmed Design-side Progress Present: `yes`
- Remaining Blocker Type: `environment`
- Formal `fail_design` Proven By This Rerun: `no`
- Release Recommendation: 不放行，`VAL-003` 继续阻断

## State Suggestion

- Target Status: `Blocked`
- Reason: 本轮 live gateway-side rerun 已经把 prior fresh rerun 的三处失败收窄到 public `orders.list` 单点失败，并确认了 `TG-004` probe 语义修补在真实运行态生效；但 `G3` 仍未完整通过，且剩余 public connect-based 读路径失败仍属于 environment blocker，因此任务级 posture 继续保持 `Blocked`。
