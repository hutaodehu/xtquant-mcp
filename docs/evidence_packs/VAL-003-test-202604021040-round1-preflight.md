# EvidencePack

Task ID: VAL-003
Role: test
Date: 2026-04-02T10:46:14.6076017+08:00
Acceptance Gate: G4
Conclusion: blocked

## Env Snapshot

- Link: [VAL-003-202604021040-round1-preflight.md](../env_snapshots/VAL-003-202604021040-round1-preflight.md)

## Scope

1. Re-run the formal Round 1 preflight for the current 2026-04-02 Beijing-time window only.
2. Capture host/process/port `/healthz` and minimal trade MCP probe evidence without entering any write path.
3. Decide whether current repo rules allow escalation to Round 2.

## Go/No-Go Packet

- side: `BUY`
- symbol: `515880.SH`
- qty: `100`
- price_mode: `l1_protect`
- cancel_timeout: `30s`
- execution result in this run: `NO-GO`
- `order.place` executed: `no`

## Required Sources Re-Read First

1. [VAL-003.md](../task_cards/VAL-003.md)
2. [CURRENT_STATUS.md](../CURRENT_STATUS.md)
3. [ACCEPTANCE_STANDARD.md](../ACCEPTANCE_STANDARD.md)
4. [OPERATIONS_RUNBOOK.md](../OPERATIONS_RUNBOOK.md)
5. [VAL-003_G4_EXECUTION_PLAN.md](../VAL-003_G4_EXECUTION_PLAN.md)
6. `.tmp/spec-task-harness/VAL-003-controller-judgment-20260402T102816+0800.md`
7. `.tmp/spec-task-harness/VAL-003-dispatch-20260402T102816+0800.md`

## Commands

1. Fresh wall clock:
   - `Get-Date -Format o`
   - `Get-Date -Format o`
2. Process check:
   - `Get-Process XtMiniQmt,miniquote -ErrorAction SilentlyContinue | Select-Object ProcessName,Id,StartTime,Path | Format-List`
3. Port checks:
   - `Test-NetConnection 127.0.0.1 -Port 58610 | Select-Object ComputerName,RemotePort,TcpTestSucceeded | Format-List`
   - `Test-NetConnection 127.0.0.1 -Port 8765 | Select-Object ComputerName,RemotePort,TcpTestSucceeded | Format-List`
   - `Test-NetConnection 127.0.0.1 -Port 8766 | Select-Object ComputerName,RemotePort,TcpTestSucceeded | Format-List`
4. Gateway health:
   - `Invoke-RestMethod http://127.0.0.1:8765/healthz | ConvertTo-Json -Depth 8`
   - `Invoke-RestMethod http://127.0.0.1:8766/healthz | ConvertTo-Json -Depth 8`
5. Repo-supported Python HTTP client against `http://127.0.0.1:8765/mcp`:
   - `initialize`
   - `tools/call probe.connection {}`
   - `resources/read diag://probe/latest`
6. Trace back-link attempts:
   - `Select-String -Path D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260402\trade_gateway_calls.jsonl -Pattern 'b05bcd80-cefa-43a9-9225-593dcbd33e53'`
   - `Select-String -Path D:\xtquant-mcp\repo\output\mcp_gateway\20260402\gateway_calls.jsonl -Pattern 'b05bcd80-cefa-43a9-9225-593dcbd33e53'`
   - `Select-String -Path D:\xtquant-mcp\output\mcp_gateway\20260402\gateway_calls.jsonl -Pattern 'b05bcd80-cefa-43a9-9225-593dcbd33e53'`
7. Read-only lookup to verify whether any current-day trade call log exists:
   - `rg --files D:\xtquant-mcp -g "*gateway_calls.jsonl"`
   - `rg -n "b05bcd80-cefa-43a9-9225-593dcbd33e53" D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260401\trade_gateway_calls.jsonl D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260331\trade_gateway_calls.jsonl D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260330\trade_gateway_calls.jsonl`

## Raw Results

- Formal posture before runtime checks:
  - [VAL-003 task card](../task_cards/VAL-003.md) still records `Status: Blocked` and `Blocking Reason: broker_blocked`.
  - [CURRENT_STATUS.md](../CURRENT_STATUS.md) still keeps `VAL-003` as the only remaining `Trade Lane Write` gap and still labels it `Blocked / broker_blocked`.
  - Controller judgment `2026-04-02T10:28:16+08:00` explicitly restricts the next safe delegated step to fresh Round 1 only and says the task is still not auto-dispatchable.

- Fresh wall clock:
  - preflight start: `2026-04-02T10:44:09.3245458+08:00`
  - snapshot closeout time: `2026-04-02T10:46:14.6076017+08:00`

- Process and port facts:
  - `XtMiniQmt.exe` present:
    - pid `24380`
    - start `2026/4/1 23:57:03`
    - path `D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
  - `miniquote.exe` present:
    - pid `24184`
    - start `2026/4/1 23:57:03`
    - path `D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe`
  - `127.0.0.1:58610` -> `TcpTestSucceeded=True`
  - `127.0.0.1:8765` -> `TcpTestSucceeded=True`
  - `127.0.0.1:8766` -> `TcpTestSucceeded=True`

- `/healthz` facts:
  - trade gateway `http://127.0.0.1:8765/healthz` returned HTTP `200` with:
    - `ok=true`
    - `server_name=xtquantGateway`
    - `server_version=1.4.1`
    - `transport_mode=streamable_http`
    - `bind_port=8765`
    - `mcp_path=/mcp`
    - `protocol_version_http=2025-11-25`
    - enabled tools include `probe.connection`, `order.place`, `order.status`, `order.cancel`, `orders.list`, and `fills.list`
  - data gateway `http://127.0.0.1:8766/healthz` did not return a JSON health payload.
    - command result: `Invoke-RestMethod ... -> Not Found`
    - this is an HTTP `404` at the documented Round 1 health endpoint, despite `127.0.0.1:8766` being reachable by TCP.

- Repo-supported Python HTTP client results against `http://127.0.0.1:8765/mcp`:
  - `initialize`
    - start `2026-04-02T10:44:59.176583+08:00`
    - finish `2026-04-02T10:44:59.179777+08:00`
    - HTTP `200`
    - `Mcp-Session-Id=null`
    - protocol `2025-11-25`
    - result server info:
      - `name=xtquantGateway`
      - `version=1.4.1`
  - `tools/call probe.connection {}`
    - start `2026-04-02T10:44:59.179812+08:00`
    - finish `2026-04-02T10:45:02.021399+08:00`
    - HTTP `200`
    - `isError=false`
    - `structuredContent.ok=true`
    - `structuredContent.data.ok=true`
    - `connect_code=0`
    - `session_id=1111`
    - `account_id=8883884325`
    - `reason=ok`
    - `precheck.qmt_exe_exists=true`
    - `precheck.process_exists=true`
    - `precheck.xtdata_port_ready=true`
    - `userdata_precheck.up_queue_xtquant_exists=true`
    - `overall_trade_ready=true`
    - `market_data_ok=true`
    - `snapshot_ok=true`
    - `probe_scope_note=probe.connection 仅覆盖 vendor 行情探针与 trader shadow snapshot，不等价于 snapshot.l1`
    - audit:
      - `trace_id=b05bcd80-cefa-43a9-9225-593dcbd33e53`
      - `server_ts=2026-04-02T10:44:59`
      - `duration_ms=2843`
      - artifacts advertised by the gateway:
        - `output/mcp_gateway/20260402/gateway_calls.jsonl`
        - `reports_e2e/broker_channel_probe_must_pass.json`
        - `reports_e2e/xtquant_spec_conformance_latest.json`
  - `resources/read diag://probe/latest`
    - start `2026-04-02T10:45:02.021512+08:00`
    - finish `2026-04-02T10:45:02.021823+08:00`
    - HTTP `200`
    - JSON-RPC error:
      - `code=-32601`
      - `message=unknown method: resources/read`

- Trace back-link attempts:
  - expected trade gateway artifact path for today:
    - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260402\trade_gateway_calls.jsonl`
    - result: path does not exist
  - advertised relative output path resolved under repo:
    - `D:\xtquant-mcp\repo\output\mcp_gateway\20260402\gateway_calls.jsonl`
    - result: path does not exist
  - advertised relative output path resolved under sibling root:
    - `D:\xtquant-mcp\output\mcp_gateway\20260402\gateway_calls.jsonl`
    - result: path does not exist
  - read-only file lookup found trade call logs only for:
    - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260330\trade_gateway_calls.jsonl`
    - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260331\trade_gateway_calls.jsonl`
    - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260401\trade_gateway_calls.jsonl`
  - no hit for trace id `b05bcd80-cefa-43a9-9225-593dcbd33e53` was found in those visible historical trade call logs.

## Hard-Stop Assessment

1. `market_window_closed`: does not apply in this run.
   - Current wall clock was `2026-04-02T10:44:09+08:00` to `2026-04-02T10:46:14+08:00`.
   - Under the repo's CN A-share trading-window rules used by `VAL-003/G4`, this time window is inside the morning trading session.

2. Formal posture hard stop: applies.
   - `VAL-003` is still formally `Blocked / broker_blocked`.
   - Controller judgment for `2026-04-02T10:28:16+08:00` still restricts this retry to Round 1 read-only preflight and requires a stop after fresh role-owned artifacts return.

3. Gateway health hard stop: applies.
   - Round 1 requires trade and data gateway `/healthz`.
   - `8766` TCP is open, but `Invoke-RestMethod http://127.0.0.1:8766/healthz` returned `Not Found`.
   - That means the documented data health endpoint was unavailable in this window.

4. Runtime contract completeness for the required resource read: not satisfied.
   - The required Round 1 call `resources/read diag://probe/latest` returned JSON-RPC `-32601 unknown method: resources/read`.
   - This prevents this run from claiming a full Round 1 pass on the documented MCP resource-read contract.

## Separation Of Notes

- Environment-side findings:
  - Data gateway listener port `8766` is reachable, but the documented `/healthz` endpoint returned `404 Not Found`.
  - No current-day trace back-link file could be found at the expected trade call-log locations advertised by runtime output.

- Governance and control-plane findings:
  - Formal posture is still `Blocked / broker_blocked`.
  - Current controller judgment explicitly authorizes Round 1 evidence capture only and still requires a controller reconcile before any Round 2 or Round 3 decision.

- Design and contract findings:
  - The live trade MCP endpoint accepted `initialize` and `tools/call`, but the required `resources/read diag://probe/latest` call returned `unknown method: resources/read`.
  - Trade `/healthz` response shape also differs from the repo's recent trade gateway evidence shape used in prior `VAL-003` no-go artifacts, so current runtime contract drift should be treated as an observation and not silently normalized.

## Execution Boundary

- `order.place` was not executed.
- `order.status` was not executed.
- `orders.list` as write-followup for the governed packet was not executed.
- `order.cancel` was not executed.
- `fills.list` was not executed.

## Verdict

`blocked`. This retry was executed during a live Beijing trading window on 2026-04-02 between `10:44` and `10:46 +08:00`, so `market_window_closed` does not apply. Host-side preflight was materially better than the previous late-night no-go: `XtMiniQmt` and `miniquote` were present, `58610/8765/8766` were reachable, trade `/healthz` was live, and `probe.connection` returned `ok=true` with trace id `b05bcd80-cefa-43a9-9225-593dcbd33e53`. Even so, Round 1 cannot pass and the task cannot proceed. Two independent stops remain active in the current window: the formal posture is still `Blocked / broker_blocked` under controller judgment, and the documented Round 1 environment/runtime contract is incomplete because `8766/healthz` returned `404 Not Found` and `resources/read diag://probe/latest` returned `-32601 unknown method`. Under repo rules the correct result for this retry is therefore `blocked`, stop after Round 1, and return control to the controller for fresh judgment rather than attempting Round 2 or any write-path action.
