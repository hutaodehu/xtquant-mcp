# EvidencePack

Task ID: VAL-002
Role: test
Date: 2026-03-30T09:07:57+08:00
Acceptance Gate: G3
Conclusion: fail_env

## Env Snapshot

- Link: D:\xtquant-mcp\repo\docs\env_snapshots\VAL-002-test-20260330-postpatch-rerun.md
- Host: CHIYU
- Shell: PowerShell 7.6.0
- Config:
  - D:\xtquant-mcp\repo\docs\task_cards\VAL-002.md
  - D:\xtquant-mcp\repo\docs\change_packages\VAL-002.md
  - D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml

## Test Scope

1. Inspect the current prod-scoped trade gateway listener, process start time, command line, and `/healthz`.
2. Restart the trade gateway so the post-patch repo code is loaded, using the repo-supported wake path (`scripts/wake_trade_gateway.ps1`) after manually stopping the existing listener process.
3. Run the minimal live `VAL-002` preflight sequence on the restarted gateway:
   - `miniqmt.ensure_logged_in`
   - `session.warm`
   - `session.status`
4. Capture exact commands, timestamps, MCP `trace_id` / `server_ts`, and artifact/log paths, then classify with repo vocabulary.

## Commands

1. Pre-restart listener and health inspection:

```powershell
$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
  $procId = $listener.OwningProcess
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$procId"
  [ordered]@{
    pid = $procId
    creation_date = $proc.CreationDate
    executable_path = $proc.ExecutablePath
    command_line = $proc.CommandLine
  } | ConvertTo-Json -Depth 4
}

Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/healthz -TimeoutSec 5 | Select-Object -ExpandProperty Content
```

2. Restart attempt that stopped the old listener and invoked the repo-supported wake script:

```powershell
$ErrorActionPreference='Stop'
$beforeTs = Get-Date
$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
$beforeProcId = $listener.OwningProcess
$beforeProc = Get-CimInstance Win32_Process -Filter "ProcessId=$beforeProcId"
Stop-Process -Id $beforeProcId -Force
$wakeTs = Get-Date
$wakeOutput = & pwsh -File scripts\wake_trade_gateway.ps1 2>&1
$wakeExit = $LASTEXITCODE
```

3. Minimal live MCP preflight against the restarted gateway via inline Python JSON-RPC:

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

def request(conn, payload, session_id=""):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    conn.request("POST", PATH, body=body, headers=headers)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8")
    return {
        "http_status": resp.status,
        "mcp_session_id": resp.getheader("Mcp-Session-Id"),
        "protocol_version": resp.getheader("MCP-Protocol-Version"),
        "json": json.loads(raw),
    }

conn = http.client.HTTPConnection(HOST, PORT, timeout=90)
init = request(conn, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
session_id = init["mcp_session_id"] or ""
sequence = [
    ("miniqmt.ensure_logged_in", {"login_timeout_seconds": 20}),
    ("session.warm", {}),
    ("session.status", {}),
]
for index, (name, arguments) in enumerate(sequence, start=10):
    request(
        conn,
        {"jsonrpc": "2.0", "id": index, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
        session_id=session_id,
    )
request(conn, {"jsonrpc": "2.0", "id": 99, "method": "resources/read", "params": {"uri": "trade://session/current"}}, session_id=session_id)
conn.close()
'@ | D:\xtquant-mcp\venv313\Scripts\python.exe -
```

## Raw Results

- Pre-restart trade gateway baseline:
  - Listener on `127.0.0.1:8765` was pid `35040`.
  - Process creation time: `2026-03-30T08:34:16+08:00`.
  - Executable path reported by Windows: `C:\Python313\python.exe`.
  - Command line: `"D:\xtquant-mcp\venv313\Scripts\python.exe" D:\xtquant-mcp\repo\scripts\run_trade_gateway_http.py --config D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
  - `/healthz` before restart returned `ok=true`, `account_contract=single_account_primary`, `account_input_mode=service_context_only`, `evidence_scope=prod`.

- Restart/load verification:
  - Repo inspection found no dedicated `restart_trade_gateway` helper; the supported bootstrap path is `pwsh -File scripts\wake_trade_gateway.ps1`.
  - The combined stop+wake shell command timed out after `124033 ms`, so no direct wake-script JSON payload was captured from that shell.
  - Despite the shell timeout, the restart did complete:
    - New listener pid became `22620`.
    - New process creation time became `2026-03-30T09:03:52.574399+08:00`.
    - New log files appeared:
      - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_090352.log`
      - `D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_090352.stderr.log`
    - `/healthz` after restart still returned `ok=true`.
  - This verifies the gateway process was replaced and relaunched from the repo entrypoint before the live rerun.

- Minimal live preflight on the restarted gateway:
  - MCP session initialization:
    - Started `2026-03-30T09:06:59.771266+08:00`
    - `initialize` returned HTTP `200`
    - `mcp_session_id=a72b7ab5-3447-4eea-9f0f-1647a809f887`
    - `protocol_version=2025-03-26`
  - `miniqmt.ensure_logged_in`
    - Started `2026-03-30T09:06:59.774842+08:00`
    - Finished `2026-03-30T09:07:20.260015+08:00`
    - `ok=false`
    - `error.code=miniqmt_not_logged_in`
    - `error.category=environment`
    - `status=login_window_not_found`
    - `process_id=25880`
    - `port_ready=true`
    - `trace_id=101bd2a2-078b-4d88-95c0-5d57714b20fd`
    - `server_ts=2026-03-30T09:06:59`
    - `duration_ms=20483`
  - `session.warm`
    - Started `2026-03-30T09:07:20.260026+08:00`
    - Finished `2026-03-30T09:07:29.729064+08:00`
    - `ok=false`
    - `error.code=server_env_not_ready`
    - `error.category=environment`
    - Message:
      `session_warm_failed: auto_account discovery failed across session candidates: session_id=100 error=xttrader connect failed: -1 (callback_registered=True, callback_status=ok); session_id=101 error=xttrader connect failed: -1 (callback_registered=True, callback_status=ok); session_id=111 error=xttrader connect failed: -1 (callback_registered=True, callback_status=ok)`
    - `trace_id=d12c5157-44ab-498d-86fe-65b99332907e`
    - `server_ts=2026-03-30T09:07:20`
    - `duration_ms=9467`
  - `session.status`
    - Started `2026-03-30T09:07:29.729078+08:00`
    - Finished `2026-03-30T09:07:29.730118+08:00`
    - `ok=true`
    - `ready=false`
    - `reason=session_not_ready`
    - `owner_generation=0`
    - `account_contract=single_account_primary`
    - `account_input_mode=service_context_only`
    - `trace_id=0db86a8a-ada9-4c46-9e16-3a3807386f51`
    - `server_ts=2026-03-30T09:07:29`
  - `trade://session/current`
    - Read immediately after the tool sequence under the same MCP session.
    - Payload remained `ready=false`, `reason=session_not_ready`, `account_id=''`, `owner_account_id=''`, `session_id=''`, `owner_generation=0`.

- Comparison with the earlier live failure:
  - The environment is still blocking `G3`.
  - The rerun does not show a successful owner-managed session.
  - The observed `session.warm` failure text is now different from the earlier `VAL-002-test-202603300306.md` run: it reports auto-account discovery failure across candidate session IDs `100/101/111`, which is consistent with the restarted process exercising the newer post-patch path rather than reusing the older already-running process.

## Artifact Refs

- Trade gateway call log:
  - D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260330\trade_gateway_calls.jsonl
- Call log line verification for this rerun:
  - `trace_id=101bd2a2-078b-4d88-95c0-5d57714b20fd` at line `24`
  - `trace_id=d12c5157-44ab-498d-86fe-65b99332907e` at line `25`
  - `trace_id=0db86a8a-ada9-4c46-9e16-3a3807386f51` at line `26`
- Trade gateway logs:
  - D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_090352.log
  - D:\xtquant-mcp\instance\prod\logs\trade_gateway\trade_gateway_20260330_090352.stderr.log
- Prior live baseline for comparison:
  - D:\xtquant-mcp\repo\docs\evidence_packs\VAL-002-test-202603300306.md

## Failure Classification

- `fail_env`: confirmed in this rerun.
  - `XtMiniQmt` and `miniquote` were running and `127.0.0.1:58610` was reachable.
  - `miniqmt.ensure_logged_in` still failed with `miniqmt_not_logged_in` / `login_window_not_found`.
  - `session.warm` still failed at the environment layer with `xttrader connect failed: -1`, now surfaced through the auto-account discovery path.
  - `session.status` remained `ready=false`, `reason=session_not_ready`.
- `fail_design`: not proven by this run.
  - The gateway did restart and serve the patched repo entrypoint.
  - The hard stop remained in MiniQMT / xttrader environment readiness before a usable session could be established.

## Verdict

`fail_env`. The trade gateway process was replaced and the live rerun executed on the restarted process, but the minimal `VAL-002` preflight still cannot establish an owner-managed session. The observable result is still environment-blocked, even though the `session.warm` failure shape changed after restart. Do not treat this rerun as `pass`, `partial`, or `fail_design`, and do not advance to `VAL-003`.
