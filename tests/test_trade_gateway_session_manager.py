from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import tempfile
from threading import Event, Thread
from time import monotonic, sleep
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.session_resolution import SessionResolution, build_effective_session_plan, build_runtime_session_resolution
from xtqmt_mcp.trade_gateway.bootstrap import TradeOpsRuntimeContext
from xtqmt_mcp.trade_gateway.config import (
    ACCOUNT_CONTRACT_SINGLE_PRIMARY,
    ACCOUNT_INPUT_MODE_SERVICE_CONTEXT,
    TradeOpsGatewayConfig,
    load_trade_gateway_config,
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
    def test_warm_timeout_preserves_timeout_reason_in_status(self) -> None:
        started = Event()
        release = Event()

        def _blocking_context_builder(config: TradeOpsGatewayConfig, tool_name: str) -> TradeOpsRuntimeContext:
            started.set()
            release.wait(timeout=5.0)
            return _build_context(config, tool_name)

        manager = GatewaySessionManager(
            TradeOpsGatewayConfig(
                account_id="ACC001",
                auto_account=False,
                trading_day=date.today(),
                session_warm_timeout_seconds=0.05,
            ),
            context_builder=_blocking_context_builder,
        )

        try:
            with self.assertRaises(SessionWarmError) as first_warm:
                manager.warm()
            self.assertEqual(first_warm.exception.payload["reason"], "session_start_timeout")

            status = manager.status()
            self.assertEqual(status["reason"], "session_start_timeout")
            self.assertEqual(status["last_error"], "session_start_timeout")
        finally:
            release.set()
            manager.close()

    def test_warm_timeout_preserves_config_session_plan_in_pending_payloads(self) -> None:
        release = Event()

        def _blocking_context_builder(config: TradeOpsGatewayConfig, tool_name: str) -> TradeOpsRuntimeContext:
            release.wait(timeout=5.0)
            return _build_context(config, tool_name)

        config = TradeOpsGatewayConfig(
            account_id="ACC001",
            auto_account=False,
            trading_day=date.today(),
            session_id=2111,
            session_candidates=(2111, 2100, 2101),
            enable_derived_session_fallback=False,
            max_session_attempts=3,
            session_warm_timeout_seconds=0.05,
        )
        expected_plan = list(
            build_effective_session_plan(
                config.session_id,
                config.session_candidates,
                config.enable_derived_session_fallback,
                max_session_attempts=config.max_session_attempts,
            )
        )
        manager = GatewaySessionManager(config, context_builder=_blocking_context_builder)

        try:
            with self.assertRaises(SessionWarmError) as first_warm:
                manager.warm()

            payload = first_warm.exception.payload
            self.assertEqual(payload["reason"], "session_start_timeout")
            self.assertEqual(payload["session_resolution"]["resolved_session_id"], 2111)
            self.assertEqual(payload["session_resolution"]["effective_session_plan"], expected_plan)
            self.assertEqual(payload["effective_session_resolution"]["resolved_session_id"], 2111)
            self.assertEqual(payload["effective_session_resolution"]["effective_session_plan"], expected_plan)

            status = manager.status()
            self.assertEqual(status["reason"], "session_start_timeout")
            self.assertEqual(status["session_resolution"]["resolved_session_id"], 2111)
            self.assertEqual(status["session_resolution"]["effective_session_plan"], expected_plan)
            self.assertEqual(status["effective_session_resolution"]["resolved_session_id"], 2111)
            self.assertEqual(status["effective_session_resolution"]["effective_session_plan"], expected_plan)

            closed = manager.close()
            self.assertTrue(closed["closed"])
            self.assertEqual(closed["session_resolution"]["resolved_session_id"], 2111)
            self.assertEqual(closed["session_resolution"]["effective_session_plan"], expected_plan)
        finally:
            release.set()
            manager.close()

    def test_pending_timeout_rewarm_fails_fast_without_second_cold_start(self) -> None:
        started = Event()
        release = Event()
        build_calls = 0

        def _blocking_context_builder(config: TradeOpsGatewayConfig, tool_name: str) -> TradeOpsRuntimeContext:
            nonlocal build_calls
            build_calls += 1
            started.set()
            release.wait(timeout=5.0)
            return _build_context(config, tool_name)

        manager = GatewaySessionManager(
            TradeOpsGatewayConfig(
                account_id="ACC001",
                auto_account=False,
                trading_day=date.today(),
                session_warm_timeout_seconds=0.05,
            ),
            context_builder=_blocking_context_builder,
        )

        try:
            with self.assertRaises(SessionWarmError) as first_warm:
                manager.warm()
            self.assertEqual(first_warm.exception.payload["reason"], "session_start_timeout")

            started_at = monotonic()
            with self.assertRaises(SessionWarmError) as second_warm:
                manager.warm(force=False)
            elapsed = monotonic() - started_at

            failures: list[str] = []
            if elapsed >= 0.5:
                failures.append(f"second warm blocked too long: elapsed={elapsed:.3f}s")
            if build_calls != 1:
                failures.append(f"expected pending rewarm to reuse existing startup window, got build_calls={build_calls}")
            if second_warm.exception.payload.get("reason") != "session_start_timeout_pending":
                failures.append(
                    "second warm did not expose same pending/timeout window semantics: "
                    f"reason={second_warm.exception.payload.get('reason')!r}"
                )
            self.assertEqual(failures, [])
        finally:
            release.set()
            manager.close()

    def test_close_during_pending_timeout_does_not_immediately_open_second_cold_start(self) -> None:
        started = Event()
        release = Event()
        build_calls = 0

        def _blocking_context_builder(config: TradeOpsGatewayConfig, tool_name: str) -> TradeOpsRuntimeContext:
            nonlocal build_calls
            build_calls += 1
            started.set()
            release.wait(timeout=15.0)
            return _build_context(config, tool_name)

        manager = GatewaySessionManager(
            TradeOpsGatewayConfig(
                account_id="ACC001",
                auto_account=False,
                trading_day=date.today(),
                session_warm_timeout_seconds=0.05,
            ),
            context_builder=_blocking_context_builder,
        )

        try:
            with self.assertRaises(SessionWarmError) as first_warm:
                manager.warm()
            self.assertEqual(first_warm.exception.payload["reason"], "session_start_timeout")

            closed = manager.close()
            self.assertTrue(closed["closed"])

            with self.assertRaises(SessionWarmError) as second_warm:
                manager.warm(force=False)

            self.assertEqual(second_warm.exception.payload.get("reason"), "session_start_timeout_pending")
            self.assertEqual(build_calls, 1)
        finally:
            release.set()
            manager.close()

    def test_require_during_pending_timeout_exposes_specific_timeout_reason(self) -> None:
        started = Event()
        release = Event()

        def _blocking_context_builder(config: TradeOpsGatewayConfig, tool_name: str) -> TradeOpsRuntimeContext:
            started.set()
            release.wait(timeout=15.0)
            return _build_context(config, tool_name)

        manager = GatewaySessionManager(
            TradeOpsGatewayConfig(
                account_id="ACC001",
                auto_account=False,
                trading_day=date.today(),
                session_warm_timeout_seconds=0.05,
            ),
            context_builder=_blocking_context_builder,
        )

        try:
            with self.assertRaises(SessionWarmError):
                manager.warm()

            with self.assertRaises(RuntimeError) as require_error:
                manager.require()

            self.assertIn("session_start_timeout", str(require_error.exception))
        finally:
            release.set()
            manager.close()

    def test_execute_during_pending_timeout_exposes_specific_timeout_reason(self) -> None:
        started = Event()
        release = Event()

        def _blocking_context_builder(config: TradeOpsGatewayConfig, tool_name: str) -> TradeOpsRuntimeContext:
            started.set()
            release.wait(timeout=15.0)
            return _build_context(config, tool_name)

        manager = GatewaySessionManager(
            TradeOpsGatewayConfig(
                account_id="ACC001",
                auto_account=False,
                trading_day=date.today(),
                session_warm_timeout_seconds=0.05,
            ),
            context_builder=_blocking_context_builder,
        )

        try:
            with self.assertRaises(SessionWarmError):
                manager.warm()

            with self.assertRaises(RuntimeError) as execute_error:
                manager.execute(runner=lambda context: "ok", require_ready=False)

            self.assertIn("session_start_timeout", str(execute_error.exception))
        finally:
            release.set()
            manager.close()

    def test_warm_fails_fast_when_worker_startup_never_becomes_ready(self) -> None:
        started = Event()
        release = Event()
        captured: dict[str, object] = {}

        def _blocking_context_builder(config: TradeOpsGatewayConfig, tool_name: str) -> TradeOpsRuntimeContext:
            started.set()
            release.wait(timeout=5.0)
            return _build_context(config, tool_name)

        manager = GatewaySessionManager(
            TradeOpsGatewayConfig(
                account_id="ACC001",
                auto_account=False,
                trading_day=date.today(),
                session_warm_timeout_seconds=0.05,
            ),
            context_builder=_blocking_context_builder,
        )

        def _run_warm() -> None:
            try:
                captured["state"] = manager.warm()
            except Exception as exc:  # pragma: no cover - assertion reads captured error shape
                captured["error"] = exc

        warm_thread = Thread(target=_run_warm, name="test-session-warm-timeout", daemon=True)
        warm_thread.start()

        try:
            self.assertTrue(started.wait(timeout=0.2))
            warm_thread.join(timeout=0.3)
            self.assertFalse(warm_thread.is_alive(), "manager.warm should fail fast instead of hanging on worker startup")
            error = captured.get("error")
            self.assertIsInstance(error, SessionWarmError)
            assert isinstance(error, SessionWarmError)
            self.assertEqual(error.payload["reason"], "session_start_timeout")
            self.assertFalse(error.payload["ready"])
        finally:
            release.set()
            warm_thread.join(timeout=1.0)
            manager.close()

    def test_status_promotes_recovered_pending_worker_after_startup_timeout(self) -> None:
        release = Event()
        context_built = Event()
        build_calls = 0

        def _blocking_context_builder(config: TradeOpsGatewayConfig, tool_name: str) -> TradeOpsRuntimeContext:
            nonlocal build_calls
            build_calls += 1
            release.wait(timeout=5.0)
            context = _build_context(config, tool_name, service_factory=_ProbeRealignService)
            context_built.set()
            return context

        manager = GatewaySessionManager(
            TradeOpsGatewayConfig(
                account_id="ACC001",
                auto_account=False,
                trading_day=date.today(),
                session_warm_timeout_seconds=0.05,
            ),
            context_builder=_blocking_context_builder,
        )

        try:
            with self.assertRaises(SessionWarmError) as first_warm:
                manager.warm()
            self.assertEqual(first_warm.exception.payload["reason"], "session_start_timeout")

            release.set()
            self.assertTrue(context_built.wait(timeout=1.0))

            deadline = monotonic() + 1.0
            while monotonic() < deadline:
                pending = manager._pending_startup
                if pending is not None and pending.worker.is_alive():
                    break
                sleep(0.01)
            else:
                self.fail("timed-out pending worker never recovered into an active session")

            status = manager.status()
            self.assertTrue(status["ready"])
            self.assertEqual(status["session_id"], 2101)
            self.assertEqual(status["effective_session_resolution"]["resolved_session_id"], 2101)
            self.assertEqual(status["runtime_session_override"]["event_source"], "probe.connection")
            self.assertEqual(build_calls, 1)
        finally:
            release.set()
            manager.close()

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

    def test_load_trade_gateway_config_clamps_session_warm_timeout_to_wake_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "trade_gateway.yaml"
            config_path.write_text(
                "trade:\n"
                "  wake_wait_seconds: 45\n"
                "  session_warm_timeout_seconds: 20\n",
                encoding="utf-8",
            )

            loaded = load_trade_gateway_config(config_path)

        self.assertEqual(loaded.trade_ops.wake_wait_seconds, 45)
        self.assertGreaterEqual(loaded.trade_ops.session_warm_timeout_seconds, loaded.trade_ops.wake_wait_seconds)


if __name__ == "__main__":
    unittest.main()
