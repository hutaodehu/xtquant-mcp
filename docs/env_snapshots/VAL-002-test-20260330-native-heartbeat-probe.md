# EnvSnapshot

Task ID: VAL-002
Date: 2026-03-30T11:45:49.2668393+08:00
Role: test

## Host

- OS: `Microsoft Windows 11 专业工作站版 10.0.26200 (Build 26200, 64 位)`
- Hostname: `CHIYU`
- Shell: `PowerShell 7.6.0`
- Working Directory: `D:\xtquant-mcp\repo`
- EvidencePack: [VAL-002-test-20260330-native-heartbeat-probe.md](../evidence_packs/VAL-002-test-20260330-native-heartbeat-probe.md)

## Runtime

- Python executable: `D:\xtquant-mcp\venv313\Scripts\python.exe`
- Python version: `3.13.12`
- xtquant package root: `D:\xtquant-mcp\vendor\xtquant_250807\xtquant`
- `XtQuantTrader.__init__`: `(self, path, session, callback=None)`
- Trade config path: `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Live userdata root: `D:\lh\国金证券QMT交易端\userdata_mini`

## Process and Port State

- Observation time: `2026-03-30T11:41:01.0184120+08:00`
- `XtMiniQmt`
  - pid `25880`
  - start `2026-03-30T00:32:23.4186077+08:00`
  - path `D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
- `miniquote`
  - pid `20604`
  - start `2026-03-30T00:32:23.6051081+08:00`
  - path `D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe`
- `127.0.0.1:58610`
  - `TcpTestSucceeded=true`

## Gateway Baseline Context

- Baseline reads performed before the native probe:
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json`
- Observed facts:
  - gateway-side login state still reported `ok=true`, `status=already_logged_in`, `qmt_userdata=D:\lh\国金证券QMT交易端\userdata_mini`
  - gateway-side trade session still reported `ready=false`, `reason=session_not_ready`, `session_id=""`

## Candidate Session Selection

- Candidate artifact inventory time: `2026-03-30T11:41:01.0183794+08:00`
- Relevant queue-file mtimes:
  - `down_queue_win_101` -> `2026-03-30T11:16:51.1858945+08:00`
  - `down_queue_win_100` -> `2026-03-30T11:16:48.1548852+08:00`
  - `down_queue_win_111` -> `2026-03-30T10:59:06.3285110+08:00`
- Selection rule used in this run:
  - choose one current active candidate only
  - prefer the freshest observed candidate-session artifact
- Chosen session:
  - `session_id=101`

## Commands Run

1. Environment/process/port baseline:

```powershell
$ErrorActionPreference='Stop'
$ts=Get-Date
$xt=Get-Process -Name XtMiniQmt -ErrorAction Stop | Select-Object Id,ProcessName,StartTime,Path
$mq=Get-Process -Name miniquote -ErrorAction Stop | Select-Object Id,ProcessName,StartTime,Path
$p58610=Test-NetConnection 127.0.0.1 -Port 58610 -WarningAction SilentlyContinue
[ordered]@{
  observed_at=$ts.ToString('o')
  xtmini=$xt
  miniquote=$mq
  port58610=[ordered]@{
    TcpTestSucceeded=$p58610.TcpTestSucceeded
    RemotePort=$p58610.RemotePort
  }
} | ConvertTo-Json -Depth 6
```

2. Runtime introspection:

```powershell
@'
import json, sys, inspect
from pathlib import Path
import xtquant
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
print(json.dumps({
  'python_executable': sys.executable,
  'python_version': sys.version,
  'xtquant_file': getattr(xtquant, '__file__', ''),
  'xtquant_package_dir': str(Path(getattr(xtquant, '__file__', '')).resolve().parent),
  'XtQuantTrader_init': str(inspect.signature(XtQuantTrader.__init__)),
  'XtQuantTraderCallback_methods': sorted([name for name in dir(XtQuantTraderCallback) if name.startswith('on_')])
}, ensure_ascii=False, indent=2))
'@ | D:\xtquant-mcp\venv313\Scripts\python.exe -
```

3. Gateway baseline reads:

```powershell
Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json

Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json
```

4. Probe command family:

```text
Base command body: identical to EvidencePack Command 5.
Probe A constants:
  SESSION_ID = 101
  POST_CONNECT_OBSERVE_SECONDS = 4.0
  PATTERN = "single_instance_single_session_readonly_bounded"
Probe B constants:
  SESSION_ID = 101
  POST_CONNECT_OBSERVE_SECONDS = 10.0
  PATTERN = "single_instance_single_session_readonly_bounded_confirmation"
Probe C constants:
  SESSION_ID = 101
  POST_CONNECT_OBSERVE_SECONDS = 20.0
  PATTERN = "single_instance_single_session_readonly_bounded_final_confirmation"
```

5. Narrow host-log correlation:

```powershell
rg -n "2026-03-30 11:42:3|2026-03-30 11:42:4|2026-03-30 11:43:4|2026-03-30 11:43:5|2026-03-30 11:46:4|2026-03-30 11:46:5|2026-03-30 11:47:0|ssid:101|quant session 101|lock_down_queue_win_101|query accountInfos found|query positions found|query account detail" 'D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log'
```

6. Focused line extraction:

```powershell
$p='D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log'
$lines=Get-Content $p
foreach($r in @(
  @{s=13938;e=13943},
  @{s=13957;e=13962},
  @{s=13990;e=13996}
)){
  "--- $($r.s)-$($r.e) ---"
  for($i=$r.s; $i -le $r.e; $i++){
    '{0}:{1}' -f $i,$lines[$i-1]
  }
}
```

## Time Windows

### Probe A

- Native process lifecycle:
  - `start`: `2026-03-30T11:42:33.399262+08:00` -> `2026-03-30T11:42:33.425793+08:00`
  - `connect`: `2026-03-30T11:42:33.425803+08:00` -> `2026-03-30T11:42:33.426227+08:00`
  - keepalive: `2026-03-30T11:42:33.426238+08:00` -> `2026-03-30T11:42:37.427006+08:00`
  - `stop`: `2026-03-30T11:42:37.427042+08:00` -> `2026-03-30T11:42:37.429504+08:00`
- Host-side correlated lines:
  - `11:42:33,412` -> `onConnected`
  - `11:42:41,068` -> `heartbeat timeout`
  - `11:42:41,068` -> `onDisconnected`
  - `11:42:41,068` -> `lock_down_queue_win_101 file lock not held, offline`
- Stop-to-timeout delta:
  - `3.638s`

### Probe B

- Native process lifecycle:
  - `start`: `2026-03-30T11:43:40.415972+08:00` -> `2026-03-30T11:43:40.443078+08:00`
  - `connect`: `2026-03-30T11:43:40.443094+08:00` -> `2026-03-30T11:43:40.443701+08:00`
  - keepalive: `2026-03-30T11:43:40.443713+08:00` -> `2026-03-30T11:43:50.443847+08:00`
  - `stop`: `2026-03-30T11:43:50.443875+08:00` -> `2026-03-30T11:43:50.445982+08:00`
- Host-side correlated lines:
  - `11:43:40,442` -> `onConnected`
  - `11:43:54,476` -> `heartbeat timeout`
  - `11:43:54,478` -> `onDisconnected`
  - `11:43:54,478` -> `lock_down_queue_win_101 file lock not held, offline`
- Stop-to-timeout delta:
  - `4.032s`

### Probe C

- Native process lifecycle:
  - `start`: `2026-03-30T11:46:45.518169+08:00` -> `2026-03-30T11:46:45.544789+08:00`
  - `connect`: `2026-03-30T11:46:45.544801+08:00` -> `2026-03-30T11:46:45.545399+08:00`
  - keepalive: `2026-03-30T11:46:45.545410+08:00` -> `2026-03-30T11:47:05.546031+08:00`
  - `stop`: `2026-03-30T11:47:05.546068+08:00` -> `2026-03-30T11:47:05.548451+08:00`
- Host-side correlated lines:
  - `11:46:45,537` -> `onConnected`
  - `11:47:09,350` -> `heartbeat timeout`
  - `11:47:09,350` -> `onDisconnected`
  - `11:47:09,350` -> `lock_down_queue_win_101 file lock not held, offline`
- Stop-to-timeout delta:
  - `3.802s`

## File-State Observations

- Before the bounded probe family:
  - `down_queue_win_101` mtime `2026-03-30T11:16:51.1858945+08:00`
  - `down_queue_win_101__mutex` mtime `2026-03-30T03:05:03.6122410+08:00`
  - no `lock_down_queue_win_101` file present in the bounded inventory
- After the last probe:
  - `down_queue_win_101` mtime `2026-03-30T11:46:45.5207461+08:00`
  - `down_queue_win_101__mutex` unchanged
  - no `lock_down_queue_win_101` file present in the bounded inventory

## Host-Log Findings

1. The same selected session `101` did connect on all three native runs.
2. The QMT host log did emit the expected heartbeat/lock-loss group each time.
3. The decisive timing detail is that each timeout/disconnect group occurred only after explicit `trader.stop()`, by about four seconds.
4. No Python callback events were captured in the bounded native process, despite host-side `onConnected` / `onDisconnected` log lines.

## Environment Classification

- This snapshot does not confirm a spontaneous in-process "transient connect then heartbeat/lock loss" failure.
- It does confirm a teardown-correlated host-side pattern:
  - native `connect()` succeeds for `session_id=101`
  - after explicit stop, host logs later emit heartbeat timeout and `file lock not held, offline`
- Therefore:
  - this bounded validation result is `partial`
  - the narrower hypothesis remains unresolved
  - task-level `VAL-002` remains blocked
  - `VAL-003` remains blocked and out of scope

## Notes

- This run stayed read-only.
- No code, task card, change package, or review files were edited.
- Only the owned `EvidencePack` and `EnvSnapshot` paths were written for this task.
