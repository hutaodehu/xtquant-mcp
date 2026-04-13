# EnvSnapshot

Task ID: VAL-003
Date: 2026-04-07T14:04:52.8254106+08:00
Role: test

## Execution Mode

- Executor: controller direct test execution
- Authorization Basis: operator-triggered execution on a TaskCard with Controller Test Policy: controller_direct_required
- Controller Judgment Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\VAL-003-controller-judgment-20260407T140452+0800-controller-direct-test.md
- Formal Truth Snapshot Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-artifact-snapshot-20260407T140452+0800.json
- Raw Runtime Capture: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-controller-direct-runtime-20260407T140452+0800.json
- Gateway Recovery Output Link 1: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-trade-wake-20260407T140452+0800.json
- Gateway Recovery Output Link 2: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-data-wake-20260407T140452+0800.json
- Native Probe Output Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-native-probe-20260407T140452+0800.json

## Environment

- Host: CHIYU
- Repo Root: D:\xtquant-mcp\repo
- Trade Health URL: http://127.0.0.1:8765/healthz
- Data Health URL: http://127.0.0.1:8766/healthz
- Market Window Open: True
- Market Window Session: afternoon
- Trade Health OK: True
- Data Health OK: True

## Ordered Chain

- initialize transport_ok: True
- miniqmt.ensure_logged_in transport_ok: True
- session.warm transport_ok: True
- session.status pre transport_ok: True
- probe.connection pre transport_ok: True
- orders.list pre transport_ok: True
- native probe overall_ok: True
- native probe sessions: 100=True, 101=True
- order.place executed: True
- order.place trace_id: 18f75ece-5fa4-4689-8dc9-e383810e76be
- order.place server_ts: 04/07/2026 14:04:59
- Conclusion: fail_env
- Acceptance Position: G4 not passed
