# 协作模板

本文件提供开发、测试、审查和验收记录的统一模板。外部工具未确定前，可直接复制这些模板到任务卡、文档或评论中使用。

与 [EXECUTION_AND_ARTIFACT_STANDARD.md](./EXECUTION_AND_ARTIFACT_STANDARD.md) 的关系如下：

- 本文件提供模板。
- 执行与工件规范定义这些模板分别承担什么职责。
- 看板、ChangePack、EvidencePack、EnvSnapshot 默认应组合使用。

## 任务卡模板

```markdown
Task ID: MCP-XXX
Title: <简明标题>
Type: feature | bug | refactor | governance | investigation
Priority: P0 | P1 | P2 | P3
Owner Role: dev | test | review
Current Role: dev | test | review
Status: Backlog | Ready | In Dev | In Self-Test | In Independent Test | In Review | Blocked | Accepted
Blocking Reason: design_blocked | env_blocked | broker_blocked | connect_gate_failed | xtdata_blocked | session_blocked | docs_blocked | <留空>
Repo Spec Link: <仓库文档链接>
Acceptance Gate: G0 | G1 | G2 | G3 | G4
Change Package Link: <ChangePack 路径>
Evidence Pack Link: <最近一次正式 EvidencePack 路径>
Review Pack Link: <最近一次正式 ReviewPack 路径或留空>
Env Snapshot Link: <环境快照路径；普通任务可留空>
Verifier: <独立测试或审查使用的主要验证器>
Merge Owner: <最终合并或收口责任人>
Review Result: pending | pass | needs_fix | blocked
Lane: data | trade | ops | validation
Risk Class: low | medium | high
Write Scope: <用于并行冲突判断的模块标签，逗号分隔>
Automation Policy: auto_safe | manual_gate
Execution Class: dev_only | test_only | review_only | handoff_required
Controller Test Policy: none | delegated_test_required | controller_direct_required
Execution Packet Side: <仅 controller_direct_required 时必填；否则留空>
Execution Packet Symbol: <仅 controller_direct_required 时必填；否则留空>
Execution Packet Qty: <仅 controller_direct_required 时必填；否则留空>
Execution Packet Price Mode: <仅 controller_direct_required 时必填；否则留空>
Execution Packet Cancel Timeout: <仅 controller_direct_required 时必填；否则留空>
Trade Config Path: <可选；controller_direct_required 时可覆盖默认路径>
Data Config Path: <可选；controller_direct_required 时可覆盖默认路径>
Trade Health URL: <可选；controller_direct_required 时可覆盖默认路径>
Data Health URL: <可选；controller_direct_required 时可覆盖默认路径>

## Goal

<本任务要解决什么问题>

## Scope In

1. <明确包含的范围 1>
2. <明确包含的范围 2>

## Scope Out

1. <明确排除的范围 1>
2. <明确排除的范围 2>

## Done Means

<任务完成的判断条件>

## Notes

<补充说明>
```

## ChangePack 模板

```markdown
# ChangePack

Task ID: <任务编号>
Role: dev
Date: <时间>
Branch/Commit: <版本标识>

## Goal

<本任务要达成的主目标>

## Implemented

1. <本次已完成的实现 1>
2. <本次已完成的实现 2>

## Not Implemented

1. <明确未实现的范围 1>
2. <明确保留到后续卡片的范围 2>

## Files Changed

- <文件路径 1>
- <文件路径 2>

## Self-check

1. <开发自测步骤 1>
2. <开发自测步骤 2>

## Known Risks

1. <已知风险 1>
2. <已知风险 2>

## Needs Independent Test

1. <独立测试点 1>
2. <独立测试点 2>
```

## 开发自测记录模板

```markdown
# 开发自测记录

Task ID: <任务编号>
Role: dev
Date: <时间>
Branch/Commit: <版本标识>
Change Package Link: <ChangePack 路径>

## 变更摘要

<本次实现了什么>

## 自测范围

1. <步骤 1>
2. <步骤 2>

## 自测结果

- Result: pass | partial | blocked
- Summary: <一句话总结>

## 风险与未覆盖项

1. <风险点 1>
2. <未覆盖项 2>

## Evidence

- <artifact 路径或链接>
```

## EvidencePack 模板

```markdown
# EvidencePack

Task ID: <任务编号>
Role: dev | test | review
Date: <时间>
Acceptance Gate: G0 | G1 | G2 | G3 | G4 | N/A
Conclusion: pass | partial | blocked | fail_env | fail_design | pending
Executor: <默认留空；主控亲测时写 controller direct test execution>
Authorization Basis: <默认留空；主控亲测时必填>
Controller Judgment Link: <默认留空；主控亲测时必填>
Raw Runtime Capture: <默认留空；主控亲测时必填>
Gateway Recovery Output Link: <默认留空；主控亲测时必填>

## Env Snapshot

- Link: <EnvSnapshot 路径或留空>
- Host: <主机>
- Shell: <shell>
- Config: <配置路径>

## Commands

1. <命令 1>
2. <命令 2>

## Raw Results

- Health: <摘要>
- MCP Calls: <摘要>
- Errors: <错误码或留空>

## Session Plan Consistency

- Gateway Owner Session: <session.warm / session.status 暴露的 owner session；没有则留空>
- Native Probe Session Plan: <宿主侧 direct probe 实际覆盖的 session 列表>
- Write-Path Session Plan: <Round 3 写路径实际使用或预期使用的 session 列表>
- Same-Call Connect Gate Session: <若执行过 order.place，则写 connect_gate 里实际出现的 session；否则留空>
- Derived Fallback Enabled: yes | no
- Probe/Write Same-Plan Verdict: yes | no
- Note: <若为 no，必须说明为什么该 packet 不能把 probe pass 外推成 write readiness>

## Artifact Refs

- <trace_id>
- <artifact 路径>
- <日志路径>

## Verdict

<一句话结论>
```

## EnvSnapshot 模板

```markdown
# EnvSnapshot

Task ID: <任务编号>
Date: <时间>
Role: dev | test | review
Executor: <默认留空；主控亲测时写 controller direct test execution>
Controller Judgment Link: <默认留空；主控亲测时必填>
Raw Runtime Capture: <默认留空；主控亲测时必填>
Gateway Recovery Output Link: <默认留空；主控亲测时必填>

## Host

- OS: <系统>
- Hostname: <主机名>
- Shell: <shell>

## Runtime

- Python: <版本或路径>
- Gateway Config: <配置路径>
- Working Dir: <目录>

## Port and Permission State

- xtdata port: <状态>
- trade gateway port: <状态>
- data gateway port: <状态>
- Permission Notes: <权限说明>

## Session Plan

- Gateway Owner Session: <owner session 或留空>
- Native Probe Session Plan: <session 列表或留空>
- Write-Path Session Plan: <session 列表或留空>
- Same-Call Connect Gate Session: <session 或留空>
- Derived Fallback Enabled: yes | no
- Probe/Write Same-Plan Verdict: yes | no

## Time Window

- Market Window: <开/闭市信息>
- Observation Time: <时间>
```

## 独立测试记录模板

```markdown
# 独立测试记录

Task ID: <任务编号>
Role: test
Date: <时间>
Acceptance Gate: G0 | G1 | G2 | G3 | G4
Config Path: <配置路径>
Change Package Link: <ChangePack 路径>
Evidence Pack Link: <EvidencePack 路径>

## 执行步骤

1. <步骤 1>
2. <步骤 2>

## 结果

- Result: pass | partial | blocked | fail_env | fail_design
- Failure Class: <若失败，写环境或设计分类>
- Summary: <一句话总结>

## Observations

1. <观察 1>
2. <观察 2>

## Evidence

- <artifact 路径>
- <日志链接>
```

## ReviewPack 模板

```markdown
# ReviewPack

Task ID: <任务编号>
Role: review
Date: <时间>
Change Package Link: <ChangePack 路径>
Evidence Pack Link: <EvidencePack 路径>
Env Snapshot Link: <EnvSnapshot 路径或留空>

## Findings

1. <问题 1>
2. <问题 2>

## Severity

- highest: low | medium | high | critical

## Impact

<影响范围>

## Required Fix

1. <必须修复项 1>
2. <必须修复项 2>

## Release Decision

- Decision: pass | needs_fix | blocked
- Summary: <一句话放行意见>

## Controller Direct Test Check

- Executor: <若 EvidencePack/EnvSnapshot 为主控亲测，则写 controller direct test execution；否则写 N/A>
- Metadata Complete: yes | no
- Session Plan Consistent: yes | no | N/A
- Review Note: <说明 review 只基于 formal test evidence，不因执行者是 controller 放宽 gate>

## State Suggestion

- Target Status: In Dev | In Independent Test | In Review | Blocked | Accepted
- Reason: <状态建议依据>
```

## 主控派单模板

```markdown
# 主控派单

Task ID: <任务编号>
Controller Mode: controller-only | controller-with-delegation
Delegation Model Floor: gpt-5.4 / high
Target Role: dev | test | review
Spec Link: <规范链接>
Change Package Link: <ChangePack 路径或预留路径>
Evidence Pack Link: <EvidencePack 路径或预留路径>

## In Scope

1. <本次明确要求完成的范围 1>
2. <本次明确要求完成的范围 2>

## Out of Scope

1. <本次禁止顺手扩散的范围 1>
2. <本次禁止顺手扩散的范围 2>

## Expected Outputs

1. <必须交付的工件 1>
2. <必须交付的工件 2>
```

## 主控账本同步清单模板

```markdown
# 主控账本同步清单

Sync Basis: existing role-owned artifacts only
Target Ledger: <外部看板 / RunLedger 名称>

## Updates

1. Task ID: <任务编号>
   - Status: <目标状态>
   - Owner Role: <目标 owner role>
   - Current Role: <目标 current role>
   - Blocking Reason: <若有>
   - Review Result: <pending | pass | needs_fix | blocked>
   - Change Package Link: <路径>
   - Evidence Pack Link: <路径>
   - Review Pack Link: <路径>
   - Env Snapshot Link: <路径或留空>
   - Reason: <同步依据>
```

最小 JSON contract 与样例见：

- `.agents/skills/spec-task-harness/references/board-json-contract.md`
- `.agents/skills/spec-task-harness/references/board-sync-contract.md`
- `.agents/skills/spec-task-harness/examples/board_export.sample.json`
- `.agents/skills/spec-task-harness/examples/board_sync.sample.json`

## 主控模式触发词模板

### `controller-only`

```text
Use $spec-task-harness, controller-only. Reconcile first, then give the next safe action. Do not do role work directly.
```

```text
用 $spec-task-harness，controller-only。先 reconcile 当前真实状态，再给 next safe action。主控不要自己干 dev/test/review 的活。
```

适用场景：

- 先对账，再判断从哪里恢复
- 只需要 closeout / validation preparation / next safe action
- 只需要生成主控派单文本，不需要当场拉起子代理

### `controller-with-delegation`

```text
Use $spec-task-harness, controller-with-delegation. Reconcile first, then dispatch the next safe bounded step to child agents. The controller must not substitute for dev, test, or review.
```

```text
用 $spec-task-harness，controller-with-delegation。先 reconcile 当前真实状态，再把下一步边界清晰的任务派给子代理。主控不得代做 dev/test/review 的工件。
```

适用场景：

- 用户已经明确授权多 agent 编排
- 主控要基于当前真实状态直接派 `dev`、`test`、`review` 子代理
- 主控后续只负责收集工件、再 reconcile，不亲自代做角色工作
- 子代理模型必须不低于 `gpt-5.4`，且 `reasoning_effort` 必须不低于 `high`

## 主控亲测入口模板

当且仅当任务卡满足 `Controller Test Policy: controller_direct_required` 且仍处于 `manual_gate`，主控才可直接执行：

```powershell
pwsh -File scripts\run_controller_direct_test.ps1 -TaskId VAL-003
```

该入口不是第三种主控模式，也不会自动放行；它只负责在显式人工触发下生成正式 `Role: test` 工件，并把独立审查留给后续 `ReviewPack`。

## 审查回流模板

```markdown
# 审查回流

Task ID: <任务编号>
Role: review
Date: <时间>

## Findings

1. <问题 1>
2. <问题 2>

## Required Fix

1. <必须修复项 1>
2. <必须修复项 2>

## State Rollback

- Target Status: In Dev | In Independent Test | Blocked
- Reason: <回退原因>
```

## 验收证据模板

```markdown
# 验收证据

Task ID: <任务编号>
Date: <时间>
Executor Role: test | review
Acceptance Gate: G0 | G1 | G2 | G3 | G4
Conclusion: pass | partial | blocked | fail_env | fail_design

## Environment

- Env Snapshot Link: <EnvSnapshot 路径或留空>
- Host: <主机>
- Runtime: <python / gateway / MiniQMT 信息>
- Config: <配置路径>

## Raw Results

- Health: <结果摘要>
- MCP Calls: <工具调用摘要>
- Errors: <错误码或留空>

## Evidence Paths

- <trace_id>
- <artifact 路径>
- <日志路径>
- <截图路径，可选>

## Final Note

<最终说明>
```
