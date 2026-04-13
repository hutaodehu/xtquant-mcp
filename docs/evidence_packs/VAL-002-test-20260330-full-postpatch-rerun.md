# EvidencePack

Task ID: VAL-002
Role: test
Date: 2026-03-30T11:00:43.3485741+08:00
Acceptance Gate: G3
Conclusion: fail_env

## Env Snapshot

- Link: [VAL-002-test-20260330-full-postpatch-rerun.md](../env_snapshots/VAL-002-test-20260330-full-postpatch-rerun.md)
- Host: CHIYU
- Shell: PowerShell 7.6.0
- Config:
  - [VAL-002.md](../task_cards/VAL-002.md)
  - [VAL-002.md](../change_packages/VAL-002.md)
  - `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Code Version:
  - `git rev-parse HEAD` and `git status --short` both returned `fatal: not a git repository (or any of the parent directories): .git`
  - Runtime version was therefore verified by process replacement plus command line pointing at repo entrypoint `D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py`

## Test Scope

1. Inspect the current prod-scoped trade gateway listener, pid, start time, command line, and `/healthz`.
2. Restart the trade gateway through the repo-supported path so the latest repo code is loaded:
   - stop the existing `8765` listener process
   - invoke `pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1`
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
5. Capture exact timestamps, `trace_id`, `server_ts`, artifact/log paths, and classify whether this changes the current blocked status.

## Commands

1. Pre-restart listener and health inspection:

```powershell
$ErrorActionPreference='Stop'
$ts = Get-Date
$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $listener) { throw 'No listener on 8765' }
$procId = $listener.OwningProcess
$proc = Get-CimInstance Win32_Process -Filter "ProcessId=$procId"
$health = Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8765/healthz' -TimeoutSec 5
[ordered]@{
  observed_at = $ts.ToString('o')
  listener = [ordered]@{
    local_address = $listener.LocalAddress
    local_port = $listener.LocalPort
    state = $listener.State.ToString()
    pid = $procId
  }
  process = [ordered]@{
    creation_date = $proc.CreationDate
    executable_path = $proc.ExecutablePath
    command_line = $proc.CommandLine
  }
  health = $health
} | ConvertTo-Json -Depth 8
```

2. Controlled stop of the old trade gateway listener:

```powershell
$ErrorActionPreference='Stop'
$ts = Get-Date
$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $listener) { throw 'No listener on 8765 before restart' }
$procId = $listener.OwningProcess
$proc = Get-CimInstance Win32_Process -Filter "ProcessId=$procId"
Stop-Process -Id $procId -Force
[ordered]@{
  stopped_at = $ts.ToString('o')
  stopped_pid = $procId
  stopped_creation_date = $proc.CreationDate
  stopped_command_line = $proc.CommandLine
} | ConvertTo-Json -Depth 6
```

3. Repo-supported wake path:

```powershell
pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1
```

4. Post-restart listener and latest log verification:

```powershell
$ErrorActionPreference='Stop'
$ts = Get-Date
$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $listener) { throw 'No listener on 8765 after wake attempt' }
$procId = $listener.OwningProcess
$proc = Get-CimInstance Win32_Process -Filter "ProcessId=$procId"
$health = Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8765/healthz' -TimeoutSec 5
[ordered]@{
  observed_at = $ts.ToString('o')
  listener = [ordered]@{
    pid = $procId
    local_address = $listener.LocalAddress
    local_port = $listener.LocalPort
    state = $listener.State.ToString()
  }
  process = [ordered]@{
    creation_date = $proc.CreationDate
    executable_path = $proc.ExecutablePath
    command_line = $proc.CommandLine
  }
  health = $health
} | ConvertTo-Json -Depth 8

Get-ChildItem -Path D:\xtquant-mcp\instance\prod\logs\trade_gateway -File |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 4 FullName,LastWriteTime,Length |
  ConvertTo-Json -Depth 4
```

5. Full live MCP rerun against the restarted gateway:

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
    conn.request("POST", PATH, body=body, headers=headers)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8")
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = {"_raw": raw}
    return {
        "http_status": resp.status,
        "mcp_session_id": resp.getheader("Mcp-Session-Id"),
        "protocol_version": resp.getheader("MCP-Protocol-Version"),
        "json": parsed,
    }

conn = http.client.HTTPConnection(HOST, PORT, timeout=120)
init_resp = post(conn, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
session_id = init_resp.get("mcp_session_id") or ""
sequence = [
    ("miniqmt.ensure_logged_in", {"login_timeout_seconds": 20}),
    ("session.warm", {}),
    ("session.status", {}),
    ("probe.connection", {}),
    ("account.show", {}),
    ("positions.list", {}),
    ("orders.list", {}),
    ("snapshot.l1", {"code": "000001.SZ"}),
]
for index, (name, arguments) in enumerate(sequence, start=10):
    post(
        conn,
        {"jsonrpc": "2.0", "id": index, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
        session_id=session_id,
    )
for index, uri in enumerate(["trade://session/current", "diag://probe/latest", "diag://login/latest"], start=100):
    post(
        conn,
        {"jsonrpc": "2.0", "id": index, "method": "resources/read", "params": {"uri": uri}},
        session_id=session_id,
    )
conn.close()
'@ | D:\xtquant-mcp\venv313\Scripts\python.exe -
```

6. Trace verification in the trade gateway call log:

```powershell
$log = 'D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260330\trade_gateway_calls.jsonl'
@(
 'debddf2f-324d-406f-9f1d-dfede04e2de9',
 '1742ea3a-4eb2-4035-b5a1-e40c0e24ad34',
 'befe406d-8c9c-43f3-bc24-dc5ba0034cf5',
 '7654528f-44c9-42a2-acf1-5bb2f5e0a61a',
 '3c08c256-cd6c-4116-b19b-2ac79f9abe29',
 '3322c617-79a3-4f81-9f2c-b46a952dc50b',
 'f8c7bd6b-8354-40d5-9df3-c1785c90a4bd',
 '1ed6418b-cb9b-423f-85f0-98787d4cf9f4'
) | ForEach-Object { rg -n --fixed-strings $_ $log }
```

## Raw Results

- Pre-restart trade gateway baseline:
  - Observed at: `2026-03-30T10:54:56.0702144+08:00`
  - Listener: `127.0.0.1:8765`
  - pid: `22620`
  - Start time: `2026-03-30T09:03:52.574399+08:00`
  - Executable path: `C:\Python313\python.exe`
  - Command line: `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
  - `/healthz`: `ok=true`, `server_name=xtqmtTradeGateway`, `bind_port=8765`, `account_contract=single_account_primary`, `account_input_mode=service_context_only`, `evidence_scope=prod`

- Restart/load verification:
  - Old listener pid `22620` was stopped at `2026-03-30T10:55:06.8550276+08:00`
  - Repo-supported wake path was `pwsh -File D:\xtquant-mcp\repo\scripts\wake_trade_gateway.ps1`
  - The wake-shell call itself timed out after `94035 ms`, so there was no captured wake-script JSON payload
  - Despite the shell timeout, restart completed successfully:
    - New listener observed at `2026-03-30T10:57:04.2564051+08:00`
    - New pid: `42768`
    - New process start time: `2026-03-30T10:55:16.961535+08:00`
    - New command line remained the repo entrypoint:
      `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
    - New logs:
      - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_105516.log`
      - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_105516.stderr.log`
    - `/healthz` after restart stayed `ok=true`
  - This is sufficient evidence that the old process was replaced and the rerun executed on a fresh repo-loaded gateway process.

- Full live `G3` chain on the restarted gateway:
  - MCP initialize:
    - Started: `2026-03-30T10:57:37.057735+08:00`
    - Finished: `2026-03-30T10:57:37.060461+08:00`
    - HTTP `200`
    - `mcp_session_id=d92b421a-723d-4053-b409-63ad29846f45`
    - `protocol_version=2025-03-26`
  - `miniqmt.ensure_logged_in`
    - Started: `2026-03-30T10:57:37.060470+08:00`
    - Finished: `2026-03-30T10:57:37.147954+08:00`
    - `ok=true`
    - `status=already_logged_in`
    - `message=MiniQMT already logged in`
    - `process_id=25880`
    - `port_ready=true`
    - `initial_observation.main_window_found=true`
    - `initial_observation.login_window_found=false`
    - `evidence.host_window_fallback_used=true`
    - `trace_id=debddf2f-324d-406f-9f1d-dfede04e2de9`
    - `server_ts=2026-03-30T10:57:37`
    - `duration_ms=86`
  - `session.warm`
    - Started: `2026-03-30T10:57:37.147963+08:00`
    - Finished: `2026-03-30T10:59:09.417833+08:00`
    - `ok=false`
    - `error.code=session_warm_failed`
    - `error.category=environment`
    - `error.message=session warm health check failed: orders.list_exception`
    - `account_id=8883884325`
    - `session_id=101`
    - `ready=false`
    - `reason=orders.list_exception`
    - `last_check_at=2026-03-30T10:57:53`
    - `wake_report.status=already_ready`
    - `wake_report.xtdata_port_ready_before=true`
    - `wake_report.xtdata_port_ready_after=true`
    - `warm_trace` / `status_trace` show partial recovery before the broker stop:
      - shadow `account.show` succeeded with `cash=4497.04`, `total_asset=116612.04`, `market_value=112115.0`, `source=xttrader_shadow`
      - shadow `positions.list` succeeded with `count=2`
      - broker `orders.list` then failed with:
        `xttrader connect failed: -1 after 3 attempts (session=101, session_plan=[101, 100, 111], ... )`
    - `trace_id=1742ea3a-4eb2-4035-b5a1-e40c0e24ad34`
    - `server_ts=2026-03-30T10:57:37`
    - `duration_ms=92268`
  - `session.status`
    - Started: `2026-03-30T10:59:09.417842+08:00`
    - Finished: `2026-03-30T10:59:09.418628+08:00`
    - `ok=true`
    - `ready=false`
    - `reason=session_not_ready`
    - `owner_generation=0`
    - `account_contract=single_account_primary`
    - `account_input_mode=service_context_only`
    - `trace_id=befe406d-8c9c-43f3-bc24-dc5ba0034cf5`
    - `server_ts=2026-03-30T10:59:09`
  - `probe.connection`
    - Started: `2026-03-30T10:59:09.418634+08:00`
    - Finished: `2026-03-30T10:59:09.419297+08:00`
    - `ok=false`
    - `error.code=session_not_ready`
    - `error.category=environment`
    - `trace_id=7654528f-44c9-42a2-acf1-5bb2f5e0a61a`
    - `server_ts=2026-03-30T10:59:09`
  - `account.show`
    - Started: `2026-03-30T10:59:09.419303+08:00`
    - Finished: `2026-03-30T10:59:09.419949+08:00`
    - `ok=false`
    - `error.code=session_not_ready`
    - `error.category=environment`
    - `trace_id=3c08c256-cd6c-4116-b19b-2ac79f9abe29`
    - `server_ts=2026-03-30T10:59:09`
  - `positions.list`
    - Started: `2026-03-30T10:59:09.419955+08:00`
    - Finished: `2026-03-30T10:59:09.420425+08:00`
    - `ok=false`
    - `error.code=session_not_ready`
    - `error.category=environment`
    - `trace_id=3322c617-79a3-4f81-9f2c-b46a952dc50b`
    - `server_ts=2026-03-30T10:59:09`
  - `orders.list`
    - Started: `2026-03-30T10:59:09.420431+08:00`
    - Finished: `2026-03-30T10:59:09.421107+08:00`
    - `ok=false`
    - `error.code=session_not_ready`
    - `error.category=environment`
    - `trace_id=f8c7bd6b-8354-40d5-9df3-c1785c90a4bd`
    - `server_ts=2026-03-30T10:59:09`
  - `snapshot.l1`
    - Started: `2026-03-30T10:59:09.421112+08:00`
    - Finished: `2026-03-30T10:59:09.421660+08:00`
    - `ok=false`
    - `error.code=session_not_ready`
    - `error.category=environment`
    - `trace_id=1ed6418b-cb9b-423f-85f0-98787d4cf9f4`
    - `server_ts=2026-03-30T10:59:09`
  - `trade://session/current`
    - Read at `2026-03-30T10:59:09.421673+08:00`
    - `ready=false`
    - `reason=session_not_ready`
    - `account_id=''`
    - `owner_account_id=''`
    - `session_id=''`
    - `owner_generation=0`
  - `diag://probe/latest`
    - Read at `2026-03-30T10:59:09.421992+08:00`
    - Contained only contract metadata:
      - `account_contract=single_account_primary`
      - `account_input_mode=service_context_only`
      - `account_scope=service_context`
    - No successful probe payload was available after the hard stop
  - `diag://login/latest`
    - Read at `2026-03-30T10:59:09.427035+08:00`
    - Mirrored the successful `already_logged_in` result from this rerun

- Comparison with the earlier blocked live evidence:
  - This rerun progressed farther than `docs/evidence_packs/VAL-002-test-202603300306.md`
  - `miniqmt.ensure_logged_in` recovered from `login_window_not_found` to `already_logged_in`
  - `session.warm` now shows partial shadow-read progress (`account.show` and `positions.list`) before failing at broker-side `orders.list_exception`
  - This is still not a `G3 pass`, because the owner-managed session never became ready and the explicit downstream read tools all stayed on `session_not_ready`

## Artifact Refs

- Trade gateway call log:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260330\trade_gateway_calls.jsonl`
- Call log line verification for this rerun:
  - `trace_id=debddf2f-324d-406f-9f1d-dfede04e2de9` at line `27`
  - `trace_id=1742ea3a-4eb2-4035-b5a1-e40c0e24ad34` at line `28`
  - `trace_id=befe406d-8c9c-43f3-bc24-dc5ba0034cf5` at line `29`
  - `trace_id=7654528f-44c9-42a2-acf1-5bb2f5e0a61a` at line `30`
  - `trace_id=3c08c256-cd6c-4116-b19b-2ac79f9abe29` at line `31`
  - `trace_id=3322c617-79a3-4f81-9f2c-b46a952dc50b` at line `32`
  - `trace_id=f8c7bd6b-8354-40d5-9df3-c1785c90a4bd` at line `33`
  - `trace_id=1ed6418b-cb9b-423f-85f0-98787d4cf9f4` at line `34`
- Trade gateway logs for the restarted process:
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_105516.log`
  - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_105516.stderr.log`
- Prior live baselines:
  - [VAL-002-test-202603300306.md](./VAL-002-test-202603300306.md)
  - [VAL-002-test-20260330-postpatch-rerun.md](./VAL-002-test-20260330-postpatch-rerun.md)

## Failure Classification

- `fail_env`: confirmed in this rerun
  - The gateway restart succeeded and the rerun executed on a fresh repo-loaded process
  - MiniQMT visibility/login readiness improved enough for `miniqmt.ensure_logged_in` to return `already_logged_in`
  - The current hard stop is now `session.warm`:
    - `reason=orders.list_exception`
    - root broker error is `xttrader connect failed: -1`
    - candidate session plan observed: `101`, `100`, `111`
  - Because owner-managed session establishment still fails, the explicit downstream `probe.connection`, `account.show`, `positions.list`, `orders.list`, and `snapshot.l1` calls remain blocked with `session_not_ready`
- `fail_design`: not proven by this run
  - The run does not show schema drift or contract mismatch as the first-order stop
  - The observed stop is a live environment/broker-session failure after restart, not a demonstrated design-contract failure

## VAL-002 Status Impact

- This rerun does not clear the current `VAL-002` blocked posture
- It does show sub-step recovery versus the earlier baseline:
  - login moved from `login_window_not_found` to `already_logged_in`
  - `session.warm` now exposes deeper diagnostics and partial shadow-read progress
- But the task-level result remains blocked because `G3` still does not complete end-to-end and the broker/session layer still fails in `session.warm`
- `VAL-003` must remain blocked

## Verdict

`fail_env`. The trade gateway restart succeeded and the rerun executed on the fresh repo-loaded process, but `VAL-002` `G3` is still blocked at `session.warm` by `orders.list_exception -> xttrader connect failed: -1`. This run progressed farther than the earlier `login_window_not_found` baseline, but it still does not establish an owner-managed ready session, so it does not change the existing `VAL-002` blocked status and does not allow `VAL-003` to start.
