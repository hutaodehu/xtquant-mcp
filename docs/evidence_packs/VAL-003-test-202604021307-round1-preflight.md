# EvidencePack

Task ID: VAL-003
Role: test
Date: 2026-04-02T13:07:28.4222453+08:00
Acceptance Gate: G4
Conclusion: blocked

## Env Snapshot

- Link: [VAL-003-202604021307-round1-preflight.md](../env_snapshots/VAL-003-202604021307-round1-preflight.md)

## Scope

1. Re-run the formal Round 1 preflight for the current 2026-04-02 afternoon Beijing-time live window only.
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
2. [ACCEPTANCE_STANDARD.md](../ACCEPTANCE_STANDARD.md)
3. [OPERATIONS_RUNBOOK.md](../OPERATIONS_RUNBOOK.md)
4. [VAL-003_G4_EXECUTION_PLAN.md](../VAL-003_G4_EXECUTION_PLAN.md)
5. [VAL-003-test-202604021132-round1-preflight.md](./VAL-003-test-202604021132-round1-preflight.md)
6. [VAL-003-202604021132-round1-preflight.md](../env_snapshots/VAL-003-202604021132-round1-preflight.md)
7. [VAL-003-review-202604021138.md](../reviews/VAL-003-review-202604021138.md)
8. `.tmp/spec-task-harness/VAL-003-controller-judgment-20260402T130303+0800.md`
9. `.tmp/spec-task-harness/VAL-003-dispatch-20260402T130303+0800.md`

## Commands

1. Fresh wall clock:
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
6. Trace back-link verification:
   - `(Get-Item D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260402\trade_gateway_calls.jsonl).Refresh(); Get-Item D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260402\trade_gateway_calls.jsonl | Select-Object FullName,Length,LastWriteTime | Format-List`
   - `rg -n --fixed-strings "406afa83-dced-4fe1-b23d-7bacb68d5855" D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260402\trade_gateway_calls.jsonl`

## Raw Results

- Formal posture before runtime checks:
  - [VAL-003 task card](../task_cards/VAL-003.md) still records `Status: Blocked` and `Blocking Reason: broker_blocked`.
  - The controller judgment for `2026-04-02T13:03:03+08:00` authorizes only a fresh Round 1 rerun and does not authorize Round 2, Round 3, or any write-path action.

- Fresh wall clock:
  - preflight start: `2026-04-02T13:06:46.4152709+08:00`
  - latest timestamp captured in this run: `2026-04-02T13:07:28.4222453+08:00`

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
    - `server_name=xtqmtTradeGateway`
    - `protocol_version=2025-03-26`
    - `bind_port=8765`
    - `evidence_scope=prod`
    - `evidence_state_root=D:\xtquant-mcp\instance\prod\state`
    - `evidence_artifact_root=D:\xtquant-mcp\instance\prod\artifacts`
  - data gateway `http://127.0.0.1:8766/healthz` returned HTTP `200` with:
    - `ok=true`
    - `server_name=xtqmtDataGateway`
    - `protocol_version=2025-03-26`
    - `bind_port=8766`
    - `evidence_scope=prod`

- Repo-supported Python HTTP client results against `http://127.0.0.1:8765/mcp`:
  - `initialize`
    - start `2026-04-02T13:07:09.371194+08:00`
    - finish `2026-04-02T13:07:09.374470+08:00`
    - HTTP `200`
    - protocol `2025-03-26`
    - result server info:
      - `name=xtqmtTradeGateway`
      - `version=2.0.0a0`
  - `tools/call probe.connection {}`
    - start `2026-04-02T13:07:09.374511+08:00`
    - finish `2026-04-02T13:07:09.375458+08:00`
    - HTTP `200`
    - `isError=true`
    - `structuredContent.ok=false`
    - error:
      - `code=session_not_ready`
      - `message=session_not_ready`
      - `category=environment`
      - `retryable=true`
    - audit:
      - `trace_id=406afa83-dced-4fe1-b23d-7bacb68d5855`
      - `server_ts=2026-04-02T13:07:09`
      - `duration_ms=0`
      - artifacts advertised by the gateway:
        - `D:/xtquant-mcp/instance/prod/artifacts/trade_gateway/20260402/trade_gateway_calls.jsonl`
  - `resources/read diag://probe/latest`
    - start `2026-04-02T13:07:09.375491+08:00`
    - finish `2026-04-02T13:07:09.380088+08:00`
    - HTTP `200`
    - JSON-RPC result returned successfully
    - `uri=diag://probe/latest`
    - payload text:
      - `{"account_contract":"single_account_primary","account_input_mode":"service_context_only","account_scope":"service_context"}`

- Trace back-link verification:
  - current-day trade call-log path exists:
    - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260402\trade_gateway_calls.jsonl`
  - file facts after this rerun:
    - `Length=2564`
    - `LastWriteTime=2026/4/2 13:07:09`
  - trace lookup:
    - `rg` found `406afa83-dced-4fe1-b23d-7bacb68d5855` at line `4`

## Hard-Stop Assessment

1. `market_window_closed`: does not apply in this run.
   - Current wall clock was `2026-04-02T13:06:46+08:00` to `2026-04-02T13:07:28+08:00`.
   - Under the repo's `VAL-003/G4` CN A-share timing rules, this observed window is inside the afternoon live trading session.

2. Formal posture hard stop: applies.
   - `VAL-003` is still formally `Blocked / broker_blocked`.
   - The controller judgment for `2026-04-02T13:03:03+08:00` still restricts this rerun to Round 1 evidence capture only and still requires a stop after fresh role-owned artifacts return.

3. Runtime readiness hard stop: applies.
   - `probe.connection` still returned `session_not_ready`.
   - This run therefore did not produce a current live read-only readiness shape that would justify escalating toward Round 2.

4. Prior contract blockers from the earlier retries: do not apply.
   - `8766/healthz` returns a repo-backed JSON payload.
   - `resources/read diag://probe/latest` succeeds.
   - current-day trade call-log back-link exists and includes the current trace id.

## Separation Of Notes

- Environment-side findings:
  - host process and ports are up
  - current wall clock is inside the live afternoon session
  - runtime probe still reports `session_not_ready`

- Governance and control-plane findings:
  - formal posture remains `Blocked / broker_blocked`
  - this rerun stayed confined to Round 1 only

- Design and contract findings:
  - the previously observed runtime/doc drift around `8766/healthz` and `resources/read diag://probe/latest` remains resolved on the currently running repo-backed gateways
  - `diag://probe/latest` still returns a minimal contract-scoped payload rather than a richer live readiness snapshot; that is an observation, not the primary blocker for this rerun

## Execution Boundary

- `order.place` was not executed.
- `order.status` was not executed.
- `orders.list` as write-followup for the governed packet was not executed.
- `order.cancel` was not executed.
- `fills.list` was not executed.

## Verdict

`blocked`. This rerun materially improves the `202604021132` Round 1 retry on window timing because it was executed during the live afternoon Beijing trading session, so `market_window_closed` no longer applies. Endpoint-contract truth also remains healthy: both repo-backed `/healthz` endpoints are live, `resources/read diag://probe/latest` works, and the same-day `trade_gateway_calls.jsonl` back-link is present for trace `406afa83-dced-4fe1-b23d-7bacb68d5855`. Even so, the runtime readiness result did not improve: `probe.connection` still returns `session_not_ready`, and the card remains formally `Blocked / broker_blocked`. Under repo rules the correct result for this rerun remains `blocked`, stop after Round 1, and return control to the controller for fresh review rather than attempting Round 2 or any write-path action.
