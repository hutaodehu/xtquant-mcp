# open_source_prep_20260702 文件矩阵

## 提交分组

| 组 | 路径 | 决策 | 提交信息 | 验证命令 |
| --- | --- | --- | --- | --- |
| G1 | `docs/release/open_source_prep_20260702_status.md` | 公开提交 | `docs(release): record open-source prep audit baseline` | `git diff --cached --check` |
| G1 | `docs/release/open_source_prep_20260702_file_matrix.md` | 公开提交 | `docs(release): record open-source prep audit baseline` | `git diff --cached --check` |
| G1 | `docs/release/private_archive_manifest_20260702.md` | 公开提交 | `docs(release): record open-source prep audit baseline` | `git diff --cached --check` |
| G2 | `xtqmt_mcp/legacy_ports.py` | 公开提交前扫描 | `fix(runtime): remove hard-coded xtdata port readiness assumptions` | `python -m pytest tests/test_data_gateway_config.py tests/test_trade_gateway_config.py tests/test_trade_probe_readiness_split.py -q` |
| G2 | `xtqmt_mcp/settings.py` | 公开提交前扫描 | `fix(runtime): remove hard-coded xtdata port readiness assumptions` | 同 G2 |
| G2 | `xtqmt_mcp/runtime_support.py` | 公开提交前扫描 | `fix(runtime): remove hard-coded xtdata port readiness assumptions` | 同 G2 |
| G2 | `xtqmt_mcp/connection_orchestrator.py` | 公开提交前扫描 | `fix(runtime): remove hard-coded xtdata port readiness assumptions` | 同 G2 |
| G2 | `xtqmt_mcp/miniqmt_login/desktop_harness.py` | 延后到 G3 | `fix(miniqmt): improve desktop login window classification` | G3 测试 |
| G2 | `configs/data_gateway.example.yaml` | 延后到 G5/G6 脱敏后处理 | `feat(data-gateway): add modern MCP tools` / `feat(data-gateway): add qlib sync runtime and acceptance checks` | G5 与 G6 测试 |
| G2 | `configs/trade_gateway.example.yaml` | 公开提交前扫描 | `fix(runtime): remove hard-coded xtdata port readiness assumptions` | 同 G2 |
| G2 | `configs/trade_gateway.flow_smoke.yaml` | 公开提交前扫描 | `fix(runtime): remove hard-coded xtdata port readiness assumptions` | 同 G2 |
| G2 | `tests/test_data_gateway_config.py` | 延后到 G5/G6 脱敏后处理 | `feat(data-gateway): add modern MCP tools` / `feat(data-gateway): add qlib sync runtime and acceptance checks` | G5 与 G6 测试 |
| G2 | `tests/test_trade_gateway_config.py` | 公开提交前扫描 | `fix(runtime): remove hard-coded xtdata port readiness assumptions` | 同 G2 |
| G2 | `tests/test_trade_probe_readiness_split.py` | 延后到 G8 | `feat(trade-gateway): add governed broker reuse and order/fill truth` | G8 测试 |
| G3 | `xtqmt_mcp/miniqmt_login/contracts.py` | 公开提交前扫描 | `fix(miniqmt): improve desktop login window classification` | `python -m pytest tests/test_miniqmt_desktop_harness.py -q` |
| G3 | `tests/test_miniqmt_desktop_harness.py` | 公开提交前扫描 | `fix(miniqmt): improve desktop login window classification` | 同 G3 |
| G4 | `xtqmt_mcp/types.py` | G4 与 G8 分批复核 | `feat(market-data): preserve full tick depth for L1 pricing` | `python -m pytest tests/test_market_data_tick_payload.py tests/test_trade_order_submission_contract.py -q` |
| G4 | `xtqmt_mcp/policy.py` | 公开提交前扫描 | `feat(market-data): preserve full tick depth for L1 pricing` | 同 G4 |
| G4 | `xtqmt_mcp/market_data.py` | 公开提交前扫描 | `feat(market-data): preserve full tick depth for L1 pricing` | 同 G4 |
| G4 | `tests/test_market_data_tick_payload.py` | 公开提交前扫描 | `feat(market-data): preserve full tick depth for L1 pricing` | 同 G4 |
| G4 | `tests/test_trade_order_submission_contract.py` | 公开提交前扫描 | `feat(market-data): preserve full tick depth for L1 pricing` | 同 G4 |
| G5 | `xtqmt_mcp/data_gateway/config.py` | G5 与 G6 分批复核 | `feat(data-gateway): add modern MCP tools` | `python -m pytest tests/test_data_gateway_server.py tests/test_data_gateway_service.py tests/test_wake_data_gateway_script.py -q` |
| G5 | `xtqmt_mcp/data_gateway/jobs.py` | G5 与 G6 分批复核 | `feat(data-gateway): add modern MCP tools` | 同 G5 |
| G5 | `xtqmt_mcp/data_gateway/prompts.py` | 公开提交前扫描 | `feat(data-gateway): add modern MCP tools` | 同 G5 |
| G5 | `xtqmt_mcp/data_gateway/server.py` | 公开提交前扫描 | `feat(data-gateway): add modern MCP tools` | 同 G5 |
| G5 | `xtqmt_mcp/data_gateway/service.py` | G5 与 G6 分批复核 | `feat(data-gateway): add modern MCP tools` | G5 与 G6 测试 |
| G5 | `tests/test_data_gateway_server.py` | 公开提交前扫描 | `feat(data-gateway): add modern MCP tools` | 同 G5 |
| G5 | `tests/test_data_gateway_service.py` | G5 与 G6 分批复核 | `feat(data-gateway): add modern MCP tools` | G5 与 G6 测试 |
| G5 | `scripts/wake_data_gateway.ps1` | 公开提交前扫描 | `feat(data-gateway): add modern MCP tools` | 同 G5 |
| G5 | `tests/test_wake_data_gateway_script.py` | 公开提交前扫描 | `feat(data-gateway): add modern MCP tools` | 同 G5 |
| G6 | `xtqmt_mcp/data_gateway/qlib_runtime.py` | 公开提交前必须脱敏路径 | `feat(data-gateway): add qlib sync runtime and acceptance checks` | `python -m pytest tests/test_data_gateway_config.py tests/test_data_gateway_service.py -q` |
| G7 | `xtqmt_mcp/trade_gateway/config.py` | 公开提交前扫描 | `fix(trade-gateway): preserve session warm timeout state` | `python -m pytest tests/test_trade_gateway_bootstrap.py tests/test_trade_gateway_server.py tests/test_trade_gateway_session_manager.py tests/test_trade_ops_warm_health.py -q` |
| G7 | `xtqmt_mcp/trade_gateway/server.py` | 公开提交前扫描 | `fix(trade-gateway): preserve session warm timeout state` | 同 G7 |
| G7 | `xtqmt_mcp/trade_gateway/session_manager.py` | 公开提交前扫描 | `fix(trade-gateway): preserve session warm timeout state` | 同 G7 |
| G7 | `xtqmt_mcp/trade_gateway/bootstrap.py` | 公开提交前扫描 | `fix(trade-gateway): preserve session warm timeout state` | 同 G7 |
| G7 | `tests/test_trade_gateway_bootstrap.py` | 公开提交前扫描 | `fix(trade-gateway): preserve session warm timeout state` | 同 G7 |
| G7 | `tests/test_trade_gateway_server.py` | 公开提交前扫描 | `fix(trade-gateway): preserve session warm timeout state` | 同 G7 |
| G7 | `tests/test_trade_gateway_session_manager.py` | 公开提交前扫描 | `fix(trade-gateway): preserve session warm timeout state` | 同 G7 |
| G7 | `tests/test_trade_ops_warm_health.py` | 公开提交前扫描 | `fix(trade-gateway): preserve session warm timeout state` | 同 G7 |
| G8 | `xtqmt_mcp/adapters/xttrader_shadow.py` | 公开提交前扫描 broker 证据 | `feat(trade-gateway): add governed broker reuse and order/fill truth` | `python -m pytest tests/test_trade_gateway_fills.py tests/test_trade_write_authority.py -q` |
| G8 | `xtqmt_mcp/trade_gateway/fills.py` | 公开提交前扫描 broker 证据 | `feat(trade-gateway): add governed broker reuse and order/fill truth` | 同 G8 |
| G8 | `xtqmt_mcp/trade_ops.py` | 公开提交前扫描 broker 证据 | `feat(trade-gateway): add governed broker reuse and order/fill truth` | 同 G8 |
| G8 | `xtqmt_mcp/trade_write_authority.py` | 公开提交前扫描 broker 证据 | `feat(trade-gateway): add governed broker reuse and order/fill truth` | 同 G8 |
| G8 | `tests/test_trade_gateway_fills.py` | 公开提交前扫描 broker 证据 | `feat(trade-gateway): add governed broker reuse and order/fill truth` | 同 G8 |
| G8 | `tests/test_trade_write_authority.py` | 公开提交前扫描 broker 证据 | `feat(trade-gateway): add governed broker reuse and order/fill truth` | 同 G8 |
| G9 | `scripts/run_controller_direct_test.ps1` | 公开提交前扫描 | `fix(controller): gate authority refresh on native probe session plan` | `python -m pytest tests/test_controller_direct_authority_refresh.py -q` |
| G9 | `scripts/wake_miniqmt.ps1` | 公开提交前扫描 | `fix(controller): gate authority refresh on native probe session plan` | 同 G9 |
| G9 | `tests/test_controller_direct_authority_refresh.py` | 公开提交前扫描 | `fix(controller): gate authority refresh on native probe session plan` | 同 G9 |
| G10 | `.agents/skills/spec-task-harness/SKILL.md` | 公开提交前扫描 | `feat(agent-harness): add controller-direct closeout guardrails` | `git diff --check -- .agents/skills/spec-task-harness/SKILL.md` |
| G11 | `docs/TRADE_SESSION_BLOCK_RECOVERY_RUNBOOK.md` | 脱敏后提交或归档 | `docs(internal): sanitize trade session recovery records` | 路径、标的、broker 字段和交易中文词扫描 |
| G11 | `docs/change_packages/VAL-003.md` | 脱敏后提交或归档 | `docs(internal): sanitize trade session recovery records` | 同 G11 |
| G11 | `docs/change_packages/VAL-005.md` | 脱敏后提交或归档 | `docs(internal): sanitize trade session recovery records` | 同 G11 |
| G11 | `docs/task_cards/OPS-002.md` | 脱敏后提交或归档 | `docs(internal): sanitize trade session recovery records` | 同 G11 |
| G11 | `docs/task_cards/VAL-003.md` | 脱敏后提交或归档 | `docs(internal): sanitize trade session recovery records` | 同 G11 |
| G11 | `docs/task_cards/VAL-004.md` | 脱敏后提交或归档 | `docs(internal): sanitize trade session recovery records` | 同 G11 |
| G11 | `docs/task_cards/VAL-005.md` | 脱敏后提交或归档 | `docs(internal): sanitize trade session recovery records` | 同 G11 |
| G11 | `docs/VAL-003_G4_EXECUTION_PLAN.md` | 脱敏后提交或归档 | `docs(internal): sanitize trade session recovery records` | 同 G11 |
| G11 | `docs/SESSION_PLAN_DECISION_LOG.md` | 脱敏后提交或归档 | `docs(internal): sanitize trade session recovery records` | 同 G11 |
| G12 | `README.md` | 公开文档外部化 | `docs: externalize public README and runbooks` | `git diff --check -- README.md docs/OPERATIONS_RUNBOOK.md docs/MCP_DESIGN.md docs/CURRENT_STATUS.md docs/ACCEPTANCE_STANDARD.md` |
| G12 | `docs/OPERATIONS_RUNBOOK.md` | 公开文档外部化 | `docs: externalize public README and runbooks` | 同 G12 |
| G12 | `docs/MCP_DESIGN.md` | 公开文档外部化 | `docs: externalize public README and runbooks` | 同 G12 |
| G12 | `docs/CURRENT_STATUS.md` | 公开文档外部化 | `docs: externalize public README and runbooks` | 同 G12 |
| G12 | `docs/ACCEPTANCE_STANDARD.md` | 公开文档外部化 | `docs: externalize public README and runbooks` | 同 G12 |
| G13 | `.gitignore` | 公开提交 | `chore(archive): move private runtime evidence out of public baseline` | `git status --ignored --short` 与 `sha256sum` |
| G13 | `docs/env_snapshots/` | 私有归档，公开只保留 README 或模板 | `chore(archive): move private runtime evidence out of public baseline` | 同 G13 |
| G13 | `docs/evidence_packs/` | 私有归档，公开只保留 README 或模板 | `chore(archive): move private runtime evidence out of public baseline` | 同 G13 |
| G13 | `docs/reviews/` | 私有归档，公开只保留 README 或模板 | `chore(archive): move private runtime evidence out of public baseline` | 同 G13 |
| G13 | `docs/superpowers/plans/` | 私有归档，公开只保留 README 或模板 | `chore(archive): move private runtime evidence out of public baseline` | 同 G13 |
| G14 | `LICENSE` | 公开提交 | `chore(release): prepare v2.0.0-alpha.1 public freeze` | `python -m compileall xtqmt_mcp scripts`、`python -m pytest`、`git diff --check` |
| G14 | `pyproject.toml` | 公开提交 | `chore(release): prepare v2.0.0-alpha.1 public freeze` | 同 G14 |
| G14 | `docs/release/v2.0.0-alpha.1.md` | 公开提交 | `chore(release): prepare v2.0.0-alpha.1 public freeze` | 同 G14 |
| G14 | `docs/release/v2.0.0-alpha.1_freeze_manifest.md` | 公开提交 | `chore(release): prepare v2.0.0-alpha.1 public freeze` | 同 G14 |
| G14 | `docs/release/v2.0.0-alpha.1_validation.md` | 公开提交 | `chore(release): prepare v2.0.0-alpha.1 public freeze` | 同 G14 |
| G14 | `LICENSE` | 公开提交 | `chore(release): prepare v2.0.0-alpha.1 public freeze` | `git diff --cached --check` |

## 私有归档分组

| 路径 | 类型 | 归档原因 | 公开替代 |
| --- | --- | --- | --- |
| `.tmp/` | ignored 运行证据与人工探针 | 含 controller、probe、wake、trade flow、runtime smoke 等现场证据 | `docs/release/private_archive_manifest_20260702.md` 记录 sha256 与分类 |
| `.pytest_cache/` | 测试缓存 | 缓存不属于源码 | 无 |
| `.playwright-mcp/` | 工具运行态 | 本地工具状态不属于源码 | 无 |
| `instance/` | 本地实例运行态 | 可能含截图、SQLite、会话状态 | README 说明实例目录由用户本地配置 |
| `output/` | 运行输出 | 运行产物不属于源码 | 发布验证文档摘要 |
| `state/` | 本地状态 | 可能含真实会话和订单状态 | README 说明不提交状态目录 |
| `VAL-003/` | 历史现场证据 | 真实验收链路不公开 | 脱敏流程说明 |
| `C:\xtquant-mcp-example\instance\prod\artifacts/` | 误入仓的 Windows 运行态目录 | 真实产物路径和数据缓存不公开 | 归档清单记录 |
| `docs/env_snapshots/VAL-*` | 未跟踪现场快照 | 真实环境快照不公开 | `docs/env_snapshots/README.md` |
| `docs/evidence_packs/VAL-*` | 未跟踪证据包 | 真实执行证据不公开 | `docs/evidence_packs/README.md` |
| `docs/reviews/VAL-*` | 未跟踪 review 记录 | 可能含真实现场上下文 | `docs/reviews/README.md` |
| `docs/superpowers/plans/2026-04-15-*` | 历史执行计划 | 内部执行计划不公开 | `docs/superpowers/plans/README.md` |
| `docs/superpowers/plans/2026-04-17-*` | 历史执行计划 | 内部执行计划不公开 | `docs/superpowers/plans/README.md` |

## 实际归档结果

| 分区 | archive_path | 校验清单 | 条目数 | 处理 |
| --- | --- | --- | ---: | --- |
| 未跟踪现场工件 | `untracked/` | `SHA256SUMS.untracked` | 61 | 已移动出工作树 |
| ignored 运行态 | `ignored/` | `SHA256SUMS.ignored` | 603 | 已移动出工作树 |
| 根目录 ignored 空壳 | `ignored-extra/` | `SHA256SUMS.ignored-extra` | 0 | 已移动出工作树 |
| 已跟踪私有证据与内部计划 | `private-evidence/tracked-public-baseline-removal/` | `SHA256SUMS.tracked-private` | 183 | 已从公开 baseline 删除，保留 README stub |

## 公开历史风险

| 路径或提交 | 命中类型 | 处理方式 | 结论 |
| --- | --- | --- | --- |
| `fc3e0328110801d81b6d13f4040f91b8f538ea26` | 历史敏感模式命中 | 不允许快进公开 `main`；必须使用脱敏公开历史或新公开仓 | `sanitized_public_history_required` |
| `docs/env_snapshots/*.md` | 已跟踪历史证据目录 | 已归档并替换为 README stub；公开发布使用脱敏新历史 | `archive_private` |
| `docs/evidence_packs/*.md` | 已跟踪历史证据目录 | 已归档并替换为 README stub；公开发布使用脱敏新历史 | `archive_private` |
| `docs/reviews/*.md` | 已跟踪历史证据目录 | 已归档并替换为 README stub；公开发布使用脱敏新历史 | `archive_private` |
| `docs/superpowers/plans/*.md` | 已跟踪内部计划目录 | 已归档并替换为 README stub；公开发布使用脱敏新历史 | `archive_private` |
| `docs/superpowers/specs/*.md` | 已跟踪内部规格目录 | 已归档并替换为 README stub；公开发布使用脱敏新历史 | `archive_private` |

## 隐私扫描分类

| 范围 | 命中数量 | 决策 |
| --- | ---: | --- |
| 当前工作区全部文件 | 313 | 按 G2-G14 分批脱敏、提交或归档 |
| 当前工作区 `docs/` | 242 | 现场证据和历史执行记录优先归档，公开文档脱敏后保留 |
| 当前工作区 `xtqmt_mcp/` | 34 | 功能代码逐组复核，字段名和接口名可保留，真实默认路径和真实交易数据不得保留 |
| 当前工作区 `tests/` | 21 | 合成样例可保留，真实交易证据不得保留 |
| 当前工作区 `scripts/` | 10 | controller 和 wake 脚本逐组复核，真实路径和真实证据不得保留 |
| 当前工作区 `configs/` | 3 | 只保留示例值，真实路径、账户和端口状态不得保留 |
| 误入 Windows 运行态目录 | 2 | 私有归档 |
| Git 历史全部命中条目 | 1474 | 公开发布使用脱敏新历史 |
| Git 历史唯一命中路径 | 249 | 公开发布使用脱敏新历史 |
| 远端基线 `fc3e032` | 已命中 | 不能快进公开 `main` |

## 当前统计

| 指标 | 数量 |
| --- | ---: |
| 普通未提交条目 | 0 |
| 已修改文件 | 0 |
| 未跟踪文件 | 0 |
| 已跟踪历史证据目录文件 | 184 |
| 已归档未跟踪现场工件 | 61 |
| 已归档 ignored 可读文件 | 603 |
