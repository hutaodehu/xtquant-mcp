# xtqmt-mcp 运行手册

本文是公开仓的运行手册，面向希望在自己机器上部署 `xtqmtDataGateway` 与 `xtqmtTradeGateway` 的使用者。所有路径、账号、端口和证券代码均为示例；真实 MiniQMT 路径、账户、凭据、运行态和交易证据必须保存在本机私有配置或私有归档中，不得提交到公开仓。

## 仓库模块地图

| 路径 | 用途 | 是否需要私有配置 |
| --- | --- | --- |
| `xtqmt_mcp/` | MCP 服务实现、配置模型、数据同步运行时、交易门禁和订单/成交真相接口 | 否，源码可公开 |
| `xtqmt_mcp/data_gateway/` | Data Gateway：交易日、板块、行情、批量同步、qlib 验收 | 需要本机 xtquant 与 qlib 数据目录 |
| `xtqmt_mcp/trade_gateway/` | Trade Gateway：会话、账户、订单、成交、写路径门禁 | 需要本机 MiniQMT、账户和 userdata |
| `xtqmt_mcp/miniqmt_login/` | MiniQMT 登录探针、窗口识别和凭据读取 | 需要本机登录环境 |
| `configs/` | 公开样例配置 | 使用前复制到私有位置并填真实值 |
| `scripts/` | 启动、wake、bundle 校验、flow-smoke 与辅助脚本 | 部分脚本需要 PowerShell 7 |
| `tests/` | 不依赖真实交易的单元测试和契约测试 | 否 |
| `docs/release/` | 开源整理、归档、冻结和验证记录 | 否 |

## 依赖边界

### 必需依赖

1. Python 3.11 或更高版本。
2. `pip install -e .` 可安装本仓 Python 包和公开依赖。
3. Windows PowerShell 7，用于 Windows 侧启动和 wake 脚本。
4. MiniQMT 与 xtquant，由使用者从合法渠道自行安装。
5. 如果启用 qlib 同步，需要准备本机 qlib 数据目录和足够磁盘空间。

### 本仓不提供的内容

1. 券商客户端安装包。
2. 真实账户、密码、凭据 target 或 Windows Credential Manager 内容。
3. 真实成交、委托、持仓、资金、broker 回执或审计证据。
4. 私有运行态目录、截图、SQLite 缓存或现场排障包。
5. 任何能直接复现个人交易环境的本机路径。

## 安装步骤

推荐在仓库根目录执行：

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

Windows 侧需要 PowerShell 7。WSL 调 Windows 脚本时建议使用本仓提供的 UTF-8 包装脚本：

```bash
scripts/pwsh_utf8.sh -File scripts/wake_data_gateway.ps1
```

如果只做公开样例验证，不需要真实 MiniQMT 登录，也不要填真实账户。

## 配置文件

公开仓只提供样例配置：

```text
configs/data_gateway.example.yaml
configs/trade_gateway.example.yaml
configs/trade_gateway.flow_smoke.yaml
```

建议把样例复制到本机私有目录，例如：

```text
C:\xtquant-mcp-example\instance\prod\config\data_gateway.local.yaml
C:\xtquant-mcp-example\instance\prod\config\trade_gateway.local.yaml
```

不要直接在公开仓内写真实配置。需要私有填写的字段包括：

| 字段 | 说明 |
| --- | --- |
| `runtime.venv_path` | Windows Python 虚拟环境路径 |
| `bundle.bundle_root` | xtquant bundle 根目录 |
| `qmt.account_id` / `trade.account_id` | 本机交易账户；公开样例使用 `ACC001` |
| `qmt.qmt_exe` | MiniQMT 可执行文件路径 |
| `qmt.qmt_userdata` | MiniQMT userdata 路径 |
| `credential_target` | Windows Credential Manager target |
| `paths.state_root` | 本机运行态目录 |
| `paths.artifact_root` | 本机审计和产物目录 |
| `trade.kill_switch_file` | 真实写路径必须配置 kill switch |

端口字段默认可以为 `0`，表示由运行时解析或外部配置提供。不要把某个本机端口写成协议常量。

## 启动前检查

启动前至少确认：

1. MiniQMT 能在 Windows 桌面环境正常打开。
2. 使用的账户和 userdata 来自同一套本机环境。
3. xtquant bundle 与 Python ABI 匹配。
4. 私有配置路径存在，且没有被提交到 Git。
5. `state_root`、`artifact_root`、`logs_root` 可写。
6. 真实交易前已配置 kill switch，并确认默认状态不会误触发。
7. Data Gateway 与 Trade Gateway 使用的环境变量互不冲突。

## 启动顺序

推荐顺序如下：

1. 启动或确认 MiniQMT 登录状态。
2. 校验 xtquant bundle。
3. 启动 Data Gateway。
4. 调用 `gateway.health`，确认 xtdata 基础只读探针通过。
5. 启动 Trade Gateway。
6. 调用 `session.warm` 与 `probe.connection`，确认会话、账户和写权限分层状态。
7. 对真实写路径执行最小 dry-run 或 flow-smoke 验证。
8. 只有在全部门禁通过后，才允许进入真实交易写路径。

示例启动命令需要根据本机配置调整：

```bash
python scripts/run_data_gateway_http.py --config C:/xtquant-mcp-example/instance/prod/config/data_gateway.local.yaml
python scripts/run_trade_gateway_http.py --config C:/xtquant-mcp-example/instance/prod/config/trade_gateway.local.yaml
```

## Data Gateway 操作

Data Gateway 负责只读行情、交易日、板块、批量同步和 qlib 验收。核心工具面：

| 工具 | 用途 | 常见通过条件 |
| --- | --- | --- |
| `gateway.health` | 查看 Data Gateway 分层 readiness | 基础配置、xtdata 探针、运行态路径可用 |
| `calendar.resolve_trade_day` | 确认目标日期是否交易日 | 目标日期有明确官方或运行时判定 |
| `integrity.plan` | 生成 qlib 同步完整性计划 | 目标日期、周期、股票范围可解析 |
| `sector.list` | 查询板块或概念名称 | xtdata 板块接口可用 |
| `sector.members_at` | 查询某日板块成员 | 时间语义明确，不能用最新成员静默回填历史 |
| `sector.change_history` | 查询板块成员变更 | 后端支持变更数据，否则 fail-closed |
| `market.snapshot.batch` | 批量查询快照 | full tick 或 fallback 可解释 |
| `market.history.get_bars` | 查询历史 K 线 | 时间、周期、字段可解析 |
| `bulk.sync_job.submit` | 提交 qlib 同步任务 | 写入 manifest，后续可查状态 |
| `bulk.sync_job.status` | 查询同步任务状态 | 终态、残差和验收信息明确 |
| `bulk.sync_job.cancel` | 取消同步任务 | 任务仍处于可取消状态 |
| `artifact.manifest` | 读取同步产物清单 | 指定 job 已生成 manifest |
| `qlib.health.check` | 检查 qlib 目录健康 | 指定目录与周期存在可读数据 |
| `qlib.acceptance.check` | 验收同步结果 | pass、pass_with_boundary_residuals 或 fail |

Data Gateway 的重要口径：

1. TCP 端口可连不等于 gateway ready。
2. `58610` 可以是某次运行的有效端口，但不能被写死成协议常量。
3. 交易日解析不能静默把非交易日映射到前一交易日。
4. qlib 验收需要区分真实失败和边界残差。
5. 批量同步任务应通过 job manifest 和 acceptance 产物闭环，不只看下载命令是否返回。

## Trade Gateway 操作

Trade Gateway 负责交易会话、账户、订单、成交和写路径门禁。核心工具面：

| 工具 | 用途 | 是否可能触发真实写路径 |
| --- | --- | --- |
| `miniqmt.ensure_logged_in` | 确认或引导 MiniQMT 登录 | 否 |
| `session.warm` | 建立或复用交易会话 | 否 |
| `session.status` | 查看当前会话状态 | 否 |
| `session.close` | 关闭本服务持有的会话 | 否 |
| `probe.connection` | 检查连接、账户、session 和写权限 | 否 |
| `account.show` | 查询账户摘要 | 否 |
| `positions.list` | 查询持仓 | 否 |
| `orders.list` | 查询订单 | 否 |
| `fills.list` | 查询成交 | 否 |
| `snapshot.l1` | 查询 L1 快照 | 否 |
| `order.status` | 查询订单状态 | 否 |
| `order.cancel` | 撤单 | 是，必须过写路径门禁 |
| `order.place` | 下单 | 是，必须过写路径门禁 |

真实写路径必须满足：

1. 使用明确账户，不允许临时从请求参数切换账户。
2. session plan 与实时探针一致，或有明确的 owner-managed realign 证据。
3. `probe.connection` 对读路径和写路径给出分层 readiness。
4. kill switch 配置存在且未触发。
5. 风控阈值、白名单、交易时段、价格模式通过。
6. 审计目录可写，订单请求、结果和状态查询有结构化记录。
7. `order.place` 和 `order.cancel` 不得绕过统一 gateway 分发路径。

## flow-smoke 验证

`configs/trade_gateway.flow_smoke.yaml` 是公开非生产样例。它使用本地 dry-run/flow-smoke 语义验证工具面、状态机和门禁，不连接真实 broker，也不代表真实成交。

示例命令：

```bash
python scripts/run_trade_flow_smoke.py \
  --config configs/trade_gateway.flow_smoke.yaml \
  --output-json .tmp/trade_flow_smoke/report.json
```

通过时应看到：

1. gateway 初始化成功。
2. `session.warm` 返回 ready。
3. `order.place` 被标记为 `flow_smoke` 范围。
4. 订单状态从 submitted 到 canceled 的本地生命周期可查询。
5. 产物写入 `.tmp/trade_flow_smoke/`，该目录不进入 Git。

## 会话恢复

Trade Gateway 故障恢复要按层定位，不要把所有失败都当成同一个“登录问题”。

| 症状 | 优先检查 | 处理方向 |
| --- | --- | --- |
| `session_not_ready` | `session.status`、`session.warm` | 重新 warm 或查看启动超时原因 |
| `miniqmt_not_logged_in` | MiniQMT 窗口和登录状态 | 人工登录或修复凭据 target |
| `session_start_timeout` | session plan、userdata、MiniQMT 日志 | 检查 session id 与 userdata 残留 |
| `connect_failed` | xttrader connect 与 callback | 检查账户、session、端口和 callback 注册 |
| `market_window_closed` | 交易时段门禁 | 等待交易窗口或使用非生产 flow-smoke |
| `kill_switch_on` | kill switch 文件 | 只有确认安全后才移除 kill switch |
| `write_permission_blocked` | 写权限层 readiness | 不允许下单；先修复写路径前置 |

恢复原则：

1. 先读结构化 payload，再看日志。
2. 先恢复只读路径，再恢复写路径。
3. 不手工拼接 `order.place` 请求绕过门禁。
4. 不手工编辑 latest state 文件制造 ready 状态。
5. 不把旧 controller 现场脚本当作公开主入口。

## 证据和归档

公开仓只保留可复现代码、样例配置、测试和脱敏文档。以下内容必须留在私有归档或本机运行态，不进入公开 Git：

1. `.tmp/`、`instance/`、`output/`、`state/`。
2. 真实 EnvSnapshot、EvidencePack、ReviewPack。
3. 真实账号、成交、委托、持仓、资金、broker 回执。
4. 本机 MiniQMT 路径、userdata、截图、SQLite、缓存。
5. 内部计划、内部规格、现场 task card 和审查记录。

公开仓中的这些目录只保留 README stub：

```text
docs/env_snapshots/
docs/evidence_packs/
docs/reviews/
docs/superpowers/plans/
docs/superpowers/specs/
```

## 发布验证

发布前至少执行：

```bash
python -m compileall xtqmt_mcp scripts
python -m unittest discover -s tests -v
git diff --check
```

还应执行：

```bash
python -c "import xtqmt_mcp; print(xtqmt_mcp.__version__)"
rg -n -I "<LOCAL_PRIVATE_PATH>|<REAL_ACCOUNT>|<CREDENTIAL_PATTERN>" .
```

验收口径：

1. 版本号在 `pyproject.toml`、`xtqmt_mcp.__version__` 和样例配置中一致。
2. 高风险隐私扫描无未处理命中。
3. 测试通过；若存在非阻断后台线程打印，必须在 release 验证记录中说明。
4. release 源码包有 SHA256 校验文件。
5. 远端 `main`、release tag 和 GitHub Release 指向同一个冻结提交。

## 常见问题

### 为什么公开配置里是 `ACC001`？

`ACC001` 是合成账户占位符，不是真实账户。真实账户只应写入本机私有配置。

### 为什么样例路径是 `C:\xtquant-mcp-example`？

这是公开占位路径，用来说明目录结构。使用者应替换为自己的私有路径。

### 为什么 `flow_smoke` 不证明真实交易可用？

`flow_smoke` 只验证 gateway 接口、状态机和门禁语义。真实交易还需要 MiniQMT 登录、账户、session、写权限、交易时段、风控和 broker 回执全部通过。

### 为什么端口默认是 `0`？

`0` 表示不把某个本机端口写成协议常量。运行时应从配置、环境变量、日志探针或 xtdata 默认签名中解析真实端点。

### 为什么公开仓没有现场恢复细节？

现场恢复细节可能包含本机路径、账户、日志、回执和人工判断证据。公开仓保留通用恢复原则，真实现场证据进入私有归档。
