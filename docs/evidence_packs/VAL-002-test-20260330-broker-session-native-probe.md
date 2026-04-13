# EvidencePack

Task ID: VAL-002
Role: test
Date: 2026-03-30T11:17:31.2889758+08:00
Acceptance Gate: G3
Conclusion: fail_env

## Env Snapshot

- Link: [VAL-002-test-20260330-broker-session-native-probe.md](../env_snapshots/VAL-002-test-20260330-broker-session-native-probe.md)
- Host: CHIYU
- Shell: PowerShell 7.6.0
- Repo Working Directory: `D:\xtquant-mcp\repo`
- Live Instance: `D:\xtquant-mcp\instance\prod`
- Task Card: [VAL-002.md](../task_cards/VAL-002.md)
- Prior live baseline:
  - [VAL-002-test-20260330-full-postpatch-rerun.md](./VAL-002-test-20260330-full-postpatch-rerun.md)
  - [VAL-002-review-20260330-full-postpatch-rerun.md](../reviews/VAL-002-review-20260330-full-postpatch-rerun.md)

## Behavioral Reference

- Official ThinkTrader native API reference: <https://dict.thinktrader.net/nativeApi/xttrader.html>
- Bounded reference used in this probe:
  - `session_id` is a session identifier and must not collide.
  - Usually one `XtQuant API` instance per strategy is sufficient.
- This probe therefore used the smallest official-pattern experiment first:
  - one `XtQuantTrader` instance
  - one `session_id`
  - one connect lifecycle
  - read-only account/position/order queries only after connect succeeds

## Test Scope

1. Confirm the current environment baseline for the live `prod` instance:
   - `XtMiniQmt` process present
   - `miniquote` process present
   - `127.0.0.1:58610` reachable
   - latest gateway-side login state already recorded as `already_logged_in`
2. Confirm the repo-configured Python and `xtquant` runtime used by the gateway.
3. Run a direct native `xttrader` probe outside the gateway against `userdata_mini`, using a single native instance lifecycle first.
4. Test one configured candidate `session_id=100` and one bounded alternate `session_id=101`.
5. Record exact timestamps, connect codes, attempted methods, and classify whether the remaining blocker reproduces at broker/session connect stage or only at order-query stage.

## Commands

1. Current environment baseline:

```powershell
$ErrorActionPreference='Stop'
$ts=Get-Date
$xt=Get-Process -Name XtMiniQmt -ErrorAction Stop | Select-Object Id,ProcessName,StartTime,Path
$mq=Get-Process -Name miniquote -ErrorAction Stop | Select-Object Id,ProcessName,StartTime,Path
$port=Test-NetConnection 127.0.0.1 -Port 58610 -WarningAction SilentlyContinue
[ordered]@{
  observed_at=$ts.ToString('o')
  XtMiniQmt=$xt
  miniquote=$mq
  port58610=[ordered]@{
    ComputerName=$port.ComputerName
    RemotePort=$port.RemotePort
    TcpTestSucceeded=$port.TcpTestSucceeded
  }
} | ConvertTo-Json -Depth 6
```

2. Cheap gateway-side login and session baseline confirmation from current `prod` state:

```powershell
Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json
Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json
Get-Content D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json
```

3. Repo-configured Python and `xtquant` runtime introspection:

```powershell
@'
import json, sys, inspect
from pathlib import Path
print(json.dumps({
  'python_executable': sys.executable,
  'python_version': sys.version,
}))
import xtquant
from xtquant.xttrader import XtQuantTrader
print(json.dumps({
  'xtquant_file': getattr(xtquant, '__file__', ''),
  'xtquant_package_dir': str(Path(getattr(xtquant, '__file__', '')).resolve().parent),
  'XtQuantTrader_init': str(inspect.signature(XtQuantTrader.__init__)),
  'XtQuantTrader_methods': sorted([name for name in dir(XtQuantTrader) if name.startswith('query_') or name in ('connect','start','stop','subscribe')])
}, ensure_ascii=False, indent=2))
'@ | D:\xtquant-mcp\venv313\Scripts\python.exe -
```

4. Direct native probe outside the gateway, against `userdata_mini`, with one single-instance lifecycle per candidate session:

```powershell
@'
import json
import time
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant.xttype import StockAccount

TZ = timezone(timedelta(hours=8))
USERDATA = r"D:\lh\国金证券QMT交易端\userdata_mini"
SESSIONS = [100, 101]

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
            'login_status': safe_get(row, 'login_status', 'loginStatus', 'status'),
            'platform_id': safe_get(row, 'platform_id', 'platformId'),
        })
    return out

def summarize_asset(row):
    if row is None:
        return None
    return {
        'account_id': str(safe_get(row, 'account_id', 'accountId') or ''),
        'cash': safe_get(row, 'cash', 'm_dCash'),
        'frozen_cash': safe_get(row, 'frozen_cash', 'frozenCash'),
        'total_asset': safe_get(row, 'total_asset', 'totalAsset', 'market_value', 'marketValue'),
    }

def summarize_positions(rows):
    out = []
    for row in (rows or [])[:5]:
        out.append({
            'stock_code': str(safe_get(row, 'stock_code', 'stockCode', 'instrument_id') or ''),
            'volume': safe_get(row, 'volume', 'm_nVolume'),
            'can_use_volume': safe_get(row, 'can_use_volume', 'canUseVolume'),
            'market_value': safe_get(row, 'market_value', 'marketValue'),
        })
    return out

def summarize_orders(rows):
    out = []
    for row in (rows or [])[:5]:
        out.append({
            'order_id': safe_get(row, 'order_id', 'orderId'),
            'stock_code': str(safe_get(row, 'stock_code', 'stockCode') or ''),
            'order_status': safe_get(row, 'order_status', 'orderStatus', 'status'),
            'order_volume': safe_get(row, 'order_volume', 'orderVolume', 'volume'),
            'order_time': safe_get(row, 'order_time', 'orderTime'),
        })
    return out

class Callback(XtQuantTraderCallback):
    def __init__(self):
        super().__init__()
        self.events = []

    def on_connected(self):
        self.events.append({'ts': now(), 'event': 'on_connected'})

    def on_disconnected(self):
        self.events.append({'ts': now(), 'event': 'on_disconnected'})

    def on_account_status(self, status):
        self.events.append({
            'ts': now(),
            'event': 'on_account_status',
            'account_id': str(safe_get(status, 'account_id', 'accountId') or ''),
            'status': safe_get(status, 'status'),
        })

def run_single_instance(session_id):
    result = {
        'session_id': int(session_id),
        'pattern': 'single_instance_single_lifecycle',
        'userdata': USERDATA,
        'started_at': now(),
        'steps': [],
        'callback_events': [],
    }
    cb = Callback()
    trader = XtQuantTrader(str(Path(USERDATA)), int(session_id), cb)
    account = None
    try:
        t0 = now()
        trader.start()
        result['steps'].append({
            'step': 'start',
            'started_at': t0,
            'finished_at': now(),
            'ok': True,
        })

        t1 = time.perf_counter()
        started = now()
        connect_code = int(trader.connect())
        result['steps'].append({
            'step': 'connect',
            'started_at': started,
            'finished_at': now(),
            'duration_ms': int((time.perf_counter() - t1) * 1000),
            'ok': connect_code == 0,
            'connect_code': connect_code,
        })
        result['connect_code'] = connect_code
        if connect_code != 0:
            result['result'] = 'connect_failed'
            return result

        if hasattr(trader, 'query_account_infos'):
            t2 = time.perf_counter()
            started = now()
            infos = trader.query_account_infos() or []
            summarized_infos = summarize_account_infos(infos)
            account_ids = [row['account_id'] for row in summarized_infos if row.get('account_id')]
            result['steps'].append({
                'step': 'query_account_infos',
                'started_at': started,
                'finished_at': now(),
                'duration_ms': int((time.perf_counter() - t2) * 1000),
                'ok': True,
                'account_info_count': len(summarized_infos),
                'account_infos': summarized_infos,
            })
            if account_ids:
                account = StockAccount(str(account_ids[0]), 'STOCK')
                result['selected_account_id'] = str(account_ids[0])

        if account is None:
            result['result'] = 'connected_but_no_account'
            return result

        t3 = time.perf_counter()
        started = now()
        subscribe_code = int(trader.subscribe(account))
        result['steps'].append({
            'step': 'subscribe',
            'started_at': started,
            'finished_at': now(),
            'duration_ms': int((time.perf_counter() - t3) * 1000),
            'ok': subscribe_code == 0,
            'subscribe_code': subscribe_code,
        })
        result['subscribe_code'] = subscribe_code
        if subscribe_code != 0:
            result['result'] = 'subscribe_failed'
            return result

        for step_name, fn in [
            ('query_stock_asset', lambda: trader.query_stock_asset(account)),
            ('query_stock_positions', lambda: trader.query_stock_positions(account) or []),
            ('query_stock_orders', lambda: trader.query_stock_orders(account, False) or []),
        ]:
            t_step = time.perf_counter()
            started = now()
            try:
                payload = fn()
                entry = {
                    'step': step_name,
                    'started_at': started,
                    'finished_at': now(),
                    'duration_ms': int((time.perf_counter() - t_step) * 1000),
                    'ok': True,
                }
                if step_name == 'query_stock_asset':
                    entry['summary'] = summarize_asset(payload)
                elif step_name == 'query_stock_positions':
                    entry['count'] = len(payload or [])
                    entry['sample'] = summarize_positions(payload)
                elif step_name == 'query_stock_orders':
                    entry['count'] = len(payload or [])
                    entry['sample'] = summarize_orders(payload)
                result['steps'].append(entry)
            except Exception as exc:
                result['steps'].append({
                    'step': step_name,
                    'started_at': started,
                    'finished_at': now(),
                    'duration_ms': int((time.perf_counter() - t_step) * 1000),
                    'ok': False,
                    'exception_type': type(exc).__name__,
                    'exception': str(exc),
                    'traceback': traceback.format_exc(),
                })
                result['result'] = f'{step_name}_exception'
                return result

        result['result'] = 'success'
        return result
    except Exception as exc:
        result['result'] = 'script_exception'
        result['exception_type'] = type(exc).__name__
        result['exception'] = str(exc)
        result['traceback'] = traceback.format_exc()
        return result
    finally:
        result['callback_events'] = list(cb.events)
        try:
            trader.stop()
            result['stopped_at'] = now()
        except Exception as exc:
            result['stop_exception'] = f'{type(exc).__name__}: {exc}'

report = {
    'observed_at': now(),
    'python_executable': __import__('sys').executable,
    'probe_reference': {
        'userdata': USERDATA,
        'sessions': SESSIONS,
        'env_contract': 'repo configured venv313 + vendor xtquant',
    },
    'results': [run_single_instance(sid) for sid in SESSIONS],
}
print(json.dumps(report, ensure_ascii=False, indent=2))
'@ | D:\xtquant-mcp\venv313\Scripts\python.exe -
```

## Raw Results

### 1. Environment baseline

- Observed at: `2026-03-30T11:14:21.7053506+08:00`
- `XtMiniQmt`
  - pid: `25880`
  - start time: `2026-03-30T00:32:23.4186077+08:00`
  - path: `D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
- `miniquote`
  - pid: `20604`
  - start time: `2026-03-30T00:32:23.6051081+08:00`
  - path: `D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe`
- `127.0.0.1:58610`
  - `TcpTestSucceeded=True`

### 2. Gateway-side latest login/session baseline

- Current gateway-side login state file:
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json`
  - Latest status still reads `ok=true`, `status=already_logged_in`, `message=MiniQMT already logged in`
  - Recorded `process_id=25880`, `port_ready=true`
  - Embedded main window title shows `8883884325 - 国金证券QMT交易端 2.0.8.300`
- Current gateway-side session file:
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json`
  - Still reads `ready=false`, `reason=session_not_ready`, `session_id=''`, `owner_generation=0`
- Current gateway-side probe state file:
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json`
  - Contains only account contract scope and no ready broker session

### 3. Repo-configured Python and xtquant runtime

- Python executable: `D:\xtquant-mcp\venv313\Scripts\python.exe`
- Python version: `3.13.12`
- `xtquant` package file: `D:\xtquant-mcp\vendor\xtquant_250807\xtquant\__init__.py`
- `XtQuantTrader.__init__`: `(self, path, session, callback=None)`
- Native methods visible in this runtime include:
  - `connect`
  - `query_account_infos`
  - `query_stock_asset`
  - `query_stock_positions`
  - `query_stock_orders`
  - `start`
  - `stop`
  - `subscribe`

### 4. Direct native xttrader probe

- Probe observed at: `2026-03-30T11:16:48.136649+08:00`
- User data path: `D:\lh\国金证券QMT交易端\userdata_mini`
- Session candidates tested in this bounded run:
  - configured candidate: `100`
  - bounded alternate candidate: `101`

#### Session 100

- Pattern: `single_instance_single_lifecycle`
- Start:
  - started: `2026-03-30T11:16:48.152369+08:00`
  - finished: `2026-03-30T11:16:48.179267+08:00`
  - result: `ok=true`
- Connect:
  - started: `2026-03-30T11:16:48.179280+08:00`
  - finished: `2026-03-30T11:16:51.180991+08:00`
  - duration: `3001 ms`
  - result: `ok=false`
  - `connect_code=-1`
- Callback events: none captured
- Stop:
  - stopped at: `2026-03-30T11:16:51.183208+08:00`
- Not reached because connect failed:
  - `query_account_infos`
  - `subscribe`
  - `query_stock_asset`
  - `query_stock_positions`
  - `query_stock_orders`

#### Session 101

- Pattern: `single_instance_single_lifecycle`
- Start:
  - started: `2026-03-30T11:16:51.183872+08:00`
  - finished: `2026-03-30T11:16:51.210906+08:00`
  - result: `ok=true`
- Connect:
  - started: `2026-03-30T11:16:51.210921+08:00`
  - finished: `2026-03-30T11:16:54.222546+08:00`
  - duration: `3011 ms`
  - result: `ok=false`
  - `connect_code=-1`
- Callback events: none captured
- Stop:
  - stopped at: `2026-03-30T11:16:54.225194+08:00`
- Not reached because connect failed:
  - `query_account_infos`
  - `subscribe`
  - `query_stock_asset`
  - `query_stock_positions`
  - `query_stock_orders`

## Comparison Against Current Gateway Failure

- Prior same-day full rerun already showed:
  - login recovered to `already_logged_in`
  - `session.warm` failed with `orders.list_exception`
  - broker detail carried `xttrader connect failed: -1`
- This bounded native probe reproduced the same underlying broker/session failure outside the gateway:
  - single native `XtQuantTrader` instance
  - direct `userdata_mini`
  - no MCP transport
  - no gateway session manager
  - still `connect_code=-1` for both `100` and `101`
- Because native `connect()` itself failed, this run does **not** support the claim that the remaining blocker is only an `orders.list` implementation bug or a gateway-only query reuse bug.
- The gateway-side `orders.list_exception` remains compatible with a deeper environment/session-connect failure that happens before any stable owner-managed broker session exists.

## Interpretation

1. The login recovery baseline is real:
   - `XtMiniQmt` and `miniquote` were running.
   - `127.0.0.1:58610` was reachable.
   - latest gateway-side login state still showed `already_logged_in`.
2. The remaining blocker reproduced in a direct native `xttrader` path after login was already recovered.
3. In this bounded run, the failure happens at broker/session connect stage itself:
   - `XtQuantTrader.start()` succeeded.
   - `XtQuantTrader.connect()` returned `-1`.
   - no account, position, or order query was reached.
4. Therefore this evidence points more strongly to `fail_env` than to a proven design mismatch in the current gateway query lifecycle.
5. A narrow later dev hypothesis remains possible but unproven:
   - the configured candidate set `100/101/111` may still collide with another existing broker session or local runtime policy
   - official guidance says `session_id` must not collide
   - that hypothesis needs a later dev card if the team wants a controlled session allocation strategy
   - this test run does not prove that hypothesis, and does not convert the issue into `fail_design`

## Boundedness Notes

- No repo code was edited.
- No task card, change package, or review file was modified.
- The probe stayed read-only:
  - connect
  - account discovery if connect had succeeded
  - account/positions/orders query if connect had succeeded
- No second probe pattern was expanded in this run.
  - Reason: both bounded candidate sessions failed at `connect()` before any query step.
  - A reconnect-vs-reuse comparison would not add new stage isolation once native connect had already failed outside the gateway.

## Final Test Verdict

- Result: `fail_env`
- Gate posture: `blocked`
- Explicit statement:
  - login has already recovered
  - the remaining blocker still reproduces in direct native `xttrader` connect behavior
  - this run does not unblock `VAL-002`
  - this run does not unblock `VAL-003`
