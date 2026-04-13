# EvidencePack

Task ID: VAL-002
Role: test
Date: 2026-03-30T11:58:00+08:00
Acceptance Gate: G3
Conclusion: partial

## Env Snapshot

- Link: [VAL-002-test-20260330-native-query-chain.md](../env_snapshots/VAL-002-test-20260330-native-query-chain.md)
- Host: `CHIYU`
- Shell: `PowerShell 7.6.0`
- Repo Working Directory: `D:\xtquant-mcp\repo`
- Runtime:
  - Python: `D:\xtquant-mcp\venv313\Scripts\python.exe`
  - xtquant package: `D:\xtquant-mcp\vendor\xtquant_250807\xtquant`
  - userdata: `D:\lh\国金证券QMT交易端\userdata_mini`
- TaskCard: [VAL-002.md](../task_cards/VAL-002.md)
- ChangePack: [VAL-002.md](../change_packages/VAL-002.md)
- Prior comparison:
  - [VAL-002-test-20260330-native-heartbeat-probe.md](./VAL-002-test-20260330-native-heartbeat-probe.md)
  - [VAL-002-test-20260330-broker-session-native-probe.md](./VAL-002-test-20260330-broker-session-native-probe.md)

## Goal and Scope

1. Determine how far one native `XtQuantTrader` instance can progress in one lifecycle now that bounded native `connect()` on `session_id=101` has already been observed as successful.
2. Keep the run read-only and bounded to one session candidate only.
3. Execute the closest safe native query chain available in one lifecycle:
   - `connect`
   - `query_account_infos`
   - `subscribe`
   - `query_stock_asset`
   - `query_stock_positions`
   - `query_stock_orders`
4. Record exact timestamps, callback events if any, return values, exceptions, and whether `orders` is the first failure point.

## Session Selection

- Repo trade config still declares:
  - `trade.session_id = 100`
  - `trade.session_candidates = [100, 101, 111]`
- Current queue-file inventory at `2026-03-30T11:55:31.1772665+08:00` showed:
  - `down_queue_win_101` mtime `2026-03-30T11:46:45.5207461+08:00`
  - `down_queue_win_100` mtime `2026-03-30T11:16:48.1548852+08:00`
  - `down_queue_win_111` mtime `2026-03-30T10:59:06.3285110+08:00`
- Because same-day bounded native evidence had already shown `session_id=101` as the freshest successful connect candidate, this run used only `session_id=101`.
- No second session id was introduced in this pack.

## Commands

1. Process and port baseline:

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

2. Repo trade config and gateway baseline reads:

```powershell
Get-Content D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml

Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json

Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json
```

3. Candidate queue-file inventory:

```powershell
$root='D:\lh\国金证券QMT交易端\userdata_mini'
$ts=Get-Date
$files=Get-ChildItem $root -File |
  Where-Object { $_.Name -match '^(down_queue_win_(\d+)|lock_down_queue_win_(\d+)|down_queue_win_(\d+)__mutex)$' } |
  Sort-Object LastWriteTime -Descending |
  Select-Object Name,Length,LastWriteTime
[ordered]@{
  observed_at=$ts.ToString('o')
  root=$root
  files=$files
} | ConvertTo-Json -Depth 6
```

4. One-off native read-only query chain on a single `XtQuantTrader` lifecycle:

```powershell
@'
import json
import os
import time
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

import xtquant
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant.xttype import StockAccount

TZ = timezone(timedelta(hours=8))
USERDATA = r"D:\lh\国金证券QMT交易端\userdata_mini"
SESSION_ID = 101
SETTLE_SECONDS = 1.0
PATTERN = "single_instance_single_lifecycle_native_query_chain"

def now():
    return datetime.now(TZ).isoformat()

def safe_get(obj, *names):
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj.get(name)
        if hasattr(obj, name):
            return getattr(obj, name)
    return None

def summarize_account_infos(rows):
    out = []
    for row in rows or []:
        out.append({
            'account_id': str(safe_get(row, 'account_id', 'accountId', 'account') or ''),
            'account_type': safe_get(row, 'account_type', 'accountType', 'broker_type', 'type'),
            'broker_type': safe_get(row, 'broker_type', 'brokerType'),
            'status': safe_get(row, 'status', 'login_status', 'loginStatus'),
            'raw_type': type(row).__name__,
        })
    return out

def summarize_asset(row):
    if row is None:
        return None
    return {
        'account_id': str(safe_get(row, 'account_id', 'accountId') or ''),
        'cash': safe_get(row, 'cash', 'm_dCash'),
        'frozen_cash': safe_get(row, 'frozen_cash', 'frozenCash'),
        'market_value': safe_get(row, 'market_value', 'marketValue'),
        'total_asset': safe_get(row, 'total_asset', 'totalAsset'),
        'raw_type': type(row).__name__,
    }

def summarize_positions(rows):
    out = []
    for row in rows or []:
        out.append({
            'stock_code': str(safe_get(row, 'stock_code', 'stockCode', 'instrument_id') or ''),
            'volume': safe_get(row, 'volume', 'm_nVolume'),
            'can_use_volume': safe_get(row, 'can_use_volume', 'canUseVolume'),
            'market_value': safe_get(row, 'market_value', 'marketValue'),
            'raw_type': type(row).__name__,
        })
    return out

def summarize_orders(rows):
    out = []
    for row in rows or []:
        out.append({
            'order_id': safe_get(row, 'order_id', 'orderId'),
            'stock_code': str(safe_get(row, 'stock_code', 'stockCode') or ''),
            'order_status': safe_get(row, 'order_status', 'orderStatus', 'status'),
            'order_volume': safe_get(row, 'order_volume', 'orderVolume', 'volume'),
            'order_time': safe_get(row, 'order_time', 'orderTime'),
            'raw_type': type(row).__name__,
        })
    return out

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
            'raw_type': type(status).__name__,
        })

report = {
    'observed_at': now(),
    'pattern': PATTERN,
    'python_pid': os.getpid(),
    'python_executable': os.path.abspath(__import__('sys').executable),
    'xtquant_file': getattr(xtquant, '__file__', ''),
    'userdata': USERDATA,
    'session_id': SESSION_ID,
    'settle_seconds': SETTLE_SECONDS,
    'steps': [],
    'callback_events': [],
}
cb = Callback()
trader = XtQuantTrader(str(Path(USERDATA)), int(SESSION_ID), cb)
selected_account = None
first_failure_step = None
try:
    t0 = time.perf_counter()
    started = now()
    trader.start()
    report['steps'].append({
        'step': 'start',
        'started_at': started,
        'finished_at': now(),
        'duration_ms': int((time.perf_counter() - t0) * 1000),
        'ok': True,
    })

    t1 = time.perf_counter()
    started = now()
    connect_code = int(trader.connect())
    report['connect_code'] = connect_code
    report['steps'].append({
        'step': 'connect',
        'started_at': started,
        'finished_at': now(),
        'duration_ms': int((time.perf_counter() - t1) * 1000),
        'ok': connect_code == 0,
        'connect_code': connect_code,
    })
    if connect_code != 0:
        first_failure_step = 'connect'
        report['result'] = 'connect_failed'
    else:
        time.sleep(SETTLE_SECONDS)
        report['steps'].append({
            'step': 'post_connect_settle',
            'started_at': started,
            'finished_at': now(),
            'duration_ms': int(SETTLE_SECONDS * 1000),
            'ok': True,
            'note': 'bounded settle before first query',
        })

        t2 = time.perf_counter()
        s2 = now()
        infos = trader.query_account_infos() or []
        summarized_infos = summarize_account_infos(infos)
        report['steps'].append({
            'step': 'query_account_infos',
            'started_at': s2,
            'finished_at': now(),
            'duration_ms': int((time.perf_counter() - t2) * 1000),
            'ok': True,
            'count': len(summarized_infos),
            'account_infos': summarized_infos,
        })
        if summarized_infos:
            selected_account_id = next((row['account_id'] for row in summarized_infos if row.get('account_id')), '')
            if selected_account_id:
                selected_account = StockAccount(str(selected_account_id), 'STOCK')
                report['selected_account_id'] = str(selected_account_id)
            else:
                first_failure_step = 'query_account_infos'
                report['result'] = 'query_account_infos_no_account_id'
        else:
            first_failure_step = 'query_account_infos'
            report['result'] = 'query_account_infos_empty'

        if selected_account is not None:
            t3 = time.perf_counter()
            s3 = now()
            subscribe_code = int(trader.subscribe(selected_account))
            report['subscribe_code'] = subscribe_code
            report['steps'].append({
                'step': 'subscribe',
                'started_at': s3,
                'finished_at': now(),
                'duration_ms': int((time.perf_counter() - t3) * 1000),
                'ok': subscribe_code == 0,
                'subscribe_code': subscribe_code,
            })
            if subscribe_code != 0:
                first_failure_step = 'subscribe'
                report['result'] = 'subscribe_failed'
            else:
                time.sleep(SETTLE_SECONDS)
                report['steps'].append({
                    'step': 'post_subscribe_settle',
                    'started_at': s3,
                    'finished_at': now(),
                    'duration_ms': int(SETTLE_SECONDS * 1000),
                    'ok': True,
                    'note': 'bounded settle before readonly account/position/order queries',
                })

                for step_name, fn, summarize in [
                    ('query_stock_asset', lambda: trader.query_stock_asset(selected_account), summarize_asset),
                    ('query_stock_positions', lambda: trader.query_stock_positions(selected_account) or [], summarize_positions),
                    ('query_stock_orders', lambda: trader.query_stock_orders(selected_account, False) or [], summarize_orders),
                ]:
                    t_step = time.perf_counter()
                    s_step = now()
                    try:
                        payload = fn()
                        entry = {
                            'step': step_name,
                            'started_at': s_step,
                            'finished_at': now(),
                            'duration_ms': int((time.perf_counter() - t_step) * 1000),
                            'ok': True,
                        }
                        if step_name == 'query_stock_asset':
                            entry['summary'] = summarize(payload)
                        else:
                            entry['count'] = len(payload or [])
                            entry['sample'] = summarize(payload)[:5]
                        report['steps'].append(entry)
                    except Exception as exc:
                        first_failure_step = step_name
                        report['steps'].append({
                            'step': step_name,
                            'started_at': s_step,
                            'finished_at': now(),
                            'duration_ms': int((time.perf_counter() - t_step) * 1000),
                            'ok': False,
                            'exception_type': type(exc).__name__,
                            'exception': str(exc),
                            'traceback': traceback.format_exc(),
                        })
                        report['result'] = f'{step_name}_exception'
                        break
                else:
                    report['result'] = 'success'
except Exception as exc:
    if first_failure_step is None:
        first_failure_step = 'script'
    report['result'] = 'script_exception'
    report['exception_type'] = type(exc).__name__
    report['exception'] = str(exc)
    report['traceback'] = traceback.format_exc()
finally:
    report['first_failure_step'] = first_failure_step
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

5. Bounded host-log correlation for the probe window:

```powershell
rg -n "2026-03-30 11:56:4|ssid:101|quant session 101|query accountInfos found|query positions found|query orders found|query account detail|onSubscribe|onConnected|onDisconnected" 'D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log'
```

6. Focused line extraction for the exact probe window:

```powershell
$p='D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log'
$lines=Get-Content $p
foreach($r in @(@{s=14096;e=14114})){
  "--- $($r.s)-$($r.e) ---"
  for($i=$r.s; $i -le $r.e; $i++){
    '{0}:{1}' -f $i,$lines[$i-1]
  }
}
```

## Raw Results

### A. Baseline state before the native query chain

- Process and port baseline at `2026-03-30T11:55:30.9539019+08:00`:
  - `XtMiniQmt` pid `25880`, start `2026-03-30T00:32:23.4186077+08:00`
  - `miniquote` pid `20604`, start `2026-03-30T00:32:23.6051081+08:00`
  - `127.0.0.1:58610` -> `TcpTestSucceeded=true`
- Gateway-side baseline:
  - `diag_login_latest.json` still reported `ok=true`, `status=already_logged_in`, `port_ready=true`
  - `trade_session_current.json` still reported `ready=false`, `reason=session_not_ready`, `session_id=""`, `owner_generation=0`
- Runtime/config baseline:
  - Python executable `D:\xtquant-mcp\venv313\Scripts\python.exe`
  - `xtquant` package file `D:\xtquant-mcp\vendor\xtquant_250807\xtquant\__init__.py`
  - trade config still preferred `100`, with candidate list `[100, 101, 111]`

### B. Single native lifecycle result on `session_id=101`

- Probe observed at: `2026-03-30T11:56:43.286253+08:00`
- Pattern: `single_instance_single_lifecycle_native_query_chain`
- `XtQuantTrader.start()`:
  - `11:56:43.301297` -> `11:56:43.328320`
  - `ok=true`
- `XtQuantTrader.connect()`:
  - `11:56:43.328339` -> `11:56:43.328821`
  - `connect_code=0`
  - `ok=true`
- `query_account_infos()`:
  - `11:56:44.328933` -> `11:56:44.329560`
  - `count=1`
  - discovered account:
    - `account_id=8883884325`
    - `account_type=2`
    - `broker_type=2`
    - `status=0`
- `subscribe(StockAccount("8883884325", "STOCK"))`:
  - `11:56:44.329583` -> `11:56:44.329761`
  - `subscribe_code=0`
  - `ok=true`
- `query_stock_asset()`:
  - `11:56:45.330218` -> `11:56:45.330516`
  - `ok=true`
  - summary:
    - `cash=4497.04`
    - `frozen_cash=0.0`
    - `market_value=111129.00000000001`
    - `total_asset=115626.04`
- `query_stock_positions()`:
  - `11:56:45.330547` -> `11:56:45.330679`
  - `ok=true`
  - `count=2`
  - sample:
    - `301373.SZ`, `volume=0`, `can_use_volume=0`, `market_value=0.0`
    - `300720.SZ`, `volume=1700`, `can_use_volume=0`, `market_value=111129.00000000001`
- `query_stock_orders()`:
  - `11:56:45.330704` -> `11:56:45.330856`
  - `ok=true`
  - `count=5`
  - sample order rows returned, including:
    - `300720.SZ`, `order_status=56`, `order_volume=100`
    - `301373.SZ`, `order_status=56`, `order_volume=800`
    - more rows present in the raw command output
- `stop()`:
  - `11:56:45.330891` -> `11:56:45.333047`
  - `ok=true`
- Script result:
  - `result=success`
  - `first_failure_step=null`
  - Python callback events captured: none

### C. Host-side QMT log correlation for the same lifecycle

Focused lines `14096-14114` from `XtMiniQmt_20260330.log`:

```text
14096:2026-03-30 11:56:43,328 ... onConnected] quant session 101 connected
14097:2026-03-30 11:56:44,328 ... onQueryAccountInfosReq] query accountInfos found 1
14102:2026-03-30 11:56:44,328 ... onSubscribe] account 8883884325 2 subscribed datas in quant session 101
14103:2026-03-30 11:56:45,330 ... onQueryStockAsset] query account detail 8883884325 2, seq:4, tag:101
14104:2026-03-30 11:56:45,330 ... onQueryStockPositions] query positions found 2, 8883884325 2, seq:5, tag:101
14110:2026-03-30 11:56:45,330 ... onQueryStockOrders] query orders found 5, 8883884325 2 0, seq:7, tag:101
14111:2026-03-30 11:56:49,518 ... heartbeat timeout, ssid:101, hsz:4
14113:2026-03-30 11:56:49,520 ... onDisconnected] quant session 101 disconneted
14114:2026-03-30 11:56:49,520 ... lock_down_queue_win_101 file lock not held, offline
```

Observed alignment:

- Native `stop()` started at `2026-03-30T11:56:45.330891+08:00`
- Host heartbeat timeout landed at `2026-03-30 11:56:49,518`
- Stop-to-timeout delta was about `4.187s`

### D. Additional bounded observation

- QMT host log emitted five warnings immediately before `onQueryStockOrders`:
  - `getQuantOrderFromOrderDetail] order xttag is null`
- Despite those warnings:
  - native `query_stock_orders()` returned successfully
  - QMT still logged `query orders found 5`
- So those warning lines were not the first failure point in this lifecycle.

## Interpretation

1. In the repo-configured `venv313` plus `userdata_mini` environment, one native `XtQuantTrader` instance on `session_id=101` now completes the full bounded read-only chain in one lifecycle.
2. The first failure point was not `connect`, not `subscribe`, and not `orders`:
   - `connect_code=0`
   - `query_account_infos()` succeeded
   - `subscribe_code=0`
   - `query_stock_asset()` succeeded
   - `query_stock_positions()` succeeded
   - `query_stock_orders()` succeeded
3. This materially strengthens the `gateway sequence/lifecycle mismatch` hypothesis:
   - the host environment is able to support a native single-lifecycle read-only query chain on `session_id=101`
   - the same host still leaves gateway state stuck at `session_not_ready`
   - earlier gateway-side `orders.list_exception` can no longer be explained only as an unresolved native environment inability to connect or query on `101`
4. This pack still does not prove a specific gateway bug by itself:
   - it does not isolate the exact gateway ownership/reuse step
   - it does not re-run the full MCP-side `G3` chain
   - it therefore should not be upgraded to task-level `pass`
5. Host-side teardown behavior still exists after stop:
   - about four seconds after `stop()`, QMT logs `heartbeat timeout -> onDisconnected -> file lock not held`
   - that remains relevant for later lifecycle design analysis

## Failure Classification

- This pack is `partial`, not `pass`.
- It is not a fresh `fail_env` reproduction for the native `101` path.
- It does not by itself promote the task to `fail_design`, because the gateway defect is not yet isolated to a concrete contract break.
- Task posture remains:
  - `VAL-002` stays `blocked`
  - `VAL-003` stays blocked and out of scope

## Verdict

`partial`.

The bounded single-instance native query-chain probe on `session_id=101` progressed all the way through `connect -> query_account_infos -> subscribe -> query_stock_asset -> query_stock_positions -> query_stock_orders` in one lifecycle, with no Python exception and no first failure point on the chain. `orders` query succeeded and was not the first point of failure.

This evidence strengthens the `gateway sequence/lifecycle mismatch` hypothesis. It does not support keeping the current `101` native path classified only as unresolved `fail_env`. However, it still does not unblock `VAL-002` or `VAL-003`, because the gateway-side `G3` acceptance chain has not yet been re-proven in its own lifecycle and the precise mismatch point remains to be isolated.
