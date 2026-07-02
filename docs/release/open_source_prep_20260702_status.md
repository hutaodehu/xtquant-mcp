# open_source_prep_20260702 状态

## 基线

- 整理分支：`codex/qmt-mcp-legacy-port-archive`
- 远端 `main`：`fc3e0328110801d81b6d13f4040f91b8f538ea26`
- 规格文件：已进入私有归档，公开 baseline 只保留 `docs/superpowers/specs/README.md`。
- 实施计划：已进入私有归档，公开 baseline 只保留 `docs/superpowers/plans/README.md`。
- 私有归档根目录：`<private_archive_root>/open-source-prep-20260702/`
- 冻结版本候选：`v2.0.0-alpha.1`
- 公开发布动作：未授权；不得推送、公开仓库、创建远端 tag 或发布 GitHub release。

## 当前工作区摘要

- `git status --short --branch`：当前在整理分支，普通工作树干净。
- 普通未提交条目：0 个。
- 未跟踪现场工件：已归档 61 个。
- ignored 运行态可读文件：已归档 603 个。
- 根目录 ignored 空壳：已移动到 `ignored-extra/`。
- 已跟踪历史证据目录：已归档 183 个并替换为 README stub。

## 当前结论

- 公开历史策略：`sanitized_public_history_required`。
- 工作区状态：功能、公开文档和已跟踪证据归档整理完成；等待脱敏公开历史。
- 发布状态：`v2.0.0-alpha.1` 本地冻结候选已形成。
- 暂存策略：每个提交必须按显式路径暂存，禁止 `git add .`。
- 归档策略：真实运行态、真实交易证据、真实本机路径、真实 broker 回执、真实持仓、真实资金和真实会话内容只进入私有归档，不进入公开仓。
- 历史处理策略：`fc3e0328110801d81b6d13f4040f91b8f538ea26` 已命中敏感模式，公开发布不能依赖“后续删除提交”，必须构建脱敏公开历史或新公开仓。

## 隐私扫描摘要

- 当前工作区固定字符串扫描命中文件：313 个。
- Git 历史固定字符串扫描命中条目：1474 条。
- Git 历史固定字符串扫描命中唯一路径：249 个。
- 远端基线提交 `fc3e0328110801d81b6d13f4040f91b8f538ea26`：已命中。
- 扫描命令采用只输出文件路径的隐私保护形式，未把真实命中行写入公开文档。
- 当前工作区主要命中分类：`docs/` 242 个、`xtqmt_mcp/` 34 个、`tests/` 21 个、`scripts/` 10 个、`configs/` 3 个、误入 Windows 运行态目录 2 个、`README.md` 1 个。
- 当前工作区证据目录命中：`docs/env_snapshots/` 75 个、`docs/evidence_packs/` 87 个、`docs/reviews/` 43 个、`docs/superpowers/plans/` 3 个。
- 历史主要命中分类：`docs/env_snapshots/` 50 个、`docs/evidence_packs/` 62 个、`docs/reviews/` 39 个、`docs/superpowers/plans/` 2 个、`xtqmt_mcp/` 33 个、`tests/` 15 个、`scripts/` 10 个、`configs/` 3 个、`README.md` 1 个。

## 执行记录

| 阶段 | 结论 | 证据 |
| --- | --- | --- |
| Task 1 Step 1 | 已采集 Git 基线 | `git status --short --branch`、`git diff --stat`、`git status --ignored --short --untracked-files=all`、`git ls-files docs/env_snapshots docs/evidence_packs docs/reviews docs/superpowers/plans` |
| Task 1 Step 2 | 已建立文件矩阵 | `docs/release/open_source_prep_20260702_file_matrix.md` |
| Task 1 Step 3 | 已建立状态文档 | 本文件 |
| Task 1 Step 4 | 已建立归档清单格式 | `docs/release/private_archive_manifest_20260702.md` |
| Task 2 Step 1 | 已完成当前工作区扫描 | 固定字符串路径级扫描，命中文件 313 个 |
| Task 2 Step 2 | 已完成 Git 历史扫描 | 固定字符串路径级扫描，历史命中条目 1474 条，唯一历史路径 249 个 |
| Task 2 Step 3 | 已判定公开历史策略 | `sanitized_public_history_required` |
| Task 3 | 已提交收窄版 G2 | `824b729 fix(runtime): remove hard-coded xtdata port readiness assumptions`；只包含端口/readiness 核心文件、trade 示例配置和 `tests/test_trade_gateway_config.py` |
| Task 4 | 已提交 MiniQMT 登录识别 | `a90679b fix(miniqmt): improve desktop login window classification` |
| Task 5 | 已提交行情五档 tick | `c59fdc7 feat(market-data): preserve full tick depth for L1 pricing` |
| Task 6/7 | 已合并提交 Data Gateway 工具面与 qlib runtime | `12cf5ba feat(data-gateway): add modern tools and qlib sync runtime` |
| Task 8 | 已提交 Trade Gateway session 恢复 | `4559813 fix(trade-gateway): preserve session warm timeout state` |
| Task 9 | 已提交 broker/order/fill truth | `0d44b3c feat(trade-gateway): add governed broker reuse and order fill truth` |
| Task 10 | 已提交 controller 与 harness | `9c57424`、`42135cf` |
| Task 11/12 | 已提交脱敏公开运行文档 | `df8f0b0 docs: update public runbooks and gateway release posture` |
| Task 13 | 已完成私有归档 | `SHA256SUMS.untracked` 61 条、`SHA256SUMS.ignored` 603 条、`SHA256SUMS.tracked-private` 183 条 |
| Task 14 | 已建立冻结文档 | `docs/release/v2.0.0-alpha.1*.md`、`LICENSE` |

## 提交偏差记录

| 阶段 | 原计划 | 实际处理 | 原因 |
| --- | --- | --- | --- |
| G2 | 包含 `configs/data_gateway.example.yaml` 和 `tests/test_data_gateway_config.py` | 延后到 G5/G6 | 当前 diff 已混入现代工具面、qlib 路径字段和本机路径风险，需要先脱敏 |
| G2 | 包含 `xtqmt_mcp/miniqmt_login/desktop_harness.py` | 延后到 G3 | 当前 diff 同时包含登录窗口识别改动，避免跨组提交 |
| G2 | 包含 `tests/test_trade_probe_readiness_split.py` | 延后到 G8 | 当前 diff 同时包含 broker 复用和 owner shadow 行为，避免提前提交 G8 |

## 后续门禁

- 后续 Task 15 不得执行 `main` 快进发布路径，只能执行脱敏公开历史候选路径，或等待用户确认新公开仓策略。
- 公开发布必须使用脱敏新历史或新公开仓；后续删除提交不能视为隐私保护。
- 任何远端动作都需要用户再次确认。
