# xtqmt-mcp 公开仓 Agent 协作指南

本文件适用于公开源码仓 `D:\xtquant-mcp\repo`。它约束 agent 在公开仓内读写代码、文档、测试和 release 文件时的行为。实际运行环境总目录 `D:\xtquant-mcp` 另有本机级 `AGENTS.md` 和 `docs/RUNTIME_ENVIRONMENT_STANDARD.md`。

## 基本规则

1. 所有面向用户的回复和项目文档使用中文。
2. 先理解相关代码、配置和文档，再修改。
3. 只改与当前任务直接相关的文件，避免顺手重构。
4. 涉及功能边界、配置、启动流程、验收口径变化时，必须同步更新公开文档。
5. 不提交真实账号、凭据、MiniQMT 路径、userdata、交易证据、本机日志、截图、SQLite、运行态 latest 文件或私有归档内容。
6. 发布、改远端 `main`、移动 tag、创建 GitHub Release 或修改仓库可见性，必须有用户明确授权。

## 仓库结构

| 路径 | 职责 |
| --- | --- |
| `xtqmt_mcp/` | MCP 服务实现、配置模型、Data Gateway、Trade Gateway、MiniQMT 登录和交易门禁 |
| `configs/` | 公开样例配置，不写真实账户或真实路径 |
| `scripts/` | 启动、wake、bundle 校验、flow-smoke 和辅助脚本 |
| `tests/` | 单元测试、契约测试和公开样例验证 |
| `docs/` | 公开设计、运行手册、验收标准、当前状态和 release 文档 |
| `docs/release/` | 开源整理、归档、冻结和验证记录 |

## 文档入口

- 项目入口：`README.md`
- 运行手册：`docs/OPERATIONS_RUNBOOK.md`
- MCP 设计：`docs/MCP_DESIGN.md`
- 验收标准：`docs/ACCEPTANCE_STANDARD.md`
- 当前状态：`docs/CURRENT_STATUS.md`
- 发布记录：`docs/release/`

## 隐私和公开边界

公开仓只允许保留：

1. 源码和测试。
2. 脱敏公开文档。
3. 样例配置。
4. 合成账户，例如 `ACC001`。
5. 合成证券代码，例如 `SAMPLE001.SH`。
6. 示例路径，例如 `C:\xtquant-mcp-example\...`。

公开仓禁止保留：

1. 真实账户、真实资金、真实持仓、真实委托和真实成交。
2. 真实 broker 回执、订单号和现场交易证据。
3. 本机真实路径、MiniQMT userdata、截图、SQLite、日志和缓存。
4. 内部计划、内部规格、现场 task card、review pack 和 evidence pack 原文。
5. `.tmp/`、`instance/`、`output/`、`state/`、`.pytest_cache/` 等运行态目录。

## 配置规则

1. `configs/*.example.yaml` 只能包含示例路径和占位账户。
2. 真实配置应放在本机运行环境私有目录，例如 `D:\xtquant-mcp\instance\prod\config\`，不得提交。
3. 端口默认可以为 `0`，由运行时解析；不得把某个本机端口写成协议常量。
4. `flow_smoke` 配置只能代表非生产验证，不代表真实交易可用。

## Data Gateway 口径

1. `gateway.health` 是 Data Gateway readiness 的主要入口。
2. TCP 端口可连不等于 gateway ready。
3. 交易日解析不能静默把非交易日映射到前一交易日。
4. qlib 同步必须通过 manifest 和 acceptance 结果闭环。
5. 边界残差和真实失败要在 payload 中区分。

## Trade Gateway 口径

1. 真实写路径只能通过正式 gateway 工具面执行。
2. `order.place` 和 `order.cancel` 必须经过 kill switch、session、probe、风险、交易时段和审计门禁。
3. `session.warm`、`session.status`、`probe.connection` 是写路径前置诊断入口。
4. 不允许手工编辑 latest state 文件制造 ready 状态。
5. 不允许把 `flow_smoke` 结果解释为真实 broker 成交。

## 验证要求

普通代码或配置变更至少运行：

```bash
python -m compileall xtqmt_mcp scripts
python -m unittest discover -s tests -v
git diff --check
```

文档变更至少运行：

```bash
git diff --check -- <changed-docs>
rg -n -I "<LOCAL_PRIVATE_PATH>|<REAL_ACCOUNT>|<CREDENTIAL_PATTERN>" <changed-docs>
```

如果本机环境无法运行完整测试，必须在交付说明中写明原因，并给出已经执行的最小验证。

## Git 操作要求

1. 不使用 `git add .` 吞入无关文件。
2. 提交前查看 `git status --short --branch` 和 `git diff --cached --name-status`。
3. 不回滚用户已有改动，除非用户明确要求。
4. 不删除或重写远端历史，除非用户明确授权。
5. 修改 release tag 或 GitHub Release 后，必须重新核对远端 tag、Release 附件和 SHA256。

## 交付说明

交付时说明：

1. 修改了哪些文件。
2. 为什么修改。
3. 执行了哪些验证。
4. 是否影响公开仓、运行环境、release tag 或 GitHub Release。
5. 是否存在遗留风险或未处理的本机私有目录。
