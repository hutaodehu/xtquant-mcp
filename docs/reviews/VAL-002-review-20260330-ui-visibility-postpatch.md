# 审查结论

Task ID: VAL-002
Role: review
Date: 2026-03-30T11:05:00+08:00
Change Package Link: D:\xtquant-mcp\repo\docs\change_packages\TG-003.md
Evidence Pack Link: D:\xtquant-mcp\repo\docs\evidence_packs\VAL-002-test-20260330-ui-visibility-postpatch.md
Env Snapshot Link: D:\xtquant-mcp\repo\docs\env_snapshots\VAL-002-test-20260330-ui-visibility-postpatch.md
Previous Review Link: D:\xtquant-mcp\repo\docs\reviews\VAL-002-review-202603300701.md
Prior Baseline Evidence Link: D:\xtquant-mcp\repo\docs\evidence_packs\VAL-002-test-20260330-ui-visibility.md
Supersedes: D:\xtquant-mcp\repo\docs\reviews\VAL-002-review-202603300701.md

## Findings

1. High: 本次 follow-up evidence 只支持一个有边界的 `partial`，不能解除 `VAL-002` 的整体 `blocked` 状态。
   - 新 EvidencePack 证明 `TG-003` 已修复“observation 被压成空集合”的问题：fresh report 现在包含 `host_window_fallback_used=true`、非空 `host_visible_windows`、非空 `window_classifications`、非空 `window_titles`、以及 `selected_main_title='8883884325 - 国金证券QMT交易端 2.0.8.300'`。
   - 但这次验证并不是完整 `G3` rerun。EvidencePack 明确写明未执行 `session.warm`、`session.status`、`probe.connection`、`account.show`、`positions.list`、`orders.list`、`snapshot.l1` 链路。
   - 任务卡当前仍是 `Status: Blocked`、`Blocking Reason: env_blocked`，且上一轮正式 review 已把 `xttrader connect=-1` / `miniqmt_not_logged_in` 识别为环境硬阻断。当前 follow-up evidence 没有提供足以推翻该阻断的新增 live G3 证据。

2. Medium: 这次 patch 的有效改进仅限于“空 observation 修复为宿主层可见窗口证据”，截图与完整可复核 UI artifact 仍未关闭。
   - `TG-003` 的目标之一是截图捕获要么产出路径，要么在 evidence 中明确报告尝试和失败原因。
   - 新 EvidencePack 中 `screenshot_path=''`、`screenshot_capture_attempted=false`、`screenshot_capture_error='imagegrab_unavailable'`。这说明当前结果是“失败原因被暴露出来了”，不是“截图证据已经恢复”。
   - 因此这次结果如果要用仓库词汇描述，必须明确写成：`partial`，且只是修复 empty observations；screenshot/full G3 remain open。

3. Medium: 本次证据支持“设计方向有效，但仍未形成放行证据”，不能把 bounded improvement 误写成 `pass` 或“已修复”。
   - 与 prior baseline evidence 相比，旧报告是 `window_titles=[]`、`window_classifications=[]`、`selected_*=''`，而当前报告已能反映宿主层存在主窗口并给出标题与类名。
   - 这与 `TG-003` ChangePack 的最小安全退化路径一致，说明补丁在可诊断性上是成立的。
   - 但 review gate 关心的是 release decision。当前正确结论仍然是 `blocked`，并继续携带测试侧的 bounded `partial`，而不是转成任务级 `pass` 或解除 `env_blocked`。

## Impact

本次 follow-up review 确认：

1. `TG-003` 在真实主机上达成了有限目标，修复了“MiniQMT 主窗口存在但 probe 输出空 observation”的证据缺口。
2. 当前 improvement 没有把 UI visibility 证据提升为完整可验收链路；截图 artifact 仍缺失，完整 `G3` 只读链路仍未重跑。
3. `VAL-002` 的总体状态不变，仍然是 `blocked`。这次 bounded improvement 不改变先前关于 `xttrader connect=-1`、`miniqmt_not_logged_in` 和 `env_blocked` 的整体阻断判断。

## Required Fix

1. 若要继续关闭 UI visibility 缺口，需要补齐截图能力或在下一轮正式链路中稳定产出可复核图像 artifact，而不是只保留 `imagegrab_unavailable` 失败记录。
2. 环境恢复后必须重新执行完整 `G3` 顺序：
   - `miniqmt.ensure_logged_in`
   - `session.warm`
   - `session.status`
   - `probe.connection`
   - `account.show`
   - `positions.list`
   - `orders.list`
   - `snapshot.l1`
3. 只有在新的 EvidencePack 同时证明：
   - UI visibility 证据稳定可追溯，
   - screenshot 或等价可复核 artifact 闭环成立，
   - 完整 `G3` 只读链路不再被 `xttrader connect=-1` / `session_not_ready` 阻断，
   才能重新评估是否解除 `VAL-002` 的 `blocked` 状态。

## Release Decision

- Decision: blocked
- Bounded Evidence Conclusion Carried Forward: `partial`
- Status Change From Previous Review: unchanged
- Explicit Statement: 本次 bounded improvement 不改变 `VAL-002` 的整体 `blocked` 状态。它只修复了 empty observations，并未关闭 screenshot 缺口，也未完成完整 `G3` rerun。
- Recommended next board status: `Blocked`
- Blocking Reason: `env_blocked`
- Release Recommendation: 不放行，不进入 `VAL-003`

## Residual Risks

1. 当前 host-visible fallback 只能证明宿主层看到了顶层窗口，不能单独证明控件树可操作、登录态可信或交易只读链路可用。
2. 如果后续只看见这次 `partial` 改进而忽略 screenshot 与完整 `G3` 缺口，controller 容易误把“诊断改善”当成“阻断解除”。
3. 即使 UI visibility 证据继续改善，只要 `xttrader connect=-1` 或 `session_not_ready` 仍存在，`VAL-002` 依旧应保持 `blocked`。
