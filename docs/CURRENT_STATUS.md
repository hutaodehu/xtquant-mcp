# 当前状态

本文记录 `xtqmt-mcp` 公开候选版本的状态。真实运行证据、账户、成交、持仓、资金、截图和本机路径不随仓库分发。

## 版本状态

- 候选版本：`v2.0.0-alpha.1`
- 许可证：MIT
- 发布形态：可运行样例项目
- 公开历史策略：使用脱敏公开历史或新公开仓，不复用含历史证据的旧提交链。
- 远端发布状态：未推送，未创建远端 tag，未发布 GitHub release。

## 已保留能力

1. `xtqmtDataGateway`：提供行情、日历、完整性计划、批量同步任务、artifact manifest 和 qlib 验收检查等工具面。
2. `xtqmtTradeGateway`：提供会话、探针、账户、订单、成交和写路径门禁等工具面。
3. MiniQMT 登录辅助：提供桌面观察、登录窗口识别、凭据读取接口和 readiness 语义。
4. 配置样例：`configs/*.example.yaml` 和 `configs/trade_gateway.flow_smoke.yaml` 只保留示例值。
5. 测试：保留 deterministic 单元测试和不触发真实交易的 flow-smoke 契约测试。

## 不随仓分发

- 真实 MiniQMT 安装路径、用户目录和账户号。
- 真实 broker 回执、委托、成交、持仓和资金。
- 真实 EnvSnapshot、EvidencePack、ReviewPack、controller judgment 和运行态 latest 文件。
- `.tmp/`、`instance/`、`output/`、`state/`、`.pytest_cache/` 等本地运行态。

## 当前限制

1. 真实 xtquant/MiniQMT 依赖需要使用者在本机自行安装，并通过配置或环境变量注入路径。
2. 写路径默认必须通过 dry-run、flow-smoke、kill switch、交易时段和权限门禁。
3. 公开仓只说明接口语义和操作顺序，不提供任何真实交易证据。
