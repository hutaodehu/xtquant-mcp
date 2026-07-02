from __future__ import annotations

from datetime import date
from pathlib import Path
import shutil
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.broker_order import DryRunBrokerOrderAdapter
from xtqmt_mcp.trade_gateway.fills import list_fills
from xtqmt_mcp.trade_ops import TradeOpsConfig, TradeOpsService
from xtqmt_mcp.types import OrderPlaceRequest, Side


class TradeFlowSmokeTests(unittest.TestCase):
    def _build_service(self, root: Path) -> TradeOpsService:
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 4, 8),
            output_dir=str(root / "output"),
            state_dir=str(root / "state"),
            execution_mode="flow_smoke",
        )
        return TradeOpsService(
            cfg,
            market_data_provider=object(),
            shadow_adapter=None,
            broker_order_adapter=DryRunBrokerOrderAdapter(),
            session_resolution={
                "configured_session_id": 1111,
                "resolved_base_session_id": 1111,
                "resolved_session_id": 1111,
                "configured_session_candidates": [1111],
                "effective_session_plan": [1111],
                "derived_session_fallback_enabled": False,
                "max_session_attempts": 1,
                "explicit_session_resolution_applied": False,
            },
        )

    def test_flow_smoke_warm_health_orders_list_succeeds_without_shadow(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "flow_smoke_warm_health"
        shutil.rmtree(work_root, ignore_errors=True)
        service = self._build_service(work_root)
        try:
            result = service.warm_health_orders_list()
            self.assertTrue(result.ok)
            self.assertEqual(result.payload["count"], 0)
            self.assertEqual(result.payload["execution_mode"], "flow_smoke")
            self.assertEqual(result.payload["truth_scope"], "flow_smoke_local")
            self.assertFalse(result.payload["broker_truth_confirmed"])
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_flow_smoke_fixed_price_order_lifecycle_runs_end_to_end(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "flow_smoke_lifecycle"
        shutil.rmtree(work_root, ignore_errors=True)
        service = self._build_service(work_root)
        try:
            placed = service.place_order(
                OrderPlaceRequest(
                    account_id="ACC001",
                    code="SAMPLE001.SH",
                    side=Side.BUY,
                    quantity=100,
                    guard_token="mcp_server_governed_write_path",
                    price_mode="fixed",
                    limit_price=1.23,
                    client_order_key="COID-FLOW-SMOKE-001",
                    intent_id="INT-FLOW-SMOKE-001",
                )
            )
            self.assertTrue(placed.ok)
            self.assertEqual(placed.payload["execution_mode"], "flow_smoke")
            self.assertEqual(placed.payload["submission_scope"], "flow_smoke")
            self.assertFalse(placed.payload["broker_submission_attempted"])
            broker_order_id = placed.payload["broker_order_id"]
            self.assertTrue(str(broker_order_id).isdigit())

            status_before_cancel = service.order_status(broker_order_id)
            self.assertTrue(status_before_cancel.ok)
            self.assertEqual(status_before_cancel.payload["status"], "submitted")
            self.assertFalse(status_before_cancel.payload["terminal"])

            open_orders = service.orders_list()
            self.assertTrue(open_orders.ok)
            self.assertEqual(open_orders.payload["count"], 1)
            self.assertEqual(open_orders.payload["execution_mode"], "flow_smoke")
            self.assertEqual(open_orders.payload["truth_scope"], "flow_smoke_local")
            self.assertFalse(open_orders.payload["broker_truth_confirmed"])

            fills = list_fills(service, trading_day=date(2026, 4, 8), broker_order_id=broker_order_id)
            self.assertTrue(fills.ok)
            self.assertEqual(fills.payload["row_count"], 0)

            canceled = service.order_cancel(broker_order_id)
            self.assertTrue(canceled.ok)
            self.assertEqual(canceled.payload["status"], "canceled")

            status_after_cancel = service.order_status(broker_order_id)
            self.assertTrue(status_after_cancel.ok)
            self.assertEqual(status_after_cancel.payload["status"], "canceled")
            self.assertTrue(status_after_cancel.payload["terminal"])

            open_orders_after_cancel = service.orders_list()
            self.assertTrue(open_orders_after_cancel.ok)
            self.assertEqual(open_orders_after_cancel.payload["count"], 0)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
