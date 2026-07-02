from __future__ import annotations

from datetime import date
from pathlib import Path
import shutil
import sys
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.trade_gateway.bootstrap import _resolve_explicit_account_session, build_trade_ops_context
from xtqmt_mcp.trade_gateway.config import TradeOpsGatewayConfig


class _FakeMarketDataProvider:
    def __init__(self, *, policy, idle_timeout_seconds: float) -> None:
        self.policy = policy
        self.idle_timeout_seconds = idle_timeout_seconds


class _FakeShadowAdapter:
    def __init__(self, cfg) -> None:
        self.cfg = cfg

    def close(self) -> None:
        return None


class _FakeBrokerAdapter:
    def __init__(self, cfg) -> None:
        self.cfg = cfg

    def close(self) -> None:
        return None


class _FakeDryRunBrokerAdapter:
    def close(self) -> None:
        return None


def _install_stub_adapter_modules() -> dict[str, types.ModuleType]:
    from dataclasses import dataclass

    market_data_module = types.ModuleType("xtqmt_mcp.market_data")
    market_data_module.XtQuantMarketDataProvider = _FakeMarketDataProvider

    shadow_module = types.ModuleType("xtqmt_mcp.adapters.xttrader_shadow")

    @dataclass
    class XtTraderShadowConfig:
        user_data_path: str
        account_id: str
        account_type: str = "STOCK"
        session_id: int = 100
        connect_retries: int = 3
        connect_retry_interval_seconds: float = 3.0
        session_candidates: tuple[int, ...] = (100, 101, 111)
        enable_derived_session_fallback: bool = False
        register_callback: bool = True
        connect_cooldown_seconds: float = 3.2
        enforce_connect_precheck: bool = True
        require_up_queue_file: bool = True
        max_session_attempts: int = 12

    shadow_module.XtTraderShadowConfig = XtTraderShadowConfig
    shadow_module.XtTraderShadowAdapter = _FakeShadowAdapter
    shadow_module.discover_stock_account_ids = lambda **_: ["ACC001"]

    broker_module = types.ModuleType("xtqmt_mcp.broker_order")

    @dataclass
    class XtTraderBrokerOrderConfig:
        user_data_path: str
        account_id: str
        account_type: str = "STOCK"
        session_id: int = 100
        connect_retries: int = 3
        connect_retry_interval_seconds: float = 3.0
        strategy_name: str = "xtqmt_trade_gateway"
        register_callback: bool = True
        connect_cooldown_seconds: float = 3.2
        enforce_connect_precheck: bool = True
        require_up_queue_file: bool = True
        session_candidates: tuple[int, ...] = (100, 101, 111)
        enable_derived_session_fallback: bool = False
        max_session_attempts: int = 12

    broker_module.XtTraderBrokerOrderConfig = XtTraderBrokerOrderConfig
    broker_module.XtTraderBrokerOrderAdapter = _FakeBrokerAdapter
    broker_module.DryRunBrokerOrderAdapter = _FakeDryRunBrokerAdapter
    return {
        "xtqmt_mcp.market_data": market_data_module,
        "xtqmt_mcp.adapters.xttrader_shadow": shadow_module,
        "xtqmt_mcp.broker_order": broker_module,
    }


class TradeGatewayBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work_root = ROOT / "instance" / "test_tmp" / "bootstrap_gating"
        shutil.rmtree(self.work_root, ignore_errors=True)
        self.userdata = self.work_root / "userdata"
        self.userdata.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.work_root, ignore_errors=True)

    def _base_config(self) -> TradeOpsGatewayConfig:
        return TradeOpsGatewayConfig(
            account_id="",
            auto_account=True,
            trading_day=date(2026, 3, 31),
            output_dir=str(self.work_root / "artifacts" / "trade_ops"),
            state_dir=str(self.work_root / "state" / "trade_ops"),
            qmt_userdata=str(self.userdata),
            qmt_exe="",
            require_up_queue_file=True,
            session_id=1111,
            session_candidates=(1111, 1100, 1101, 100, 101, 111),
            enable_derived_session_fallback=True,
        )

    def test_session_warm_uses_read_only_account_resolution_and_skips_broker(self) -> None:
        captured: dict[str, object] = {}

        def _discover_stock_account_ids(**kwargs):
            captured["discover_require_up_queue_file"] = kwargs["require_up_queue_file"]
            return ["ACC001"]

        def _shadow_factory(cfg):
            captured["shadow_require_up_queue_file"] = cfg.require_up_queue_file
            return _FakeShadowAdapter(cfg)

        def _broker_factory(cfg):
            captured.setdefault("broker_require_up_queue_file_values", []).append(bool(cfg.require_up_queue_file))
            return _FakeBrokerAdapter(cfg)

        explicit_session_resolver = Mock(return_value=2111)

        with (
            patch.dict(sys.modules, _install_stub_adapter_modules()),
            patch("xtqmt_mcp.trade_gateway.bootstrap._resolve_explicit_account_session", explicit_session_resolver),
        ):
            context = build_trade_ops_context(
                self._base_config(),
                "session.warm",
                ensure_miniqmt_awake_fn=lambda **_: {"ok": True, "xtdata_port_ready_after": True},
                discover_stock_account_ids_fn=_discover_stock_account_ids,
                market_data_factory=_FakeMarketDataProvider,
                shadow_adapter_factory=_shadow_factory,
                broker_order_adapter_factory=_broker_factory,
            )
        try:
            self.assertEqual(context.resolved_account_id, "ACC001")
            self.assertEqual(context.resolved_session_id, 2111)
            self.assertFalse(bool(captured["discover_require_up_queue_file"]))
            self.assertFalse(bool(captured["shadow_require_up_queue_file"]))
            self.assertEqual(captured.get("broker_require_up_queue_file_values", []), [])
            explicit_session_resolver.assert_called_once_with(
                self._base_config(),
                account_id="ACC001",
                fallback_session_id=1111,
            )
            resolution = context.session_resolution
            self.assertIsNotNone(resolution)
            resolution_payload = resolution.as_payload()
            self.assertEqual(resolution_payload["configured_session_id"], 1111)
            self.assertEqual(resolution_payload["resolved_base_session_id"], 1111)
            self.assertEqual(resolution_payload["resolved_session_id"], 2111)
            self.assertTrue(resolution_payload["explicit_session_resolution_applied"])
            self.assertIn(2111, resolution_payload["effective_session_plan"])
            self.assertEqual(context.service.cfg.session_candidates, tuple(resolution_payload["effective_session_plan"]))
            read_broker = context.service._ensure_broker_adapter(require_write_permission=False)
            write_broker = context.service._ensure_broker_adapter(require_write_permission=True)
            self.assertIsInstance(read_broker, _FakeBrokerAdapter)
            self.assertIsInstance(write_broker, _FakeBrokerAdapter)
            self.assertFalse(bool(read_broker.cfg.require_up_queue_file))
            self.assertTrue(bool(write_broker.cfg.require_up_queue_file))
            self.assertEqual(captured["broker_require_up_queue_file_values"], [False, True])
        finally:
            context.close()

    def test_explicit_account_session_resolution_falls_back_to_legacy_candidates_after_primary_plan_fails(self) -> None:
        config = TradeOpsGatewayConfig(
            account_id="SAMPLE_ACCOUNT",
            auto_account=False,
            trading_day=date(2026, 3, 31),
            qmt_exe="C:\\QMT\\XtMiniQmt.exe",
            qmt_userdata=str(self.userdata),
            session_id=2111,
            session_candidates=(2111, 2100, 2101),
            connect_retries=1,
            connect_retry_interval_seconds=3.0,
            wake_wait_seconds=30,
            require_connect_stage=True,
            require_subscribe_stage=True,
            require_snapshot_stage=True,
        )
        captured_plans: list[tuple[int, ...]] = []

        def _run_connection_orchestrator(orchestrator_cfg):
            captured_plans.append(tuple(orchestrator_cfg.session_plan))
            if len(captured_plans) == 1:
                return types.SimpleNamespace(overall_ok=False, selected_session_id=None)
            return types.SimpleNamespace(overall_ok=True, selected_session_id=101)

        with patch("xtqmt_mcp.connection_orchestrator.run_connection_orchestrator", _run_connection_orchestrator):
            resolved = _resolve_explicit_account_session(
                config,
                account_id="SAMPLE_ACCOUNT",
                fallback_session_id=2111,
            )

        self.assertEqual(resolved, 101)
        self.assertEqual(
            captured_plans,
            [
                (2111, 2100, 2101),
                (2111, 2100, 2101, 100, 101, 111),
            ],
        )

    def test_order_place_keeps_write_permission_gate_for_account_resolution_and_broker(self) -> None:
        captured: dict[str, object] = {}

        def _discover_stock_account_ids(**kwargs):
            captured["discover_require_up_queue_file"] = kwargs["require_up_queue_file"]
            return ["ACC001"]

        def _shadow_factory(cfg):
            captured["shadow_require_up_queue_file"] = cfg.require_up_queue_file
            return _FakeShadowAdapter(cfg)

        def _broker_factory(cfg):
            captured["broker_require_up_queue_file"] = cfg.require_up_queue_file
            return _FakeBrokerAdapter(cfg)

        explicit_session_resolver = Mock(return_value=1111)

        with (
            patch.dict(sys.modules, _install_stub_adapter_modules()),
            patch("xtqmt_mcp.trade_gateway.bootstrap._resolve_explicit_account_session", explicit_session_resolver),
        ):
            context = build_trade_ops_context(
                self._base_config(),
                "order.place",
                ensure_miniqmt_awake_fn=lambda **_: {"ok": True, "xtdata_port_ready_after": True},
                discover_stock_account_ids_fn=_discover_stock_account_ids,
                market_data_factory=_FakeMarketDataProvider,
                shadow_adapter_factory=_shadow_factory,
                broker_order_adapter_factory=_broker_factory,
            )
        try:
            self.assertEqual(context.resolved_account_id, "ACC001")
            self.assertTrue(bool(captured["discover_require_up_queue_file"]))
            self.assertFalse(bool(captured["shadow_require_up_queue_file"]))
            self.assertTrue(bool(captured["broker_require_up_queue_file"]))
            explicit_session_resolver.assert_called_once_with(
                self._base_config(),
                account_id="ACC001",
                fallback_session_id=1111,
            )
            self.assertEqual(context.session_resolution.as_payload()["effective_session_plan"][0], 1111)
        finally:
            context.close()

    def test_explicit_session_resolution_collapses_to_selected_session_when_selected_outside_configured_candidates(self) -> None:
        config = TradeOpsGatewayConfig(
            account_id="SAMPLE_ACCOUNT",
            auto_account=False,
            trading_day=date(2026, 3, 31),
            output_dir=str(self.work_root / "artifacts" / "trade_ops"),
            state_dir=str(self.work_root / "state" / "trade_ops"),
            qmt_userdata=str(self.userdata),
            qmt_exe="",
            require_up_queue_file=True,
            session_id=2111,
            session_candidates=(2111, 2100, 2101),
            enable_derived_session_fallback=False,
        )
        with (
            patch.dict(sys.modules, _install_stub_adapter_modules()),
            patch("xtqmt_mcp.trade_gateway.bootstrap._resolve_explicit_account_session", return_value=101),
        ):
            context = build_trade_ops_context(
                config,
                "order.place",
                ensure_miniqmt_awake_fn=lambda **_: {"ok": True, "xtdata_port_ready_after": True},
                market_data_factory=_FakeMarketDataProvider,
                shadow_adapter_factory=lambda cfg: _FakeShadowAdapter(cfg),
                broker_order_adapter_factory=lambda cfg: _FakeBrokerAdapter(cfg),
            )
        try:
            resolution = context.session_resolution.as_payload()
            self.assertEqual(resolution["resolved_session_id"], 101)
            self.assertEqual(resolution["effective_session_plan"], [101])
            self.assertEqual(context.service.cfg.session_candidates, (101,))
        finally:
            context.close()

    def test_order_place_rebuilds_prebuilt_write_broker_after_session_realign(self) -> None:
        captured: dict[str, object] = {"broker_cfgs": []}

        def _discover_stock_account_ids(**kwargs):
            return ["ACC001"]

        def _shadow_factory(cfg):
            return _FakeShadowAdapter(cfg)

        def _broker_factory(cfg):
            captured["broker_cfgs"].append(
                {
                    "session_id": cfg.session_id,
                    "session_candidates": cfg.session_candidates,
                    "require_up_queue_file": cfg.require_up_queue_file,
                }
            )
            return _FakeBrokerAdapter(cfg)

        with (
            patch.dict(sys.modules, _install_stub_adapter_modules()),
            patch("xtqmt_mcp.trade_gateway.bootstrap._resolve_explicit_account_session", return_value=1111),
        ):
            context = build_trade_ops_context(
                self._base_config(),
                "order.place",
                ensure_miniqmt_awake_fn=lambda **_: {"ok": True, "xtdata_port_ready_after": True},
                discover_stock_account_ids_fn=_discover_stock_account_ids,
                market_data_factory=_FakeMarketDataProvider,
                shadow_adapter_factory=_shadow_factory,
                broker_order_adapter_factory=_broker_factory,
            )
        try:
            initial_broker = context.service.broker
            self.assertIsInstance(initial_broker, _FakeBrokerAdapter)
            self.assertEqual(captured["broker_cfgs"], [
                {
                    "session_id": 1111,
                    "session_candidates": (1111, 1100, 1101, 100, 101, 111),
                    "require_up_queue_file": True,
                }
            ])

            context.service.realign_session_resolution(100)
            realigned_broker = context.service._ensure_broker_adapter(require_write_permission=True)

            self.assertIsInstance(realigned_broker, _FakeBrokerAdapter)
            self.assertIsNot(realigned_broker, initial_broker)
            self.assertEqual(captured["broker_cfgs"], [
                {
                    "session_id": 1111,
                    "session_candidates": (1111, 1100, 1101, 100, 101, 111),
                    "require_up_queue_file": True,
                },
                {
                    "session_id": 100,
                    "session_candidates": (100, 1111, 1100, 1101, 101, 111, 2111, 2100, 2101),
                    "require_up_queue_file": True,
                },
            ])
        finally:
            context.close()

    def test_broker_factory_uses_realigned_session_resolution_when_owner_session_changes(self) -> None:
        captured: dict[str, object] = {}

        def _discover_stock_account_ids(**kwargs):
            return ["ACC001"]

        def _shadow_factory(cfg):
            return _FakeShadowAdapter(cfg)

        def _broker_factory(cfg):
            captured["broker_session_id"] = cfg.session_id
            captured["broker_session_candidates"] = cfg.session_candidates
            captured["broker_derived_fallback"] = cfg.enable_derived_session_fallback
            return _FakeBrokerAdapter(cfg)

        explicit_session_resolver = Mock(return_value=2111)

        with (
            patch.dict(sys.modules, _install_stub_adapter_modules()),
            patch("xtqmt_mcp.trade_gateway.bootstrap._resolve_explicit_account_session", explicit_session_resolver),
        ):
            context = build_trade_ops_context(
                self._base_config(),
                "session.warm",
                ensure_miniqmt_awake_fn=lambda **_: {"ok": True, "xtdata_port_ready_after": True},
                discover_stock_account_ids_fn=_discover_stock_account_ids,
                market_data_factory=_FakeMarketDataProvider,
                shadow_adapter_factory=_shadow_factory,
                broker_order_adapter_factory=_broker_factory,
            )
        try:
            context.service.realign_session_resolution(100)
            write_broker = context.service._ensure_broker_adapter(require_write_permission=True)
            self.assertIsInstance(write_broker, _FakeBrokerAdapter)
            self.assertEqual(captured["broker_session_id"], 100)
            self.assertEqual(captured["broker_session_candidates"][0], 100)
            self.assertFalse(bool(captured["broker_derived_fallback"]))
        finally:
            context.close()

    def test_realign_session_resolution_preserves_seed_truth_and_records_runtime_event(self) -> None:
        def _discover_stock_account_ids(**kwargs):
            return ["ACC001"]

        def _shadow_factory(cfg):
            return _FakeShadowAdapter(cfg)

        with (
            patch.dict(sys.modules, _install_stub_adapter_modules()),
            patch("xtqmt_mcp.trade_gateway.bootstrap._resolve_explicit_account_session", return_value=1111),
        ):
            context = build_trade_ops_context(
                self._base_config(),
                "order.place",
                ensure_miniqmt_awake_fn=lambda **_: {"ok": True, "xtdata_port_ready_after": True},
                discover_stock_account_ids_fn=_discover_stock_account_ids,
                market_data_factory=_FakeMarketDataProvider,
                shadow_adapter_factory=_shadow_factory,
                broker_order_adapter_factory=lambda cfg: _FakeBrokerAdapter(cfg),
            )
        try:
            baseline = dict(context.service.session_resolution)
            self.assertEqual(baseline["resolved_session_id"], 1111)
            self.assertNotIn("runtime_resolution_event", baseline)

            realigned = context.service.realign_session_resolution(
                100,
                reason="owner_probe_realign",
                owner_session_id=1111,
                attempted_broker_session_id=100,
            )

            self.assertEqual(realigned["resolved_session_id"], 100)
            self.assertEqual(realigned["seed_resolved_session_id"], 1111)
            self.assertEqual(realigned["resolved_base_session_id"], 1111)
            self.assertTrue(realigned["runtime_session_resolution_applied"])
            self.assertEqual(realigned["runtime_resolution_event"]["previous_resolved_session_id"], 1111)
            self.assertEqual(realigned["runtime_resolution_event"]["resolved_session_id"], 100)
            self.assertEqual(realigned["runtime_resolution_event"]["reason"], "owner_probe_realign")
            self.assertEqual(realigned["runtime_resolution_event"]["owner_session_id"], 1111)
            self.assertEqual(realigned["runtime_resolution_event"]["attempted_broker_session_id"], 100)

            # 基础显式解析真相仍保留在 seed 字段里，而不是被 runtime 健康检查静默覆盖。
            self.assertEqual(dict(context.service.session_resolution)["seed_resolved_session_id"], 1111)
        finally:
            context.close()

    def test_order_status_keeps_broker_read_path_without_write_permission_precheck(self) -> None:
        captured: dict[str, object] = {}

        def _broker_factory(cfg):
            captured["broker_require_up_queue_file"] = cfg.require_up_queue_file
            return _FakeBrokerAdapter(cfg)

        config = TradeOpsGatewayConfig(
            account_id="ACC001",
            auto_account=False,
            trading_day=date(2026, 3, 31),
            output_dir=str(self.work_root / "artifacts" / "trade_ops"),
            state_dir=str(self.work_root / "state" / "trade_ops"),
            qmt_userdata=str(self.userdata),
            qmt_exe="",
            require_up_queue_file=True,
            session_id=1111,
            session_candidates=(1111, 1100, 1101, 100, 101, 111),
            enable_derived_session_fallback=True,
        )
        with (
            patch.dict(sys.modules, _install_stub_adapter_modules()),
            patch("xtqmt_mcp.trade_gateway.bootstrap._resolve_explicit_account_session", return_value=1111),
        ):
            context = build_trade_ops_context(
                config,
                "order.status",
                ensure_miniqmt_awake_fn=lambda **_: {"ok": True, "xtdata_port_ready_after": True},
                market_data_factory=_FakeMarketDataProvider,
                shadow_adapter_factory=lambda cfg: _FakeShadowAdapter(cfg),
                broker_order_adapter_factory=_broker_factory,
            )
        try:
            self.assertEqual(context.resolved_account_id, "ACC001")
            self.assertFalse(bool(captured["broker_require_up_queue_file"]))
        finally:
            context.close()

    def test_flow_smoke_context_uses_dry_run_broker_without_live_shadow_dependencies(self) -> None:
        config = TradeOpsGatewayConfig(
            account_id="ACC001",
            auto_account=False,
            trading_day=date(2026, 3, 31),
            output_dir=str(self.work_root / "artifacts" / "trade_ops"),
            state_dir=str(self.work_root / "state" / "trade_ops"),
            qmt_userdata="",
            qmt_exe="",
            require_up_queue_file=True,
            session_id=1111,
            session_candidates=(1111, 1100, 1101),
            enable_derived_session_fallback=False,
            execution_mode="flow_smoke",
        )
        with patch.dict(sys.modules, _install_stub_adapter_modules()):
            context = build_trade_ops_context(
                config,
                "order.place",
                ensure_miniqmt_awake_fn=lambda **_: (_ for _ in ()).throw(
                    AssertionError("flow_smoke should not wake MiniQMT")
                ),
                market_data_factory=_FakeMarketDataProvider,
                shadow_adapter_factory=lambda cfg: (_ for _ in ()).throw(
                    AssertionError("flow_smoke should not build live shadow")
                ),
            )
        try:
            self.assertEqual(context.resolved_account_id, "ACC001")
            self.assertEqual(context.resolved_session_id, 1111)
            self.assertIsNone(context.service.shadow)
            self.assertIsInstance(context.service.broker, _FakeDryRunBrokerAdapter)
            self.assertIsNone(context.service._broker_order_adapter_factory)
            self.assertEqual(context.service.cfg.execution_mode, "flow_smoke")
        finally:
            context.close()


if __name__ == "__main__":
    unittest.main()
