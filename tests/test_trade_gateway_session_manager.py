from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.session_resolution import SessionResolution, build_runtime_session_resolution
from xtqmt_mcp.trade_gateway.bootstrap import TradeOpsRuntimeContext
from xtqmt_mcp.trade_gateway.config import (
    ACCOUNT_CONTRACT_SINGLE_PRIMARY,
    ACCOUNT_INPUT_MODE_SERVICE_CONTEXT,
    TradeOpsGatewayConfig,
)
from xtqmt_mcp.trade_gateway.session_manager import GatewaySessionManager, SessionWarmError


class _FakeResult:
    def __init__(self, ok: bool = True, payload: dict[str, object] | None = None) -> None:
        self.ok = ok
        self.payload = dict(payload or {})


class _FakeService:
    def __init__(self, account_id: str) -> None:
        self.cfg = type("Cfg", (), {"account_id": account_id})()
        self.base_session_resolution: dict[str, object] = {}
        self.session_resolution: dict[str, object] = {}

    def account_show(self) -> _FakeResult:
        return _FakeResult(True, {"account_id": self.cfg.account_id})

    def positions_list(self) -> _FakeResult:
        return _FakeResult(True, {"account_id": self.cfg.account_id, "rows": []})

    def orders_list(self) -> _FakeResult:
        return _FakeResult(True, {"account_id": self.cfg.account_id, "rows": []})

    def warm_health_orders_list(self) -> _FakeResult:
        return _FakeResult(True, {"account_id": self.cfg.account_id, "rows": [], "count": 0, "source": "xttrader_shadow"})

    def close(self) -> None:
        return None

    def effective_session_resolution(self) -> dict[str, object]:
        return dict(self.session_resolution)

    def runtime_session_override(self) -> dict[str, object]:
        override = self.session_resolution.get("runtime_resolution_event")
        return dict(override or {}) if isinstance(override, dict) else {}


class _WarmHealthShadowService(_FakeService):
    def __init__(self, account_id: str) -> None:
        super().__init__(account_id)
        self.public_orders_calls = 0
        self.warm_orders_calls = 0

    def orders_list(self) -> _FakeResult:
        self.public_orders_calls += 1
        raise AssertionError("public orders_list should not be used by session.warm health")

    def warm_health_orders_list(self) -> _FakeResult:
        self.warm_orders_calls += 1
        return _FakeResult(
            True,
            {
                "account_id": self.cfg.account_id,
                "rows": [{"broker_order_id": "20001", "code": "000001.SZ"}],
                "count": 1,
                "source": "xttrader_shadow",
                "read_scope": "warm_health_only",
            },
        )


class _AccountShowFailService(_FakeService):
    def __init__(self, account_id: str) -> None:
        super().__init__(account_id)
        self.account_show_calls = 0
        self.positions_calls = 0
        self.warm_orders_calls = 0

    def account_show(self) -> _FakeResult:
        self.account_show_calls += 1
        raise RuntimeError("xttrader connect failed: -1")

    def positions_list(self) -> _FakeResult:
        self.positions_calls += 1
        raise AssertionError("positions_list should not run after account.show failure")

    def warm_health_orders_list(self) -> _FakeResult:
        self.warm_orders_calls += 1
        raise AssertionError("warm_health_orders_list should not run after account.show failure")


class _OwnerSessionAwareService(_FakeService):
    def __init__(self, account_id: str, owner_session_id: int = 1100) -> None:
        super().__init__(account_id)
        self.owner_session_id = int(owner_session_id)
        self.session_resolution = {
            "configured_session_id": 1111,
            "resolved_base_session_id": 1111,
            "resolved_session_id": 901,
            "configured_session_candidates": [1111, 1100, 1101, 100, 101, 111],
            "effective_session_plan": [901, 1111, 1100, 1101, 100, 101, 111, 1901, 2111, 2100, 2101],
            "derived_session_fallback_enabled": True,
            "max_session_attempts": 12,
            "explicit_session_resolution_applied": True,
        }
        self.base_session_resolution = dict(self.session_resolution)

    def owner_managed_session_id(self) -> int:
        return int(self.owner_session_id)

    def realign_session_resolution(self, preferred_session_id: int, **kwargs) -> dict[str, object]:
        self.session_resolution = build_runtime_session_resolution(self.session_resolution, preferred_session_id, **kwargs)
        return dict(self.session_resolution)


class _ProbeRealignService(_FakeService):
    def __init__(self, account_id: str) -> None:
        super().__init__(account_id)
        self.owner_session_id = 2100
        self.session_resolution = {
            "configured_session_id": 2111,
            "resolved_base_session_id": 2111,
            "resolved_session_id": 2100,
            "configured_session_candidates": [2100, 2111, 2101],
            "effective_session_plan": [2100, 2111, 2101],
            "derived_session_fallback_enabled": False,
            "max_session_attempts": 3,
            "explicit_session_resolution_applied": True,
        }
        self.base_session_resolution = dict(self.session_resolution)

    def owner_managed_session_id(self) -> int:
        return int(self.owner_session_id)

    def probe_connection(self) -> _FakeResult:
        return _FakeResult(
            True,
            {
                "session_id": "2101",
                "same_plan_verdict": True,
                "probe_complete_verdict": True,
                "fresh_connect_verified": True,
                "write_authority_ready": True,
                "session_resolution": {
                    "resolved_session_id": 2101,
                    "effective_session_plan": [2101, 2100, 2111],
                },
            },
        )

    def realign_session_resolution(self, preferred_session_id: int, **kwargs) -> dict[str, object]:
        self.session_resolution = build_runtime_session_resolution(self.session_resolution, preferred_session_id, **kwargs)
        return dict(self.session_resolution)


class _FlakyProbeRealignService(_ProbeRealignService):
    def __init__(self, account_id: str) -> None:
        super().__init__(account_id)
        self.probe_calls = 0

    def probe_connection(self) -> _FakeResult:
        self.probe_calls += 1
        if self.probe_calls == 1:
            return super().probe_connection()
        return _FakeResult(
            True,
            {
                "session_id": "2101",
                "same_plan_verdict": False,
                "probe_complete_verdict": False,
                "fresh_connect_verified": False,
                "write_authority_ready": False,
            },
        )


class _ResolvedWriteSessionService(_ProbeRealignService):
    def probe_connection(self) -> _FakeResult:
        return _FakeResult(
            True,
            {
                "session_id": "2101",
                "same_plan_verdict": True,
                "probe_complete_verdict": True,
                "fresh_connect_verified": False,
                "write_authority_ready": False,
                "session_resolution": {
                    "resolved_session_id": 2101,
                    "effective_session_plan": [2101, 2100, 2111],
                },
            },
        )


def _build_context(
    config: TradeOpsGatewayConfig,
    tool_name: str,
    *,
    service_factory: type[_FakeService] = _FakeService,
) -> TradeOpsRuntimeContext:
    resolved_account_id = str(config.account_id or "ACC_AUTO")
    session_resolution = SessionResolution(
        configured_session_id=1111,
        resolved_base_session_id=1111,
        resolved_session_id=901,
        configured_session_candidates=(1111, 1100, 1101, 100, 101, 111),
        effective_session_plan=(901, 1111, 1100, 1101, 100, 101, 111, 1901, 2111, 2100, 2101),
        derived_session_fallback_enabled=True,
        max_session_attempts=12,
        explicit_session_resolution_applied=True,
    )
    service = service_factory(resolved_account_id)
    base_payload = session_resolution.as_payload()
    if not getattr(service, "base_session_resolution", None):
        service.base_session_resolution = dict(base_payload)
    if not getattr(service, "session_resolution", None):
        service.session_resolution = dict(base_payload)
    return TradeOpsRuntimeContext(
        service=service,
        wake_report={"ok": True},
        resolved_account_id=resolved_account_id,
        resolved_session_id=901,
        session_resolution=session_resolution,
    )


class TradeGatewaySessionManagerTests(unittest.TestCase):
    def test_warm_uses_auto_resolved_primary_account_when_config_account_is_empty(self) -> None:
        manager = GatewaySessionManager(
            TradeOpsGatewayConfig(account_id="", auto_account=True, trading_day=date.today()),
            context_builder=_build_context,
        )
        state = manager.warm()
        self.assertEqual(state.account_id, "ACC_AUTO")
        summary = manager.status()
        self.assertEqual(summary["account_id"], "ACC_AUTO")
        self.assertEqual(summary["account_contract"], ACCOUNT_CONTRACT_SINGLE_PRIMARY)
        self.assertEqual(summary["account_input_mode"], ACCOUNT_INPUT_MODE_SERVICE_CONTEXT)
        self.assertEqual(summary["account_scope"], "primary_session")
        self.assertEqual(summary["session_resolution"]["resolved_session_id"], 901)
        self.assertEqual(summary["session_resolution"]["configured_session_id"], 1111)
        closed = manager.close()
        self.assertTrue(closed["closed"])
        self.assertEqual(closed["account_id"], "ACC_AUTO")
        self.assertEqual(closed["session_resolution"]["resolved_session_id"], 901)

    def test_warm_health_orders_step_uses_warm_only_shadow_reader(self) -> None:
        captured: dict[str, object] = {}

        def _context_builder(config: TradeOpsGatewayConfig, tool_name: str) -> TradeOpsRuntimeContext:
            context = _build_context(config, tool_name, service_factory=_WarmHealthShadowService)
            captured["service"] = context.service
            return context

        manager = GatewaySessionManager(
            TradeOpsGatewayConfig(account_id="ACC001", auto_account=False, trading_day=date.today()),
            context_builder=_context_builder,
        )

        try:
            state = manager.warm()
            service = captured["service"]
            self.assertIsInstance(service, _WarmHealthShadowService)
            self.assertEqual(service.public_orders_calls, 0)
            self.assertEqual(service.warm_orders_calls, 1)
            self.assertTrue(state.ready)
            self.assertEqual(state.warm_trace[-1]["step"], "orders.list")
            self.assertEqual(state.warm_trace[-1]["payload"]["source"], "xttrader_shadow")
            self.assertEqual(state.warm_trace[-1]["payload"]["read_scope"], "warm_health_only")
        finally:
            manager.close()

    def test_warm_and_status_expose_live_owner_session_id_when_service_reports_it(self) -> None:
        def _context_builder(config: TradeOpsGatewayConfig, tool_name: str) -> TradeOpsRuntimeContext:
            return _build_context(config, tool_name, service_factory=_OwnerSessionAwareService)

        manager = GatewaySessionManager(
            TradeOpsGatewayConfig(account_id="ACC001", auto_account=False, trading_day=date.today()),
            context_builder=_context_builder,
        )

        try:
            state = manager.warm()
            self.assertEqual(state.session_id, 1100)
            summary = manager.status()
            self.assertEqual(summary["session_id"], 1100)
            self.assertEqual(summary["session_resolution"]["resolved_session_id"], 901)
            self.assertEqual(summary["effective_session_resolution"]["resolved_session_id"], 1100)
            self.assertEqual(summary["effective_session_resolution"]["effective_session_plan"][0], 1100)
            self.assertEqual(summary["runtime_session_override"]["event_source"], "owner_managed_session")
        finally:
            manager.close()

    def test_warm_and_status_follow_probe_realign_when_fresh_verify_succeeds(self) -> None:
        def _context_builder(config: TradeOpsGatewayConfig, tool_name: str) -> TradeOpsRuntimeContext:
            return _build_context(config, tool_name, service_factory=_ProbeRealignService)

        manager = GatewaySessionManager(
            TradeOpsGatewayConfig(account_id="ACC001", auto_account=False, trading_day=date.today()),
            context_builder=_context_builder,
        )

        try:
            state = manager.warm()
            self.assertEqual(state.session_id, 2101)
            summary = manager.status()
            self.assertEqual(summary["session_id"], 2101)
            self.assertEqual(summary["session_resolution"]["resolved_session_id"], 2100)
            self.assertEqual(summary["effective_session_resolution"]["resolved_session_id"], 2101)
            self.assertEqual(summary["effective_session_resolution"]["effective_session_plan"][0], 2101)
            self.assertEqual(summary["runtime_session_override"]["event_source"], "probe.connection")
        finally:
            manager.close()

    def test_warm_and_status_realign_to_resolved_write_session_before_fresh_connect_turns_green(self) -> None:
        captured: dict[str, object] = {}

        def _context_builder(config: TradeOpsGatewayConfig, tool_name: str) -> TradeOpsRuntimeContext:
            context = _build_context(config, tool_name, service_factory=_ResolvedWriteSessionService)
            captured["service"] = context.service
            return context

        manager = GatewaySessionManager(
            TradeOpsGatewayConfig(account_id="ACC001", auto_account=False, trading_day=date.today()),
            context_builder=_context_builder,
        )

        try:
            state = manager.warm()
            self.assertEqual(state.session_id, 2101)
            self.assertTrue(state.ready)
            self.assertEqual(state.warm_trace[-1]["payload"]["session_resolution"]["resolved_session_id"], 2101)
            self.assertEqual(state.warm_trace[-1]["payload"]["runtime_session_override"]["event_source"], "probe.connection")

            summary = manager.status()
            self.assertEqual(summary["session_id"], 2101)
            self.assertEqual(summary["session_resolution"]["resolved_session_id"], 2100)
            self.assertEqual(summary["effective_session_resolution"]["resolved_session_id"], 2101)
            self.assertEqual(summary["effective_session_resolution"]["effective_session_plan"][0], 2101)
            self.assertEqual(summary["status_trace"][-1]["payload"]["session_resolution"]["resolved_session_id"], 2101)
            service = captured["service"]
            self.assertIsInstance(service, _ResolvedWriteSessionService)
            probe_payload = service.probe_connection().payload
            self.assertFalse(probe_payload["fresh_connect_verified"])
            self.assertFalse(probe_payload["write_authority_ready"])
        finally:
            manager.close()

    def test_status_keeps_last_realigned_session_when_subsequent_health_probe_flaps(self) -> None:
        def _context_builder(config: TradeOpsGatewayConfig, tool_name: str) -> TradeOpsRuntimeContext:
            return _build_context(config, tool_name, service_factory=_FlakyProbeRealignService)

        manager = GatewaySessionManager(
            TradeOpsGatewayConfig(account_id="ACC001", auto_account=False, trading_day=date.today()),
            context_builder=_context_builder,
        )

        try:
            state = manager.warm()
            self.assertEqual(state.session_id, 2101)
            summary = manager.status()
            self.assertEqual(summary["session_id"], 2101)
            self.assertEqual(summary["session_resolution"]["resolved_session_id"], 2100)
            self.assertEqual(summary["effective_session_resolution"]["resolved_session_id"], 2101)
            self.assertEqual(summary["effective_session_resolution"]["effective_session_plan"][0], 2101)
        finally:
            manager.close()

    def test_warm_stops_health_check_after_first_failure(self) -> None:
        captured: dict[str, object] = {}

        def _context_builder(config: TradeOpsGatewayConfig, tool_name: str) -> TradeOpsRuntimeContext:
            context = _build_context(config, tool_name, service_factory=_AccountShowFailService)
            captured["service"] = context.service
            return context

        manager = GatewaySessionManager(
            TradeOpsGatewayConfig(account_id="ACC001", auto_account=False, trading_day=date.today()),
            context_builder=_context_builder,
        )

        with self.assertRaises(SessionWarmError) as cm:
            manager.warm()

        service = captured["service"]
        self.assertIsInstance(service, _AccountShowFailService)
        self.assertEqual(service.account_show_calls, 1)
        self.assertEqual(service.positions_calls, 0)
        self.assertEqual(service.warm_orders_calls, 0)
        self.assertEqual(cm.exception.payload["reason"], "account.show_exception")
        self.assertEqual(len(cm.exception.payload["warm_trace"]), 1)
        self.assertEqual(cm.exception.payload["warm_trace"][0]["step"], "account.show")


if __name__ == "__main__":
    unittest.main()
