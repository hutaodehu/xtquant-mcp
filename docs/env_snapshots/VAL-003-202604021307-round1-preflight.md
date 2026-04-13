# EnvSnapshot

Task ID: VAL-003
Date: 2026-04-02T13:07:28.4222453+08:00
Role: test

## Host

- Working Directory: `D:\xtquant-mcp\repo`
- EvidencePack: [VAL-003-test-202604021307-round1-preflight.md](../evidence_packs/VAL-003-test-202604021307-round1-preflight.md)
- TaskCard: [VAL-003.md](../task_cards/VAL-003.md)
- ChangePack: [VAL-003.md](../change_packages/VAL-003.md)
- Controller Judgment Input:
  - `.tmp/spec-task-harness/VAL-003-controller-judgment-20260402T130303+0800.md`
  - `.tmp/spec-task-harness/VAL-003-dispatch-20260402T130303+0800.md`

## Runtime Scope

- Intended governed-write packet:
  - side: `BUY`
  - symbol: `515880.SH`
  - qty: `100`
  - price_mode: `l1_protect`
  - cancel_timeout: `30s`
- Execution posture in this snapshot:
  - Round 1 only
  - `order.place` not executed
  - `order.status` not executed
  - `orders.list` write-followup chain for this packet not executed
  - `order.cancel` not executed
  - `fills.list` not executed

## Wall Clock

- Preflight start: `2026-04-02T13:06:46.4152709+08:00`
- Latest timestamp captured in this run: `2026-04-02T13:07:28.4222453+08:00`
- Trading-window assessment:
  - `market_window_closed=false` for this observed wall-clock window under the repo's `VAL-003/G4` CN A-share timing rules

## Process State

- XtMiniQmt:
  - pid: `24380`
  - start time: `2026/4/1 23:57:03`
  - executable: `D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
- miniquote:
  - pid: `24184`
  - start time: `2026/4/1 23:57:03`
  - executable: `D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe`

## Port Reachability

- `127.0.0.1:58610` -> `TcpTestSucceeded=True`
- `127.0.0.1:8765` -> `TcpTestSucceeded=True`
- `127.0.0.1:8766` -> `TcpTestSucceeded=True`

## Gateway Health Snapshot

- Trade gateway `/healthz`:
  - endpoint: `http://127.0.0.1:8765/healthz`
  - HTTP result: `200`
  - `ok=true`
  - `server_name=xtqmtTradeGateway`
  - `server_version=2.0.0a0`
  - `bind_host=127.0.0.1`
  - `bind_port=8765`
  - `mcp_path=/mcp`
  - `health_path=/healthz`
  - `protocol_version=2025-03-26`
  - `evidence_scope=prod`
  - `evidence_state_root=D:\xtquant-mcp\instance\prod\state`
  - `evidence_artifact_root=D:\xtquant-mcp\instance\prod\artifacts`
- Data gateway `/healthz`:
  - endpoint: `http://127.0.0.1:8766/healthz`
  - HTTP result: `200`
  - `ok=true`
  - `server_name=xtqmtDataGateway`
  - `server_version=2.0.0a0`
  - `bind_host=127.0.0.1`
  - `bind_port=8766`
  - `protocol_version=2025-03-26`
  - `evidence_scope=prod`

## Trade MCP Probe Snapshot

- Transport:
  - endpoint: `http://127.0.0.1:8765/mcp`
  - protocol version: `2025-03-26`
- `initialize`:
  - start: `2026-04-02T13:07:09.371194+08:00`
  - finish: `2026-04-02T13:07:09.374470+08:00`
  - HTTP `200`
  - server info:
    - `name=xtqmtTradeGateway`
    - `version=2.0.0a0`
- `probe.connection`:
  - start: `2026-04-02T13:07:09.374511+08:00`
  - finish: `2026-04-02T13:07:09.375458+08:00`
  - HTTP `200`
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
    - advertised artifacts:
      - `D:/xtquant-mcp/instance/prod/artifacts/trade_gateway/20260402/trade_gateway_calls.jsonl`
- `resources/read diag://probe/latest`:
  - start: `2026-04-02T13:07:09.375491+08:00`
  - finish: `2026-04-02T13:07:09.380088+08:00`
  - HTTP `200`
  - JSON-RPC result returned successfully
  - payload text:
    - `{"account_contract":"single_account_primary","account_input_mode":"service_context_only","account_scope":"service_context"}`

## Trace Back-Link Status

- Expected today trade call-log path:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260402\trade_gateway_calls.jsonl`
  - result: file exists
- File facts after this rerun:
  - `Length=2564`
  - `LastWriteTime=2026/4/2 13:07:09`
- Trace id lookup result:
  - `406afa83-dced-4fe1-b23d-7bacb68d5855` found in the current-day file at line `4`

## Classification Notes

- Environment:
  - host process and ports were up, the current wall clock was inside the live afternoon session, but the runtime probe still reported `session_not_ready`
- Governance/control-plane:
  - task remained formally `Blocked / broker_blocked` and this rerun stayed confined to Round 1 only
- Design/contract:
  - required `resources/read diag://probe/latest` works on the live trade MCP endpoint in this run
  - documented `8766/healthz` works and returns the repo-backed data gateway health payload

## Snapshot Summary

This Round 1 snapshot was taken on `2026-04-02 13:06-13:07 +08`, inside the live afternoon trading session under the repo's CN A-share timing rules, so `market_window_closed` does not apply for this observed window. The host remains healthy on transport and contract terms: QMT processes existed, `58610/8765/8766` were reachable, both repo-backed `/healthz` endpoints were healthy, `resources/read diag://probe/latest` succeeded, and the current-day `trade_gateway_calls.jsonl` back-link existed for trace `406afa83-dced-4fe1-b23d-7bacb68d5855`. Even so, the snapshot remains a no-go snapshot only because `probe.connection` still returned `session_not_ready` and formal posture remains `Blocked / broker_blocked`. `order.place` was not executed.
