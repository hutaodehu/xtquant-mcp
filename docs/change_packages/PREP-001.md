# ChangePack

Task ID: PREP-001
Role: dev
Date: reserved-pre-dev
Branch/Commit: TBD
Stage: skeleton

## Goal

建立首轮开发前的任务卡、`ChangePack` 和工件目录骨架。

## Implemented

1. 当前仅预留工件路径和边界说明。
2. 真实实现内容需在本卡进入 `In Dev` 后补写。

## Not Implemented

1. 不包含任何 gateway 功能改动。
2. 不包含 live smoke、独立测试或审查结论。

## Files Expected to Change

- `docs/FIRST_WAVE_TASK_BREAKDOWN.md`
- `docs/task_cards/*.md`
- `docs/change_packages/*.md`
- `docs/evidence_packs/README.md`
- `docs/env_snapshots/README.md`

## Self-check

1. 确认所有首轮 `Task ID` 均有稳定文档路径。
2. 确认入口文档已能回链到首轮拆分文档。

## Known Risks

1. 若后续任务边界重排，本文件需要同步维护依赖与范围。
2. 若外部看板字段另行变更，需要同步调整卡片头部字段。

## Needs Independent Test

1. review 需要确认拆分粒度与 `MCP_DESIGN.md` 的 gap 对齐。
2. 主控需要确认外部看板字段能直接映射到卡片内容。
