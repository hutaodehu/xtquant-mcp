# Golden Examples

本目录提供设计级 golden examples，用于验证：

- `workflow-router` 的 mode 选择是否一致
- `acceptance-analysis` 的 contract 结构是否完整
- `evidence-gate` 是否把 `decision`、`blocker_class` 和 authority 边界分开
- 高风险 quant / runtime / trade 场景是否正确要求新鲜证据与受控 gate
- 多 agent / tooling / background agent 场景是否正确约束 handoff、权限与放行

样例分为两类：

- route fixture
  - 保持轻量形状：`task_spec`、`expected_route_decision`、`expected_gate_result`
- worked example
  - 增加 `expected_risk_profile`、`expected_acceptance_contract`、`evidence_inputs` 等字段
  - 用于演示 `acceptance-analysis` 与 `evidence-gate` 的完整使用边界

## 基础样例

1. `docs_only_fast_loop.yaml`
   - docs-only 快速迭代，应保持在 `fast_loop`
2. `pure_logic_bugfix_fast_loop.yaml`
   - 纯内部逻辑 bugfix，可通过 deterministic local checks 收敛
3. `public_api_change_gated_change.yaml`
   - 公共接口变化，应进入 `gated_change`
4. `cross_module_refactor_gated_change.yaml`
   - 跨模块共享改动，需要独立验证与评审
5. `schema_migration_live_rollout.yaml`
   - schema migration 属于高后果 rollout
6. `trade_order_place_live_rollout.yaml`
   - 真实下单路径必须走 `live_rollout`
7. `agent_tool_routing_gated_change.yaml`
   - tool routing / permission hint 变化默认是 shared gated change
8. `missing_contract_analyze_only.yaml`
   - 缺失 acceptance contract 时必须停在 `analyze_only`

## 高风险扩展样例

9. `stale_runtime_evidence_live_rollout.yaml`
   - 验证 stale runtime evidence 不能支撑 live rollout
   - 重点检查 `fresh_env_snapshot_required` 与 `fail_env`
10. `broker_session_volatility_gated_change.yaml`
   - 验证 quant / broker session 波动场景下不能只凭共享改动自测推进
   - 重点检查 runtime probe 与 env snapshot
11. `tool_permission_drift_gated_change.yaml`
   - 验证工具权限模型与 schema 漂移时应判为 `fail_design`
   - 重点检查 permission boundary 与 contract 对齐
12. `background_agent_remote_write_live_rollout.yaml`
   - 验证 background agent 处理远程高副作用写任务时不能绕过 approval
   - 重点检查 `background_agent_allowed` 不等于自动放行
13. `multi_agent_handoff_authority_gap_gated_change.yaml`
   - 验证多 agent handoff 若 authority 边界不清，应被明确阻断
   - 重点检查 handoff contract、authority matrix 与独立评审

## Worked Examples

14. `deterministic_quant_factor_fast_loop_worked_example.yaml`
   - 覆盖可 TDD 的 quant fast-loop 正例
   - 重点检查 scenario-level acceptance 如何区分本地证明与最终放行
15. `stale_runtime_evidence_live_rollout_worked_example.yaml`
   - 覆盖 stale runtime evidence 的完整 gate judgement
   - 重点检查 evidence freshness、authority 和 fail_env 的分离

## 补充决策样例

16. `multi_agent_controlled_opt_in_gated_change.yaml`
   - 覆盖多 agent 在 write set 明确、handoff 契约稳定时的受控正例
17. `plugin_packaging_decision_analyze_only.yaml`
   - 覆盖 pluginization `No-Go` 的默认判断
18. `contract_missing_recovery_analyze_only.yaml`
   - 覆盖缺失 contract 时如何进入 recovery-oriented analyze-only
19. `safety_boundary_docs_gated_change.yaml`
   - 覆盖文档任务一旦改变 safety / approval / release / permission boundary，就不再属于普通 docs-only `fast_loop`

## 使用建议

- 新增样例时，优先复用现有枚举，不要发明新的 `base_mode`、overlay 或 blocker 分类。
- 若样例要表达“证据过期”，优先通过 `required_gates` 和 `blocker_class` 表达，不要跳出当前 schema。
- 若样例涉及 live-ready 结论，默认应先检查是否需要 `manual_gate`、`human_review_required` 或 `fresh_env_snapshot_required`。
- 需要验证 authority/evidence/freshness 的场景，优先补 worked example，而不是继续压成只剩最终标签的 route fixture。
- 若样例包含 `expected_acceptance_contract` 或 `expected_gate_result`，其字段 `SHOULD` 与当前 schema 最小结构保持一致，不要让 worked example 落后于 schema。
