# EvidencePack

Task ID: VAL-002
Role: test
Date: 2026-03-30T12:46:17.578620+08:00
Acceptance Gate: G3
Conclusion: partial

## Env Snapshot

- Link: [VAL-002-test-20260330-124617-live-gateway-rerun.md](../env_snapshots/VAL-002-test-20260330-124617-live-gateway-rerun.md)
- Host: `CHIYU`
- Shell: `PowerShell 7.6.0`
- Config:
  - [VAL-002.md](../task_cards/VAL-002.md)
  - [VAL-002.md](../change_packages/VAL-002.md)
  - `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Code Version:
  - `git rev-parse HEAD` and `git status --short` remain unavailable because this workspace does not expose `.git`
  - Runtime freshness was verified by the post-wake process start time `2026-03-30T12:40:38.004714+08:00` and repo entrypoint command line `D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py`

## Test Scope

1. Capture the pre-restart gateway runtime state, including the possibility that `8765` is already down.
2. Start the trade gateway through the repo-supported path so the current repo code is loaded:
   - `pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1`
3. Run the full live `VAL-002` `G3` read-only chain on the restarted gateway:
   - `miniqmt.ensure_logged_in`
   - `session.warm`
   - `session.status`
   - `probe.connection`
   - `account.show`
   - `positions.list`
   - `orders.list`
   - `snapshot.l1`
4. Read `trade://session/current`, `diag://probe/latest`, and `diag://login/latest` after the chain.
5. Compare the fresh gateway-side result with the prior blocker narrative recorded in:
   - [VAL-002-test-20260330-full-postpatch-rerun.md](./VAL-002-test-20260330-full-postpatch-rerun.md)
   - [VAL-002-review-20260330-native-query-chain.md](../reviews/VAL-002-review-20260330-native-query-chain.md)

## Commands

1. Pre-restart state capture:

```powershell
$ErrorActionPreference='Stop'
$ts = Get-Date
$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
try {
  $health = Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8765/healthz' -TimeoutSec 5
} catch {
  $health = $null
}
Test-NetConnection -ComputerName 127.0.0.1 -Port 8765 -InformationLevel Quiet
Get-Process -Name XtMiniQmt -ErrorAction SilentlyContinue
Get-Process -Name miniquote -ErrorAction SilentlyContinue
```

2. Repo-supported wake path:

```powershell
pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1
```

3. Post-restart listener, process, and `/healthz` verification:

```powershell
$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction Stop | Select-Object -First 1
$proc = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $listener.OwningProcess)
Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8765/healthz' -TimeoutSec 10
Get-ChildItem D:\xtquant-mcp\instance\prod\logs\trade_gateway -File |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 6 FullName,LastWriteTime,Length
```

4. Full live MCP rerun:

```powershell
@'
import json
import http.client
from datetime import datetime, timezone, timedelta

HOST = "127.0.0.1"
PORT = 8765
PATH = "/mcp"
TZ = timezone(timedelta(hours=8))

def now():
    return datetime.now(TZ).isoformat()

def post(conn, payload, session_id=""):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    started = now()
    conn.request("POST", PATH, body=body, headers=headers)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8")
    finished = now()
    return started, finished, resp.status, raw

conn = http.client.HTTPConnection(HOST, PORT, timeout=180)
post(conn, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
for i, (name, arguments) in enumerate([
    ("miniqmt.ensure_logged_in", {"login_timeout_seconds": 20}),
    ("session.warm", {}),
    ("session.status", {}),
    ("probe.connection", {}),
    ("account.show", {}),
    ("positions.list", {}),
    ("orders.list", {}),
    ("snapshot.l1", {"code": "000001.SZ"}),
], start=10):
    post(conn, {"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": arguments}})
for i, uri in enumerate(["trade://session/current", "diag://probe/latest", "diag://login/latest"], start=100):
    post(conn, {"jsonrpc": "2.0", "id": i, "method": "resources/read", "params": {"uri": uri}})
conn.close()
'@ | D:\xtquant-mcp\venv313\Scripts\python.exe -
```

5. Call-log trace verification:

```powershell
$log='D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260330\trade_gateway_calls.jsonl'
$ids=@(
  '0eba2b26-bd3a-421b-b29b-fb800b150ef4',
  'ee1eca12-ee08-4ce5-9c1f-161bbf52229f',
  'f7af2184-5590-486e-aa4f-0bd6b19b77fd',
  '80ab2097-9df1-425c-a170-4d37b5a79162',
  '33803f97-8fbe-46f3-8a94-dd0101ca5662',
  '27db9be5-77c7-4cfd-bc06-fcb9c879bb0c',
  '06a85f5e-a89f-4437-b12c-e85667fd34f6',
  'e2c3306f-4762-4e0a-88c1-9ed6c8ae8f16'
)
foreach ($id in $ids) { rg -n --fixed-strings $id $log }
```

## Raw Results

- Pre-restart gateway state:
  - Observed at: `2026-03-30T12:40:24.0119828+08:00`
  - No listener existed on `127.0.0.1:8765`
  - `/healthz` was unavailable: `connection refused`
  - `XtMiniQmt.exe` and `miniquote.exe` were already present
  - `127.0.0.1:58610` remained reachable
- Restart/load verification:
  - Repo-supported path used: `pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1`
  - The shell call itself timed out after `154028 ms`
  - Despite that timeout, restart succeeded:
    - New listener observed at `2026-03-30T12:43:30.2759775+08:00`
    - pid: `34748`
    - new process start time: `2026-03-30T12:40:38.004714+08:00`
    - new command line points at repo entrypoint:
      `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
    - new logs:
      - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_124037.log`
      - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_124037.stderr.log`
    - `/healthz` after restart returned `ok=true`
  - This is sufficient evidence that a fresh repo-loaded gateway process was started for this rerun.

- Full live `G3` chain on the restarted gateway:
  - MCP initialize:
    - Started: `2026-03-30T12:43:54.190420+08:00`
    - Finished: `2026-03-30T12:43:54.193111+08:00`
    - HTTP `200`
    - `mcp_session_id=4bfb33ca-d767-4813-a147-428249cd87e5`
  - `miniqmt.ensure_logged_in`
    - Started: `2026-03-30T12:43:54.193143+08:00`
    - Finished: `2026-03-30T12:43:54.194860+08:00`
    - `ok=false`
    - `status=desktop_not_interactive`
    - `message=interactive desktop required`
    - `process_id=null`
    - `port_ready=false`
    - `trace_id=0eba2b26-bd3a-421b-b29b-fb800b150ef4`
    - `server_ts=2026-03-30T12:43:54`
    - `duration_ms=0`
  - `session.warm`
    - Started: `2026-03-30T12:43:54.194907+08:00`
    - Finished: `2026-03-30T12:44:46.183432+08:00`
    - `ok=true`
    - `ready=true`
    - `account_id=8883884325`
    - `owner_account_id=8883884325`
    - `session_id=101`
    - `owner_generation=1`
    - `warm_trace` succeeded on:
      - `account.show`
      - `positions.list`
      - `orders.list` with `count=5`, `source=xttrader_shadow`, `read_scope=warm_health_only`
    - `trace_id=ee1eca12-ee08-4ce5-9c1f-161bbf52229f`
    - `server_ts=2026-03-30T12:43:54`
    - `duration_ms=51987`
  - `session.status`
    - Started: `2026-03-30T12:44:46.183539+08:00`
    - Finished: `2026-03-30T12:44:46.186234+08:00`
    - `ok=true`
    - `ready=true`
    - `session_id=101`
    - `reason=''`
    - `trace_id=f7af2184-5590-486e-aa4f-0bd6b19b77fd`
    - `server_ts=2026-03-30T12:44:46`
  - `probe.connection`
    - Started: `2026-03-30T12:44:46.186345+08:00`
    - Finished: `2026-03-30T12:45:31.638964+08:00`
    - `ok=false`
    - `error.code=connect_failed`
    - `error.category=connectivity`
    - `connect_code=-1`
    - `connection_trace` showed:
      - `precheck_userdata_read_only=ok`
      - `precheck_userdata_write_permission=ok`
      - `precheck_process=ok`
      - `wait_xtdata_ready=ok`
      - `connect_session_101=-1`
      - `connect_session_100=-1`
      - `connect_session_111=-1`
    - `trace_id=80ab2097-9df1-425c-a170-4d37b5a79162`
    - `server_ts=2026-03-30T12:44:46`
    - `duration_ms=45451`
  - `account.show`
    - Started: `2026-03-30T12:45:31.639077+08:00`
    - Finished: `2026-03-30T12:45:31.640789+08:00`
    - `ok=true`
    - `cash=4497.04`
    - `total_asset=115626.04`
    - `market_value=111129.00000000001`
    - `source=xttrader_shadow`
    - `trace_id=33803f97-8fbe-46f3-8a94-dd0101ca5662`
    - `server_ts=2026-03-30T12:45:31`
  - `positions.list`
    - Started: `2026-03-30T12:45:31.640825+08:00`
    - Finished: `2026-03-30T12:45:31.641986+08:00`
    - `ok=true`
    - `count=2`
    - `trace_id=27db9be5-77c7-4cfd-bc06-fcb9c879bb0c`
    - `server_ts=2026-03-30T12:45:31`
  - `orders.list`
    - Started: `2026-03-30T12:45:31.642025+08:00`
    - Finished: `2026-03-30T12:46:16.963627+08:00`
    - `ok=false`
    - `error.category=environment`
    - `error.message=xttrader connect failed: -1 after 3 attempts (...)`
    - session plan in error text: `101`, `100`, `111`
    - `trace_id=06a85f5e-a89f-4437-b12c-e85667fd34f6`
    - `server_ts=2026-03-30T12:45:31`
    - `duration_ms=45320`
  - `snapshot.l1`
    - Started: `2026-03-30T12:46:16.963731+08:00`
    - Finished: `2026-03-30T12:46:17.566444+08:00`
    - `ok=true`
    - `code=000001.SZ`
    - `last_price=11.03`
    - `source=online_pull`
    - `trace_id=e2c3306f-4762-4e0a-88c1-9ed6c8ae8f16`
    - `server_ts=2026-03-30T12:46:16`

- Resource reads after the chain:
  - `trade://session/current`
    - Read at `2026-03-30T12:46:17.569343+08:00`
    - `ready=true`
    - `account_id=8883884325`
    - `owner_account_id=8883884325`
    - `session_id=101`
    - `owner_generation=1`
  - `diag://probe/latest`
    - Read at `2026-03-30T12:46:17.574278+08:00`
    - `ok=false`
    - `reason=connect_failed`
    - `connect_code=-1`
    - `readiness_layers.read_only.ok=false`
    - `readiness_layers.write_permission.ok=true`
  - `diag://login/latest`
    - Read at `2026-03-30T12:46:17.578620+08:00`
    - `ok=false`
    - `status=desktop_not_interactive`
    - `message=interactive desktop required`

## Comparison Against Prior Blocker Narrative

- Compared with [VAL-002-test-20260330-full-postpatch-rerun.md](./VAL-002-test-20260330-full-postpatch-rerun.md):
  - The earlier fresh-process rerun failed inside `session.warm` and left `trade://session/current` in `session_not_ready`.
  - This rerun still uses a fresh repo-loaded gateway process, but `session.warm` now succeeds and `trade://session/current` is `ready=true` with `session_id=101`.
  - The hard stop moved:
    - away from `session.warm`
    - to `miniqmt.ensure_logged_in=desktop_not_interactive`
    - and to public connect-based reads `probe.connection` / `orders.list`
- Compared with [VAL-002-review-20260330-native-query-chain.md](../reviews/VAL-002-review-20260330-native-query-chain.md):
  - The review there noted that a new gateway-side rerun was still required.
  - This EvidencePack now supplies that fresh gateway-side rerun on a restarted process.
  - The new evidence shows the restarted gateway can establish an owner-managed session and serve `session.status`, `account.show`, `positions.list`, and `snapshot.l1`.
  - It does not prove `G3 pass`, because the ordered chain still contains failures at step 1, step 4, and step 7.

## Failure Classification

- `partial`
  - This rerun is not a `pass`, because the required `G3` ordered chain did not complete cleanly.
  - It is also not a pure replay of the earlier `fail_env` pattern, because the fresh gateway-side rerun now demonstrates:
    - `session.warm=ready`
    - `session.status=ready`
    - `trade://session/current=ready`
    - `account.show`, `positions.list`, and `snapshot.l1` all succeed
- Environment issues still observed in this run:
  - `miniqmt.ensure_logged_in` failed with `desktop_not_interactive`
  - `probe.connection` failed with `connect_failed` after `connect_session_101/100/111=-1`
  - public `orders.list` failed with `xttrader connect failed: -1 after 3 attempts (...)`
- `fail_design`: not proven by this run
  - This pack records a changed failure shape and a mixed success/failure profile.
  - It does not, by itself, prove a design-contract failure.

## Artifact Refs

- Raw capture bundle:
  - `C:\Users\Yun\AppData\Local\Temp\VAL-002-live-rerun-20260330_123841\01_pre_restart.json`
  - `C:\Users\Yun\AppData\Local\Temp\VAL-002-live-rerun-20260330_123841\03_post_restart.json`
  - `C:\Users\Yun\AppData\Local\Temp\VAL-002-live-rerun-20260330_123841\04_mcp_chain.json`
  - `C:\Users\Yun\AppData\Local\Temp\VAL-002-live-rerun-20260330_123841\06_python_version.txt`
- Trade gateway call log:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260330\trade_gateway_calls.jsonl`
- Call log line verification for this rerun:
  - `trace_id=0eba2b26-bd3a-421b-b29b-fb800b150ef4` at line `35`
  - `trace_id=ee1eca12-ee08-4ce5-9c1f-161bbf52229f` at line `36`
  - `trace_id=f7af2184-5590-486e-aa4f-0bd6b19b77fd` at line `37`
  - `trace_id=80ab2097-9df1-425c-a170-4d37b5a79162` at line `38`
  - `trace_id=33803f97-8fbe-46f3-8a94-dd0101ca5662` at line `39`
  - `trace_id=27db9be5-77c7-4cfd-bc06-fcb9c879bb0c` at line `40`
  - `trace_id=06a85f5e-a89f-4437-b12c-e85667fd34f6` at line `41`
  - `trace_id=e2c3306f-4762-4e0a-88c1-9ed6c8ae8f16` at line `42`
- Resource state files:
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_session_current.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_probe_latest.json`
  - `D:\xtquant-mcp\instance\prod\state\trade_resources\diag_login_latest.json`
- Restarted gateway logs:
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_124037.log`
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_124037.stderr.log`

## VAL-002 Status Impact

- Release posture: `no change`
  - `VAL-002` remains `blocked`
  - `VAL-003` must not start from this EvidencePack
- Diagnostic posture: `changed`
  - This fresh gateway-side rerun proves the patched gateway can now restart cleanly from repo-supported path even when the pre-state is `8765 down`
  - It also proves the restarted gateway can establish and expose a ready owner-managed session
  - The remaining blockers are narrower than before and no longer centered on `session_not_ready` after warm

## Verdict

`partial`. This fresh gateway-side rerun succeeded on the repo-supported restart path and produced a materially improved live `G3` profile on the restarted process: `session.warm`, `session.status`, `trade://session/current`, `account.show`, `positions.list`, and `snapshot.l1` all succeeded. But the full ordered chain still did not pass, because `miniqmt.ensure_logged_in` failed with `desktop_not_interactive`, `probe.connection` failed with `connect_failed`, and public `orders.list` failed with `xttrader connect failed: -1`. The task-level `VAL-002` posture therefore remains `blocked`, and `VAL-003` must not start.
