# 设计与落地审查

审查时间：2026-03-27 19:29:47 +08:00

关联文档：
- [MCP_DESIGN.md](./MCP_DESIGN.md)
- [CURRENT_STATUS.md](./CURRENT_STATUS.md)
- [../AGENTS.md](../AGENTS.md)
- [WORKFLOW_AND_BOARD.md](./WORKFLOW_AND_BOARD.md)
- [ACCEPTANCE_STANDARD.md](./ACCEPTANCE_STANDARD.md)
- [TEMPLATES.md](./TEMPLATES.md)

## 审查范围

本轮审查覆盖以下四部分：

1. `repo/docs` 中的设计文档与进度文档。
2. `xtqmt_mcp` 下 MCP 服务、交易会话、数据会话与工具暴露实现。
3. `instance/prod` 当前实例配置与落地产物。
4. ThinkTrader 官方文档对 `xtdata` / `xttrader` / MiniQMT 连接模型的约束。

本文件的目标不是重复 README 或使用说明，而是回答三个问题：

1. 这个项目当前到底落到了什么程度。
2. 哪些设计和官方模型冲突，已经会误导 agent。
3. 应该按什么顺序修，才能把 MCP 面真正变成可交付的 agent 消费面。

## 结论摘要

当前状态应判定为 `partial`。

仓库骨架、双 gateway、配置、bundle、HTTP transport、资源缓存和审计落盘都已经成型，说明项目已经从概念阶段进入了“可运行骨架阶段”。但它还没有到“可以放心交给 agent 自主消费”的程度。当前最大风险不是缺几个工具，而是已有工具正在向 agent 传递错误或不完整的系统模型。

最需要立刻处理的不是 live smoke，而是以下三类设计偏差：

1. 交易写路径与文档描述不一致，`order.place` 实际绕过了关键门禁。
2. `xtdata` 端口、订阅和恢复语义被错误地抽象成了稳定常量或已证能力。
3. `xttrader` 会话模型把 `session_id` 教成了固定模板，而不是服务端托管的冲突资源。

如果不先修这些问题，后续即便补完 live smoke，agent 学到的也仍然是错误心智模型。

## 当前落地情况

### 已经落地的部分

以下部分已经是成立的：

1. 项目职责边界明确，当前只保留交易与数据两类 MCP 服务，见 [MCP_DESIGN.md](./MCP_DESIGN.md)。
2. 目录分层已经完成，代码仓、实例目录、vendor bundle 和 Python 运行时分离。
3. 两个 gateway 的工具、资源、prompt 和 HTTP 服务入口都已经实现。
4. 实例配置已经不是纯示例态，当前本地实例已经绑定了实际的 `XtMiniQmt.exe` 与 `userdata_mini` 路径。

### 尚未成立的部分

以下部分还不能视为“已落地完成”：

1. 真实 `xtdata` 只读查询链路尚未形成可靠基线。
2. 真实交易会话预热、显式账户探测和写路径安全闭环尚未形成可靠基线。
3. 订阅能力还没有被证明满足官方推荐的运行模型。
4. 当前文档中的部分“已验证”表述已经和当下真实环境不一致。

### 当前环境快照

本轮审查时的环境快照如下：

1. `XtMiniQmt` 进程已存在，路径为 `D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`。
2. `127.0.0.1:58610` 已打开，说明当前 `xtdata` 服务端口在该时点可达。
3. `127.0.0.1:8765` 和 `127.0.0.1:8766` 仍未打开，说明两个 MCP gateway 在该时点并未处于 agent 可调用状态。
4. `instance/prod/state/data_resources/xtdata_service_status.json` 当前仍保留了 `{"ready": true, "source": "fake"}` 这样的测试污染内容，不适合作为生产状态证据。

因此，环境层面的判断是：

- MiniQMT 与 `xtdata` 端口当前已被拉起。
- MCP 面当前还未被拉起。
- 现有实例状态目录不能完全作为真实运行证据直接信任。

## 与官方文档冲突的设计点

### 1. `xtdata` 端口被抽象成了稳定常量

当前代码和配置在多个位置把 `xtdata` 端口固定为 `58610`，包括：

- [xtqmt_mcp/trade_gateway/config.py](../xtqmt_mcp/trade_gateway/config.py)
- [xtqmt_mcp/data_gateway/config.py](../xtqmt_mcp/data_gateway/config.py)
- [xtqmt_mcp/connection_orchestrator.py](../xtqmt_mcp/connection_orchestrator.py)
- [configs/trade_gateway.example.yaml](../configs/trade_gateway.example.yaml)
- [configs/data_gateway.example.yaml](../configs/data_gateway.example.yaml)

这和官方文档存在明显偏差。

官方口径不是“`xtdata` 永远监听 58610”，而是：

1. `xtdata.connect(port=...)` 连接的是数据服务实际监听的端口。
2. `xtdc.listen()` 可以显式指定端口，也可以在端口范围内自动寻找可用端口。
3. `xtdatacenter.init` 还存在其他默认监听端口冲突场景，例如官方 FAQ 提到的 `58609`。

官方来源：

- <https://dict.thinktrader.net/dictionary/>
- <https://dict.thinktrader.net/nativeApi/code_examples.html?id=3WR14v>
- <https://dict.thinktrader.net/nativeApi/question_function.html?id=TB5IbM>

这意味着当前设计至少有两个问题：

1. 服务端没有把“当前解析到的实际端点”作为状态输出。
2. agent 会被训练成把 `58610` 视为协议常量，而不是实例状态。

### 2. `xtdata` 订阅能力没有按官方模型建模

当前 Data Gateway 暴露了：

- `xtdata.subscribe.start`
- `xtdata.subscribe.stop`

对应实现见：

- [xtqmt_mcp/data_gateway/server.py](../xtqmt_mcp/data_gateway/server.py)
- [xtqmt_mcp/data_gateway/service.py](../xtqmt_mcp/data_gateway/service.py)

问题在于，官方文档把 callback 订阅和 `xtdata.run()` 绑定得很明确：

1. 使用回调时，必须同时使用 `xtdata.run()` 阻塞程序。
2. 连接断开或下游服务重启后，订阅恢复语义需要显式重建。

官方来源：

- <https://dict.thinktrader.net/nativeApi/xtdata.html>
- <https://dict.thinktrader.net/nativeApi/code_examples.html?id=3WR14v>
- <https://dict.thinktrader.net/dictionary/question_answer.html>

而当前仓内没有任何 `xtdata.run()` 调用。这使得 `xtdata.subscribe.start` 至少存在以下未证前提：

1. 回调是否真的在当前进程模型下稳定持续。
2. 连接断开后订阅是否会被正确重建。
3. agent 是否能分辨“订阅对象仍存在”与“订阅已失效但状态文件没清理”。

因此，当前把订阅能力当作稳定 MCP 能力暴露给 agent，证据不足。

### 3. `xttrader` 会话 ID 被教成了固定模板

当前实例配置和默认代码都把 `session_id` / `session_candidates` 固定为：

- `100`
- `101`
- `111`

相关位置：

- [xtqmt_mcp/trade_gateway/config.py](../xtqmt_mcp/trade_gateway/config.py)
- [xtqmt_mcp/trade_gateway/bootstrap.py](../xtqmt_mcp/trade_gateway/bootstrap.py)
- [xtqmt_mcp/miniqmt_login/service.py](../xtqmt_mcp/miniqmt_login/service.py)
- [instance/prod/config/trade_gateway.local.yaml](../../instance/prod/config/trade_gateway.local.yaml)

官方 `xttrader` 文档强调的是：

1. `session_id` 只要求“不重”。
2. 通常只需要一个 API 实例。
3. 连接断开后不会自动重连，需要再次主动连接。
4. 同一 session 的跨进程重复 connect 还有间隔限制。

官方来源：

- <https://dict.thinktrader.net/nativeApi/xttrader.html>
- <https://dict.thinktrader.net/nativeApi/question_function.html?id=TB5IbM>

因此，当前设计的问题不是“支持 session 候选”本身，而是把候选列表塑造成了默认模板，并把会话资源暴露成了可预测值。这会让 agent 学到错误规则：

1. 以为 `100/101/111` 是官方推荐或稳定方案。
2. 以为同一时刻可以让多条 trader 路径自然共用同一个会话。

这两点都不成立。

### 4. `up_queue_xtquant` 被错误上升成整体 readiness 条件

当前交易前置检查里，`up_queue_xtquant` 缺失会直接影响 readiness，相关逻辑见：

- [xtqmt_mcp/xttrader_precheck.py](../xtqmt_mcp/xttrader_precheck.py)
- [xtqmt_mcp/connection_orchestrator.py](../xtqmt_mcp/connection_orchestrator.py)

官方 FAQ 对这个文件的定义更接近“写权限能力标志”，即没有该文件意味着没有对应下单权限，需要联系券商。

官方来源：

- <https://dict.thinktrader.net/nativeApi/question_function.html?id=TB5IbM>

这意味着当前设计把“无写权限”与“连只读探测都不可做”混成了一层。这对 agent 来说会产生错误结论：

1. 本来可做只读诊断的环境，被标成完全不可用。
2. agent 可能因此跳过应当允许的 `account.show`、`positions.list`、探测类动作。

### 5. `xtdata.status` 把板块元数据误当成服务 readiness

当前 `xtdata.status` 会把 `get_sector_list()` 这样的板块分类能力纳入 readiness 判断，`xtdata.instruments.search` 也直接依赖 sector 数据。

相关实现：

- [xtqmt_mcp/data_gateway/service.py](../xtqmt_mcp/data_gateway/service.py)

官方 `xtdata` 文档明确指出：

1. `get_sector_list()` 和 `get_stock_list_in_sector()` 依赖板块分类信息。
2. 这类信息需要通过 `download_sector_data()` 预先下载。

官方来源：

- <https://dict.thinktrader.net/nativeApi/xtdata.html>

但当前 Data Gateway 并没有暴露等价恢复工具。这会导致 fresh 环境中：

1. `xtdata.status` 可能因元数据未准备而表现为“不 ready”。
2. `xtdata.instruments.search` 可能空结果。
3. agent 却没有对应 MCP 工具修复这个前置条件。

## 面向 agent 的接口设计问题

### 1. `order.place` 的服务端安全边界与文档描述不一致

这是当前最严重的问题。

文档与 prompt 明确表达的是：

1. 先登录。
2. 再预热。
3. 再探测。
4. 最后才决定是否写入。

见：

- [MCP_DESIGN.md](./MCP_DESIGN.md)
- [CURRENT_STATUS.md](./CURRENT_STATUS.md)
- [xtqmt_mcp/trade_gateway/prompts.py](../xtqmt_mcp/trade_gateway/prompts.py)

但真实写路径是：

1. [xtqmt_mcp/trade_gateway/server.py](../xtqmt_mcp/trade_gateway/server.py) 将 `order.place` 路由到 capability 路径。
2. [xtqmt_mcp/trade_gateway/capability_v2.py](../xtqmt_mcp/trade_gateway/capability_v2.py) 直接面向 broker adapter 做下单。

而真正包含以下关键保护的路径在 [xtqmt_mcp/trade_ops.py](../xtqmt_mcp/trade_ops.py)：

1. `guard_token`
2. `connect_gate`
3. `session_gate`
4. `risk_engine`
5. `kill switch`
6. 更完整的审计与状态持久化

这会带来两个后果：

1. agent 会误以为 `order.place` 已经被 MCP 服务端严格治理。
2. 实际上 agent 只要拿到 warmed session，就可能走到一条约束明显更弱的写路径。

### 2. 账户会话契约不一致

当前接口对账户维度的表达不一致：

1. `session.warm` / `session.status` / `session.close` 支持 `account_id`。
2. `fills.list` 支持 `account_id`。
3. `account.show` / `positions.list` / `orders.list` / `order.place` 不支持 `account_id` 参数。
4. 实际执行时，server 又用默认配置中的账户值去取 warmed session。

相关实现：

- [xtqmt_mcp/trade_gateway/server.py](../xtqmt_mcp/trade_gateway/server.py)
- [xtqmt_mcp/trade_gateway/resources.py](../xtqmt_mcp/trade_gateway/resources.py)

在当前实例配置里，这个问题更突出，因为：

1. `trade.account_id` 为空。
2. `auto_account` 打开。

见 [instance/prod/config/trade_gateway.local.yaml](../../instance/prod/config/trade_gateway.local.yaml)。

这对 agent 的影响非常直接：

1. 它可能先 warm 出一个显式账户。
2. 随后却发现大多数工具根本不消费那个账户的会话。

### 3. `probe.connection` 的工具语义和 schema 相互打架

`probe.connection` 的工具描述写的是“严格显式账户探测”，但 schema 不接收任何参数，代码进入后又从 `arguments` 里继续读取账户信息。

相关实现：

- [xtqmt_mcp/trade_gateway/server.py](../xtqmt_mcp/trade_gateway/server.py)

这意味着：

1. 接口文案在暗示“支持按账户探测”。
2. schema 在表达“你不能指定账户”。
3. 实现内部又试图保留按账户探测的痕迹。

这会直接误导 agent 的故障诊断策略。

### 4. 资源缓存当前不能完全作为真实证据

资源缓存的方向本身是合理的，但当前存在两个问题：

1. 默认读取很多是配置默认账户上下文，不是调用时上下文。
2. 实例状态目录已经被测试污染。

相关位置：

- [xtqmt_mcp/trade_gateway/resources.py](../xtqmt_mcp/trade_gateway/resources.py)
- [xtqmt_mcp/data_gateway/resources.py](../xtqmt_mcp/data_gateway/resources.py)
- `D:\xtquant-mcp\instance\prod\state\data_resources\xtdata_service_status.json`

这意味着 agent 读取资源时不能默认把它们当作高可信运行证据。

## 文档与代码口径漂移

### 1. `CURRENT_STATUS.md` 的测试结论已不可直接复现

当前进度文档写明：

1. 13 个 `unittest` 全部通过。

见 [CURRENT_STATUS.md](./CURRENT_STATUS.md)。

但本轮实际执行：

```powershell
D:\xtquant-mcp\venv313\Scripts\python.exe -m unittest discover -s tests -v
```

得到的结果是：

1. 共运行 13 个测试。
2. 其中 6 个通过。
3. 7 个报错。

报错主体并非交易业务逻辑断言失败，而是：

1. Windows 临时目录权限问题。
2. 默认 call log 与默认状态目录写入权限问题。

这说明当前进度文档至少需要降格为：

1. 某一轮环境下曾通过。
2. 当前环境下尚未复核为“全通过”。

### 2. 实例目录中混入测试 fake 状态

当前看到的 `xtdata_service_status.json` 是：

```json
{
  "ready": true,
  "source": "fake"
}
```

同时 `data_gateway_calls.jsonl` 中也混有 fake `xtdata.status` 记录。

这说明：

1. 测试与生产实例目录没有完全隔离。
2. 当前实例状态目录不能直接作为生产证据给 agent 使用。

## 哪些设计是合理的

尽管上面的问题较多，但以下设计方向是成立的，应该保留：

1. 将能力切分为 `Trade Gateway` 和 `Data Gateway` 是正确方向。
2. WSL / agent 不直接 `import xtquant`，而通过本机 MCP 网关访问能力，是正确方向。
3. 本机绑定、origin 白名单、审计落盘、资源缓存和 prompt 约束，都是适合 agent 恢复流程的做法。
4. `download.submit/status/cancel` 加 job manager 的模式总体合理，尤其在长耗时数据下载场景下比同步阻塞调用更适合 agent。

问题不在总方向，而在若干关键能力的“契约定义”还不够严谨。

## 修正顺序

### 第一优先级

1. 收口 `order.place`，只保留一条受控写路径。
2. 将 `xtdata_port` 从静态配置降级为动态解析与诊断输出。
3. 重构交易会话 owner 模型，避免同一 warm 流程中构造多套 trader 实例共用 session。

### 第二优先级

1. 将 read-only preflight 与 write-permission preflight 拆开。
2. 明确单账户还是多账户契约，并统一所有 schema、资源和执行路径。
3. 清理实例目录中的 fake 状态与测试污染。

### 第三优先级

1. 在做完真实 smoke 前，将 `xtdata.subscribe.start` 标记为实验能力。
2. 重新定义 `xtdata.status` 的 readiness 分层，至少拆成：
   - 连接 readiness
   - 元数据 readiness
   - 下载作业状态
   - 订阅租约状态
3. 更新 `CURRENT_STATUS.md`，只陈述当前可复核的事实。

## 建议的验收标准

在把 MCP 面重新声明为“可供 agent 使用”之前，建议至少满足以下验收条件：

1. `order.place` 的唯一写路径已经统一，且服务端强制执行风控门禁。
2. `xtdata.status` 能输出“实际解析到的端点”，而不是只输出静态配置值。
3. `session.warm` 到后续读写工具之间的账户契约一致。
4. 只读探测在缺失 `up_queue_xtquant` 时仍能执行并给出准确诊断。
5. 测试与生产实例目录完全隔离，资源缓存不再出现 fake 污染。
6. 完成一轮真实只读 smoke，并将证据沉淀到可追溯工件中。

## 最终判断

这套项目当前最需要修的不是“功能不够多”，而是“已经暴露出来的能力在教 agent 什么规则”。

现在最大的问题是：

1. 把偶然事实包装成契约，例如固定端口与固定 session 模板。
2. 把实验性能力包装成稳定能力，例如当前的订阅接口。
3. 把文档中描述的安全边界和代码中的真实边界做成了两套。

如果先补更多工具而不先修这些基础契约，后面 agent 的误判成本会越来越高。

## 参考来源

官方文档：

- <https://dict.thinktrader.net/dictionary/>
- <https://dict.thinktrader.net/nativeApi/xtdata.html>
- <https://dict.thinktrader.net/nativeApi/xttrader.html>
- <https://dict.thinktrader.net/nativeApi/code_examples.html?id=3WR14v>
- <https://dict.thinktrader.net/nativeApi/question_function.html?id=TB5IbM>
- <https://dict.thinktrader.net/dictionary/question_answer.html>

本地代码与配置：

- [xtqmt_mcp/trade_gateway/server.py](../xtqmt_mcp/trade_gateway/server.py)
- [xtqmt_mcp/trade_gateway/capability_v2.py](../xtqmt_mcp/trade_gateway/capability_v2.py)
- [xtqmt_mcp/trade_ops.py](../xtqmt_mcp/trade_ops.py)
- [xtqmt_mcp/data_gateway/service.py](../xtqmt_mcp/data_gateway/service.py)
- [xtqmt_mcp/connection_orchestrator.py](../xtqmt_mcp/connection_orchestrator.py)
- [xtqmt_mcp/xttrader_precheck.py](../xtqmt_mcp/xttrader_precheck.py)
- [instance/prod/config/trade_gateway.local.yaml](../../instance/prod/config/trade_gateway.local.yaml)
- [instance/prod/config/data_gateway.local.yaml](../../instance/prod/config/data_gateway.local.yaml)
