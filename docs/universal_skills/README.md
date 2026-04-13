# 通用技能设计包

关联研究文档：[../research/UNIVERSAL_AGENT_DELIVERY_ROUTING_RESEARCH_20260330.md](../research/UNIVERSAL_AGENT_DELIVERY_ROUTING_RESEARCH_20260330.md)  
关联当前执行规范：[../EXECUTION_AND_ARTIFACT_STANDARD.md](../EXECUTION_AND_ARTIFACT_STANDARD.md)  
关联当前协作规范：[../WORKFLOW_AND_BOARD.md](../WORKFLOW_AND_BOARD.md)  
关联当前验收标准：[../ACCEPTANCE_STANDARD.md](../ACCEPTANCE_STANDARD.md)

## 目录说明

本目录用于沉淀“通用 Agent 交付技能套件”的设计草案，目标是为后续技能实现提供决策完整的设计输入，而不是直接替代当前仓库已生效规范。

本目录包含：

- [ADAPTIVE_DELIVERY_SUITE_DESIGN.md](./ADAPTIVE_DELIVERY_SUITE_DESIGN.md)
  - 套件总体设计、模式模型、路由规则、authority matrix、adapter contract
- [ADAPTIVE_DELIVERY_SUITE_MANUAL.md](./ADAPTIVE_DELIVERY_SUITE_MANUAL.md)
  - 技能使用手册、调用顺序、常见场景、反模式与 FAQ
- [ADAPTIVE_DELIVERY_SUITE_REVIEW_20260330.md](./ADAPTIVE_DELIVERY_SUITE_REVIEW_20260330.md)
  - 二轮深入复审、产品验收视角结论、插件化决策与后续优化方向
- [contracts/](./contracts/)
  - 通用 schema、authority matrix、release decision schema、adapter contract
- [examples/](./examples/)
  - 设计级 golden examples

## 套件范围

首版通用技能套件固定包含以下技能：

1. `workflow-router`
2. `acceptance-analysis`
3. `evidence-gate`
4. `mode-analyze-only`
5. `mode-fast-loop`
6. `mode-gated-change`
7. `mode-live-rollout`

## 使用边界

- 本目录定义通用抽象，不直接绑定当前仓库的 `TaskCard`、`ChangePack`、`EvidencePack`、`ReviewPack` 命名。
- 当前仓库专用工件只在 `adapter contract` 中出现，作为一种可选映射。
- 首版不定义运行时脚本，只定义技能职责、契约结构和例子。

## 当前仓库 adapter 落点

- 当前仓库对通用字段的正式绑定，见 [contracts/ADAPTER_CONTRACT.md](./contracts/ADAPTER_CONTRACT.md) 中的 `xtqmt-mcp` TaskCard/ChangePack adapter 映射。
- repo-local 的角色纪律、artifact chain 与 ledger 边界，仍以 [../../AGENTS.md](../../AGENTS.md)、[../EXECUTION_AND_ARTIFACT_STANDARD.md](../EXECUTION_AND_ARTIFACT_STANDARD.md)、[../WORKFLOW_AND_BOARD.md](../WORKFLOW_AND_BOARD.md) 为准。
- `controller-only` 与 `controller-with-delegation` 是当前仓库 specialized controller skill 的运行方式，不是本目录中的通用 `base_mode`。
- 外部看板 / `RunLedger`、`Board Export`、`Board Sync` 和 controller judgment 属于 repo-local control plane；通用 suite 只定义这些对象需要如何被 adapter 归类，不直接拥有这些对象。
- 若当前仓库某类 authority、runtime evidence 或 env evidence 还无法稳定映射，应在 repo adapter 文档中显式登记 gap，而不是在通用抽象层假装已经闭合。

## Pluginization Status

- 当前决策：`No-Go`
- 当前分发形态：`repo-local skills + contracts + examples`
- 重新评估前提：
  - 至少一个真实 repo adapter 已稳定落地
  - router -> acceptance -> mode -> gate 链路已经在多个项目上复用
  - Codex CLI 的 plugin surface 已公开且稳定
  - 插件 manifest、入口、版本兼容与 authority 边界已明确
