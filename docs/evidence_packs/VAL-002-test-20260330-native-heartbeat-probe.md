# EvidencePack

Task ID: VAL-002
Role: test
Date: 2026-03-30T11:45:49.2668393+08:00
Acceptance Gate: G3
Conclusion: partial

## Env Snapshot

- Link: [VAL-002-test-20260330-native-heartbeat-probe.md](../env_snapshots/VAL-002-test-20260330-native-heartbeat-probe.md)
- Host: `CHIYU`
- Shell: `PowerShell 7.6.0`
- Repo Working Directory: `D:\xtquant-mcp\repo`
- Runtime:
  - Python: `D:\xtquant-mcp\venv313\Scripts\python.exe`
  - xtquant package: `D:\xtquant-mcp\vendor\xtquant_250807\xtquant`
  - userdata: `D:\lh\国金证券QMT交易端\userdata_mini`

## Goal and Scope

1. Validate whether the remaining native broker/session issue currently looks like a short-lived connect followed by heartbeat/lock loss.
2. Keep the probe read-only and bounded to one currently active candidate session.
3. Record exact native timings, callback visibility, process survival window, and narrow host-log correlation.

## Session Selection

- Current candidate-session file state at `2026-03-30T11:41:01.0183794+08:00` showed:
  - `down_queue_win_101` last write `2026-03-30T11:16:51.1858945+08:00`
  - `down_queue_win_100` last write `2026-03-30T11:16:48.1548852+08:00`
  - `down_queue_win_111` last write `2026-03-30T10:59:06.3285110+08:00`
- This bounded run therefore selected only `session_id=101` as the freshest active candidate.
- No second session id was introduced in this pack.

## Commands

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

2. Candidate-session artifact inventory before probing:

```powershell
$ts=Get-Date
$root='D:\lh\国金证券QMT交易端\userdata_mini'
$files=Get-ChildItem $root -File |
  Where-Object {
    $_.Name -match '^(down_queue_win_(\d+)|lock_down_queue_win_(\d+)|down_queue_win_(\d+)__mutex|up_queue(_win)?_xtquant|lock_up_queue(_win)?_xtquant|up_queue(_win)?_xtquant__mutex)$'
  } |
  Sort-Object LastWriteTime -Descending |
  Select-Object Name,Length,LastWriteTime
[ordered]@{
  observed_at=$ts.ToString('o')
  root=$root
  files=$files
} | ConvertTo-Json -Depth 6
```

3. Repo-configured Python and xtquant runtime introspection:

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

4. Gateway-side login/session baseline read:

```powershell
Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json

Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json
```

5. Probe A, `session_id=101`, 4-second keepalive after `connect()`:

```powershell
@'
import json
import os
import time
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback

TZ = timezone(timedelta(hours=8))
USERDATA = r"D:\lh\国金证券QMT交易端\userdata_mini"
SESSION_ID = 101
POST_CONNECT_OBSERVE_SECONDS = 4.0
PATTERN = "single_instance_single_session_readonly_bounded"

def now():
    return datetime.now(TZ).isoformat()

def safe_get(obj, *names):
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj.get(name)
        if hasattr(obj, name):
            return getattr(obj, name)
    return None

class Callback(XtQuantTraderCallback):
    def __init__(self):
        super().__init__()
        self.events = []

    def _push(self, event, payload=None):
        row = {'ts': now(), 'event': event}
        if payload is not None:
            row['payload'] = payload
        self.events.append(row)

    def on_connected(self):
        self._push('on_connected')

    def on_disconnected(self):
        self._push('on_disconnected')

    def on_account_status(self, status):
        self._push('on_account_status', {
            'account_id': str(safe_get(status, 'account_id', 'accountId') or ''),
            'account_type': safe_get(status, 'account_type', 'accountType'),
            'status': safe_get(status, 'status'),
        })

report = {
    'observed_at': now(),
    'python_pid': os.getpid(),
    'python_executable': os.path.abspath(__import__('sys').executable),
    'userdata': USERDATA,
    'session_id': SESSION_ID,
    'pattern': PATTERN,
    'post_connect_observe_seconds': POST_CONNECT_OBSERVE_SECONDS,
    'steps': [],
    'callback_events': [],
}
cb = Callback()
trader = XtQuantTrader(str(Path(USERDATA)), int(SESSION_ID), cb)
try:
    started = now()
    trader.start()
    report['steps'].append({
        'step': 'start',
        'started_at': started,
        'finished_at': now(),
        'ok': True,
    })

    t0 = time.perf_counter()
    connect_started = now()
    connect_code = int(trader.connect())
    connect_finished = now()
    report['connect_code'] = connect_code
    report['steps'].append({
        'step': 'connect',
        'started_at': connect_started,
        'finished_at': connect_finished,
        'duration_ms': int((time.perf_counter() - t0) * 1000),
        'ok': connect_code == 0,
        'connect_code': connect_code,
    })

    observe_started = now()
    time.sleep(POST_CONNECT_OBSERVE_SECONDS)
    report['steps'].append({
        'step': 'post_connect_observe',
        'started_at': observe_started,
        'finished_at': now(),
        'duration_ms': int(POST_CONNECT_OBSERVE_SECONDS * 1000),
        'ok': True,
        'note': 'kept native process alive after connect return to capture short callback window if any',
    })

    report['result'] = 'connect_ok' if connect_code == 0 else 'connect_failed'
except Exception as exc:
    report['result'] = 'script_exception'
    report['exception_type'] = type(exc).__name__
    report['exception'] = str(exc)
    report['traceback'] = traceback.format_exc()
finally:
    report['callback_events'] = list(cb.events)
    stop_started = now()
    try:
        trader.stop()
        report['steps'].append({
            'step': 'stop',
            'started_at': stop_started,
            'finished_at': now(),
            'ok': True,
        })
    except Exception as exc:
        report['steps'].append({
            'step': 'stop',
            'started_at': stop_started,
            'finished_at': now(),
            'ok': False,
            'exception_type': type(exc).__name__,
            'exception': str(exc),
        })
    report['finished_at'] = now()

print(json.dumps(report, ensure_ascii=False, indent=2))
'@ | D:\xtquant-mcp\venv313\Scripts\python.exe -
```

6. Probe B reused the same command body as Command 5 with only these exact changes:

```text
POST_CONNECT_OBSERVE_SECONDS = 10.0
PATTERN = "single_instance_single_session_readonly_bounded_confirmation"
```

7. Probe C reused the same command body as Command 5 with only these exact changes:

```text
POST_CONNECT_OBSERVE_SECONDS = 20.0
PATTERN = "single_instance_single_session_readonly_bounded_final_confirmation"
```

8. Post-probe artifact check for `session_id=101`:

```powershell
$sid=101
$root='D:\lh\国金证券QMT交易端\userdata_mini'
$ts=Get-Date
$files=Get-ChildItem $root -File |
  Where-Object { $_.Name -match "^(down_queue_win_${sid}|down_queue_win_${sid}__mutex|lock_down_queue_win_${sid})$" } |
  Sort-Object Name |
  Select-Object Name,Length,LastWriteTime
[ordered]@{
  observed_at=$ts.ToString('o')
  session_id=$sid
  files=$files
} | ConvertTo-Json -Depth 5
```

9. Narrow host-log correlation:

```powershell
rg -n "2026-03-30 11:42:3|2026-03-30 11:42:4|2026-03-30 11:43:4|2026-03-30 11:43:5|2026-03-30 11:46:4|2026-03-30 11:46:5|2026-03-30 11:47:0|ssid:101|quant session 101|lock_down_queue_win_101|query accountInfos found|query positions found|query account detail" 'D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log'
```

10. Focused line extraction for the three probe windows:

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

## Raw Results

### A. Baseline and runtime facts

- Process/port baseline at `2026-03-30T11:41:01.0184120+08:00`:
  - `XtMiniQmt` pid `25880`, start `2026-03-30T00:32:23.4186077+08:00`
  - `miniquote` pid `20604`, start `2026-03-30T00:32:23.6051081+08:00`
  - `127.0.0.1:58610` -> `TcpTestSucceeded=true`
- Repo runtime:
  - Python executable `D:\xtquant-mcp\venv313\Scripts\python.exe`
  - Python version `3.13.12`
  - `xtquant` package file `D:\xtquant-mcp\vendor\xtquant_250807\xtquant\__init__.py`
  - `XtQuantTrader.__init__` signature `(self, path, session, callback=None)`
- Gateway-side same-window baseline before probing:
  - `diag_login_latest.json` still reported `ok=true`, `status=already_logged_in`, `qmt_userdata=D:\lh\国金证券QMT交易端\userdata_mini`, `port_ready=true`
  - `trade_session_current.json` still reported `ready=false`, `reason=session_not_ready`, `session_id=""`

### B. Probe A, 4-second keepalive

- Native report:
  - observed at `2026-03-30T11:42:33.383472+08:00`
  - `start`: `11:42:33.399262` -> `11:42:33.425793`
  - `connect`: `11:42:33.425803` -> `11:42:33.426227`
  - `connect_code=0`
  - keepalive window: `11:42:33.426238` -> `11:42:37.427006`
  - `stop`: `11:42:37.427042` -> `11:42:37.429504`
  - callback events observed: none
- Host log correlation:

```text
13940:2026-03-30 11:42:33,412 ... onConnected] quant session 101 connected
13941:2026-03-30 11:42:41,068 ... heartbeat timeout, ssid:101, hsz:4
13942:2026-03-30 11:42:41,068 ... onDisconnected] quant session 101 disconneted
13943:2026-03-30 11:42:41,068 ... lock_down_queue_win_101 file lock not held, offline
```

- Timing implication:
  - host-side timeout/disconnect landed `3.638s` after probe stop
  - this first keepalive was not long enough to determine whether the disconnect would also have happened while the process was still alive

### C. Probe B, 10-second keepalive

- Native report:
  - observed at `2026-03-30T11:43:40.401440+08:00`
  - `start`: `11:43:40.415972` -> `11:43:40.443078`
  - `connect`: `11:43:40.443094` -> `11:43:40.443701`
  - `connect_code=0`
  - keepalive window: `11:43:40.443713` -> `11:43:50.443847`
  - `stop`: `11:43:50.443875` -> `11:43:50.445982`
  - callback events observed: none
- Host log correlation:

```text
13959:2026-03-30 11:43:40,442 ... onConnected] quant session 101 connected
13960:2026-03-30 11:43:54,476 ... heartbeat timeout, ssid:101, hsz:4
13961:2026-03-30 11:43:54,478 ... onDisconnected] quant session 101 disconneted
13962:2026-03-30 11:43:54,478 ... lock_down_queue_win_101 file lock not held, offline
```

- Timing implication:
  - host-side timeout/disconnect landed `4.032s` after probe stop
  - the second keepalive still did not show the loss while the process was alive

### D. Probe C, 20-second keepalive

- Native report:
  - observed at `2026-03-30T11:46:45.502916+08:00`
  - `start`: `11:46:45.518169` -> `11:46:45.544789`
  - `connect`: `11:46:45.544801` -> `11:46:45.545399`
  - `connect_code=0`
  - keepalive window: `11:46:45.545410` -> `11:47:05.546031`
  - `stop`: `11:47:05.546068` -> `11:47:05.548451`
  - callback events observed: none
- Host log correlation:

```text
13992:2026-03-30 11:46:45,537 ... onConnected] quant session 101 connected
13993:2026-03-30 11:47:09,350 ... heartbeat timeout, ssid:101, hsz:4
13994:2026-03-30 11:47:09,350 ... onDisconnected] quant session 101 disconneted
13995:2026-03-30 11:47:09,350 ... lock_down_queue_win_101 file lock not held, offline
```

- Timing implication:
  - host-side timeout/disconnect landed `3.802s` after probe stop
  - even the 20-second keepalive did not reproduce the disconnect before explicit stop

### E. Queue-file observations

- Before probing, `session_id=101` file state at `2026-03-30T11:41:43.1020699+08:00`:
  - `down_queue_win_101` mtime `2026-03-30T11:16:51.1858945+08:00`
  - `down_queue_win_101__mutex` mtime `2026-03-30T03:05:03.6122410+08:00`
  - no `lock_down_queue_win_101` file present in the bounded inventory
- After the last probe, `session_id=101` file state at `2026-03-30T11:47:31.0263428+08:00`:
  - `down_queue_win_101` mtime advanced to `2026-03-30T11:46:45.5207461+08:00`
  - `down_queue_win_101__mutex` mtime unchanged
  - no `lock_down_queue_win_101` file present in the bounded inventory

### F. Callback/event-sink observation

- Across all three native runs:
  - `connect_code` was `0`
  - the Python callback sink recorded no `on_connected`, `on_disconnected`, or `on_account_status` events
- For this bounded probe, the definitive lifecycle evidence came from host-side QMT logs rather than Python callback delivery.

## Interpretation

1. The current native path did run successfully in the repo-configured environment.
2. In this bounded same-session window, the remaining native issue did not reproduce as `connect() == -1`.
3. Host logs do still show the sequence:
   - `onConnected`
   - `heartbeat timeout`
   - `onDisconnected`
   - `lock_down_queue_win_101 file lock not held, offline`
4. However, all three host-side timeout/disconnect events aligned to roughly `3.6s` to `4.0s` after explicit `trader.stop()`, not during the native keepalive window.
5. Therefore this pack does not confirm a spontaneous "transient connect then heartbeat/lock loss while the probe remains alive" pattern.
6. It leaves that specific hypothesis unresolved, while showing a narrower teardown-correlated pattern:
   - native `connect()` can succeed for `session_id=101`
   - after explicit stop, QMT logs later report heartbeat timeout and file-lock-not-held offline for that session

## Failure Classification

- `partial`
  - this bounded test produced useful narrowing evidence
  - it did not prove the targeted spontaneous heartbeat/lock-loss hypothesis
- `fail_env`
  - not re-proven by this exact native window
  - earlier same-day `VAL-002` evidence remains environment-blocked, but this pack itself is a narrowing probe rather than a fresh `connect=-1` reproduction
- `fail_design`
  - not established
- `blocked`
  - `VAL-002` remains blocked at task level
  - `VAL-003` must remain blocked and out of scope

## Verdict

`partial`.

This bounded native heartbeat/lock probe did run successfully in the repo-configured `venv313` / `xtquant` environment against `userdata_mini`, and it used only one selected active candidate session: `101`.

The current finding is narrower than the original suspicion. In this run, native `XtQuantTrader.connect()` returned `0` three times, so the remaining native broker/session issue did not reproduce as an immediate connect failure. Host-side QMT logs still showed `onConnected -> heartbeat timeout -> onDisconnected -> lock_down_queue_win_101 file lock not held, offline`, but all three such events landed only after explicit `trader.stop()`, by roughly four seconds.

So this pack does not confirm a spontaneous "transient connect then heartbeat/lock loss" pattern while the native probe remains alive. It leaves that hypothesis unresolved and instead supports a teardown-correlated heartbeat/lock-release observation. `VAL-002` remains blocked, and this pack must not be used to unblock `VAL-003`.
