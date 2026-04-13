# Package A xtquant-mcp G4 真写闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `D:\xtquant-mcp\repo` 的 `VAL-003 / G4` 从当前 stale blocked truth 收口成一轮 fresh formal truth，并向后续 Package B 暴露唯一可消费的 write authority 结论。

**Architecture:** 先补齐 repo-local 设计与任务分解，再用 TDD 冻结 canonical session plan / trade_write_authority 语义，随后对 `trade_ops.py`、`trade_write_authority.py` 与 `run_controller_direct_test.ps1` 做最小闭环改动，最后在允许交易窗口内跑一轮 controller-direct formal packet，生成新的 `EvidencePack / EnvSnapshot / ReviewPack / state truth`。所有 warm / probe / write 的主真相都固定为 `session_resolution.effective_session_plan`，不再接受 legacy probe 单独外推写路径 readiness。

**Tech Stack:** Python 3.13, FastMCP HTTP, MiniQMT, PowerShell 7, pytest, repo-local formal docs artifacts.

---

## 执行前提

1. 当前 `/mnt/d/xtquant-mcp/repo` 未发现 `.git` 元数据；实现阶段若仍保持该状态，必须先切换到 git-backed working copy，或由主代理明确记录“无法执行标准 worktree”的环境 blocker，不能假装已经完成 `using-git-worktrees`。
2. 目标仓的 repo-local `spec/plan` 已经落在：
   - `D:\xtquant-mcp\repo\docs\superpowers\specs\2026-04-10-package-a-xtquant-mcp-g4-closure-design.md`
   - `D:\xtquant-mcp\repo\docs\superpowers\plans\2026-04-10-package-a-xtquant-mcp-g4-closure.md`
3. 每个 Task 必须严格按顺序执行：
   - implementer
   - spec reviewer
   - code quality reviewer
4. 任一 reviewer 提出问题，必须修完并复审通过，才能进入下一 Task。
5. live packet 只能在 targeted tests fresh 通过且交易窗口允许时执行。

## 文件结构与职责映射

- `xtqmt_mcp/session_resolution.py`
  负责 canonical session plan 的构建与序列化；这是 write-path session SoT 的源头。
- `xtqmt_mcp/trade_ops.py`
  负责 `probe.connection`、`order.place`、connect gate 与 write-session alignment；是 warm/probe/write 合流点。
- `xtqmt_mcp/trade_write_authority.py`
  负责把 runtime diag truth 与 formal doc truth 收口成 `trade_write_authority_latest.json`。
- `xtqmt_mcp/trade_gateway/bootstrap.py`
  负责把 session resolution 装入 service/bootstrap 生命周期。
- `xtqmt_mcp/trade_gateway/server.py`
  负责对外 contract 元数据与 write contract flags 的暴露。
- `scripts/run_controller_direct_test.ps1`
  负责 Round 1 -> Round 3 controller-direct formal packet，必须 hard-stop same-plan mismatch。
- `tests/test_trade_write_authority.py`
  冻结 authority 绿灯 / 阻断语义。
- `tests/test_trade_probe_readiness_split.py`
  冻结 probe.connection 的 read-only 与 write-path truth 拆层语义。
- `tests/test_trade_order_submission_contract.py`
  冻结 `connect_gate_failed + broker_order_id=""` 的本地 gate 拦截语义。
- `docs/task_cards/VAL-003.md`
  记录 task-level posture 与阻断原因。
- `docs/VAL-003_G4_EXECUTION_PLAN.md`
  记录 live packet 的入口、停点与 hard-stop 规则。
- `docs/CURRENT_STATUS.md`
  镜像当前最高可信 fresh truth。
- `docs/ACCEPTANCE_STANDARD.md`
  冻结 `G4` 与 same-plan 放行标准。
- `docs/OPERATIONS_RUNBOOK.md`
  冻结 operator-facing 的 higher-gate 恢复与 no-go 语义。
- `docs/MCP_DESIGN.md`
  冻结 agent-first contract 与字段语义。

### Task 1: 用 TDD 冻结 authority 与 session truth 语义

**Files:**
- Modify: `D:\xtquant-mcp\repo\tests\test_trade_write_authority.py`
- Modify: `D:\xtquant-mcp\repo\tests\test_trade_probe_readiness_split.py`
- Modify: `D:\xtquant-mcp\repo\tests\test_trade_order_submission_contract.py`

- [ ] **Step 1: 在 `test_trade_write_authority.py` 先写两个失败用例**

```python
def test_build_trade_write_authority_report_blocks_when_same_plan_false_even_if_observed_probe_session_matches() -> None:
    diag_probe = {
        "reason": "probe_session_differs_from_resolved_write_session",
        "read_only_ready": True,
        "write_permission_ready": True,
        "write_permission_block_reason": "",
        "same_plan_verdict": False,
        "fresh_connect_verified": True,
        "session_id": "2111",
        "observed_probe_session_id": "2111",
        "resource_trace_id": "trace-003",
        "write_session_alignment": {
            "resolved_session_id": "3111",
            "observed_probe_session_id": "2111",
            "same_plan_reason": "probe_session_differs_from_resolved_write_session",
        },
    }
    current_status = \"\"\"
| Trade Lane Write | 未闭环 | < G4 | blocker |
| [VAL-003](./task_cards/VAL-003.md) | `Blocked` | `G4` | `connect_gate_failed` |
\"\"\"
    report = build_trade_write_authority_report(
        diag_probe=diag_probe,
        current_status_markdown=current_status,
        diag_probe_path=Path("D:/xtquant-mcp/instance/prod/state/trade_resources/diag_probe_latest.json"),
        current_status_path=Path("D:/xtquant-mcp/repo/docs/CURRENT_STATUS.md"),
    )
    assert report["status"] == "fail"
    assert report["same_plan_verdict"] is False
    assert report["resolved_session_id"] == "3111"
    assert report["observed_probe_session_id"] == "2111"


def test_build_trade_write_authority_report_blocks_when_same_plan_true_but_formal_write_still_open() -> None:
    diag_probe = {
        "reason": "reuse_only_not_sufficient",
        "read_only_ready": True,
        "write_permission_ready": True,
        "same_plan_verdict": True,
        "fresh_connect_verified": True,
        "resource_trace_id": "trace-004",
        "write_session_alignment": {"resolved_session_id": "2111", "same_plan_reason": "same_session"},
    }
    current_status = \"\"\"
| Trade Lane Write | 未闭环 | < G4 | blocker |
| [VAL-003](./task_cards/VAL-003.md) | `Blocked` | `G4` | `connect_gate_failed` |
\"\"\"
    report = build_trade_write_authority_report(
        diag_probe=diag_probe,
        current_status_markdown=current_status,
        diag_probe_path=Path("D:/xtquant-mcp/instance/prod/state/trade_resources/diag_probe_latest.json"),
        current_status_path=Path("D:/xtquant-mcp/repo/docs/CURRENT_STATUS.md"),
    )
    assert report["status"] == "fail"
    assert report["blocking_reason"] == "formal_trade_write_lane_not_closed"
    assert report["formal_trade_write_closed"] is False
```

- [ ] **Step 2: 在 `test_trade_probe_readiness_split.py` 写 same-plan hard-stop 用例**

```python
def test_probe_connection_same_plan_false_even_when_observed_probe_session_is_in_effective_plan(self) -> None:
    work_root = ROOT / "instance" / "test_tmp" / "tg004_probe_same_plan_false"
    shutil.rmtree(work_root, ignore_errors=True)
    service = self._build_service(work_root, shadow_adapter=_LiveShadow(session_id="2100"))
    try:
        with patch(
            "xtqmt_mcp.trade_ops.run_layered_user_data_precheck",
            return_value={
                "read_only": {"ok": True, "report": {"ok": True}},
                "write_permission": {"ok": True, "report": {"ok": True}},
            },
        ), patch("xtqmt_mcp.trade_ops._tcp_port_ready", return_value=True), patch(
            "xtqmt_mcp.channel_probe.run_channel_probe",
            side_effect=AssertionError("fresh connect probe should not run when owner session is live"),
        ):
            result = service.probe_connection()
        self.assertTrue(result.ok)
        self.assertEqual(result.payload["session_id"], "2111")
        self.assertEqual(result.payload["observed_probe_session_id"], "2100")
        self.assertFalse(result.payload["same_plan_verdict"])
        self.assertEqual(
            result.payload["write_session_alignment"]["same_plan_reason"],
            "probe_session_differs_from_resolved_write_session",
        )
    finally:
        service.close()
        shutil.rmtree(work_root, ignore_errors=True)
```

- [ ] **Step 3: 在 `test_trade_order_submission_contract.py` 写本地 gate 语义回归用例**

```python
def test_order_place_connect_gate_failure_freezes_local_gate_semantics(self) -> None:
    work_root = ROOT / "instance" / "test_tmp" / "tg006_connect_gate_semantics"
    shutil.rmtree(work_root, ignore_errors=True)
    work_root.mkdir(parents=True, exist_ok=True)
    service, shadow = self._build_service(work_root)
    try:
        result = service.place_order(
            OrderPlaceRequest(
                account_id="ACC001",
                code="000001.SZ",
                side=Side.BUY,
                quantity=100,
                guard_token="mcp_server_governed_write_path",
                client_order_key="COID-TG006-SEMANTICS",
                intent_id="INT-TG006-SEMANTICS",
            )
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.payload["code"], "connect_gate_failed")
        self.assertEqual(result.payload["broker_order_id"], "")
        self.assertFalse(result.payload["broker_submission_attempted"])
        self.assertTrue(result.payload["local_gate_intercepted"])
        self.assertEqual(result.payload["submission_scope"], "local_gate")
        self.assertEqual(result.payload["submission_stage"], "connect_gate")
    finally:
        service.close()
        shutil.rmtree(work_root, ignore_errors=True)
```

- [ ] **Step 4: 运行 targeted tests，确认新用例先失败**

Run:

```bash
pwsh -NoLogo -Command "Set-Location 'D:\xtquant-mcp\repo'; & 'D:\xtquant-mcp\venv313\Scripts\python.exe' -m pytest tests/test_trade_write_authority.py tests/test_trade_probe_readiness_split.py tests/test_trade_order_submission_contract.py -q"
```

Expected:

```text
FAIL 至少 1 个新增 same-plan / authority 用例
```

- [ ] **Step 5: 提交给 implementer -> spec reviewer -> code quality reviewer 顺序处理**

Review focus:

```text
reviewer 必须确认：新增测试明确区分 resolved write session 与 observed probe session；formal 未闭合时 authority 不能被 runtime 绿灯覆盖。
```

### Task 2: 以最小代码改动收口 canonical session plan 与 authority 判定

**Files:**
- Modify: `D:\xtquant-mcp\repo\xtqmt_mcp\trade_write_authority.py`
- Modify: `D:\xtquant-mcp\repo\xtqmt_mcp\trade_ops.py`
- Modify: `D:\xtquant-mcp\repo\xtqmt_mcp\trade_gateway\bootstrap.py`
- Modify: `D:\xtquant-mcp\repo\xtqmt_mcp\trade_gateway\server.py`
- Modify: `D:\xtquant-mcp\repo\xtqmt_mcp\session_resolution.py`

- [ ] **Step 1: 在 `trade_write_authority.py` 固定 authority 绿灯条件**

```python
formal_trade_write_closed = bool(formal_truth["trade_lane_write_closed"])
same_plan_verdict = bool(diag_probe.get("same_plan_verdict", False))
fresh_connect_verified = bool(diag_probe.get("fresh_connect_verified", False))

authority_green = bool(
    same_plan_verdict
    and fresh_connect_verified
    and formal_trade_write_closed
)
```

要求：

```text
1. resolved_session_id 优先取 write_session_alignment.resolved_session_id
2. observed_probe_session_id 仅回填观测字段
3. blocking_reason 顺序保持：formal closeout -> read-only -> same-plan -> fresh connect
```

- [ ] **Step 2: 在 `trade_ops.py` 确保 warm / probe / write 都回链同一个 session plan**

```python
payload["session_resolution"] = dict(self.session_resolution)
payload["session_id"] = str(write_session_alignment.get("resolved_session_id") or observed_probe_session_id)
payload["observed_probe_session_id"] = observed_probe_session_id
payload["same_plan_verdict"] = bool(write_session_alignment.get("same_plan_verdict", False))
```

要求：

```text
1. 顶层 session_id 始终代表 write-path resolved session
2. observed_probe_session_id 不能覆盖 resolved session
3. connect_gate 的 expected_effective_session_plan 必须等于 session_resolution.effective_session_plan
```

- [ ] **Step 3: 在 `trade_gateway/bootstrap.py` / `server.py` 保持对外 contract 一致**

```python
session_resolution = SessionResolution(...)
payload["session_resolution"] = session_resolution.as_payload()
payload["write_contract_flags"] = ["broker_submission_attempted", "local_gate_intercepted"]
```

要求：

```text
health / resources / tool payload 中的 session_resolution.effective_session_plan 语义必须一致；不再保留旧 MCP 回退口径。
```

- [ ] **Step 4: 重跑 Task 1 的 targeted tests，确认全部转绿**

Run:

```bash
pwsh -NoLogo -Command "Set-Location 'D:\xtquant-mcp\repo'; & 'D:\xtquant-mcp\venv313\Scripts\python.exe' -m pytest tests/test_trade_write_authority.py tests/test_trade_probe_readiness_split.py tests/test_trade_order_submission_contract.py -q"
```

Expected:

```text
全部 PASS，0 failures
```

- [ ] **Step 5: 走 implementer -> spec reviewer -> code quality reviewer**

Review focus:

```text
reviewer 必须确认：authority green 不再由 observed probe 或 flow_smoke 误触发；connect_gate_failed + broker_order_id="" 仍稳定表示本地 gate 层拦截。
```

### Task 3: 收口 controller-direct runner 与正式文档口径

**Files:**
- Modify: `D:\xtquant-mcp\repo\scripts\run_controller_direct_test.ps1`
- Modify: `D:\xtquant-mcp\repo\docs\task_cards\VAL-003.md`
- Modify: `D:\xtquant-mcp\repo\docs\VAL-003_G4_EXECUTION_PLAN.md`
- Modify: `D:\xtquant-mcp\repo\docs\CURRENT_STATUS.md`
- Modify: `D:\xtquant-mcp\repo\docs\ACCEPTANCE_STANDARD.md`
- Modify: `D:\xtquant-mcp\repo\docs\OPERATIONS_RUNBOOK.md`
- Modify: `D:\xtquant-mcp\repo\docs\MCP_DESIGN.md`

- [ ] **Step 1: 在 `run_controller_direct_test.ps1` 明确 same-plan hard-stop 与 artifact 字段**

```powershell
if (-not $Runtime.preflight_session_plan.ok) {
    return [ordered]@{
        conclusion = "fail_design"
        failure_layer = "design"
        acceptance_position = "Round 2 session plan mismatch"
        summary = "preflight tools did not expose one canonical session_resolution.effective_session_plan"
    }
}
```

补充要求：

```text
1. judgment 中必须写出 canonical plan、native probe same-plan verdict、Round 3 write session
2. 不允许以 `100/101` 单独 probe pass 放行 Round 3
```

- [ ] **Step 2: 同步任务卡与执行计划**

需要写入的文案点：

```text
1. single source of truth 固定为 session_resolution.effective_session_plan
2. observed_probe_session_id 仅为观测字段
3. connect_gate_failed + broker_order_id="" = 本地 gate 层拦截，未进入券商柜台
4. 允许终态只有 G4 pass / fresh blocked
```

- [ ] **Step 3: 同步 CURRENT_STATUS / ACCEPTANCE_STANDARD / RUNBOOK / MCP_DESIGN**

需要写入的文案点：

```text
1. flow_smoke 不能升格为 release authority
2. trade_write_authority 转绿至少要求 same_plan_verdict=true、probe_complete_verdict=true、fresh_connect_verified=true、formal_trade_write_closed=true
3. stale evidence 不得继续充当当前结论
```

- [ ] **Step 4: 做文档扫描与脚本静态验证**

Run:

```bash
pwsh -NoLogo -Command "Set-Location 'D:\xtquant-mcp\repo'; & 'D:\xtquant-mcp\venv313\Scripts\python.exe' scripts/check_doc_refs.py --scan docs --strict"
pwsh -NoLogo -Command "Set-Location 'D:\xtquant-mcp\repo'; & 'D:\xtquant-mcp\venv313\Scripts\python.exe' -m pytest tests/test_controller_direct_host_recovery.py -q"
```

Expected:

```text
doc refs 通过；controller-direct 相关单测通过
```

- [ ] **Step 5: 走 implementer -> spec reviewer -> code quality reviewer**

Review focus:

```text
reviewer 必须确认：文档、脚本、状态口径一致，没有把 blocked 包装成 ready，也没有把 flow_smoke 升格成 release authority。
```

### Task 4: 执行 fresh formal packet，刷新 truth，并按结果收口

**Files:**
- Modify: `D:\xtquant-mcp\repo\docs\evidence_packs\VAL-003-test-*-controller-direct-live.md`
- Modify: `D:\xtquant-mcp\repo\docs\env_snapshots\VAL-003-*-controller-direct-live.md`
- Modify: `D:\xtquant-mcp\repo\docs\reviews\VAL-003-review-*.md`
- Modify: `D:\xtquant-mcp\repo\docs\CURRENT_STATUS.md`
- Modify: `D:\xtquant-mcp\repo\docs\task_cards\VAL-003.md`
- Verify: `D:\xtquant-mcp\instance\prod\state\trade_resources\trade_write_authority_latest.json`
- Verify: `D:\xtquant-mcp\instance\prod\state\trade_resources\ter_execution_gate_latest.json`

- [ ] **Step 1: 先重跑 targeted tests，确认 fresh 绿**

Run:

```bash
pwsh -NoLogo -Command "Set-Location 'D:\xtquant-mcp\repo'; & 'D:\xtquant-mcp\venv313\Scripts\python.exe' -m pytest tests/test_trade_write_authority.py tests/test_trade_probe_readiness_split.py tests/test_trade_order_submission_contract.py tests/test_controller_direct_host_recovery.py -q"
```

Expected:

```text
全部 PASS，0 failures
```

- [ ] **Step 2: 只在允许交易窗口内跑 controller-direct formal packet**

Run:

```bash
pwsh -NoLogo -File D:\xtquant-mcp\repo\scripts\run_controller_direct_test.ps1 -TaskId VAL-003
```

Expected:

```text
只允许两种结果：
1. G4 pass
2. fresh blocked
```

Live packet 条件：

```text
1. 市场窗口允许
2. Round 1 预检通过
3. Round 2 canonical plan / native probe same-plan 通过
4. 如果 packet 失败，不直接“再试一单”，而是转 systematic-debugging
```

- [ ] **Step 3: 生成新的 EvidencePack / EnvSnapshot / ReviewPack**

期望路径模式：

```text
docs/evidence_packs/VAL-003-test-*-controller-direct-live.md
docs/env_snapshots/VAL-003-*-controller-direct-live.md
docs/reviews/VAL-003-review-*.md
```

- [ ] **Step 4: 刷新 state truth 并核对四处一致**

核对对象：

```text
1. D:\xtquant-mcp\instance\prod\state\trade_resources\trade_write_authority_latest.json
2. D:\xtquant-mcp\instance\prod\state\trade_resources\ter_execution_gate_latest.json
3. D:\xtquant-mcp\repo\docs\CURRENT_STATUS.md
4. D:\xtquant-mcp\repo\docs\task_cards\VAL-003.md
```

核对规则：

```text
1. posture 一致
2. blocker 一致
3. review/evidence 回链一致
4. 不能再指向 2026-04-08 之前的 stale judgment 作为当前结论
```

- [ ] **Step 5: 若 live packet blocked，则立即进入 systematic-debugging**

Run:

```text
围绕唯一主 blocker 做根因定位，不允许直接追加第二单 live order。
```

- [ ] **Step 6: 最终仍按 implementer -> spec reviewer -> code quality reviewer 完成 Task 收口**

Review focus:

```text
reviewer 必须确认：最终结论只写 G4 pass 或 fresh blocked；如果 blocked，只保留唯一主 blocker；Package B 只收到 posture + review path + authority json path + gate truth path。
```

## 最终验证门槛

- [ ] `verification-before-completion` 必须基于本轮 fresh command output，而不是旧 artifact。
- [ ] 最终答复必须包含：
  - 测试命令
  - controller-direct 命令
  - 退出码
  - 关键结果
  - 四处 truth 一致性结论
- [ ] 若未产出 fresh evidence，不得宣称“通过”“完成”“ready”“已闭环”。
