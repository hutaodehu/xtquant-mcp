# 审查结论

Task ID: VAL-002
Role: review
Date: 2026-03-30T09:30:00+08:00
Change Package Link: D:\xtquant-mcp\repo\docs\change_packages\TG-004.md
Evidence Pack Link: D:\xtquant-mcp\repo\docs\evidence_packs\VAL-002-test-20260330-postpatch-rerun.md
Env Snapshot Link: D:\xtquant-mcp\repo\docs\env_snapshots\VAL-002-test-20260330-postpatch-rerun.md
Previous Review Link: D:\xtquant-mcp\repo\docs\reviews\VAL-002-review-202603300701.md
Supersedes: D:\xtquant-mcp\repo\docs\reviews\VAL-002-review-202603300701.md

## Findings

1. High: post-patch live rerun 仍未通过 `G3` 的环境硬停止条件，`VAL-002` 不能解除阻断。
   - EvidencePack 明确记录：`miniqmt.ensure_logged_in` 仍返回 `miniqmt_not_logged_in` / `login_window_not_found`，`session.warm` 仍返回 `server_env_not_ready`，并带出 `xttrader connect failed: -1`。
   - EnvSnapshot 明确记录：`XtMiniQmt` 进程存在、`127.0.0.1:58610` 可达、trade gateway 已重启到新 pid `22620`，但 `trade://session/current` 仍为 `ready=false`、`reason=session_not_ready`、`owner_generation=0`。
   - 这满足 `docs/ACCEPTANCE_STANDARD.md` 中 `G3` 的硬停止条件，属于环境层阻断，不构成设计放行证据。

2. Medium: 本次 rerun 改善的是可诊断性，不是可用性。
   - 与上一轮 live 证据相比，本次在确认重启加载补丁后，`session.warm` 的失败文本从单点 `xttrader connect failed: -1`，细化为对候选 session `100/101/111` 的逐候选诊断。
   - 这与 `docs/change_packages/TG-004.md` 中 follow-up patch 对 auto-account session candidate 扫描的收敛目标一致，说明补丁提升了错误暴露质量。
   - 但 rerun 仍未建立 owner-managed session，`session.status` 和 `trade://session/current` 仍停在 `session_not_ready`，因此该改进只能记为 diagnosability improvement，不能记为 `partial` 或 `pass`。

3. Medium: 本次审查结论必须保持“测试结论 `fail_env` + 审查放行结论 `blocked`”的词汇分层，不能把两者混写。
   - 新 EvidencePack 的正式结论词是 `fail_env`，这是测试角色对失败类型的分类。
   - Review gate 需要表达的是任务是否放行；在当前证据下，正确 release decision 仍是 `blocked`。
   - 若把本次 rerun 的改进表述成“已修复”或“基本通过”，会与仓库的 gate 语义冲突，并错误诱导后续 `VAL-003` 启动。

## Impact

本次 post-patch live rerun 不改变现有 `VAL-002` 的 `blocked` 状态。它证明了：

1. rerun 的确跑在重启后的新 gateway 进程上，而不是旧进程残留；
2. `TG-004` follow-up patch 让 `session.warm` 的失败诊断更具体；
3. 但真实结果仍是 `fail_env`，尚未形成 `G3` 只读链路通过证据。

因此，`VAL-002` 继续阻断，`VAL-003` 继续不得启动。

## Required Fix

1. 先修复本机 MiniQMT 登录可用性，使 `miniqmt.ensure_logged_in` 不再停在 `login_window_not_found`。
2. 继续排除 `xttrader connect=-1` 的环境阻断，直到 `session.warm` 能实际建立 owner-managed session。
3. 环境恢复后，由测试角色重新执行完整 `G3` 顺序：
   - `miniqmt.ensure_logged_in`
   - `session.warm`
   - `session.status`
   - `probe.connection`
   - `account.show`
   - `positions.list`
   - `orders.list`
   - `snapshot.l1`
4. 只有在新的 EvidencePack 证明 `G3` 只读链路成立后，才允许进入下一轮 review 判断是否解除 `blocked`。

## Release Decision

- Decision: blocked
- Test Failure Classification Carried Forward: `fail_env`
- Status Change From Previous Review: unchanged
- Explicit Statement: 本次 post-patch live rerun 没有改变既有 `VAL-002` 的 `blocked` 状态；它只提升了失败可诊断性，但结果仍然是 `fail_env`。
- Recommended next board status: `Blocked`
- Release Recommendation: 不放行，不进入 `VAL-003`

## Residual Risks

1. 当前只证明补丁后的错误暴露路径发生了变化，未证明真实 session owner 生命周期已经恢复。
2. 若后续环境恢复后仍出现 session candidate 抖动、owner 冲突或 `xttrader connect=-1` 间歇复现，仍需重新区分 `fail_env` 与 `fail_design`，不能沿用本次结论直接外推。
