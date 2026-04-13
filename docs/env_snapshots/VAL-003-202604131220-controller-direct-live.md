# EnvSnapshot

Task ID: VAL-003
Date: 2026-04-13T12:20:20.2928579+08:00
Role: test

## Execution Mode

- Executor: controller direct test execution
- Authorization Basis: operator-triggered execution on a TaskCard with Controller Test Policy: controller_direct_required
- Controller Judgment Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\VAL-003-controller-judgment-20260413T122020+0800-controller-direct-test.md
- Formal Truth Snapshot Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-artifact-snapshot-20260413T122020+0800.json
- Raw Runtime Capture: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-controller-direct-runtime-20260413T122020+0800.json
- Gateway Recovery Output Link 1: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-trade-wake-20260413T122020+0800.json
- Gateway Recovery Output Link 2: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-data-wake-20260413T122020+0800.json
- Native Probe Output Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-native-probe-20260413T122020+0800.json
- Host Recovery Output Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-host-recovery-20260413T122020+0800.json
- Packet Readiness Output Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-packet-readiness-20260413T122020+0800.json

## Environment

- Host: CHIYU
- Repo Root: D:\xtquant-mcp\repo
- Trade Health URL: http://127.0.0.1:8765/healthz
- Data Health URL: http://127.0.0.1:8766/healthz
- Market Window Open: False
- Market Window Session: midday_break
- Trade Health OK: True
- Data Health OK: True

## Ordered Chain

- initialize transport_ok: True
- miniqmt.ensure_logged_in transport_ok: True
- session.warm transport_ok: False
- session.status pre transport_ok: True
- probe.connection pre transport_ok: True
- orders.list pre transport_ok: True
- trade://session/current pre transport_ok: True
- diag://probe/latest pre transport_ok: True
- diag://login/latest pre transport_ok: True
- clean-window attempted: True
- clean-window ok: True
- clean-window status_ready_after_close: False
- host recovery attempted: True
- host recovery ok: False
- host recovery reason: native_probe_failed_after_recovery
- native probe overall_ok: False
- native probe user_data_path: D:\lh\国金证券QMT交易端\userdata_mini
- native probe user_data source: trade_config:trade.qmt_userdata
- native probe user_data exists: True
- native probe sessions: N/A
- native probe requested sessions: N/A
- native probe session source: 
- preflight effective session plan: N/A
- session_plan_version: 
- preflight same-plan verdict: False
- native probe same-plan verdict: False
- packet readiness status: no_go
- packet readiness no_go_reason: market_window_closed
- order.place executed: False
- order.place session plan: N/A
- postwrite same-plan verdict: False
- order.place trace_id: 
- order.place server_ts: 
- Conclusion: blocked
- Acceptance Position: G4 not started
