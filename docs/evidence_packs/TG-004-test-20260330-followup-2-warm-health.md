# EvidencePack

Task ID: TG-004
Role: test
Date: 2026-03-30T12:28:22.2398504+08:00
Acceptance Gate: bounded local independent verification for Follow-up Patch 2
Conclusion: pass

## Env Snapshot

- Link: none
- Host: CHIYU
- Shell: PowerShell 7.6.0
- Python: 3.13.12
- Working Dir: `D:\xtquant-mcp\repo`
- Config: `docs/change_packages/TG-004.md`

## Test Scope

1. Independent local verification of `docs/change_packages/TG-004.md` under `Follow-up Patch 2 (2026-03-30)` only.
2. Verify `session.warm` / `session.status` health check uses the warm-only shadow-backed orders read path.
3. Verify public `orders.list` remains broker-backed.
4. Run only the required focused unittest and compile checks.
5. Do not claim live G3 recovery, VAL-002 recovery, or full live gateway smoke from this bounded run.

## Commands

1. `python -m unittest -v tests.test_trade_gateway_session_manager tests.test_trade_ops_warm_health`
2. `python -m py_compile xtqmt_mcp\trade_gateway\session_manager.py xtqmt_mcp\trade_ops.py tests\test_trade_gateway_session_manager.py tests\test_trade_ops_warm_health.py`
3. `rg -n "warm_health_orders_list|orders_list\(|query_open_orders|warm_orders_runner|checks =" xtqmt_mcp\trade_gateway\session_manager.py xtqmt_mcp\trade_ops.py tests\test_trade_gateway_session_manager.py tests\test_trade_ops_warm_health.py`
4. `$i=1; Get-Content xtqmt_mcp\trade_gateway\session_manager.py | ForEach-Object { if($i -ge 30 -and $i -le 55){ '{0}:{1}' -f $i, $_ }; $i++ }`
5. `$i=1; Get-Content xtqmt_mcp\trade_ops.py | ForEach-Object { if($i -ge 483 -and $i -le 530){ '{0}:{1}' -f $i, $_ }; $i++ }`
6. `$i=1; Get-Content xtqmt_mcp\trade_ops.py | ForEach-Object { if($i -ge 671 -and $i -le 710){ '{0}:{1}' -f $i, $_ }; $i++ }`
7. `$i=1; Get-Content tests\test_trade_gateway_session_manager.py | ForEach-Object { if($i -ge 104 -and $i -le 128){ '{0}:{1}' -f $i, $_ }; $i++ }`
8. `$i=1; Get-Content tests\test_trade_ops_warm_health.py | ForEach-Object { if($i -ge 87 -and $i -le 118){ '{0}:{1}' -f $i, $_ }; $i++ }`

## Raw Results

- Focused unittest:
  - `test_warm_health_orders_step_uses_warm_only_shadow_reader ... ok`
  - `test_warm_uses_auto_resolved_primary_account_when_config_account_is_empty ... ok`
  - `test_public_orders_list_still_uses_broker_adapter ... ok`
  - `test_warm_health_orders_list_uses_shadow_without_broker ... ok`
  - `Ran 4 tests in 0.012s`
  - `OK`
- Compile check:
  - `python -m py_compile xtqmt_mcp\trade_gateway\session_manager.py xtqmt_mcp\trade_ops.py tests\test_trade_gateway_session_manager.py tests\test_trade_ops_warm_health.py`
  - Exit status `0`
  - No stderr/stdout diagnostics emitted
- Code inspection:
  - `xtqmt_mcp/trade_gateway/session_manager.py:39-45` binds `warm_orders_runner = getattr(context.service, "warm_health_orders_list", None) or context.service.orders_list` and wires `("orders.list", warm_orders_runner)` into the health-check trace. Within this bounded patch scope, warm health prefers the dedicated warm-only method instead of the public broker-backed `orders_list()`.
  - `xtqmt_mcp/trade_ops.py:483-522` implements `warm_health_orders_list()` via `self.shadow.get_orders()`, returning `source="xttrader_shadow"` and `read_scope="warm_health_only"`.
  - `xtqmt_mcp/trade_ops.py:671-697` keeps public `orders_list()` on `self.broker.query_open_orders(self.cfg.account_id)`.
  - `tests/test_trade_gateway_session_manager.py:104-128` asserts `session.warm` increments `warm_orders_calls`, leaves `public_orders_calls == 0`, and records `source="xttrader_shadow"` plus `read_scope="warm_health_only"` in `warm_trace`.
  - `tests/test_trade_ops_warm_health.py:87-118` asserts `warm_health_orders_list()` uses shadow without broker calls, while public `orders_list()` leaves shadow untouched and calls broker exactly once.

## Artifact Refs

- ChangePack: `docs/change_packages/TG-004.md`
- Source under test: `xtqmt_mcp/trade_gateway/session_manager.py`
- Source under test: `xtqmt_mcp/trade_ops.py`
- Focused tests: `tests/test_trade_gateway_session_manager.py`
- Focused tests: `tests/test_trade_ops_warm_health.py`
- EvidencePack: `docs/evidence_packs/TG-004-test-20260330-followup-2-warm-health.md`

## Failure Classification

- Result: pass
- fail_env: none observed in this bounded local run
- fail_design: none observed in this bounded patch scope
- Explicit bounded-limit note: this run does not establish live G3 recovery, does not establish VAL-002 recovery, and did not rerun full live gateway smoke

## Verdict

No defect was found in this bounded scope. The required unittest and compile checks both passed independently, and code inspection matches the claimed contract split: `session.warm` / `session.status` health uses the warm-only shadow-backed orders read path, while public `orders.list` remains broker-backed.

## Recommended Next Board Status

- `In Review`
