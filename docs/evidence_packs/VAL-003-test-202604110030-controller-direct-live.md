# EvidencePack

Task ID: VAL-003
Role: test
Date: 2026-04-11T00:30:25.1525475+08:00
Acceptance Gate: G4
Conclusion: fail_env
Change Package Link: [VAL-003.md](../change_packages/VAL-003.md)
Env Snapshot Link: [VAL-003-202604110030-controller-direct-live.md](../env_snapshots/VAL-003-202604110030-controller-direct-live.md)

## 执行模式

- 执行方式：controller direct test execution
- 授权依据：TaskCard 已声明 `Controller Test Policy: controller_direct_required`
- Controller Judgment Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\VAL-003-controller-judgment-20260411T003025+0800-controller-direct-test.md
- Formal Truth Snapshot Link: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-artifact-snapshot-20260411T003025+0800.json
- Gateway Recovery Output Link 1: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-trade-wake-20260411T003025+0800.json
- Gateway Recovery Output Link 2: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-data-wake-20260411T003025+0800.json
- Root Cause Evidence Link 1: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-data-port-conflict-process-20260411T003408+0800.json
- Root Cause Evidence Link 2: D:\xtquant-mcp\repo\.tmp\spec-task-harness\val-003-data-port-conflict-health-20260411T003408+0800.json

## 固定测试包

- side: BUY
- symbol: 515880.SH
- qty: 100
- price_mode: l1_protect
- cancel_timeout: 30s

## 预先确认

- targeted tests 已在目标仓通过：
  - `/home/yun/qlib/.venv_qlib/bin/python -m pytest tests/test_trade_gateway_server.py tests/test_trade_gateway_bootstrap.py tests/test_trade_write_authority.py tests/test_trade_probe_readiness_split.py tests/test_trade_order_submission_contract.py tests/test_trade_flow_smoke.py -q`
  - 结果：`31 passed`

## Gateway Recovery

- trade status: started
- trade health ok: True
- data status: port_conflict
- data health ok: False
- gateway recovery stop point: data wake
- controller judgment summary: gateway recovery did not reach expected repo listeners
- Executed Test Role Work: no

## 本轮原始结果

- expected data server: xtqmtDataGateway
- data wake listener pid: 26480
- data wake reason: listener already bound on expected port but /healthz does not match expected repo gateway; rerun with -ForceRestart to replace it
- port 8766 process command line: `"D:\xtquant-mcp\venv313\Scripts\python.exe" \\wsl.localhost\Ubuntu-22.04\home\yun\qlib\scripts\..\scripts\run_xtdata_gateway.py --transport streamable-http --host 127.0.0.1 --port 8766 --path /mcp`
- `http://127.0.0.1:8766/healthz` result: `404 Not Found`
- current repo trade listener ready: yes
- current repo data listener ready: no
- unique blocker: `data_gateway_port_conflict_nonrepo_listener_8766`
- native probe executed: False
- host recovery executed: False
- real `order.place` executed: False
- broker_order_id: `""`
- current-round `connect_gate_failed` verdict available: no

## 分类

- Final Conclusion: fail_env
- Failure Layer: environment
- Current Task Posture: fresh blocked
- Primary Blocker: `data_gateway_port_conflict_nonrepo_listener_8766`
- Acceptance Position: controller-direct packet stopped in gateway recovery before Round 2 native probe and Round 3 `order.place`

## 测试结论

本轮 `2026-04-11 00:30 +08` controller-direct packet 在 gateway recovery 阶段即停止，原因是 `8766` 端口被非当前 repo 期望的 listener 占用；trade wake 已启动，但 data wake 未达到 repo `xtqmtDataGateway`。因此本轮没有执行 `order.place`，不能沿用旧的 `connect_gate_failed` 作为当前 formal truth，只能以 `data_gateway_port_conflict_nonrepo_listener_8766` 收口为 fresh blocked。
