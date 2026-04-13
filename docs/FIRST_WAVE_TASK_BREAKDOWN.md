# 首轮开发前任务拆分

关联设计规范：[MCP_DESIGN.md](./MCP_DESIGN.md)  
关联设计审查：[DESIGN_REVIEW_20260327.md](./DESIGN_REVIEW_20260327.md)  
执行与工件规范：[EXECUTION_AND_ARTIFACT_STANDARD.md](./EXECUTION_AND_ARTIFACT_STANDARD.md)  
协作与看板规则：[WORKFLOW_AND_BOARD.md](./WORKFLOW_AND_BOARD.md)  
验收标准：[ACCEPTANCE_STANDARD.md](./ACCEPTANCE_STANDARD.md)

## 目的

本文把 [MCP_DESIGN.md](./MCP_DESIGN.md) 中已经确认的 `Current Gaps` 和 [DESIGN_REVIEW_20260327.md](./DESIGN_REVIEW_20260327.md) 中已经确认的优先级，拆成可以直接进入外部看板的首轮正式任务卡。

本文不是新的 spec，也不替代正式看板；它承担三个职责：

1. 固化首轮任务编号、边界、依赖关系和验收 gate。
2. 让开发前就有稳定的 `TaskCard` 与 `ChangePack` 路径。
3. 约束首轮开发不要再回到“直接实现整个 spec”的粗粒度推进方式。

## 首轮任务总表

| Task ID | Title | Type | Priority | Start Role | Initial Status | Acceptance Gate | Depends On | TaskCard | ChangePack |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `PREP-001` | 首轮任务卡与工件骨架建立 | `governance` | `P0` | `dev` | `Ready` | `G0` | - | [PREP-001](./task_cards/PREP-001.md) | [PREP-001](./change_packages/PREP-001.md) |
| `TG-004` | 交易 session owner 与单 trader 生命周期收口 | `refactor` | `P0` | `dev` | `Ready` | `G3` | `PREP-001` | [TG-004](./task_cards/TG-004.md) | [TG-004](./change_packages/TG-004.md) |
| `TG-002` | session/account 单账户主契约统一 | `refactor` | `P0` | `dev` | `Ready` | `G3` | `TG-004` | [TG-002](./task_cards/TG-002.md) | [TG-002](./change_packages/TG-002.md) |
| `TG-003` | 只读 preflight 与写权限 preflight 拆层 | `refactor` | `P0` | `dev` | `Ready` | `G3` | `TG-002` | [TG-003](./task_cards/TG-003.md) | [TG-003](./change_packages/TG-003.md) |
| `TG-001` | `order.place` 唯一受控写路径收口 | `refactor` | `P0` | `dev` | `Ready` | `G4` | `TG-004`, `TG-002`, `TG-003` | [TG-001](./task_cards/TG-001.md) | [TG-001](./change_packages/TG-001.md) |
| `DG-001` | `xtdata.status` 分层 readiness 与 runtime endpoint | `refactor` | `P0` | `dev` | `Ready` | `G2` | `PREP-001` | [DG-001](./task_cards/DG-001.md) | [DG-001](./change_packages/DG-001.md) |
| `DG-002` | `xtdata://leases/active` 与 subscription lease 健康输出 | `feature` | `P1` | `dev` | `Ready` | `G2` | `DG-001` | [DG-002](./task_cards/DG-002.md) | [DG-002](./change_packages/DG-002.md) |
| `OPS-001` | fake 状态与真实证据隔离 | `refactor` | `P0` | `dev` | `Ready` | `G0` | `PREP-001` | [OPS-001](./task_cards/OPS-001.md) | [OPS-001](./change_packages/OPS-001.md) |
| `VAL-001` | Data Gateway 首轮只读 live smoke | `investigation` | `P1` | `test` | `Ready` | `G2` | `DG-001`, `DG-002`, `OPS-001` | [VAL-001](./task_cards/VAL-001.md) | [VAL-001](./change_packages/VAL-001.md) |
| `VAL-002` | Trade Gateway 首轮只读 smoke | `investigation` | `P1` | `test` | `Ready` | `G3` | `TG-004`, `TG-002`, `TG-003`, `OPS-001` | [VAL-002](./task_cards/VAL-002.md) | [VAL-002](./change_packages/VAL-002.md) |
| `VAL-003` | `order.place` 受控最小真单验证 | `investigation` | `P1` | `test` | `Ready` | `G4` | `TG-001`, `VAL-002` | [VAL-003](./task_cards/VAL-003.md) | [VAL-003](./change_packages/VAL-003.md) |

## 推荐执行顺序

### Wave 0: 工件落地

1. `PREP-001`

退出条件：

- 首轮卡片、`ChangePack` 骨架和工件目录均已存在。
- 外部看板可以直接按这些 `Task ID` 建卡。

### Wave 1: Data Lane

1. `DG-001`
2. `DG-002`
3. `VAL-001`

退出条件：

- `xtdata.status` 已经表达 configured endpoint 与 resolved runtime endpoint。
- `xtdata://leases/active` 已能表达 lease 健康，而不是只有句柄残留。
- `VAL-001` 已产出正式 `EvidencePack`。

### Wave 2: Trade Lane

1. `TG-004`
2. `TG-002`
3. `TG-003`
4. `TG-001`
5. `VAL-002`
6. `VAL-003`

退出条件：

- 交易 session owner、账户上下文、只读与写权限门禁已统一。
- `order.place` 已成为唯一受控写路径。
- `VAL-002` 和 `VAL-003` 已完成对应 gate 的正式证据沉淀。

### Shared Ops Lane

1. `OPS-001`

退出条件：

- fake / test 状态不会再污染正式实例证据。
- `G0` 与 `G1` 验收可以基于真实运行态判断。

## 并行规则

- `Data Lane` 与 `Trade Lane` 只有在写集明确不重叠时才允许并行。
- `TG-001` 与 `VAL-003` 默认串行，不允许和其他高副作用写路径任务并发推进。
- `OPS-001` 应在任一正式 smoke 前落地，否则验证结论不具备证据可信度。
- `VAL-*` 任务默认由 `test` 角色起手；若为了补齐观测脚本或验收 harness 需要代码改动，也必须继续维护对应 `ChangePack`，不能只留口头说明。

## 开发前必备工件

首轮开发前，以下路径已经被预留：

- `docs/task_cards/`
- `docs/change_packages/`
- `docs/evidence_packs/`
- `docs/env_snapshots/`

本轮只预建 `TaskCard` 与 `ChangePack` 骨架。正式测试或高风险执行时，继续按下列模式创建：

- `docs/evidence_packs/<TaskID>-<Role>-<YYYYMMDDHHMM>.md`
- `docs/env_snapshots/<TaskID>-<YYYYMMDDHHMM>.md`

## 看板建卡要求

外部看板建卡时，至少同步以下字段：

1. `Task ID`
2. `Title`
3. `Priority`
4. `Owner Role`
5. `Current Role`
6. `Status`
7. `Acceptance Gate`
8. `Repo Spec Link`
9. `Change Package Link`
10. `Evidence Pack Link`
11. `Verifier`
12. `Merge Owner`

建卡时 `Repo Spec Link` 应优先回链到 [MCP_DESIGN.md](./MCP_DESIGN.md) 与对应 `TaskCard`；`Change Package Link` 则直接回链到本文所列 skeleton。

## 开发启动条件

任一功能卡进入 `In Dev` 前，至少满足以下条件：

1. 当前卡片 `TaskCard` 与 `ChangePack` 已存在。
2. 依赖卡片若未关闭，主控已明确本次开发不会越过依赖边界。
3. 需要的 `Acceptance Gate` 已经在 [ACCEPTANCE_STANDARD.md](./ACCEPTANCE_STANDARD.md) 中可执行。
4. 需要的角色交付格式已经在 [TEMPLATES.md](./TEMPLATES.md) 中可复用。

如果不满足以上条件，应停留在 `Ready` 或回退到任务拆分阶段，而不是直接编码。
