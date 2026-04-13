# ReviewPack

Task ID: VAL-002
Role: review
Date: 2026-03-30T12:03:29.4996258+08:00
Evidence Pack Link: [VAL-002-test-20260330-native-query-chain.md](../evidence_packs/VAL-002-test-20260330-native-query-chain.md)
Env Snapshot Link: [VAL-002-test-20260330-native-query-chain.md](../env_snapshots/VAL-002-test-20260330-native-query-chain.md)
Prior Review Link 1: [VAL-002-review-20260330-broker-log-extract.md](./VAL-002-review-20260330-broker-log-extract.md)
Prior Review Link 2: [VAL-002-review-20260330-full-postpatch-rerun.md](./VAL-002-review-20260330-full-postpatch-rerun.md)
Prior Review Link 3: [VAL-002-review-20260330-broker-session-native-probe.md](./VAL-002-review-20260330-broker-session-native-probe.md)

## Findings

1. High: 本次新增 native query-chain evidence 仍不足以把 `VAL-002` 从 `blocked` 提升到 `pass`，因为 `G3` 要求的是 gateway 自身只读链路成立，而不是宿主外的 bounded native 单例链路成立。
   - [ACCEPTANCE_STANDARD.md](../ACCEPTANCE_STANDARD.md) 明确要求 `G3` 依次验证 `miniqmt.ensure_logged_in -> session.warm -> session.status -> probe.connection -> account.show -> positions.list -> orders.list -> snapshot.l1`。
   - 本次 EvidencePack 证明的是同机同 bundle 下，单个 native `XtQuantTrader(session_id=101)` 可以在一个生命周期内完成 `connect -> query_account_infos -> subscribe -> query_stock_asset -> query_stock_positions -> query_stock_orders`。
   - 但该包没有提供一次新的 gateway `G3` rerun，也没有提供 `session.status ready=true`、`trade://session/current` 持有真实 owner-managed session，或后续 MCP 只读工具恢复成功的证据。
   - 因此 release posture 只能继续保持 `blocked`，不能据此解除 `VAL-002` gate，也不能推进 `VAL-003`。

2. High: 这批证据已经不再支持把当前 `101` 只读路径继续表述为“纯 `fail_env` 即可解释”，但仍不足以正式改判为 `fail_design`。
   - 先前审查链条的核心依据是：gateway rerun 停在 `session.warm -> orders.list_exception -> xttrader connect failed: -1`，而 native broker/session probe 也在 gateway 外复现了 `connect()=-1`，所以当时 `fail_env` 是最强结论。
   - 本次新证据则给出相反的 bounded fact：同一主机、同一 `venv313`、同一 vendor bundle、同一 `userdata_mini` 下，native `session_id=101` 已能完整跑通 read-only query chain，并且 QMT 宿主日志对齐确认了 `query accountInfos found 1`、`query positions found 2`、`query orders found 5`。
   - 与此同时，probe 前基线仍显示 gateway `trade_session_current.json` 为 `ready=false`、`reason=session_not_ready`、`session_id=''`、`owner_generation=0`。
   - 这说明“环境本身无法在 `101` 上完成 connect/query”已不再是充分解释；更强的解释变成“gateway session/lifecycle/ownership 边界与宿主可用路径之间存在设计或实现层面的不匹配假设”。
   - 但因为本包没有在同一窗口内重跑完整 gateway `G3`，也没有把 mismatch 收敛到一个已证实的 contract break，所以仍不能正式改判为 `fail_design`。

3. Medium: 本次 evidence 的真正增量是把 design-vs-environment 的讨论从“环境阻断已证实”推进到“环境解释被削弱、design-mismatch 假设被补强”，审查文案必须精确表达，避免 controller 误读。
   - 如果继续沿用上一轮 `broker-log-extract` review 的表述，把当前状态简单写成“仍是 `fail_env`”，会掩盖一个新事实：native `101` 只读链路已经成功，之前的环境硬停止不再完整覆盖现状。
   - 如果反过来直接写成“已证明 gateway 设计失败”，又会超出本包证据边界，因为本包没有把 gateway 侧 owner lifecycle、会话复用、session candidate 选择或 teardown 时序精确钉到单一缺陷点。
   - 正确写法应是：正式 release decision 仍为 `blocked`；正式 `fail_design` 尚未证明；但新的 evidence 只会加强 `gateway sequence/lifecycle mismatch` 假设，而不是继续单纯加强 `fail_env`。

4. Medium: `stop()` 之后约四秒出现的 `heartbeat timeout -> onDisconnected -> file lock not held, offline` 仍然只能作为后续生命周期分析线索，不能被提升为本轮已证实根因。
   - 本次 QMT 宿主日志显示读链路成功发生在 `11:56:43` 到 `11:56:45`，而 timeout/disconnect 出现在 `11:56:49`，时间上位于显式 `stop()` 之后。
   - 这支持“teardown-related observation”而不是“orders 是 first failure point”。
   - 但它还不能单独证明 gateway 当前阻断一定来自 stop/teardown 设计错误；若后续团队要把这一点收敛成 required fix，需要新的 dev/test 工件把 gateway owner-managed lifecycle 与该宿主现象直接对齐。

## Impact

本次新增证据没有改变 `VAL-002` 的放行状态，但改变了当前最强可支撑解释。

在放行层，`VAL-002` 仍未通过 `G3`，因此正式状态继续是 `blocked`。在分类层，这次 evidence 不足以把任务直接改判为 `fail_design`，但它已经削弱了“当前问题完全是 native 环境不可用”的旧叙事，因为 native `session_id=101` 的 bounded read-only query chain 已成功。

因此，当前最准确的审查口径应更新为：`VAL-002` 仍然 `blocked`；纯 `fail_env` 不再是足够解释；本次 evidence 只是在不解除阻断的前提下，显著增强了 `gateway sequence/lifecycle mismatch` 的设计不匹配假设。

## Required Fix

1. 在不改写本轮 `blocked` 决定的前提下，后续 dev/test 必须补一轮与本次 native 成功窗口可直接对比的 gateway `G3` rerun，至少要能对齐同一 host、同一 bundle、同一 `userdata_mini`、同一 session candidate 选择依据。
2. 后续定位必须把以下三类问题拆开记录，不能再混写成单一 `fail_env`：
   - native host capability 是否可用
   - gateway owner-managed session 是否建立成功
   - gateway query lifecycle / session reuse / ownership contract 是否与宿主可用路径不一致
3. 在没有新的独立证据把 mismatch 收敛到明确 contract break 前，不得把本卡正式改判为 `fail_design`。
4. 在没有新的 gateway-side `G3 pass` EvidencePack 前，不得解除 `VAL-002` 的 `blocked`，也不得推进 `VAL-003`。

## Release Decision

- Decision: `blocked`
- Evidence Conclusion Carried Forward: `partial`
- Current `G3` Gate Status: `blocked`
- Formal `fail_design` Proven By This Evidence: `no`
- Formal Design-vs-Environment Reclassification: `no`
- Explicit Statement: 本次新增 native query-chain evidence 不改变 `VAL-002` 当前的正式 release decision，任务仍然是 `blocked`。它也不足以把当前问题正式改判为 `fail_design`。这批证据带来的变化是解释层而不是放行层的变化: 它不再支持继续把当前 `101` 只读路径简单归因成“纯环境不可用”，而是只会加强 `gateway sequence/lifecycle mismatch` 的设计不匹配假设，同时保持 `VAL-002` 继续阻断。
- Release Recommendation: 不放行，不进入 `VAL-003`

## State Suggestion

- Target Status: `Blocked`
- Reason: gateway `G3` 仍未被新证据重新跑通；本轮只证明 native `101` bounded read-only chain 成功，因而只能加强设计不匹配假设，不能解除任务阻断。
