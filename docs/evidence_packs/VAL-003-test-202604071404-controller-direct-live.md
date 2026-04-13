# EvidencePack

Task ID: VAL-003
Role: test
Date: 2026-04-07T14:04:52.8254106+08:00
Acceptance Gate: G4
Conclusion: fail_env
Change Package Link: [VAL-003.md](../change_packages/VAL-003.md)
Env Snapshot Link: D:\xtquant-mcp\repo\docs\env_snapshots\VAL-003-202604071404-controller-direct-live.md

## Execution Mode

- Executor: controller direct test execution
- Authorization Basis: operator-triggered execution on a TaskCard with Controller Test Policy: controller_direct_required
- Controller Judgment Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\VAL-003-controller-judgment-20260407T140452+0800-controller-direct-test.md
- Formal Truth Snapshot Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-artifact-snapshot-20260407T140452+0800.json
- Raw Runtime Capture: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-controller-direct-runtime-20260407T140452+0800.json
- Gateway Recovery Output Link 1: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-trade-wake-20260407T140452+0800.json
- Gateway Recovery Output Link 2: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-data-wake-20260407T140452+0800.json
- Native Probe Output Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-native-probe-20260407T140452+0800.json

## Fixed Packet

- side: BUY
- symbol: 515880.SH
- qty: 100
- price_mode: l1_protect
- cancel_timeout: 30s

## Gateway Recovery

- trade status: already_ready
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
- native probe overall_ok: True
- native probe sessions: 100=True, 101=True
- real order.place executed: True
- order.place trace_id: 18f75ece-5fa4-4689-8dc9-e383810e76be
- order.place server_ts: 04/07/2026 14:04:59
- broker_order_id: 
- post-session.status transport_ok: True
- post-probe.connection transport_ok: True
- post-orders.list transport_ok: True
- order.status transport_ok: False
- order.cancel skipped: True
- order.cancel transport_ok: False
- fills.list transport_ok: False

## Classification

- Final Conclusion: fail_env
- Failure Layer: environment
- Acceptance Position: G4 not passed

## Test Conclusion

real order.place executed but no broker_order_id was obtained
