# EnvSnapshot

Task ID: VAL-002
Date: 2026-03-30T11:34:40.5117954+08:00
Role: test

## Host

- OS: Microsoft Windows NT 10.0.26200.0
- Hostname: CHIYU
- Shell: PowerShell 7.6.0
- Working Directory: `D:\xtquant-mcp\repo`
- EvidencePack: [VAL-002-test-20260330-broker-log-extract.md](../evidence_packs/VAL-002-test-20260330-broker-log-extract.md)

## Investigation Inputs

- Live log root:
  - `D:\lh\国金证券QMT交易端\userdata_mini\log`
- Primary files inspected:
  - `D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log`
    - length: `1612195`
    - last write time: `2026-03-30T11:34:28.9118594+08:00`
  - `D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_perform_20260330.log`
    - length: `877670`
    - last write time: `2026-03-30T11:34:30.2724192+08:00`
- Prior evidence used only to anchor time windows:
  - [VAL-002-test-20260330-full-postpatch-rerun.md](../evidence_packs/VAL-002-test-20260330-full-postpatch-rerun.md)
  - [VAL-002-test-20260330-broker-session-native-probe.md](../evidence_packs/VAL-002-test-20260330-broker-session-native-probe.md)

## Correlated Time Windows

- Gateway rerun window from prior evidence:
  - initialize started: `2026-03-30T10:57:37.057735+08:00`
  - final resource read finished: `2026-03-30T10:59:09.432290+08:00`
  - gateway verdict there remained `fail_env`
- Native direct probe window from prior evidence:
  - session `100` connect window: `2026-03-30T11:16:48.179280+08:00` to `2026-03-30T11:16:51.180991+08:00`
  - session `101` connect window: `2026-03-30T11:16:51.210921+08:00` to `2026-03-30T11:16:54.222546+08:00`
  - native verdict there remained `fail_env`

## Commands Run

1. Current inspection context:

```powershell
$ts=Get-Date
[ordered]@{
  observed_at=$ts.ToString('o')
  host=$env:COMPUTERNAME
  shell=$PSVersionTable.PSVersion.ToString()
  cwd=(Get-Location).Path
} | ConvertTo-Json -Depth 4
```

2. Log file metadata:

```powershell
Get-Item `
  'D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log',`
  'D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_perform_20260330.log' |
  Select-Object FullName,Length,LastWriteTime |
  ConvertTo-Json -Depth 4
```

3. Main time-window search:

```powershell
rg -n "2026-03-30 10:57|2026-03-30 10:58|2026-03-30 10:59|2026-03-30 11:16|2026-03-30 11:17|2026-03-30 11:18" `
  'D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log'
```

4. Performance-log time-window search:

```powershell
rg -n "2026-03-30 10:57|2026-03-30 10:58|2026-03-30 10:59|2026-03-30 11:16|2026-03-30 11:17|2026-03-30 11:18" `
  'D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_perform_20260330.log'
```

5. Main keyword search:

```powershell
rg -n -i "connect|session|queryNodeInfo|order|account|InstantMode|up_queue|lock|error|fail|100|101|111" `
  'D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log'
```

6. Focused line extraction:

```powershell
$p='D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log'
$lines=Get-Content $p
$ranges=@(
  @{s=12851;e=12870},
  @{s=12900;e=12910},
  @{s=12950;e=12959},
  @{s=13449;e=13460},
  @{s=817;e=831}
)
foreach($r in $ranges){
  "--- $($r.s)-$($r.e) ---"
  for($i=$r.s; $i -le $r.e; $i++){
    '{0}:{1}' -f $i,$lines[$i-1]
  }
}
```

7. Negative/auxiliary field search:

```powershell
$patterns=@('queryNodeInfo','InstantMode','m_bInstantMode','up_queue','lock_up_queue')
foreach($pat in $patterns){
  $m = rg -n --fixed-strings $pat `
    'D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log' `
    'D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_perform_20260330.log'
  if($LASTEXITCODE -eq 0){ "### $pat"; $m } else { "### $pat`n(no matches)" }
}
```

## Host-Log Findings

### 10:57 to 10:59

- `XtMiniQmt_20260330.log` shows:
  - session `100` connected and `query accountInfos found 1`
  - session `101` connected, subscribed, and logged both `query positions found 2` and `query account detail`
  - session `111` connected, subscribed, and logged both `query account detail` and `query positions found 2`
  - heartbeat timeout lines existed, but `lock_down_queue_win_100` and `lock_down_queue_win_111` remained `file lock held, keep online`

### 11:16 to 11:16:55

- `XtMiniQmt_20260330.log` shows:
  - session `100` connected at `11:16:48,178`
  - session `101` connected at `11:16:51,210`
  - session `100` then hit heartbeat timeout and disconnected at `11:16:52,339`
  - session `101` then hit heartbeat timeout and disconnected at `11:16:55,050`
  - the corresponding lock lines were:
    - `lock_down_queue_win_100 file lock not held, offline`
    - `lock_down_queue_win_101 file lock not held, offline`

### Additional same-day context

- `queryNodeInfo` exists earlier in the day at `00:32:24,867`.
- The same logged request contains `m_bInstantMode: false`.
- The subsequent `queryNodeInfo` result for that startup request logged:
  - `query node info data size 0`
  - `ErrorID: 200006`
  - `ErrorMsg: "无效的请求参数"`
- This is reported as same-day context only, not as a blocker-window event.

## Negative Search Results

- No `up_queue` matches were found in the two inspected files.
- No `lock_up_queue` matches were found in the two inspected files.
- `XtMiniQmt_perform_20260330.log` did not expose broker/session-specific failure details in the bounded `10:57-10:59` and `11:16-11:18` windows beyond periodic `threadpool ... is alive` lines.

## Environment Classification

- Stronger `fail_env` support than before:
  - The native `11:16` blocker window is now host-side correlated to brief session connect events followed by heartbeat timeout and `lock_down_queue_win_* file lock not held, offline`.
- Root cause still not fully closed at host-log layer:
  - The earlier `10:57-10:59` gateway rerun window still shows active QMT-side session/account activity for `100`, `101`, and `111`, which does not cleanly explain the simultaneous gateway-side `session_not_ready` result.
- `fail_design` was not proven by this bounded extraction.

## Notes

- This snapshot is intentionally limited to host-log evidence extraction and the two owned documentation files.
- No code, task card, change package, or review files were edited.
- `VAL-002` remains blocked at the environment layer.
- `VAL-003` stays out of scope and must remain blocked.

