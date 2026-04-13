# ReviewPack

Task ID: VAL-002
Role: review
Date: 2026-03-30T12:20:00+08:00
Evidence Pack Link: [VAL-002-test-20260330-broker-log-extract.md](../evidence_packs/VAL-002-test-20260330-broker-log-extract.md)
Env Snapshot Link: [VAL-002-test-20260330-broker-log-extract.md](../env_snapshots/VAL-002-test-20260330-broker-log-extract.md)
Prior Review Link 1: [VAL-002-review-20260330-broker-session-native-probe.md](./VAL-002-review-20260330-broker-session-native-probe.md)
Prior Review Link 2: [VAL-002-review-20260330-full-postpatch-rerun.md](./VAL-002-review-20260330-full-postpatch-rerun.md)

## Findings

1. High: 新增主机日志证据没有改变 `VAL-002` 的正式 `blocked` 状态，`G3` 仍然停在环境硬停止条件上。
   - `docs/ACCEPTANCE_STANDARD.md` 明确把 `xttrader connect=-1`、session 无法建立、broker/session connect 失败列为 `G3` 的环境侧硬停止。
   - 新证据虽然补上了 QMT 宿主侧相关日志，但没有提供一次成功的 owner-managed session 建立，也没有提供 `session.status ready=true`、`probe.connection` 成功或后续账户查询链路打通的证据。
   - 在 `11:16` native probe 对应窗口里，主机日志显示 session `100`、`101` 都先 `onConnected`，随后迅速出现 `heartbeat timeout`、`onDisconnected`，并落到 `lock_down_queue_win_<session> file lock not held, offline`。
   - 这说明 broker/session 层的失败有了更强的宿主侧相关性，但验收结论仍然只能保持 `fail_env` / `blocked`，不能解除 `VAL-002` 的 gate 阻断。
   - Source:
     - [VAL-002-test-20260330-broker-log-extract.md](../evidence_packs/VAL-002-test-20260330-broker-log-extract.md)
     - [VAL-002-test-20260330-broker-log-extract.md](../env_snapshots/VAL-002-test-20260330-broker-log-extract.md)
     - [ACCEPTANCE_STANDARD.md](../ACCEPTANCE_STANDARD.md)

2. High: 新证据强化的是环境层解释，不是设计层失败；当前设计-vs-环境分类保持不变。
   - 先前 review 已经确认：登录恢复后，full rerun 仍卡在 `session.warm -> orders.list_exception -> xttrader connect failed: -1`，native probe 也在 gateway 外复现了 `connect()=-1`。
   - 本次 host-log extraction 进一步把 native `11:16` 失败窗口与 QMT 宿主日志对齐，支持“会话曾短暂连上，但未稳定持有 lock-backed online 状态”这一环境层事实。
   - 但这些日志并没有证明 gateway schema、session contract、`orders.list` 实现或 probe semantics 本身存在自洽性错误；也没有形成“native 成功而 gateway 独占失败”的反证。
   - 因此，这批证据不能把当前问题从 `fail_env` 改写为 `fail_design`。
   - Source:
     - [VAL-002-review-20260330-broker-session-native-probe.md](./VAL-002-review-20260330-broker-session-native-probe.md)
     - [VAL-002-review-20260330-full-postpatch-rerun.md](./VAL-002-review-20260330-full-postpatch-rerun.md)
     - [VAL-002-test-20260330-broker-log-extract.md](../evidence_packs/VAL-002-test-20260330-broker-log-extract.md)

3. Medium: 新增主机日志提高了诊断深度，但没有闭合根因，不能把“更强相关性”误写成“根因已定位”。
   - 在较早的 `10:57-10:59` gateway rerun 窗口中，宿主日志同时记录了 session `100`、`101`、`111` 的连接与账户/持仓查询活动，且部分 `lock_down_queue_win_*` 仍是 `file lock held, keep online`。
   - 与此同时，gateway 侧在同一时间窗仍给出 `session_not_ready` / `xttrader connect failed: -1` 相关阻断结论。
   - 这意味着本次提取虽然为 `11:16` native 失败提供了更强宿主解释，但还没有把更早 `10:57-10:59` 的端到端差异完全闭合到单一根因。
   - 审查侧应要求后续修复继续保持边界：把“已证明的环境现象”与“尚未闭合的根因解释”分开记录，避免 controller 把这批日志当成设计缺陷已锁定或 blocker 已解除的证据。
   - Source:
     - [VAL-002-test-20260330-broker-log-extract.md](../evidence_packs/VAL-002-test-20260330-broker-log-extract.md)
     - [VAL-002-review-20260330-full-postpatch-rerun.md](./VAL-002-review-20260330-full-postpatch-rerun.md)

4. Medium: `queryNodeInfo` / `m_bInstantMode` 的同日启动上下文不能被提升为本轮 blocker 的 required fix。
   - 该字段和 `ErrorID: 200006` 日志出现在 `00:32` 的启动上下文，不在本轮两个 blocker 窗口内。
   - 当前 EvidencePack 也明确声明不对 `m_bInstantMode` 赋予额外语义。
   - 因此，审查不能基于这批 bounded host logs 直接下结论说“InstantMode 参数错误就是当前剩余 blocker 的根因”，也不能据此把 required fix 收敛成单一设计修改。
   - 若后续团队要把这一线索升级为修复项，必须先有新的 dev/test 工件把它与 `10:57` / `11:16` 失败窗口直接关联起来。
   - Source:
     - [VAL-002-test-20260330-broker-log-extract.md](../evidence_packs/VAL-002-test-20260330-broker-log-extract.md)

## Impact

这批 host-log evidence 的价值在于：它把先前 native probe 的环境阻断从“外部症状”推进到了“宿主侧可观察现象”。当前最强可支撑表述应更新为：登录已恢复，broker/session 失败并非纯 gateway 表象；在 native `11:16` 窗口里，QMT 宿主日志确实显示短暂连接后因 heartbeat timeout 和 `lock_down_queue_win_* file lock not held, offline` 而掉线。

但这批证据没有改变 release posture。`VAL-002` 仍未通过 `G3`，没有新的成功 session 证据，也没有新的设计级反证。因此它只提升环境诊断置信度，不改变正式状态，也不允许推进 `VAL-003`。

## Required Fix

1. 继续把 `VAL-002` 作为环境阻断处理，直到新的 EvidencePack 能证明真实 owner-managed session 已建立成功，并且不再出现 `xttrader connect=-1` / `session_not_ready`。
2. 后续 investigation 必须分开产出两类结论：
   - 已证实的宿主侧环境现象，例如 heartbeat timeout、`lock_down_queue_win_* file lock not held, offline`
   - 尚未闭合的根因假设，例如 session owner 冲突、broker runtime policy、特定参数语义
3. 不得基于本次 bounded host-log extraction 把当前问题改判为 `fail_design`；只有在同环境下出现“native 可稳定通过而 gateway 独占失败”的新证据，才有资格重新打开设计层判定。
4. 不得基于 `queryNodeInfo` / `m_bInstantMode` 的同日上下文直接发起单点修复宣告；若要进入修复流，需先由新卡或新一轮独立测试把该线索与 blocker 窗口直接绑定。
5. `VAL-003` 继续保持不可启动，直到 `VAL-002` 有新的正式 `G3 pass` 证据。

## Release Decision

- Decision: `blocked`
- Test Conclusion Carried Forward: `fail_env`
- Host-Log Evidence Changes Blocked Status: `no`
- Host-Log Evidence Changes Design-vs-Environment Classification: `no`
- Explicit Statement: 本次新增 host-log evidence 不改变 `VAL-002` 当前的 `blocked` 状态，也不改变“环境阻断而非已证明设计失败”的分类。它只增强了 `fail_env` 的宿主侧证据强度，没有形成解除 `G3` 阻断或改判 `fail_design` 的依据。
- Release Recommendation: 不放行，不进入 `VAL-003`

## State Suggestion

- Target Status: `Blocked`
- Reason: `G3` 仍被 broker/session 环境问题阻断；新增主机日志只增强环境诊断，不构成状态解除或设计改判证据。
