# EvidencePack

Task ID: VAL-002
Role: test
Date: 2026-03-30T11:24:08.7987780+08:00
Acceptance Gate: G3
Conclusion: fail_env

## Env Snapshot

- Link: [VAL-002-test-20260330-official-checklist.md](../env_snapshots/VAL-002-test-20260330-official-checklist.md)
- Host: `CHIYU`
- Shell: `PowerShell 7.6.0`
- Repo Working Directory: `D:\xtquant-mcp\repo`
- Task Card: [VAL-002.md](../task_cards/VAL-002.md)
- Change Package: [VAL-002.md](../change_packages/VAL-002.md)
- Related live baselines:
  - [VAL-002-test-20260330-full-postpatch-rerun.md](./VAL-002-test-20260330-full-postpatch-rerun.md)
  - [VAL-002-review-20260330-full-postpatch-rerun.md](../reviews/VAL-002-review-20260330-full-postpatch-rerun.md)

## Scope

This is a bounded official-checklist environment investigation only. It does not rerun the full live `G3` read-only chain and does not modify code, task cards, change packages, or reviews.

Checklist context used in this run was the user-provided official FAQ subset for `xttrader connect=-1` after login is already recovered:

1. confirm the configured `userdata` path is correct
2. confirm the path is not on `C:` and is writable
3. confirm `up_queue_xtquant` exists
4. inspect artifacts relevant to trying different `session_id`s
5. do not guess about `极简模式登录` if it cannot be directly evidenced

## Test Scope

1. Confirm current login-recovered state from live repo state files.
2. Confirm `userdata_mini` path facts from config and filesystem.
3. Run one bounded create/delete probe inside `D:\lh\国金证券QMT交易端\userdata_mini`.
4. Inspect `up_queue_xtquant` and related queue/session artifacts in read-only mode.
5. Record candidate-session artifact counts and mtimes for `100`, `101`, and `111` without cleanup.

## Commands

1. Current login/session baseline:

```powershell
$ErrorActionPreference='Stop'
$login='D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json'
$session='D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json'
$probe='D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json'
[ordered]@{
  observed_at=(Get-Date).ToString('o')
  diag_login_latest=(Get-Content $login -Raw | ConvertFrom-Json)
  trade_session_current=(Get-Content $session -Raw | ConvertFrom-Json)
  diag_probe_latest=(Get-Content $probe -Raw | ConvertFrom-Json)
} | ConvertTo-Json -Depth 8
```

2. Config path and live `userdata_mini` facts:

```powershell
$ErrorActionPreference='Stop'
$cfg='D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml'
$userdata='D:\lh\国金证券QMT交易端\userdata_mini'
$cfgHits = Select-String -Path $cfg -Pattern 'userdata|mini' | ForEach-Object {
  [ordered]@{ line=$_.LineNumber; text=$_.Line.Trim() }
}
$resolved = Resolve-Path -LiteralPath $userdata
$item = Get-Item -LiteralPath $userdata -Force
[ordered]@{
  observed_at=(Get-Date).ToString('o')
  config_path=$cfg
  config_hits=$cfgHits
  userdata=[ordered]@{
    literal=$userdata
    resolved=$resolved.Path
    exists=Test-Path -LiteralPath $userdata
    psdrive=$item.PSDrive.Name
    root=$item.PSDrive.Root
    is_on_c_drive=($resolved.Path -like 'C:*')
    item_type=if($item.PSIsContainer){'directory'}else{'file'}
    last_write_time=$item.LastWriteTime.ToString('o')
  }
} | ConvertTo-Json -Depth 6
```

3. Bounded writeability probe:

```powershell
$ErrorActionPreference='Stop'
$userdata='D:\lh\国金证券QMT交易端\userdata_mini'
$probe=Join-Path $userdata 'codex_val002_write_probe_20260330.txt'
if (Test-Path -LiteralPath $probe) { throw "Probe file already exists: $probe" }
$before=(Get-Date)
"VAL-002 official checklist bounded write probe $(Get-Date -Format o)" | Set-Content -LiteralPath $probe -Encoding UTF8
$afterCreate=(Get-Date)
$file=Get-Item -LiteralPath $probe -Force
$createResult=[ordered]@{
  started_at=$before.ToString('o')
  finished_at=$afterCreate.ToString('o')
  path=$probe
  exists_after_create=Test-Path -LiteralPath $probe
  length=$file.Length
  last_write_time=$file.LastWriteTime.ToString('o')
  attributes=[string]$file.Attributes
}
Remove-Item -LiteralPath $probe -Force
$afterDelete=(Get-Date)
[ordered]@{
  observed_at=$afterDelete.ToString('o')
  create=$createResult
  delete=[ordered]@{
    started_at=$afterCreate.ToString('o')
    finished_at=$afterDelete.ToString('o')
    path=$probe
    exists_after_delete=Test-Path -LiteralPath $probe
  }
} | ConvertTo-Json -Depth 6
```

4. Top-level `userdata_mini` inventory:

```powershell
$ErrorActionPreference='Stop'
$userdata='D:\lh\国金证券QMT交易端\userdata_mini'
Get-ChildItem -LiteralPath $userdata -Force |
  Select-Object Mode,LastWriteTime,Length,Name,FullName |
  Format-Table -AutoSize
```

5. Queue/session-related files:

```powershell
$ErrorActionPreference='Stop'
$userdata='D:\lh\国金证券QMT交易端\userdata_mini'
Get-ChildItem -LiteralPath $userdata -Force -Recurse -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match 'up_queue_xtquant|queue|session' } |
  Select-Object FullName,Name,PSIsContainer,LastWriteTime,Length |
  Sort-Object FullName |
  Format-Table -AutoSize
```

6. Focused queue/session artifact summary:

```powershell
$ErrorActionPreference='Stop'
$userdata='D:\lh\国金证券QMT交易端\userdata_mini'
$names = @(
  'up_queue_xtquant',
  'up_queue_xtquant__mutex',
  'lock_up_queue_xtquant',
  'up_queue_win_xtquant',
  'up_queue_win_xtquant__mutex',
  'lock_up_queue_win_xtquant',
  'down_queue_win_100',
  'down_queue_win_100__mutex',
  'down_queue_win_101',
  'down_queue_win_101__mutex',
  'down_queue_win_111',
  'down_queue_win_111__mutex',
  'lock_down_queue_win_111'
)
$rows = foreach($name in $names){
  $p = Join-Path $userdata $name
  if(Test-Path -LiteralPath $p){
    $it = Get-Item -LiteralPath $p -Force
    [ordered]@{
      name=$name
      exists=$true
      length=$it.Length
      last_write_time=$it.LastWriteTime.ToString('o')
      attributes=[string]$it.Attributes
    }
  } else {
    [ordered]@{
      name=$name
      exists=$false
      length=$null
      last_write_time=$null
      attributes=$null
    }
  }
}
[ordered]@{
  observed_at=(Get-Date).ToString('o')
  files=$rows
} | ConvertTo-Json -Depth 5
```

7. Candidate-session artifact counts for `100/101/111`:

```powershell
$ErrorActionPreference='Stop'
$userdata='D:\lh\国金证券QMT交易端\userdata_mini'
$sessions=@(100,101,111)
$result = foreach($sid in $sessions){
  $items = Get-ChildItem -LiteralPath $userdata -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match "(^|_)$sid($|_)" }
  [ordered]@{
    session_id=$sid
    count=$items.Count
    files=@(
      $items | Sort-Object Name | ForEach-Object {
        [ordered]@{
          name=$_.Name
          length=$_.Length
          last_write_time=$_.LastWriteTime.ToString('o')
        }
      }
    )
  }
}
[ordered]@{
  observed_at=(Get-Date).ToString('o')
  session_artifacts=$result
} | ConvertTo-Json -Depth 8
```

## Raw Results

### 1. Login is already recovered, but live session is still not ready

- Observation time: `2026-03-30T11:23:43.0315502+08:00`
- `diag_login_latest.json`
  - `ok=true`
  - `status=already_logged_in`
  - `message=MiniQMT already logged in`
  - `qmt_userdata=D:\lh\国金证券QMT交易端\userdata_mini`
  - `port_ready=true`
- `trade_session_current.json`
  - `ready=false`
  - `reason=session_not_ready`
  - `owner_generation=0`
- This matches the intended investigation posture:
  - login recovery is already evidenced
  - the remaining problem space is the post-login `session_not_ready` / `xttrader connect=-1` environment path

### 2. `userdata_mini` path is correct and not on `C:`

- Observation time: `2026-03-30T11:22:30.9257460+08:00`
- Config file: `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Matching config entries observed:
  - line `25`: `qmt_userdata: D:\lh\国金证券QMT交易端\userdata_mini`
  - line `52`: `qmt_userdata: D:\lh\国金证券QMT交易端\userdata_mini`
  - line `86`: `qmt_userdata: D:\lh\国金证券QMT交易端\userdata_mini`
- Filesystem facts:
  - `resolved=D:\lh\国金证券QMT交易端\userdata_mini`
  - `exists=true`
  - `psdrive=D`
  - `root=D:\`
  - `is_on_c_drive=false`
  - `item_type=directory`

### 3. Bounded writeability probe succeeded

- Observation time: `2026-03-30T11:22:43.4289984+08:00`
- Probe file path:
  - `D:\lh\国金证券QMT交易端\userdata_mini\codex_val002_write_probe_20260330.txt`
- Create phase:
  - started: `2026-03-30T11:22:43.4148872+08:00`
  - finished: `2026-03-30T11:22:43.4208646+08:00`
  - `exists_after_create=true`
  - `length=82`
  - `last_write_time=2026-03-30T11:22:43.4206289+08:00`
- Delete phase:
  - started: `2026-03-30T11:22:43.4208646+08:00`
  - finished: `2026-03-30T11:22:43.4289984+08:00`
  - `exists_after_delete=false`
- Result:
  - the official FAQ-style bounded create/delete test succeeded
  - no residual probe file remained after the test

### 4. `up_queue_xtquant` exists

- Observation time: `2026-03-30T11:23:24.4647100+08:00`
- Focused file states:
  - `up_queue_xtquant`
    - `exists=true`
    - `length=75497752`
    - `last_write_time=2026-03-30T00:32:24.7416471+08:00`
  - `up_queue_xtquant__mutex`
    - `exists=true`
    - `length=0`
    - `last_write_time=2026-03-30T00:32:24.7624462+08:00`
  - `lock_up_queue_xtquant`
    - `exists=true`
    - `length=0`
    - `last_write_time=2026-03-30T00:32:24.7624462+08:00`
  - `up_queue_win_xtquant`
    - `exists=true`
    - `length=75497752`
    - `last_write_time=2026-03-30T00:32:24.7644484+08:00`
- This clears the narrow FAQ item "existence of `up_queue_xtquant`" for the current `userdata_mini`.

### 5. Candidate-session queue artifacts exist for `100/101/111`

- Observation time: `2026-03-30T11:23:43.2165990+08:00`
- `session_id=100`
  - artifact count: `2`
  - `down_queue_win_100`, mtime `2026-03-30T11:16:48.1548852+08:00`, length `75497752`
  - `down_queue_win_100__mutex`, mtime `2026-03-30T03:04:48.2607086+08:00`, length `0`
- `session_id=101`
  - artifact count: `2`
  - `down_queue_win_101`, mtime `2026-03-30T11:16:51.1858945+08:00`, length `75497752`
  - `down_queue_win_101__mutex`, mtime `2026-03-30T03:05:03.6122410+08:00`, length `0`
- `session_id=111`
  - artifact count: `3`
  - `down_queue_win_111`, mtime `2026-03-30T10:59:06.3285110+08:00`, length `75497752`
  - `down_queue_win_111__mutex`, mtime `2026-03-30T03:05:33.8614918+08:00`, length `0`
  - `lock_down_queue_win_111`, mtime `2026-03-30T10:58:24.0387995+08:00`, length `0`
- Interpretation boundary:
  - this run records hard artifact presence for the configured candidate ids
  - this run did not actively retry native `connect()` with alternate `session_id`s
  - therefore the FAQ action "try different session ids" is only artifact-correlated here, not re-executed end-to-end in this bounded run

## Official Checklist Mapping

| Official checklist item | Evidence in this run | Status |
| --- | --- | --- |
| Correct `userdata` path | Config lines `25/52/86` all point to `D:\lh\国金证券QMT交易端\userdata_mini`, and the directory resolves/exist on disk | evidenced |
| Not on `C:` | `psdrive=D`, `root=D:\`, `is_on_c_drive=false` | evidenced |
| Writable / permission OK | bounded create/delete probe succeeded with exact timestamps and cleanup | evidenced |
| `up_queue_xtquant` exists | `up_queue_xtquant`, mutex, and lock files are present in `userdata_mini` | evidenced |
| Try different `session_id`s | config still carries `100/101/111`; corresponding queue files exist and have fresh mtimes | partial_only |
| `极简模式登录` | no direct observable artifact or explicit runtime flag was inspected in this bounded run | unresolved |

## Artifact Refs

- Live config:
  - `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Live state:
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json`
- Live userdata root:
  - `D:\lh\国金证券QMT交易端\userdata_mini`
- Formal docs:
  - [VAL-002-test-20260330-official-checklist.md](./VAL-002-test-20260330-official-checklist.md)
  - [VAL-002-test-20260330-official-checklist.md](../env_snapshots/VAL-002-test-20260330-official-checklist.md)

## Verdict

`fail_env`.

This bounded official-checklist investigation does not support path misconfiguration, `C:` drive placement, missing write permission, or missing `up_queue_xtquant` as the current primary cause. Login is already recovered, yet the task remains environment-blocked because the broader live `VAL-002` baseline still ends at post-login `session_not_ready` / `xttrader connect=-1`, and this bounded run did not produce a successful owner-managed trade session. The checklist item "try different session ids" is only partially evidenced here through config plus queue artifacts for `100/101/111`; `极简模式登录` remains unresolved because it was not directly observable.
