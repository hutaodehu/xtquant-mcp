# EvidencePack

Task ID: VAL-002
Role: test
Date: 2026-03-30T11:34:40.5117954+08:00
Acceptance Gate: G3
Conclusion: fail_env

## Env Snapshot

- Link: [VAL-002-test-20260330-broker-log-extract.md](../env_snapshots/VAL-002-test-20260330-broker-log-extract.md)
- Host: CHIYU
- Shell: PowerShell 7.6.0
- Repo Working Directory: `D:\xtquant-mcp\repo`
- Prior correlated evidence:
  - [VAL-002-test-20260330-full-postpatch-rerun.md](./VAL-002-test-20260330-full-postpatch-rerun.md)
  - [VAL-002-test-20260330-broker-session-native-probe.md](./VAL-002-test-20260330-broker-session-native-probe.md)

## Test Scope

1. Inspect recent host-side QMT logs under `D:\lh\国金证券QMT交易端\userdata_mini\log`.
2. Bind the log search to the same-day failure windows already recorded by prior `VAL-002` evidence:
   - gateway rerun window around `2026-03-30 10:57:37` to `10:59:09`
   - native direct probe window around `2026-03-30 11:16:48` to `11:16:55`
3. Search only bounded terms relevant to the remaining broker/session blocker:
   - `connect`
   - `session`
   - `queryNodeInfo`
   - `order`
   - `account`
   - `InstantMode`
   - `up_queue`
   - `lock`
   - `error`
   - `fail`
   - session ids `100`, `101`, `111`
4. Determine whether host logs provide a stronger explanation for the remaining `xttrader connect=-1` blocker after login recovery.

## Commands

1. Recent log inventory:

```powershell
Get-ChildItem 'D:\lh\国金证券QMT交易端\userdata_mini\log' |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 20 FullName,LastWriteTime,Length
```

2. Time-bounded search in the main host log:

```powershell
rg -n "2026-03-30 10:57|2026-03-30 10:58|2026-03-30 10:59|2026-03-30 11:16|2026-03-30 11:17|2026-03-30 11:18" `
  'D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log'
```

3. Same time-bounded search in the performance log:

```powershell
rg -n "2026-03-30 10:57|2026-03-30 10:58|2026-03-30 10:59|2026-03-30 11:16|2026-03-30 11:17|2026-03-30 11:18" `
  'D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_perform_20260330.log'
```

4. Keyword search in the main host log:

```powershell
rg -n -i "connect|session|queryNodeInfo|order|account|InstantMode|up_queue|lock|error|fail|100|101|111" `
  'D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log'
```

5. Focused window extraction around the most relevant line ranges:

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

6. Negative/auxiliary search for additional broker/session fields:

```powershell
$patterns=@('queryNodeInfo','InstantMode','m_bInstantMode','up_queue','lock_up_queue')
foreach($pat in $patterns){
  $m = rg -n --fixed-strings $pat `
    'D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log' `
    'D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_perform_20260330.log'
  if($LASTEXITCODE -eq 0){ "### $pat"; $m } else { "### $pat`n(no matches)" }
}
```

## Paths Inspected

- `D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log`
  - length: `1612195`
  - last write time: `2026-03-30T11:34:28.9118594+08:00`
- `D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_perform_20260330.log`
  - length: `877670`
  - last write time: `2026-03-30T11:34:30.2724192+08:00`

## Raw Results

### A. Gateway rerun correlation window: 10:57 to 10:59

Source: `D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log`

Relevant extracted lines:

```text
12852:2026-03-30 10:57:38,457 ... onConnected] quant session 100 connected
12853:2026-03-30 10:57:38,458 ... onQueryAccountInfosReq] query accountInfos found 1
12856:2026-03-30 10:57:42,563 ... heartbeat timeout, ssid:100, hsz:4
12857:2026-03-30 10:57:42,563 ... lock_down_queue_win_100 file lock held, keep online
12863:2026-03-30 10:57:53,782 ... onConnected] quant session 101 connected
12868:2026-03-30 10:57:53,783 ... onSubscribe] account 8883884325 2 subscribed datas in quant session 101
12869:2026-03-30 10:57:53,783 ... onQueryStockPositions] query positions found 2, 8883884325 2, seq:3, tag:101
12870:2026-03-30 10:57:53,783 ... onQueryStockAsset] query account detail 8883884325 2, seq:4, tag:101
12900:2026-03-30 10:58:24,038 ... onConnected] quant session 111 connected
12905:2026-03-30 10:58:24,038 ... onSubscribe] account 8883884325 2 subscribed datas in quant session 111
12906:2026-03-30 10:58:24,039 ... onQueryStockAsset] query account detail 8883884325 2, seq:3, tag:111
12907:2026-03-30 10:58:24,041 ... onQueryStockPositions] query positions found 2, 8883884325 2, seq:4, tag:111
12953:2026-03-30 10:59:09,371 ... [orderservice] [quant] account [...] unsubscribe
12954:2026-03-30 10:59:09,371 ... onUnsubscribe] account 8883884325 2 unsubscribed datas in quant session 111
12958:2026-03-30 10:59:13,946 ... heartbeat timeout, ssid:111, hsz:4
12959:2026-03-30 10:59:13,946 ... lock_down_queue_win_111 file lock held, keep online
```

Direct evidence:

- During the same host window as the `10:57:37` MCP rerun, the QMT-side `COrderServiceQuantAdaptor` logged successful connects for session ids `100`, `101`, and `111`.
- In that same window, host log lines show read-like follow-on activity for sessions `101` and `111`:
  - `query accountInfos found 1`
  - `query positions found 2`
  - `query account detail ...`
- Heartbeat timeout lines existed in this window, but for these entries the corresponding `lock_down_queue_win_*` state was `file lock held, keep online`, not immediate offline.

Bounded inference:

- These host lines show that the broker-side QMT process was not globally dead during the `10:57-10:59` rerun window.
- They do not, by themselves, explain why the gateway-side `session.warm` still ended in `orders.list_exception -> xttrader connect failed: -1`, because the host log does not map each QMT internal session event back to the exact MCP caller outcome.

### B. Native probe correlation window: 11:16 to 11:16:55

Source: `D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log`

Relevant extracted lines:

```text
13451:2026-03-30 11:16:48,178 ... onConnected] quant session 100 connected
13452:2026-03-30 11:16:51,210 ... onConnected] quant session 101 connected
13453:2026-03-30 11:16:52,334 ... heartbeat timeout, ssid:100, hsz:4
13454:2026-03-30 11:16:52,339 ... onDisconnected] quant session 100 disconneted
13455:2026-03-30 11:16:52,339 ... lock_down_queue_win_100 file lock not held, offline
13457:2026-03-30 11:16:55,045 ... heartbeat timeout, ssid:101, hsz:4
13458:2026-03-30 11:16:55,050 ... onDisconnected] quant session 101 disconneted
13459:2026-03-30 11:16:55,050 ... lock_down_queue_win_101 file lock not held, offline
```

Direct evidence:

- The host log aligns tightly with the prior native probe timestamps recorded in [VAL-002-test-20260330-broker-session-native-probe.md](./VAL-002-test-20260330-broker-session-native-probe.md):
  - session `100` probe connect window: `11:16:48.179280` to `11:16:51.180991`
  - session `101` probe connect window: `11:16:51.210921` to `11:16:54.222546`
- For both `100` and `101`, the host log shows a brief `onConnected` event followed almost immediately by:
  - `heartbeat timeout`
  - `onDisconnected`
  - `lock_down_queue_win_<session> file lock not held, offline`

Bounded inference:

- This is a stronger host-side explanation for the `11:16` native `xttrader connect=-1` than the gateway output alone.
- The log pattern suggests the failure is not "never reached broker process at all"; it is closer to "session briefly connected but did not remain stably online because the corresponding lock-backed session state was not held".
- The host log still does not say why the lock stopped being held, so the root cause remains unresolved at the host-log layer.

### C. Additional broker/session context outside the failure windows

Source: `D:\lh\国金证券QMT交易端\userdata_mini\log\XtMiniQmt_20260330.log`

Relevant extracted lines from startup context:

```text
817:2026-03-30 00:32:24,867 ... tryQueryNodeInfo] [exec queryNodeInfo] req info: { account: { ... m_bInstantMode: false, ... } ... }
830:2026-03-30 00:32:24,905 ... [queryNodeInfo] query node info data size 0
831:2026-03-30 00:32:24,905 ... [queryNodeInfo] query node info boError: {} error: { error: { ErrorID: 200006, ErrorMsg: "无效的请求参数" } }
```

Direct evidence:

- The field name `m_bInstantMode` does appear in the same-day host log, and the captured value in this request is `false`.
- The same same-day startup context also shows `queryNodeInfo` returning `ErrorID: 200006` with `ErrorMsg: "无效的请求参数"`.

Important boundary:

- The `queryNodeInfo` and `m_bInstantMode` lines above are not inside the `10:57` or `11:16` blocker windows.
- The log itself does not explain the semantic meaning of `m_bInstantMode`; this pack reports the field exactly as logged and does not assign extra meaning to it.

### D. Negative results from bounded searches

Direct evidence:

- In the inspected files, bounded searches for `up_queue` and `lock_up_queue` returned no matches.
- `XtMiniQmt_perform_20260330.log` did not add broker/session-specific diagnostics for the `10:57-10:59` and `11:16-11:18` windows; the visible lines in those windows were periodic `threadpool ... is alive` health messages only.

## Failure Classification

- `fail_env`
  - supported by direct host-log evidence in the `11:16` native probe window:
    - session `100` connected, then heartbeat timeout, then `lock_down_queue_win_100 file lock not held, offline`
    - session `101` connected, then heartbeat timeout, then `lock_down_queue_win_101 file lock not held, offline`
- `fail_design`
  - not established by this bounded log extraction
  - host logs do not isolate a gateway-only defect
- `blocked`
  - the overall `VAL-002` posture remains blocked at the environment layer

## Verdict

`fail_env`.

This host-log extraction adds a stronger explanation for the later `11:16` broker/session failure window: `xttrader connect=-1` correlates with QMT-side sessions `100` and `101` briefly connecting, then immediately dropping on heartbeat timeout because the corresponding `lock_down_queue_win_*` session lock was not held.

At the same time, the host-log layer still does not fully resolve the broader blocker after login recovery. In the earlier `10:57-10:59` gateway rerun window, the same host log shows QMT-side session/account/position activity for `100`, `101`, and `111`, while the MCP rerun still ended in `session_not_ready`. So the logs strengthen the environment diagnosis, but they do not close the root cause end-to-end at the host-log layer.

`VAL-002` remains environment-blocked. Do not advance to `VAL-003`.

