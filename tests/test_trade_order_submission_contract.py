from __future__ import annotations

from datetime import datetime
from datetime import date
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.trade_ops import TradeOpsConfig, TradeOpsResult, TradeOpsService
from xtqmt_mcp.types import DataOrigin, OrderPlaceRequest, Side


class _GateMismatchShadow:
    def __init__(self, session_id: str = "101") -> None:
        self.session_id = session_id
        self.calls = 0

    def probe_connection(self) -> dict[str, str]:
        self.calls += 1
        return {
            "ok": "True",
            "connect_code": "0",
            "session_id": str(self.session_id),
            "base_session_id": "1111",
        }

    def probe_live_readiness(self, *, snapshot_requires_position: bool = False) -> dict[str, object]:
        self.calls += 1
        return {
            "available": True,
            "reused_session": True,
            "ok": True,
            "reason": "",
            "account_id": "ACC001",
            "session_id": str(self.session_id),
            "source": "xttrader_shadow",
            "positions_rows": 1,
            "asset_rows": 1,
            "snapshot_requires_position": snapshot_requires_position,
        }

    def close(self) -> None:
        return None


class _ConnectGateDownShadow:
    def __init__(self) -> None:
        self.calls = 0

    def probe_connection(self) -> dict[str, str]:
        self.calls += 1
        return {
            "ok": "False",
            "connect_code": "-1",
            "session_id": "",
            "base_session_id": "1111",
        }

    def probe_live_readiness(self, *, snapshot_requires_position: bool = False) -> dict[str, object]:
        self.calls += 1
        return {
            "available": True,
            "reused_session": True,
            "ok": False,
            "reason": "connect_failed",
            "account_id": "ACC001",
            "session_id": "",
            "source": "xttrader_shadow",
            "positions_rows": 0,
            "asset_rows": 0,
            "snapshot_requires_position": snapshot_requires_position,
        }


class _CancelBrokerRecorder:
    def __init__(self) -> None:
        self.query_calls = 0
        self.cancel_calls = 0

    def query_order(self, account_id: str, broker_order_id: str):
        self.query_calls += 1
        return None

    def cancel_order(self, account_id: str, broker_order_id: str):
        self.cancel_calls += 1
        raise AssertionError("cancel_order should not run when write authority gate is blocked")

    def close(self) -> None:
        return None


class _PositiveGateShadow:
    def __init__(self, session_id: str = "2111") -> None:
        self.session_id = session_id
        self.calls = 0

    def probe_connection(self) -> dict[str, str]:
        self.calls += 1
        return {
            "ok": "True",
            "connect_code": "0",
            "session_id": str(self.session_id),
            "base_session_id": "1111",
        }

    def get_asset(self):
        return [
            {
                "account_id": "ACC001",
                "cash": 1000000.0,
                "total_asset": 1000000.0,
                "market_value": 0.0,
            }
        ]

    def get_positions(self):
        return [
            {
                "account_id": "ACC001",
                "stock_code": "000001.SZ",
                "quantity": 100,
                "sellable": 100,
                "avg_price": 10.0,
                "market_value": 1000.0,
            }
        ]

    def close(self) -> None:
        return None


class _FakeOnlineEvent:
    def __init__(self, code: str, *, price: float = 10.0) -> None:
        self.code = code
        self.ts = datetime(2026, 4, 8, 10, 0, 0)
        self.bid1 = price - 0.01
        self.bid2 = price - 0.02
        self.bid3 = price - 0.03
        self.ask1 = price + 0.01
        self.ask2 = price + 0.02
        self.ask3 = price + 0.03
        self.last_price = price
        self.source = DataOrigin.ONLINE_PULL


class _PositiveMarketDataProvider:
    def latest_online_event(self, code: str, trading_day: date, event_mode: str):
        return _FakeOnlineEvent(code)


class _FiveLevelGetFullTickEvent:
    def __init__(self, code: str) -> None:
        self.code = code
        self.ts = datetime(2026, 6, 24, 13, 7, 39)
        self.bid1 = 1.795
        self.bid2 = 1.794
        self.bid3 = 1.793
        self.bid4 = 1.792
        self.bid5 = 1.791
        self.ask1 = 1.796
        self.ask2 = 1.797
        self.ask3 = 1.798
        self.ask4 = 1.799
        self.ask5 = 1.800
        self.last_price = 1.795
        self.source = DataOrigin.GET_FULL_TICK


class _FiveLevelGetFullTickMarketDataProvider:
    def latest_online_event(self, code: str, trading_day: date, event_mode: str):
        return _FiveLevelGetFullTickEvent(code)


class _LastPriceOnlyOnlineEvent:
    def __init__(self, code: str, *, price: float = 10.0) -> None:
        self.code = code
        self.ts = datetime(2026, 4, 8, 10, 0, 0)
        self.bid1 = None
        self.bid2 = None
        self.bid3 = None
        self.ask1 = None
        self.ask2 = None
        self.ask3 = None
        self.last_price = price
        self.source = DataOrigin.ONLINE_SUBSCRIBE


class _LastPriceOnlyMarketDataProvider:
    def latest_online_event(self, code: str, trading_day: date, event_mode: str):
        return _LastPriceOnlyOnlineEvent(code)


class _PositiveBroker:
    def __init__(self) -> None:
        self.place_calls = 0
        self.query_calls = 0
        self.cancel_calls = 0
        self.last_intent = None

    def place_order(self, intent):
        self.place_calls += 1
        self.last_intent = intent
        return type(
            "Ack",
            (),
            {
                "ts": datetime(2026, 4, 8, 10, 1, 0),
                "client_order_id": intent.client_order_id,
                "account_id": intent.account_id,
                "code": intent.code,
                "side": intent.side,
                "quantity": intent.quantity,
                "ok": True,
                "status": "submitted",
                "broker_order_id": "20001",
                "message": "accepted",
                "reject_code": "",
                "price_hint": intent.price_hint,
            },
        )()

    def query_order(self, account_id: str, broker_order_id: str):
        self.query_calls += 1
        return type(
            "State",
            (),
            {
                "terminal": False,
                "account_id": account_id,
                "broker_order_id": broker_order_id,
                "status": "submitted",
            },
        )()

    def cancel_order(self, account_id: str, broker_order_id: str):
        self.cancel_calls += 1
        return type(
            "Ack",
            (),
            {
                "ts": datetime(2026, 4, 8, 10, 2, 0),
                "client_order_id": "COID-TG009-GREEN",
                "account_id": account_id,
                "code": "000001.SZ",
                "side": Side.BUY,
                "quantity": 100,
                "ok": True,
                "status": "canceled",
                "broker_order_id": broker_order_id,
                "message": "cancel accepted",
                "reject_code": "",
                "price_hint": 10.01,
            },
        )()

    def close(self) -> None:
        return None


class _BrokerCapablePositiveShadow:
    def __init__(self, session_id: str = "2101") -> None:
        self.session_id = session_id
        self.calls = 0
        self.place_calls = 0
        self.open_order_calls = 0
        self.query_order_calls = 0
        self.cancel_calls = 0
        self.trade_calls = 0
        self._orders: dict[str, object] = {}
        self.cfg = type("Cfg", (), {"session_id": int(session_id)})()

    def active_session_id(self) -> int:
        return int(self.session_id)

    def probe_live_readiness(self, *, snapshot_requires_position: bool = False) -> dict[str, object]:
        self.calls += 1
        return {
            "available": True,
            "reused_session": True,
            "ok": True,
            "reason": "",
            "account_id": "ACC001",
            "session_id": str(self.session_id),
            "source": "xttrader_shadow",
            "positions_rows": 1,
            "asset_rows": 1,
            "snapshot_requires_position": snapshot_requires_position,
        }

    def get_asset(self):
        return [
            {
                "account_id": "ACC001",
                "cash": 1000000.0,
                "total_asset": 1000000.0,
                "market_value": 0.0,
            }
        ]

    def get_positions(self):
        return [
            {
                "account_id": "ACC001",
                "stock_code": "000001.SZ",
                "quantity": 100,
                "sellable": 100,
                "avg_price": 10.0,
                "market_value": 1000.0,
            }
        ]

    def query_open_orders(self, account_id: str):
        self.open_order_calls += 1
        return [value for value in self._orders.values() if not bool(getattr(value, "terminal", False))]

    def query_order(self, account_id: str, broker_order_id: str):
        self.query_order_calls += 1
        return self._orders.get(str(broker_order_id or ""))

    def query_trades(self, account_id: str, since_ts=None):
        self.trade_calls += 1
        return []

    def place_order(self, intent):
        self.place_calls += 1
        state = type(
            "State",
            (),
            {
                "terminal": False,
                "account_id": intent.account_id,
                "broker_order_id": "20001",
                "status": "submitted",
                "code": intent.code,
                "side": intent.side,
                "quantity": intent.quantity,
                "message": "accepted",
                "price_hint": intent.price_hint,
            },
        )()
        self._orders["20001"] = state
        return type(
            "Ack",
            (),
            {
                "ts": datetime(2026, 4, 8, 10, 1, 0),
                "client_order_id": intent.client_order_id,
                "account_id": intent.account_id,
                "code": intent.code,
                "side": intent.side,
                "quantity": intent.quantity,
                "ok": True,
                "status": "submitted",
                "broker_order_id": "20001",
                "message": "accepted",
                "reject_code": "",
                "price_hint": intent.price_hint,
            },
        )()

    def cancel_order(self, account_id: str, broker_order_id: str):
        self.cancel_calls += 1
        return type(
            "Ack",
            (),
            {
                "ts": datetime(2026, 4, 8, 10, 2, 0),
                "client_order_id": "COID-TG006-SHADOW",
                "account_id": account_id,
                "code": "000001.SZ",
                "side": Side.BUY,
                "quantity": 100,
                "ok": True,
                "status": "canceled",
                "broker_order_id": broker_order_id,
                "message": "cancel accepted",
                "reject_code": "",
                "price_hint": 10.01,
            },
        )()

    def close(self) -> None:
        return None


class TradeOrderSubmissionContractTests(unittest.TestCase):
    def _session_resolution(self) -> dict[str, object]:
        return {
            "configured_session_id": 1111,
            "resolved_base_session_id": 1111,
            "resolved_session_id": 2111,
            "configured_session_candidates": [1111, 1100, 1101, 100, 101, 111],
            "effective_session_plan": [2111, 1111, 1100, 1101, 100, 101, 111, 3111, 2100, 2101],
            "session_plan_version": "v1:2111,1111,1100,1101,100,101,111,3111,2100,2101",
            "derived_session_fallback_enabled": True,
            "max_session_attempts": 12,
            "explicit_session_resolution_applied": True,
        }

    def _build_service(
        self,
        root: Path,
        *,
        output_dir: Path | None = None,
        state_dir: Path | None = None,
        kill_switch_file: str = "",
        broker_order_adapter: object | None = None,
    ) -> tuple[TradeOpsService, _GateMismatchShadow]:
        shadow = _GateMismatchShadow()
        userdata = root / "userdata"
        userdata.mkdir(parents=True, exist_ok=True)
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 4, 8),
            output_dir=str(output_dir or (root / "output")),
            state_dir=str(state_dir or (root / "state")),
            kill_switch_file=str(kill_switch_file or ""),
            qmt_userdata=str(userdata),
            pretrade_connect_window=1,
            pretrade_connect_interval_seconds=0.1,
        )
        service = TradeOpsService(
            cfg,
            market_data_provider=object(),
            shadow_adapter=shadow,
            broker_order_adapter=broker_order_adapter,
            session_resolution=self._session_resolution(),
        )
        return service, shadow

    def test_snapshot_l1_payload_preserves_get_full_tick_source_and_five_level_book(self) -> None:
        work_root = Path(tempfile.mkdtemp(prefix="tg010_snapshot_l1_get_full_tick_depth_"))
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 6, 24),
            output_dir=str(work_root / "output"),
            state_dir=str(work_root / "state"),
            qmt_userdata="",
            kill_switch_file="",
            pretrade_connect_window=1,
            pretrade_connect_interval_seconds=0.1,
            enforce_trading_session=False,
        )
        service = TradeOpsService(
            cfg,
            market_data_provider=_FiveLevelGetFullTickMarketDataProvider(),
            shadow_adapter=None,
            broker_order_adapter=None,
            session_resolution=self._session_resolution(),
        )
        try:
            result = service.snapshot_l1("000001.SZ")
            self.assertTrue(result.ok)
            self.assertEqual(result.payload["source"], "get_full_tick")
            self.assertEqual(result.payload["depth_available_levels"], 5)
            self.assertEqual(result.payload["bid4"], 1.792)
            self.assertEqual(result.payload["bid5"], 1.791)
            self.assertEqual(result.payload["ask4"], 1.799)
            self.assertEqual(result.payload["ask5"], 1.800)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_order_place_connect_gate_failure_marks_local_intercept_without_broker_submit(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg006_connect_gate_local_intercept"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        service, shadow = self._build_service(work_root)
        try:
            with patch(
                "xtqmt_mcp.trade_ops.run_layered_user_data_precheck",
                return_value={
                    "read_only": {"ok": True, "report": {"ok": True}},
                    "write_permission": {"ok": True, "report": {"ok": True}},
                },
            ), patch("xtqmt_mcp.trade_ops._tcp_port_ready", return_value=True):
                result = service.place_order(
                    OrderPlaceRequest(
                        account_id="ACC001",
                        code="000001.SZ",
                        side=Side.BUY,
                        quantity=100,
                        guard_token="mcp_server_governed_write_path",
                        client_order_key="COID-TG006-TEST",
                        intent_id="INT-TG006-TEST",
                    )
                )
            self.assertFalse(result.ok)
            self.assertEqual(result.payload["code"], "connect_gate_failed")
            self.assertEqual(result.payload["status"], "risk_rejected")
            self.assertEqual(result.payload["broker_order_id"], "")
            self.assertFalse(result.payload["broker_submission_attempted"])
            self.assertTrue(result.payload["local_gate_intercepted"])
            self.assertEqual(result.payload["submission_scope"], "local_gate")
            self.assertEqual(result.payload["submission_stage"], "connect_gate")
            self.assertEqual(result.payload["connect_gate"]["gate_source"], "probe.connection")
            self.assertEqual(result.payload["connect_gate"]["expected_write_session_id"], "2111")
            self.assertEqual(result.payload["connect_gate"]["expected_base_session_id"], "1111")
            self.assertEqual(result.payload["session_plan_version"], self._session_resolution()["session_plan_version"])
            self.assertEqual(
                result.payload["connect_gate"]["session_plan_version"],
                self._session_resolution()["session_plan_version"],
            )
            self.assertFalse(result.payload["connect_gate"]["pass"])
            self.assertEqual(result.payload["connect_gate"]["reason"], "probe_session_differs_from_resolved_write_session")
            self.assertEqual(
                result.payload["connect_gate"]["session_alignment"]["observed_session_ids"],
                ["101"],
            )
            self.assertFalse(result.payload["connect_gate"]["session_alignment"]["same_plan_verdict"])
            self.assertEqual(result.payload["write_authority_snapshot"]["blocking_reason"], "probe_session_differs_from_resolved_write_session")
            self.assertEqual(result.payload["write_authority_snapshot"]["resolved_session_id"], "2111")
            self.assertEqual(result.payload["write_authority_snapshot"]["observed_probe_session_id"], "101")
            self.assertEqual(shadow.calls, 1)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_probe_connection_and_order_place_share_same_write_authority_truth_under_same_fixture(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg006_same_fixture_authority_truth"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        service, _ = self._build_service(work_root)
        try:
            with patch(
                "xtqmt_mcp.trade_ops.run_layered_user_data_precheck",
                return_value={
                    "read_only": {"ok": True, "report": {"ok": True}},
                    "write_permission": {"ok": True, "report": {"ok": True}},
                },
            ), patch("xtqmt_mcp.trade_ops._tcp_port_ready", return_value=True):
                probe = service.probe_connection()
                placed = service.place_order(
                    OrderPlaceRequest(
                        account_id="ACC001",
                        code="000001.SZ",
                        side=Side.BUY,
                        quantity=100,
                        guard_token="mcp_server_governed_write_path",
                        client_order_key="COID-TG006-SAME-FIXTURE",
                        intent_id="INT-TG006-SAME-FIXTURE",
                    )
                )
            self.assertFalse(probe.payload["same_plan_verdict"])
            self.assertFalse(placed.ok)
            self.assertEqual(
                placed.payload["write_authority_snapshot"]["blocking_reason"],
                probe.payload["reason"],
            )
            self.assertEqual(
                placed.payload["write_authority_snapshot"]["resolved_session_id"],
                probe.payload["session_id"],
            )
            self.assertEqual(
                placed.payload["write_authority_snapshot"]["observed_probe_session_id"],
                probe.payload["observed_probe_session_id"],
            )
            self.assertEqual(
                placed.payload["write_authority_snapshot"]["session_plan_version"],
                probe.payload["session_plan_version"],
            )
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_order_place_requires_non_empty_kill_switch_file_in_prod_scope(self) -> None:
        work_root = ROOT / "instance" / "prod" / "state" / "test_tmp" / "tg006_kill_switch_required"
        artifacts_root = ROOT / "instance" / "prod" / "artifacts" / "test_tmp" / "tg006_kill_switch_required"
        shutil.rmtree(work_root, ignore_errors=True)
        shutil.rmtree(artifacts_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        artifacts_root.mkdir(parents=True, exist_ok=True)
        service, shadow = self._build_service(
            work_root,
            output_dir=artifacts_root,
            state_dir=work_root,
            kill_switch_file="",
        )
        try:
            result = service.place_order(
                OrderPlaceRequest(
                    account_id="ACC001",
                    code="000001.SZ",
                    side=Side.BUY,
                    quantity=100,
                    guard_token="mcp_server_governed_write_path",
                    client_order_key="COID-TG006-KILL-TEST",
                    intent_id="INT-TG006-KILL-TEST",
                )
            )
            self.assertFalse(result.ok)
            self.assertEqual(result.payload["code"], "kill_switch_unconfigured")
            self.assertEqual(result.payload["status"], "risk_rejected")
            self.assertFalse(result.payload["broker_submission_attempted"])
            self.assertTrue(result.payload["local_gate_intercepted"])
            self.assertEqual(result.payload["submission_scope"], "local_risk")
            self.assertEqual(result.payload["submission_stage"], "kill_switch_configuration")
            self.assertFalse(result.payload["kill_switch_configured"])
            self.assertEqual(shadow.calls, 0)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)
            shutil.rmtree(artifacts_root, ignore_errors=True)

    def test_order_place_connect_gate_unstable_still_marks_local_gate_contract_flags(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg006_connect_gate_unstable_contract"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        shadow = _ConnectGateDownShadow()
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 4, 8),
            output_dir=str(work_root / "output"),
            state_dir=str(work_root / "state"),
            qmt_userdata=str(work_root / "userdata"),
            kill_switch_file="",
            pretrade_connect_window=1,
            pretrade_connect_interval_seconds=0.1,
        )
        (work_root / "userdata").mkdir(parents=True, exist_ok=True)
        service = TradeOpsService(
            cfg,
            market_data_provider=object(),
            shadow_adapter=shadow,
            broker_order_adapter=None,
            session_resolution=self._session_resolution(),
        )
        try:
            with patch(
                "xtqmt_mcp.trade_ops.run_layered_user_data_precheck",
                return_value={
                    "read_only": {"ok": True, "report": {"ok": True}},
                    "write_permission": {"ok": True, "report": {"ok": True}},
                },
            ), patch("xtqmt_mcp.trade_ops._tcp_port_ready", return_value=True):
                result = service.place_order(
                    OrderPlaceRequest(
                        account_id="ACC001",
                        code="000001.SZ",
                        side=Side.BUY,
                        quantity=100,
                        guard_token="mcp_server_governed_write_path",
                        client_order_key="COID-TG006-UNSTABLE",
                        intent_id="INT-TG006-UNSTABLE",
                    )
                )
            self.assertFalse(result.ok)
            self.assertEqual(result.payload["code"], "connect_gate_failed")
            self.assertEqual(result.payload["broker_order_id"], "")
            self.assertFalse(result.payload["broker_submission_attempted"])
            self.assertTrue(result.payload["local_gate_intercepted"])
            self.assertEqual(result.payload["submission_scope"], "local_gate")
            self.assertEqual(result.payload["submission_stage"], "connect_gate")
            self.assertEqual(result.payload["session_plan_version"], self._session_resolution()["session_plan_version"])
            self.assertEqual(
                result.payload["connect_gate"]["session_plan_version"],
                self._session_resolution()["session_plan_version"],
            )
            self.assertEqual(result.payload["connect_gate"]["reason"], "connect_failed")
            self.assertEqual(result.payload["write_authority_snapshot"]["blocking_reason"], "connect_failed")
            self.assertEqual(shadow.calls, 1)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_order_place_can_reuse_owner_managed_live_shadow_broker_session(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg009_owner_managed_shadow_broker_reuse"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        userdata = work_root / "userdata"
        userdata.mkdir(parents=True, exist_ok=True)
        shadow = _BrokerCapablePositiveShadow(session_id="2101")
        session_resolution = self._session_resolution()
        session_resolution["resolved_session_id"] = 2100
        session_resolution["configured_session_candidates"] = [2100, 2101, 111]
        session_resolution["effective_session_plan"] = [2100, 2101, 111]
        session_resolution["session_plan_version"] = "v1:2100,2101,111"
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 4, 8),
            output_dir=str(work_root / "output"),
            state_dir=str(work_root / "state"),
            qmt_userdata=str(userdata),
            kill_switch_file="",
            pretrade_connect_window=1,
            pretrade_connect_interval_seconds=0.1,
            enforce_trading_session=False,
        )
        service = TradeOpsService(
            cfg,
            market_data_provider=_PositiveMarketDataProvider(),
            shadow_adapter=shadow,
            broker_order_adapter=None,
            broker_order_adapter_factory=lambda require_write_permission: (_ for _ in ()).throw(
                AssertionError("owner-managed live shadow reuse should bypass ephemeral broker factory")
            ),
            session_resolution=session_resolution,
        )
        try:
            with patch(
                "xtqmt_mcp.trade_ops.run_layered_user_data_precheck",
                return_value={
                    "read_only": {"ok": True, "report": {"ok": True}},
                    "write_permission": {"ok": True, "report": {"ok": True}},
                },
            ), patch("xtqmt_mcp.trade_ops._tcp_port_ready", return_value=True):
                probe = service.probe_connection()
                orders_pre = service.orders_list()
                placed = service.place_order(
                    OrderPlaceRequest(
                        account_id="ACC001",
                        code="000001.SZ",
                        side=Side.BUY,
                        quantity=100,
                        guard_token="mcp_server_governed_write_path",
                        client_order_key="COID-TG009-SHADOW",
                        intent_id="INT-TG009-SHADOW",
                    )
                )
            self.assertTrue(probe.ok)
            self.assertEqual(probe.payload["reason"], "ok")
            self.assertEqual(probe.payload["session_id"], "2101")
            self.assertTrue(probe.payload["fresh_connect_verified"])
            self.assertTrue(orders_pre.ok)
            self.assertEqual(orders_pre.payload["count"], 0)
            self.assertTrue(placed.ok)
            self.assertEqual(placed.payload["broker_order_id"], "20001")
            self.assertTrue(placed.payload["broker_submission_attempted"])
            self.assertFalse(placed.payload["local_gate_intercepted"])
            self.assertEqual(placed.payload["submission_scope"], "broker_submit")
            self.assertEqual(shadow.place_calls, 1)
            self.assertGreaterEqual(shadow.open_order_calls, 1)
            self.assertIs(service._ensure_broker_adapter(require_write_permission=True), shadow)
            self.assertIs(service._ensure_broker_adapter(require_write_permission=False), shadow)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_live_no_shadow_connect_gate_uses_probe_connection_instead_of_flow_smoke_bypass(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg009_live_no_shadow_connect_gate"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 4, 8),
            output_dir=str(work_root / "output"),
            state_dir=str(work_root / "state"),
            qmt_userdata=str(work_root / "userdata"),
            execution_mode="live",
        )
        (work_root / "userdata").mkdir(parents=True, exist_ok=True)
        service = TradeOpsService(
            cfg,
            market_data_provider=_PositiveMarketDataProvider(),
            shadow_adapter=None,
            broker_order_adapter=None,
            session_resolution=self._session_resolution(),
        )
        probe_payload = {
            "reason": "write_connect_failed",
            "session_id": "2111",
            "observed_probe_session_id": "2111",
            "same_plan_verdict": True,
            "probe_complete_verdict": False,
            "fresh_connect_verified": False,
            "write_authority_ready": False,
            "session_plan_version": self._session_resolution()["session_plan_version"],
            "write_session_alignment": {
                "resolved_session_id": "2111",
                "observed_probe_session_id": "2111",
                "same_session_as_write_path": True,
                "observed_probe_session_in_effective_plan": True,
                "same_plan_reason": "write_connect_failed",
            },
        }
        try:
            with patch.object(
                service,
                "probe_connection",
                return_value=TradeOpsResult(command="probe.connection", ok=False, payload=probe_payload),
            ) as probe_mock:
                result = service._run_connect_gate()
            self.assertTrue(result["enabled"])
            self.assertFalse(result["pass"])
            self.assertEqual(result["reason"], "write_connect_failed")
            self.assertEqual(result["write_authority_snapshot"]["source"], "probe.connection")
            self.assertFalse(result["write_authority_snapshot"]["ready"])
            probe_mock.assert_called_once_with()
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_live_no_shadow_write_authority_snapshot_uses_probe_payload(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg009_live_no_shadow_authority_snapshot"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 4, 8),
            output_dir=str(work_root / "output"),
            state_dir=str(work_root / "state"),
            qmt_userdata=str(work_root / "userdata"),
            execution_mode="live",
        )
        (work_root / "userdata").mkdir(parents=True, exist_ok=True)
        service = TradeOpsService(
            cfg,
            market_data_provider=_PositiveMarketDataProvider(),
            shadow_adapter=None,
            broker_order_adapter=None,
            session_resolution=self._session_resolution(),
        )
        probe_payload = {
            "reason": "write_connect_failed",
            "session_id": "2111",
            "observed_probe_session_id": "2111",
            "same_plan_verdict": True,
            "probe_complete_verdict": False,
            "fresh_connect_verified": False,
            "write_authority_ready": False,
            "session_plan_version": self._session_resolution()["session_plan_version"],
            "write_session_alignment": {
                "resolved_session_id": "2111",
                "observed_probe_session_id": "2111",
            },
        }
        try:
            with patch.object(
                service,
                "probe_connection",
                return_value=TradeOpsResult(command="probe.connection", ok=False, payload=probe_payload),
            ) as probe_mock:
                snapshot = service._write_authority_snapshot()
            self.assertFalse(snapshot["ready"])
            self.assertEqual(snapshot["blocking_reason"], "write_connect_failed")
            self.assertEqual(snapshot["source"], "probe.connection")
            self.assertFalse(snapshot["fresh_connect_verified"])
            probe_mock.assert_called_once_with()
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_order_place_green_path_marks_broker_submit_scope(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg006_order_place_green_path"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        broker = _PositiveBroker()
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 4, 8),
            output_dir=str(work_root / "output"),
            state_dir=str(work_root / "state"),
            qmt_userdata="",
            kill_switch_file="",
            pretrade_connect_window=1,
            pretrade_connect_interval_seconds=0.1,
            enforce_trading_session=False,
        )
        service = TradeOpsService(
            cfg,
            market_data_provider=_PositiveMarketDataProvider(),
            shadow_adapter=None,
            broker_order_adapter=broker,
            session_resolution=self._session_resolution(),
        )
        try:
            with patch.object(
                service,
                "_run_connect_gate",
                return_value={
                    "enabled": True,
                    "pass": True,
                    "reason": "ok",
                    "gate_source": "probe.connection",
                    "session_plan_version": self._session_resolution()["session_plan_version"],
                    "expected_write_session_id": "2111",
                    "expected_base_session_id": "1111",
                    "expected_effective_session_plan": self._session_resolution()["effective_session_plan"],
                    "write_authority_snapshot": {
                        "ready": True,
                        "blocking_reason": "",
                        "resolved_session_id": "2111",
                        "observed_probe_session_id": "2111",
                        "same_plan_verdict": True,
                        "probe_complete_verdict": True,
                        "fresh_connect_verified": True,
                        "write_authority_ready": True,
                        "session_plan_version": self._session_resolution()["session_plan_version"],
                        "source": "probe.connection",
                    },
                    "session_alignment": {
                        "observed_session_ids": ["2111"],
                        "all_samples_in_effective_plan": True,
                        "same_session_as_write_path": True,
                        "same_plan_verdict": True,
                        "same_plan_reason": "same_session",
                    },
                },
            ):
                result = service.place_order(
                    OrderPlaceRequest(
                        account_id="ACC001",
                        code="000001.SZ",
                        side=Side.BUY,
                        quantity=100,
                        guard_token="mcp_server_governed_write_path",
                        client_order_key="COID-TG006-GREEN",
                        intent_id="INT-TG006-GREEN",
                    )
                )
            self.assertTrue(result.ok)
            self.assertTrue(result.payload["broker_submission_attempted"])
            self.assertFalse(result.payload["local_gate_intercepted"])
            self.assertEqual(result.payload["submission_scope"], "broker_submit")
            self.assertEqual(result.payload["submission_stage"], "broker_place_order")
            self.assertEqual(result.payload["write_authority_snapshot"]["blocking_reason"], "")
            self.assertEqual(result.payload["write_authority_snapshot"]["resolved_session_id"], "2111")
            self.assertEqual(result.payload["broker_order_id"], "20001")
            self.assertEqual(broker.place_calls, 1)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_order_place_l1_protect_falls_back_to_last_price_when_quotes_missing(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg009_order_place_last_price_fallback"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        broker = _PositiveBroker()
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 4, 8),
            output_dir=str(work_root / "output"),
            state_dir=str(work_root / "state"),
            qmt_userdata="",
            kill_switch_file="",
            pretrade_connect_window=1,
            pretrade_connect_interval_seconds=0.1,
            enforce_trading_session=False,
        )
        service = TradeOpsService(
            cfg,
            market_data_provider=_LastPriceOnlyMarketDataProvider(),
            shadow_adapter=None,
            broker_order_adapter=broker,
            session_resolution=self._session_resolution(),
        )
        try:
            with patch.object(
                service,
                "_run_connect_gate",
                return_value={
                    "enabled": True,
                    "pass": True,
                    "reason": "ok",
                    "gate_source": "probe.connection",
                    "session_plan_version": self._session_resolution()["session_plan_version"],
                    "expected_write_session_id": "2111",
                    "expected_base_session_id": "1111",
                    "expected_effective_session_plan": self._session_resolution()["effective_session_plan"],
                    "write_authority_snapshot": {
                        "ready": True,
                        "blocking_reason": "",
                        "resolved_session_id": "2111",
                        "observed_probe_session_id": "2111",
                        "same_plan_verdict": True,
                        "probe_complete_verdict": True,
                        "fresh_connect_verified": True,
                        "write_authority_ready": True,
                        "session_plan_version": self._session_resolution()["session_plan_version"],
                        "source": "probe.connection",
                    },
                    "session_alignment": {
                        "observed_session_ids": ["2111"],
                        "all_samples_in_effective_plan": True,
                        "same_session_as_write_path": True,
                        "same_plan_verdict": True,
                        "same_plan_reason": "same_session",
                    },
                },
            ):
                result = service.place_order(
                    OrderPlaceRequest(
                        account_id="ACC001",
                        code="000001.SZ",
                        side=Side.BUY,
                        quantity=100,
                        guard_token="mcp_server_governed_write_path",
                        client_order_key="COID-TG009-LAST-PRICE",
                        intent_id="INT-TG009-LAST-PRICE",
                    )
                )
            self.assertTrue(result.ok)
            self.assertEqual(result.payload["effective_price_hint"], 10.0)
            self.assertEqual(result.payload["broker_order_id"], "20001")
            self.assertIsNotNone(broker.last_intent)
            self.assertEqual(float(broker.last_intent.price_hint), 10.0)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_order_cancel_respects_same_write_authority_gate_as_order_place(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg009_cancel_requires_write_authority"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        broker = _CancelBrokerRecorder()
        service, _ = self._build_service(work_root, broker_order_adapter=broker)
        try:
            with patch(
                "xtqmt_mcp.trade_ops.run_layered_user_data_precheck",
                return_value={
                    "read_only": {"ok": True, "report": {"ok": True}},
                    "write_permission": {"ok": True, "report": {"ok": True}},
                },
            ), patch("xtqmt_mcp.trade_ops._tcp_port_ready", return_value=True):
                result = service.order_cancel("12345")
            self.assertFalse(result.ok)
            self.assertEqual(result.payload["code"], "connect_gate_failed")
            self.assertFalse(result.payload["broker_submission_attempted"])
            self.assertTrue(result.payload["local_gate_intercepted"])
            self.assertEqual(result.payload["submission_scope"], "local_gate")
            self.assertEqual(result.payload["submission_stage"], "connect_gate")
            self.assertEqual(result.payload["write_authority_snapshot"]["blocking_reason"], "probe_session_differs_from_resolved_write_session")
            self.assertEqual(result.payload["connect_gate"]["gate_source"], "probe.connection")
            self.assertEqual(broker.query_calls, 0)
            self.assertEqual(broker.cancel_calls, 0)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_order_cancel_green_path_marks_broker_cancel_scope(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg009_cancel_green_path"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        broker = _PositiveBroker()
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 4, 8),
            output_dir=str(work_root / "output"),
            state_dir=str(work_root / "state"),
            qmt_userdata="",
            kill_switch_file="",
            pretrade_connect_window=1,
            pretrade_connect_interval_seconds=0.1,
            enforce_trading_session=False,
        )
        service = TradeOpsService(
            cfg,
            market_data_provider=_PositiveMarketDataProvider(),
            shadow_adapter=None,
            broker_order_adapter=broker,
            session_resolution=self._session_resolution(),
        )
        try:
            with patch.object(
                service,
                "_run_connect_gate",
                return_value={
                    "enabled": True,
                    "pass": True,
                    "reason": "ok",
                    "gate_source": "probe.connection",
                    "session_plan_version": self._session_resolution()["session_plan_version"],
                    "expected_write_session_id": "2111",
                    "expected_base_session_id": "1111",
                    "expected_effective_session_plan": self._session_resolution()["effective_session_plan"],
                    "write_authority_snapshot": {
                        "ready": True,
                        "blocking_reason": "",
                        "resolved_session_id": "2111",
                        "observed_probe_session_id": "2111",
                        "same_plan_verdict": True,
                        "probe_complete_verdict": True,
                        "fresh_connect_verified": True,
                        "write_authority_ready": True,
                        "session_plan_version": self._session_resolution()["session_plan_version"],
                        "source": "probe.connection",
                    },
                    "session_alignment": {
                        "observed_session_ids": ["2111"],
                        "all_samples_in_effective_plan": True,
                        "same_session_as_write_path": True,
                        "same_plan_verdict": True,
                        "same_plan_reason": "same_session",
                    },
                },
            ):
                result = service.order_cancel("20001")
            self.assertTrue(result.ok)
            self.assertTrue(result.payload["broker_submission_attempted"])
            self.assertFalse(result.payload["local_gate_intercepted"])
            self.assertEqual(result.payload["submission_scope"], "broker_cancel")
            self.assertEqual(result.payload["submission_stage"], "broker_cancel_order")
            self.assertEqual(result.payload["write_authority_snapshot"]["blocking_reason"], "")
            self.assertEqual(broker.query_calls, 1)
            self.assertEqual(broker.cancel_calls, 1)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
