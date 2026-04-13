# EnvSnapshot

Task ID: VAL-003
Date: 2026-04-02T10:46:14.6076017+08:00
Role: test

## Host

- Working Directory: `D:\xtquant-mcp\repo`
- EvidencePack: [VAL-003-test-202604021040-round1-preflight.md](../evidence_packs/VAL-003-test-202604021040-round1-preflight.md)
- TaskCard: [VAL-003.md](../task_cards/VAL-003.md)
- ChangePack: [VAL-003.md](../change_packages/VAL-003.md)
- Controller Judgment Input:
  - `.tmp/spec-task-harness/VAL-003-controller-judgment-20260402T102816+0800.md`
  - `.tmp/spec-task-harness/VAL-003-dispatch-20260402T102816+0800.md`

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

- Preflight start: `2026-04-02T10:44:09.3245458+08:00`
- Latest timestamp captured in this run: `2026-04-02T10:46:14.6076017+08:00`
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
  - `server_name=xtquantGateway`
  - `server_version=1.4.1`
  - `transport_mode=streamable_http`
  - `bind_host=127.0.0.1`
  - `bind_port=8765`
  - `mcp_path=/mcp`
  - `health_path=/healthz`
  - `protocol_version_http=2025-11-25`
  - enabled tools include:
    - `miniqmt.ensure_logged_in`
    - `session.warm`
    - `session.status`
    - `probe.connection`
    - `orders.list`
    - `fills.list`
    - `snapshot.l1`
    - `order.status`
    - `order.cancel`
    - `order.place`
- Data gateway `/healthz`:
  - endpoint: `http://127.0.0.1:8766/healthz`
  - TCP listener reachable on `8766`
  - documented health command result: `Not Found`
  - HTTP JSON health payload for the documented endpoint was not available in this run

## Trade MCP Probe Snapshot

- Transport:
  - endpoint: `http://127.0.0.1:8765/mcp`
  - protocol version: `2025-11-25`
- `initialize`:
  - start: `2026-04-02T10:44:59.176583+08:00`
  - finish: `2026-04-02T10:44:59.179777+08:00`
  - HTTP `200`
  - `Mcp-Session-Id=null`
  - server info:
    - `name=xtquantGateway`
    - `version=1.4.1`
- `probe.connection`:
  - start: `2026-04-02T10:44:59.179812+08:00`
  - finish: `2026-04-02T10:45:02.021399+08:00`
  - HTTP `200`
  - `structuredContent.ok=true`
  - `structuredContent.data.ok=true`
  - `account_id=8883884325`
  - `connect_code=0`
  - `session_id=1111`
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
    - advertised artifacts:
      - `output/mcp_gateway/20260402/gateway_calls.jsonl`
      - `reports_e2e/broker_channel_probe_must_pass.json`
      - `reports_e2e/xtquant_spec_conformance_latest.json`
- `resources/read diag://probe/latest`:
  - start: `2026-04-02T10:45:02.021512+08:00`
  - finish: `2026-04-02T10:45:02.021823+08:00`
  - HTTP `200`
  - JSON-RPC error:
    - `code=-32601`
    - `message=unknown method: resources/read`

## Trace Back-Link Status

- Expected today trade call-log path:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260402\trade_gateway_calls.jsonl`
  - result: file not found
- Advertised repo-relative output path:
  - `D:\xtquant-mcp\repo\output\mcp_gateway\20260402\gateway_calls.jsonl`
  - result: file not found
- Advertised sibling-root output path:
  - `D:\xtquant-mcp\output\mcp_gateway\20260402\gateway_calls.jsonl`
  - result: file not found
- Visible trade call-log files discovered in read-only lookup:
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260330\trade_gateway_calls.jsonl`
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260331\trade_gateway_calls.jsonl`
  - `D:\xtquant-mcp\instance\prod\artifacts\trade_gateway\20260401\trade_gateway_calls.jsonl`
- Trace id lookup result:
  - no hit found for `b05bcd80-cefa-43a9-9225-593dcbd33e53` in the visible historical trade call-log files above

## Classification Notes

- Environment:
  - host process and ports were up, but the documented data gateway `/healthz` endpoint was unavailable via HTTP `404`
- Governance/control-plane:
  - task remained formally `Blocked / broker_blocked` and this retry stayed confined to Round 1 only
- Design/contract:
  - required `resources/read diag://probe/latest` did not work on the live trade MCP endpoint in this run

## Snapshot Summary

This Round 1 snapshot was taken during a live Beijing trading window on `2026-04-02 10:44-10:46 +08:00`, so `market_window_closed` did not apply. The host was materially live enough for observation: QMT processes existed, `58610/8765/8766` were reachable, trade `/healthz` was healthy, and `probe.connection` returned `ok=true` with trace id `b05bcd80-cefa-43a9-9225-593dcbd33e53`. Even so, the snapshot is a no-go snapshot only. It does not authorize write execution because the task remained formally blocked, the documented data gateway `/healthz` was not available, and the required MCP `resources/read diag://probe/latest` contract was not available on the observed endpoint. `order.place` was not executed.
