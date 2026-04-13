from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import shutil
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.trade_ops import TradeOpsConfig, TradeOpsService


class _FakeShadow:
    def __init__(self) -> None:
        self.calls = 0

    def get_orders(self) -> list[dict[str, object]]:
        self.calls += 1
        return [
            {
                "account_id": "ACC001",
                "order_id": "20001",
                "stock_code": "000001.SZ",
                "order_type": "23",
                "order_volume": 100,
                "price": 12.34,
                "order_status": "submitted",
                "status_msg": "shadow-order-ok",
            }
        ]

    def probe_live_readiness(self, *, snapshot_requires_position: bool = False) -> dict[str, object]:
        return {
            "available": True,
            "reused_session": True,
            "ok": True,
            "reason": "",
            "account_id": "ACC001",
            "session_id": "100",
            "source": "xttrader_shadow",
            "snapshot_requires_position": bool(snapshot_requires_position),
        }

    def close(self) -> None:
        return None


class _FakeSide:
    value = "buy"


class _FakeBrokerOrderRow:
    def __init__(self) -> None:
        self.ts = datetime(2026, 3, 30, 11, 56, 45)
        self.account_id = "ACC001"
        self.broker_order_id = "B-9001"
        self.code = "000001.SZ"
        self.side = _FakeSide()
        self.quantity = 200
        self.status = "open"
        self.message = "broker-order-ok"
        self.price_hint = 9.87


class _FakeBroker:
    def __init__(self, *, fail_connect: bool = False) -> None:
        self.query_calls = 0
        self.fail_connect = fail_connect
        self._connected = False

    def query_open_orders(self, account_id: str) -> list[_FakeBrokerOrderRow]:
        self.query_calls += 1
        if self.fail_connect:
            raise RuntimeError("xttrader connect failed: -1 after 3 attempts (session_plan=[100,101,111])")
        self._connected = True
        return [_FakeBrokerOrderRow()]

    def close(self) -> None:
        return None


class TradeOpsWarmHealthTests(unittest.TestCase):
    def _build_service(
        self,
        root: Path,
        *,
        fail_broker_connect: bool = False,
        include_shadow: bool = True,
        include_broker: bool = True,
    ) -> tuple[TradeOpsService, _FakeShadow | None, _FakeBroker | None]:
        shadow = _FakeShadow() if include_shadow else None
        broker = _FakeBroker(fail_connect=fail_broker_connect) if include_broker else None
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 3, 30),
            output_dir=str(root / "output"),
            state_dir=str(root / "state"),
        )
        service = TradeOpsService(
            cfg,
            market_data_provider=object(),
            shadow_adapter=shadow,
            broker_order_adapter=broker,
        )
        return service, shadow, broker

    def test_warm_health_orders_list_uses_shadow_without_broker(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg004_warm_health_shadow_only"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        service, shadow, broker = self._build_service(work_root)
        try:
            result = service.warm_health_orders_list()
            self.assertTrue(result.ok)
            self.assertEqual(broker.query_calls, 0)
            self.assertEqual(shadow.calls, 1)
            self.assertEqual(result.payload["source"], "xttrader_shadow")
            self.assertEqual(result.payload["read_scope"], "warm_health_only")
            self.assertEqual(result.payload["truth_scope"], "shadow_warm_health")
            self.assertFalse(result.payload["broker_truth_confirmed"])
            self.assertEqual(result.payload["count"], 1)
            self.assertEqual(result.payload["rows"][0]["broker_order_id"], "20001")
            self.assertEqual(result.payload["rows"][0]["code"], "000001.SZ")
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_public_orders_list_still_uses_broker_adapter(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg004_public_orders_broker"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        service, shadow, broker = self._build_service(work_root)
        try:
            result = service.orders_list()
            self.assertTrue(result.ok)
            self.assertEqual(shadow.calls, 0)
            self.assertEqual(broker.query_calls, 1)
            self.assertEqual(result.payload["source"], "broker")
            self.assertFalse(result.payload["degraded"])
            self.assertFalse(result.payload["fallback_used"])
            self.assertEqual(result.payload["truth_scope"], "broker_truth")
            self.assertTrue(result.payload["broker_truth_confirmed"])
            self.assertTrue(result.payload["broker_read"]["ok"])
            self.assertTrue(result.payload["broker_read"]["fresh_connect_attempted"])
            self.assertTrue(result.payload["broker_read"]["fresh_connect_ok"])
            self.assertEqual(result.payload["count"], 1)
            self.assertEqual(result.payload["rows"][0]["broker_order_id"], "B-9001")
            self.assertEqual(result.payload["rows"][0]["code"], "000001.SZ")
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_public_orders_list_falls_back_when_broker_adapter_is_missing(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg005_public_orders_broker_missing_shadow_fallback"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        service, shadow, broker = self._build_service(work_root, include_broker=False)
        try:
            result = service.orders_list()
            self.assertTrue(result.ok)
            self.assertIsNone(broker)
            assert shadow is not None
            self.assertEqual(shadow.calls, 1)
            self.assertEqual(result.payload["source"], "active_owner_shadow")
            self.assertEqual(result.payload["read_scope"], "public_fallback")
            self.assertTrue(result.payload["degraded"])
            self.assertTrue(result.payload["fallback_used"])
            self.assertEqual(result.payload["truth_scope"], "shadow_fallback")
            self.assertFalse(result.payload["broker_truth_confirmed"])
            self.assertEqual(result.payload["fallback_reason"], "broker_missing")
            self.assertEqual(result.payload["broker_read"]["error"], "broker_adapter_missing")
            self.assertNotEqual(result.payload["read_scope"], "warm_health_only")
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_public_orders_list_explicitly_falls_back_to_live_owner_shadow_when_broker_connect_fails(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg004_public_orders_shadow_fallback"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        service, shadow, broker = self._build_service(work_root, fail_broker_connect=True)
        try:
            result = service.orders_list()
            self.assertTrue(result.ok)
            self.assertEqual(broker.query_calls, 1)
            self.assertEqual(shadow.calls, 1)
            self.assertEqual(result.payload["source"], "active_owner_shadow")
            self.assertEqual(result.payload["read_scope"], "public_fallback")
            self.assertTrue(result.payload["degraded"])
            self.assertTrue(result.payload["fallback_used"])
            self.assertEqual(result.payload["truth_scope"], "shadow_fallback")
            self.assertFalse(result.payload["broker_truth_confirmed"])
            self.assertEqual(result.payload["fallback_reason"], "broker_connect_failed")
            self.assertIn("broker connect failed", result.payload["message"])
            self.assertFalse(result.payload["broker_read"]["ok"])
            self.assertTrue(result.payload["broker_read"]["fresh_connect_attempted"])
            self.assertFalse(result.payload["broker_read"]["fresh_connect_ok"])
            self.assertIn("xttrader connect failed: -1", result.payload["broker_read"]["error"])
            self.assertTrue(result.payload["shadow_fallback"]["used"])
            self.assertTrue(result.payload["shadow_fallback"]["reused_session"])
            self.assertEqual(result.payload["shadow_fallback"]["source"], "active_owner_shadow")
            self.assertEqual(result.payload["rows"][0]["broker_order_id"], "20001")
            self.assertEqual(result.payload["rows"][0]["code"], "000001.SZ")
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_public_orders_list_returns_machine_readable_fail_design_when_broker_and_shadow_are_missing(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg005_public_orders_broker_missing_no_shadow"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        service, shadow, broker = self._build_service(work_root, include_shadow=False, include_broker=False)
        try:
            result = service.orders_list()
            self.assertFalse(result.ok)
            self.assertIsNone(shadow)
            self.assertIsNone(broker)
            self.assertEqual(result.payload["code"], "orders_list_broker_missing")
            self.assertEqual(result.payload["error"], "orders_list_broker_missing")
            self.assertEqual(result.payload["failure_classification"], "fail_design")
            self.assertEqual(result.payload["source"], "broker_unavailable")
            self.assertEqual(result.payload["read_scope"], "public_broker")
            self.assertFalse(result.payload["fallback_used"])
            self.assertEqual(result.payload["truth_scope"], "broker_unavailable")
            self.assertFalse(result.payload["broker_truth_confirmed"])
            self.assertEqual(result.payload["shadow_fallback_reason"], "shadow_unavailable")
            self.assertIn("broker adapter is missing", result.payload["message"])
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
