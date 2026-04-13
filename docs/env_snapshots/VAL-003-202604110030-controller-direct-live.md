# EnvSnapshot

Task ID: VAL-003
Date: 2026-04-11T00:30:25.1525475+08:00
Role: test

## 执行模式

- 执行方式：controller direct test execution
- 授权依据：TaskCard 已声明 `Controller Test Policy: controller_direct_required`
- Controller Judgment Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\VAL-003-controller-judgment-20260411T003025+0800-controller-direct-test.md
- Formal Truth Snapshot Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-artifact-snapshot-20260411T003025+0800.json
- Gateway Recovery Output Link 1: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-trade-wake-20260411T003025+0800.json
- Gateway Recovery Output Link 2: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-data-wake-20260411T003025+0800.json
- Root Cause Evidence Link 1: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-data-port-conflict-process-20260411T003408+0800.json
- Root Cause Evidence Link 2: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-data-port-conflict-health-20260411T003408+0800.json

## 环境概览

- Repo Root: D:\xtquant-mcp\repo
- Trade Health URL: http://127.0.0.1:8765/healthz
- Data Health URL: http://127.0.0.1:8766/healthz
- Trade Health OK: True
- Data Health OK: False
- 当前 packet 是否进入 live write 链：否

## 顺序链路

- gateway recovery.trade_wake status: started
- gateway recovery.trade_wake listener: xtqmtTradeGateway@127.0.0.1:8765
- gateway recovery.data_wake status: port_conflict
- gateway recovery.data_wake expected server: xtqmtDataGateway
- gateway recovery.data_wake listener pid: 26480
- gateway recovery.data_wake command line: `"D:\xtquant-mcp\venv313\Scripts\python.exe" \\wsl.localhost\Ubuntu-22.04\home\yun\qlib\scripts\..\scripts\run_xtdata_gateway.py --transport streamable-http --host 127.0.0.1 --port 8766 --path /mcp`
- gateway recovery.data_wake `/healthz`: 404 Not Found
- controller judgment summary: gateway recovery did not reach expected repo listeners
- native probe executed: False
- order.place executed: False
- broker_order_id: `""`
- 当前唯一 blocker: `data_gateway_port_conflict_nonrepo_listener_8766`
- 旧 `connect_gate_failed` 是否适用本轮：否，仅可作历史 baseline
- Conclusion: fail_env
- Acceptance Position: gateway recovery blocked before any governed write attempt
