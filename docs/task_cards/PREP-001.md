Task ID: PREP-001
Title: 首轮任务卡与工件骨架建立
Type: governance
Priority: P0
Owner Role: dev
Current Role: dev
Status: Ready
Blocking Reason:
Repo Spec Link: [MCP_DESIGN.md](../MCP_DESIGN.md)
Acceptance Gate: G0
Change Package Link: [PREP-001.md](../change_packages/PREP-001.md)
Evidence Pack Link: `docs/evidence_packs/PREP-001-<role>-<YYYYMMDDHHMM>.md`，见 [evidence_packs/README.md](../evidence_packs/README.md)
Review Pack Link:
Env Snapshot Link: N/A
Verifier: 主控文档核对 + review
Merge Owner: 主控
Review Result: pending
Depends On: -
Lane: ops
Risk Class: low
Write Scope: docs.task_governance,docs.templates
Automation Policy: auto_safe
Execution Class: dev_only

## Goal

把首轮 spec 缺口拆成正式任务卡，并预建后续开发、测试、审查所需的稳定工件路径。

## Scope In

1. 建立首轮任务拆分文档与正式 `TaskCard`。
2. 为每张首轮卡片预建 `ChangePack` skeleton。
3. 建立 `docs/task_cards`、`docs/change_packages`、`docs/evidence_packs`、`docs/env_snapshots` 的目录约定。

## Scope Out

1. 不修改任何 Trade Gateway 或 Data Gateway 功能实现。
2. 不执行 live smoke 或真实写路径验证。

## Done Means

`FIRST_WAVE_TASK_BREAKDOWN.md`、首轮 `TaskCard` 和对应 `ChangePack` 均已存在，外部看板可以直接按这些 `Task ID` 建卡并进入开发排期。

## Notes

本卡只负责把开发前工件准备好，不负责实现 spec gap。
