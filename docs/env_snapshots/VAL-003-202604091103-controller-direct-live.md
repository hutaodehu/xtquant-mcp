# EnvSnapshot

Task ID: VAL-003
Date: 2026-04-09T11:03:05.9216627+08:00
Role: test

## Execution Mode

- Executor: controller direct test execution
- Authorization Basis: operator-triggered execution on a TaskCard with Controller Test Policy: controller_direct_required
- Controller Judgment Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\VAL-003-controller-judgment-20260409T110305+0800-controller-direct-test.md
- Formal Truth Snapshot Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-artifact-snapshot-20260409T110305+0800.json
- Raw Runtime Capture: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-controller-direct-runtime-20260409T110305+0800.json
- Gateway Recovery Output Link 1: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-trade-wake-20260409T110305+0800.json
- Gateway Recovery Output Link 2: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-data-wake-20260409T110305+0800.json
- Native Probe Output Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-native-probe-20260409T110305+0800.json

## Environment

- Host: CHIYU
- Repo Root: D:\xtquant-mcp\repo
- Trade Health URL: http://127.0.0.1:8765/healthz
- Data Health URL: http://127.0.0.1:8766/healthz
- Market Window Open: True
- Market Window Session: morning
- Trade Health OK: True
- Data Health OK: True

## Ordered Chain

- initialize transport_ok: True
- miniqmt.ensure_logged_in transport_ok: True
- session.warm transport_ok: True
- session.status pre transport_ok: True
- probe.connection pre transport_ok: True
- orders.list pre transport_ok: True
- trade://session/current pre transport_ok: True
- diag://probe/latest pre transport_ok: True
- diag://login/latest pre transport_ok: True
- native probe overall_ok: False
- native probe user_data_path: D:\lh\国金证券QMT交易端\userdata_mini
- native probe user_data source: trade_config:trade.qmt_userdata
- native probe user_data exists: True
- native probe sessions: 1111=False, 1100=False, 1101=False, 100=True, 101=True, 111=True, 2111=True, 2100=True, 2101=True
- native probe requested sessions: 1111,1100,1101,100,101,111,2111,2100,2101
- native probe session source: session.warm
- preflight effective session plan: 1111,1100,1101,100,101,111,2111,2100,2101
- preflight same-plan verdict: True
- native probe same-plan verdict: True
- order.place executed: False
- order.place session plan: N/A
- postwrite same-plan verdict: False
- order.place trace_id: 
- order.place server_ts: 
- Conclusion: fail_env
- Acceptance Position: Round 2 broker/session probe failed
