# Adaptive Delivery Suite 二轮复审

关联设计文档：[ADAPTIVE_DELIVERY_SUITE_DESIGN.md](./ADAPTIVE_DELIVERY_SUITE_DESIGN.md)  
关联使用手册：[ADAPTIVE_DELIVERY_SUITE_MANUAL.md](./ADAPTIVE_DELIVERY_SUITE_MANUAL.md)  
关联研究文档：[../research/UNIVERSAL_AGENT_DELIVERY_ROUTING_RESEARCH_20260330.md](../research/UNIVERSAL_AGENT_DELIVERY_ROUTING_RESEARCH_20260330.md)

## 文档状态

- 文档类型：二轮深入复审
- 主要受众：产品验收者、技能设计者、主控编排者
- 复审日期：2026-03-30
- 复审范围：
  - 风险失败与任务路由是否能结构化落地
  - 角色分离、authority matrix、TDD/ATDD 是否真正进入 schema
  - quant 与 agent 场景是否覆盖充分
  - 是否应打包为 Codex plugin

## 结论摘要

二轮复审后的总体判断是：

1. 这套技能组的整体架构方向是合理的，核心分层依然应保持 `workflow-router -> acceptance-analysis -> mode-* -> evidence-gate`。
2. 第一版最大的风险不在“模式拆分错了”，而在“研究里讲清楚的边界还没有全部变成机器可读结构”。
3. 因此本轮不推翻架构，而是补强四类薄弱面：
   - authority 结构化
   - scenario-level acceptance
   - evidence freshness / provenance
   - quant / agent 特有风险输入
4. 当前不建议再把它额外打包成 Codex plugin，继续保持 `repo-local skills + contracts` 更符合现阶段成熟度。

## 与研究结论的对照

### 与头部工程实践的一致处

本设计与研究中抽取的外部实践总体一致：

- Google / GitHub / Microsoft 的思路是把 shared change gate、review、CI、environment approval 外置
- OpenAI / Anthropic / Cursor 的思路是把权限、sandbox、approval、eval 外置
- 开源项目里 `gstack`、`OpenSpec`、`get-shit-done` 的差异主要在编排形态，而不是在“是否允许执行模型自封放行”

当前这套设计仍然成立的原因是：

- 模式选择由 policy 驱动，而不是由模型凭感觉
- TDD 只承担开发内环，不承担最终验收 authority
- evidence 和 authority 都在模型外部有落点
- 高风险任务会升格到 `gated_change` 或 `live_rollout`

### 第一版与研究结论的偏差

第一版主要有五个偏差：

1. `route_decision` 仍然偏扁平，authority 和 handoff 还不够机器可执行
2. `acceptance_contract` 过于平面化，场景层不够
3. `gate_result` 对 evidence freshness 与 provenance 表达不足
4. `risk_profile` 未完整覆盖 runtime volatility、agent topology、privilege surface
5. pluginization 没有正式结论，容易被误解为“自然下一步”

这些偏差在本轮已通过 schema、manual、examples 和 skill 文案修订进行补强。

## 本轮已解决的关键问题

### 1. 手册缺失

上一轮文档引用了 `ADAPTIVE_DELIVERY_SUITE_MANUAL.md`，但文件本身缺失。这个问题会直接导致设计草案无法被真实使用者采用。

本轮处理：

- 新增正式手册 `ADAPTIVE_DELIVERY_SUITE_MANUAL.md`
- 把调用顺序、多 agent 使用法、TDD/ATDD 分工、quant 与 agent 场景、plugin 决策都补进手册

### 2. authority 只有概念，没有落到 schema

上一轮虽然有 `AUTHORITY_MATRIX`，但 `route_decision` 与 `gate_result` 仍然用扁平字段，很难支撑真正的角色分离和 handoff。

本轮处理：

- 在 `ROUTE_DECISION_SCHEMA` 中加入 `authority_requirements`
- 加入 `handoff_required_roles`
- 在 `GATE_RESULT_SCHEMA` 中拆分 `validation_authority_satisfied` 与 `release_authority_satisfied`

### 3. acceptance 只有平面 checks，没有场景层

这会直接弱化 ATDD / BDD 的价值，也让 TDD 更容易被误读为最终验收。

本轮处理：

- 在 `ACCEPTANCE_CONTRACT_SCHEMA` 中加入 `acceptance_scenarios`
- 加入 `gate_definitions`
- 加入 `required_authorities`
- 明确 feature / migration / rollout / agent-routing 等场景不应只保留平面 checks

### 4. evidence 缺 freshness / provenance

这对 quant runtime、broker session、trade rollout、background agent 都是实际风险。

本轮处理：

- 在 `GATE_RESULT_SCHEMA` 中加入 `evidence_freshness`
- 把原来的自由 `evidence` map 提升为 `evidence_items`
- 要求带 `artifact_path`、`captured_at`、`environment_id`

### 5. quant 与 agent 风险输入仍偏通用软件视角

原有 `risk_profile` 虽然已经够第一版使用，但对 runtime state、session volatility、多 agent 拓扑和权限面表达不足。

本轮处理：

- 加入 `execution_topology`
- 加入 `runtime_dependency`
- 加入 `runtime_volatility`
- 加入 `fresh_evidence_required`
- 加入 `privilege_surface`
- 加入 `data_integrity_risk`

### 6. 缺少 worked examples

如果只有最薄的 route fixture，使用者很难理解 `acceptance-analysis` 和 `evidence-gate` 的完整职责。

本轮处理：

- 保留原有轻量 route fixtures
- 新增 worked examples，显式展示：
  - `risk_profile`
  - `acceptance_contract`
  - `evidence_inputs`
  - 完整 `gate_result`
- 新增 quant fast-loop 正例、plugin no-go 样例、contract recovery 样例、多 agent 正例

## 产品验收视角的判断

从产品验收角度看，这套技能组现在更接近“可用的通用设计包”，但还不是“安装即用的终端产品”。

### 为什么说它现在合理

因为它已经明确分离了四件事：

1. 路由判断
2. 验收契约
3. 执行模式
4. 证据判定

这四件事恰好对应了大多数工程组织里真正分离的权责边界。

### 为什么说它还不是最终产品

因为它仍然主要交付为：

- 技能说明
- 契约结构
- golden examples
- repo-local 使用手册

而不是：

- 已稳定的安装入口
- 已稳定的运行时适配器
- 已验证的跨仓库分发机制

## 对 quant 与 agent 场景的判断

### quant 适配性

目前已经能够较好覆盖三类典型工作：

1. 离线因子/回测逻辑
   - 可以进入 `fast_loop`
   - 通过 deterministic fixture + benchmark diff 做局部证明
2. 行情接入 / 订阅 / runtime state
   - 默认 `gated_change`
   - 强调 env snapshot、runtime probe 和 freshness
3. 交易写路径 / broker / 真实账户
   - 默认 `live_rollout`
   - 明确 approval、rollback、fresh runtime evidence

这一点与研究预期一致，也比“所有 quant 任务都走重流程”更符合实际。

### agent 适配性

目前已经能够覆盖以下风险类型：

- prompt / tool routing 变化
- permission boundary drift
- multi-agent handoff
- background agent / remote agent

但本轮也明确了一个重要前提：

`multi_agent_allowed` 与 `background_agent_allowed` 只是受控 opt-in，不是默认可用能力，更不是 authority 升级。

## 是否需要打包为 Codex plugin

当前结论：`No-Go`

原因不是“永远不需要”，而是“现在打包会早于设计成熟度”。

### 当前不适合插件化的原因

1. 这套设计当前主要价值在 skill、contract、adapter 抽象，不在 runtime 壳层。
2. repo 已经以 `.agents/skills/*` 形式具备直接可用的最小交付形态。
3. adapter、runtime entrypoint、artifact 映射、安装边界还未稳定。
4. 当前 Codex CLI 的 plugin surface 仍不应被当成稳定公开产品面。

### 重新评估插件化的前提

只有以下条件同时满足才建议重评：

1. 两个及以上项目已复用这套链路
2. 至少一个 adapter 已稳定落地
3. plugin manifest、入口、兼容策略、版本策略已明确
4. plugin 只作为分发载体，不替代 review / approver / repo policy

## 仍然保留的非目标

本轮补强后，以下仍然不是当前交付目标：

- 不提供 repo-agnostic runtime adapter 实现
- 不提供 plugin manifest 与 marketplace 交付
- 不把 controller mode 当作通用 base mode
- 不让模型独自拥有最终 release authority

## 后续建议

### 高优先级

1. 如果后续要真正工程化复用，先做至少一个真实 adapter
2. 为 worked examples 增加回归检查，防止 schema 演进时文档漂移
3. 在真实项目中验证 router -> acceptance -> mode -> gate 链路

### 中优先级

1. 增加 repo-level templates，使 acceptance_scenarios 更易落地
2. 为 background agent / remote agent 补更多正反例
3. 补充更多 quant runtime 场景的 worked examples

### 低优先级

1. 当 plugin surface 稳定后，再评估是否包装成 Codex plugin
2. 如果要做插件，只包装稳定入口，不包装仍在试验中的 authority 逻辑
