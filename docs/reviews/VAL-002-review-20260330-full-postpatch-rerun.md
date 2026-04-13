# 审查结论

Task ID: VAL-002
Role: review
Date: 2026-03-30T11:06:12.9825215+08:00
Evidence Pack Link: [VAL-002-test-20260330-full-postpatch-rerun.md](../evidence_packs/VAL-002-test-20260330-full-postpatch-rerun.md)
Env Snapshot Link: [VAL-002-test-20260330-full-postpatch-rerun.md](../env_snapshots/VAL-002-test-20260330-full-postpatch-rerun.md)
Prior Review Link 1: [VAL-002-review-20260330-postpatch-rerun.md](./VAL-002-review-20260330-postpatch-rerun.md)
Prior Review Link 2: [VAL-002-review-20260330-ui-visibility-postpatch.md](./VAL-002-review-20260330-ui-visibility-postpatch.md)

## Findings

1. High: 新的 full post-patch rerun 仍未通过 `G3`，`VAL-002` 的 release decision 继续保持 `blocked`，不发生状态解除。
   - 本轮测试结论已明确定义为 `fail_env`，且验收 gate 是 `G3`。
   - 新证据确认 trade gateway 确实完成了旧进程停止、新进程拉起和 fresh code load，排除了“其实仍跑在旧进程上”的歧义。
   - 但 `session.warm` 仍以 `error.category=environment` / `orders.list_exception` 失败，根因仍是 broker/session 层的 `xttrader connect failed: -1`。
   - 在该硬停止之后，`session.status`、`probe.connection`、`account.show`、`positions.list`、`orders.list`、`snapshot.l1` 全部停在 `session_not_ready`，`trade://session/current` 仍为 `ready=false`、`owner_generation=0`。
   - 依据 `docs/ACCEPTANCE_STANDARD.md`，`xttrader connect=-1` 和 session 无法建立属于 `G3` 的环境硬停止条件，不构成设计放行证据。
   - Source:
     - [VAL-002-test-20260330-full-postpatch-rerun.md](../evidence_packs/VAL-002-test-20260330-full-postpatch-rerun.md)
     - [VAL-002-test-20260330-full-postpatch-rerun.md](../env_snapshots/VAL-002-test-20260330-full-postpatch-rerun.md)
     - [ACCEPTANCE_STANDARD.md](../ACCEPTANCE_STANDARD.md)

2. High: 登录态本身已恢复，但 session/broker 仍被环境阻断；这次 improvement 只能写成“登录恢复，交易只读链未恢复”，不能误写成整体通过。
   - `miniqmt.ensure_logged_in` 现在返回 `ok=true`、`status=already_logged_in`、`port_ready=true`，`diag://login/latest` 也镜像该结果。
   - 这说明先前的 `login_window_not_found` 已不再是本轮 first-order blocker。
   - 但 owner-managed session 并未建立成功，真正的新阻断点是 `session.warm -> orders.list_exception -> xttrader connect failed: -1`。
   - 因此本轮必须明确区分：
     - 登录/UI 可见性改进属于“环境恢复到更深一层”；
     - broker/session 失败仍是“环境阻断未解除”；
     - 本轮没有新增证据证明 `fail_design`。
   - Source:
     - [VAL-002-test-20260330-full-postpatch-rerun.md](../evidence_packs/VAL-002-test-20260330-full-postpatch-rerun.md)
     - [VAL-002-test-20260330-full-postpatch-rerun.md](../env_snapshots/VAL-002-test-20260330-full-postpatch-rerun.md)
     - [VAL-002-review-20260330-ui-visibility-postpatch.md](./VAL-002-review-20260330-ui-visibility-postpatch.md)

3. Medium: 这次 full rerun 改变的是阻断位置和可诊断性，不改变既有 review 对 `VAL-002` 的总体阻断判断。
   - 与较早 review 相比，当前证据已经从“登录未确认 / UI 可见性异常”推进到“登录成功，但 broker `orders.list` 在 `session.warm` 内失败”。
   - 与 UI visibility follow-up review 相比，这次不再只是 bounded `partial`，而是完整重跑了 `G3` 链路；因此可以确认 UI/login 的改善已经进入真实链路，而不是孤立 probe 结果。
   - 但该完整链路仍在 broker/session 层被环境条件拦截，所以既有 `blocked` 结论仍然成立，只是阻断描述需要更新为“login recovered, session/broker still blocked”。
   - Source:
     - [VAL-002-review-20260330-postpatch-rerun.md](./VAL-002-review-20260330-postpatch-rerun.md)
     - [VAL-002-review-20260330-ui-visibility-postpatch.md](./VAL-002-review-20260330-ui-visibility-postpatch.md)
     - [VAL-002-test-20260330-full-postpatch-rerun.md](../evidence_packs/VAL-002-test-20260330-full-postpatch-rerun.md)

## Impact

本次新的 full rerun 对 `VAL-002` 的影响如下：

1. 它确认了补丁后的 gateway 是在 fresh process 上被实际执行的，因此本轮证据具有有效性。
2. 它确认了登录层已有恢复：`miniqmt.ensure_logged_in=already_logged_in`，MiniQMT 与 `58610` 端口都处于可见/可达状态。
3. 它同样确认了总体阻断并未解除：owner-managed session 仍未建立，broker/session 层依旧卡在 `xttrader connect failed: -1`。
4. 因此，这次 full rerun 不改变现有 `VAL-002` 的 `blocked` 状态；变化的是阻断位置和环境诊断深度，而不是放行结果。

## Required Fix

1. 继续按环境问题处理 broker/session 层阻断，直到 `session.warm` 不再落到 `orders.list_exception` / `xttrader connect failed: -1`。
2. 在环境恢复后重新证明 owner-managed session 已建立成功，至少需要看到：
   - `session.status` 返回 `ready=true`
   - `trade://session/current` 不再是空 `account_id=''` / `session_id=''`
   - 后续 `probe.connection`、`account.show`、`positions.list`、`orders.list`、`snapshot.l1` 不再因为 `session_not_ready` 失败
3. 若后续 rerun 仍失败，必须继续区分：
   - 设计问题：schema、session contract、probe semantics 与实现冲突
   - 环境问题：broker connect、session ownership、权限、实例状态或券商进程异常
4. 在新的 EvidencePack 明确证明完整 `G3` 通过之前，不允许把 `VAL-002` 从 `blocked` 改写成 `pass` 或推动 `VAL-003` 放行。

## Release Decision

- Decision: `blocked`
- Test Conclusion Carried Forward: `fail_env`
- Design Failure Proven By This Rerun: `no`
- Status Change From Existing VAL-002 Reviews: `unchanged`
- Explicit Statement: 本次新的 full post-patch rerun 没有改变既有 `VAL-002` 的 `blocked` 状态。登录已恢复到 `already_logged_in`，但 session/broker 仍在 `session.warm` 阶段被 `orders.list_exception -> xttrader connect failed: -1` 阻断，这属于环境层阻断，不是已证明的设计层失败。
- Recommended Next Board Status: `Blocked`
- Release Recommendation: 不放行，不进入 `VAL-003`

## Residual Risks

1. 当前 fresh rerun 只证明登录恢复和阻断位置下沉，未证明 broker session ownership 生命周期已经稳定。
2. 若后续只关注“登录恢复”而忽略 `session_not_ready` 和 `xttrader connect=-1`，controller 容易误判为阻断解除。
3. 这次 run 没有新增 `fail_design` 证据，但也没有排除环境恢复后出现新的 contract/design 缺陷；后续 rerun 仍需继续独立分类。
