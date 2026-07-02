from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from xtqmt_mcp.trade_gateway.fills import list_fills


class _ShadowWithTradedOrderFallback:
    def get_trades(self) -> list[dict[str, object]]:
        return []

    def get_orders(self) -> list[dict[str, object]]:
        return [
            {
                "account_id": "ACC001",
                "order_id": "broker-001",
                "stock_code": "000001.SZ",
                "order_type": 24,
                "traded_volume": 100,
                "traded_price": 1.234,
                "traded_time": "2026-05-12T10:00:00",
                "client_order_key": "cok-001",
                "intent_id": "intent-001",
            }
        ]


def test_fills_list_uses_broker_order_traded_volume_fallback(tmp_path) -> None:
    service = SimpleNamespace(
        cfg=SimpleNamespace(
            account_id="ACC001",
            output_dir=tmp_path / "output",
            state_dir=tmp_path / "state",
        ),
        shadow=_ShadowWithTradedOrderFallback(),
    )

    result = list_fills(
        service,
        trading_day=date(2026, 5, 12),
        broker_order_id="broker-001",
    )
    payload = result.payload

    assert result.ok is True
    assert payload["row_count"] == 1
    assert payload["source"] == "broker_order_traded_volume"
    assert payload["broker_attempted"] is True
    assert payload["broker_row_count"] == 0
    assert payload["local_row_count"] == 0
    assert payload["fallback_used"] is True
    row = payload["rows"][0]
    assert row["trade_id"] == "broker_order_traded_volume:broker-001"
    assert row["broker_order_id"] == "broker-001"
    assert row["client_order_key"] == "cok-001"
    assert row["intent_id"] == "intent-001"
    assert row["code"] == "000001.SZ"
    assert row["side"] == "24"
    assert row["traded_volume"] == 100
    assert row["traded_price"] == 1.234
    assert row["source"] == "broker_order_traded_volume"
