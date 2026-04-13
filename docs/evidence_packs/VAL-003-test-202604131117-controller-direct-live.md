# EvidencePack

Task ID: VAL-003
Role: test
Date: 2026-04-13T11:17:05.9112572+08:00
Acceptance Gate: G4
Conclusion: fail_env
Change Package Link: [VAL-003.md](../change_packages/VAL-003.md)
Env Snapshot Link: D:\xtquant-mcp\repo\docs\env_snapshots\VAL-003-202604131117-controller-direct-live.md

## Execution Mode

- Executor: controller direct test execution
- Authorization Basis: operator-triggered execution on a TaskCard with Controller Test Policy: controller_direct_required
- Controller Judgment Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\VAL-003-controller-judgment-20260413T111705+0800-controller-direct-test.md
- Formal Truth Snapshot Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-artifact-snapshot-20260413T111705+0800.json
- Raw Runtime Capture: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-controller-direct-runtime-20260413T111705+0800.json
- Gateway Recovery Output Link 1: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-trade-wake-20260413T111705+0800.json
- Gateway Recovery Output Link 2: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-data-wake-20260413T111705+0800.json
- Native Probe Output Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-native-probe-20260413T111705+0800.json
- Host Recovery Output Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-host-recovery-20260413T111705+0800.json
- Packet Readiness Output Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-packet-readiness-20260413T111705+0800.json

## Fixed Packet

- side: BUY
- symbol: 515880.SH
- qty: 100
- price_mode: l1_protect
- cancel_timeout: 30s

## Gateway Recovery

- trade status: started
- data status: started
- trade health ok: True
- data health ok: True

## Raw Results

- market window open: True
- miniqmt.ensure_logged_in transport_ok: True
- session.warm transport_ok: True
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
- native probe sessions: 2111=False, 2100=False, 2101=True
- native probe requested sessions: 2111,2100,2101
- native probe session source: session.warm
- preflight effective session plan: 2111,2100,2101
- session_plan_version: 
- preflight same-plan verdict: True
- native probe same-plan verdict: True
- packet readiness status: no_go
- packet readiness no_go_reason: host_recovery_not_ready
- real order.place executed: False
- order.place session plan: N/A
- postwrite same-plan verdict: False
- order.place trace_id: 
- order.place server_ts: 
- broker_order_id: 
- post-session.status transport_ok: False
- post-probe.connection transport_ok: False
- post-orders.list transport_ok: False
- order.status transport_ok: False
- order.cancel skipped: True
- order.cancel transport_ok: False
- fills.list transport_ok: False

## Classification

- Final Conclusion: fail_env
- Failure Layer: environment
- Acceptance Position: Round 2 host recovery failed

## Test Conclusion

controlled host recovery did not restore a successful fresh native broker/session probe on the canonical session plan
