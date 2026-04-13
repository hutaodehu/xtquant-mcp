# OPS-001 历史污染 Artifact 识别与处置策略

Task ID: OPS-001  
Owner Role: dev (strategy artifact delivery)  
Status Intent: provide formal disposal strategy; does not replace independent test/review

## 1. 目的

为 `instance/prod` 下可能存在的历史污染 artifact 提供可执行的识别与处置规则，避免未标记污染被误当成 `G0/G1` 正式证据。

本策略是 `OPS-001` 的正式补充工件，覆盖 review 要求中的“识别规则 + 清理/隔离步骤”缺口。

## 2. 适用范围

In Scope:

1. `D:\xtquant-mcp\instance\prod\state\**`
2. `D:\xtquant-mcp\instance\prod\artifacts\data_gateway\**`
3. `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\**`
4. 与 `G0/G1` 证据链直接相关的健康与资源状态文件

Out of Scope:

1. 真实交易写路径验证 (`G4`)
2. 自动化批量清洗脚本开发
3. 对非 `instance/prod` 目录的历史数据重写

## 3. 污染识别规则

命中任一规则即判定为“疑似污染”，需要进入处置流程：

1. payload 含 `source=fake`、`mock`、`synthetic` 等测试来源标记。
2. 产物来源与健康字段不一致，例如 `evidence_scope != prod` 但文件落在 `instance/prod`。
3. call log 出现明显测试运行痕迹（测试临时目录、测试会话标签）且写入 `prod` 路径。
4. 关键状态文件缺少可追踪字段（例如缺失 `trace_id` 或 `server_ts`）且无法回链到正式执行记录。
5. 时间窗异常：artifact 时间戳落在已知测试窗口，但被归档为生产证据。

## 4. 处置等级

按风险分三类，禁止“一刀切删除”：

1. `P0` 高风险污染：直接影响 `G0/G1` 判定的状态文件或健康证据。  
   动作：立即隔离 + 标记为不可用于验收。
2. `P1` 中风险污染：不直接影响健康结论，但会误导排查或追踪。  
   动作：隔离并补充索引说明，保留原件供审计。
3. `P2` 低风险残留：历史调试文件，对当前 gate 无直接影响。  
   动作：记录后按维护窗口清理。

## 5. 标准处置流程

### Step 0: 快照

1. 记录执行时间、执行人、当前主机与配置路径。
2. 对待处理目录先生成文件清单（含大小、修改时间）。

### Step 1: 识别与分级

1. 按“污染识别规则”扫描目标目录。
2. 对命中文件标注 `P0/P1/P2` 分级和命中规则。

### Step 2: 隔离

1. 在 `D:\xtquant-mcp\instance\prod\artifacts\quarantine\YYYYMMDDHHMM\` 建立本次隔离目录。
2. 将 `P0/P1` 文件移动到隔离目录，保留相对路径结构。
3. 在隔离目录写入 `manifest.json`，至少包含：
   - original_path
   - quarantine_path
   - reason_rule
   - severity
   - operator
   - ts
   - original_sha256
   - total_lines
   - flagged_lines
   - contains_non_flagged_records

### Step 2A: 混合日志（JSONL）处置约束

1. 对 JSONL 或其他可逐条解析的日志，默认 `MUST NOT` 按单一 `fake` 理由整文件隔离。
2. 若日志同时包含污染条目和非污染条目（mixed-content），优先做条目级筛分：
   - 保留原文件副本（不可改写）用于审计回放。
   - 将命中污染规则的条目分流到 quarantine 子文件。
   - 将未命中条目保留在原证据链或同步生成 clean 副本并回链。
3. 若当前工具链无法立即做条目级分流，允许临时整文件隔离，但必须先执行并记录：
   - 原文件 SHA256（`original_sha256`）。
   - 总行数（`total_lines`）。
   - 命中污染规则行数（`flagged_lines`）。
   - 是否包含未命中条目（`contains_non_flagged_records`）。
   - 该整文件隔离仅可标记为 `temporary_mixed_log_quarantine`，不得标记为纯污染文件。
4. 任何 mixed-content 处置都必须在后续复核中证明“污染隔离”和“历史证据保全”同时成立。

### Step 3: 验证

1. 复查 `instance/prod/state` 与 `instance/prod/artifacts/*gateway*`，确认已无本轮命中的 `P0/P1` 文件。
2. 重新采集 `/healthz` 与关键资源读取结果，确保证据来源字段与目录语义一致。
3. 将复查结果写入新的 EvidencePack/EnvSnapshot（由测试角色执行并归档）。

### Step 4: 清理或保留

1. `P0`：默认保留隔离件至少 7 天，待审查确认后再删除。
2. `P1`：默认保留隔离件至少 14 天，供回溯。
3. `P2`：按维护窗口批量删除或归档。

## 6. 最小命令模板（PowerShell）

以下仅为执行模板，正式执行必须写入对应 EvidencePack：

```powershell
# A. 生成待检查清单
Get-ChildItem -Path D:\xtquant-mcp\instance\prod\state -Recurse -File |
  Select-Object FullName, Length, LastWriteTime |
  Export-Csv -NoTypeInformation D:\xtquant-mcp\instance\prod\artifacts\quarantine\scan_state.csv

# B. 按关键词定位疑似污染（示例）
Get-ChildItem -Path D:\xtquant-mcp\instance\prod -Recurse -File |
  Select-String -Pattern '"source"\s*:\s*"fake"|mock|synthetic' |
  Select-Object Path, LineNumber, Line

# C. 创建隔离目录（示例）
$ts = Get-Date -Format "yyyyMMddHHmm"
$qRoot = "D:\xtquant-mcp\instance\prod\artifacts\quarantine\$ts"
New-Item -ItemType Directory -Path $qRoot -Force

# D. mixed-content 日志最小完整性统计（示例）
$log = "D:\xtquant-mcp\instance\prod\artifacts\data_gateway\20260327\data_gateway_calls.jsonl"
$hash = (Get-FileHash -Path $log -Algorithm SHA256).Hash
$total = (Get-Content -Path $log | Measure-Object -Line).Lines
$flagged = (Select-String -Path $log -Pattern '"source"\s*:\s*"fake"|mock|synthetic').Count
$containsNonFlagged = $flagged -lt $total
@{
  original_path = $log
  original_sha256 = $hash
  total_lines = $total
  flagged_lines = $flagged
  contains_non_flagged_records = $containsNonFlagged
}
```

## 7. 失败分类建议（供测试/审查使用）

1. `fail_design`：出现语义冲突，例如健康字段与产物路径语义矛盾、契约未要求可追踪字段导致无法判定真伪。
2. `fail_env`：规则清晰但执行受环境限制，例如权限不足、文件锁定、网关进程不可达导致无法完成隔离或复核。
3. `blocked`：策略已明确但缺少执行窗口或前置条件（例如真实进程尚未就绪）而无法完成 gate 闭环。

## 8. 与 OPS-001 当前实现的边界

1. 已实现：prod scope 下对 `source=fake` 的读取阻断、证据来源字段补充、测试写入路径隔离。
2. 本文新增：对“未标记但污染”的历史 artifact 给出正式识别与处置流程。
3. 未实现：自动化清洗脚本与一键处置器；仍需后续任务按该策略执行并沉淀独立测试证据。

## 9. 执行纪律

1. 本策略文档本身不是验收通过证明。
2. 任何“已清理/已隔离”结论必须回链 EvidencePack 与 EnvSnapshot。
3. 禁止自动进入下一卡；`OPS-001` 仍需独立测试与审查闭环。
