from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datetime import date
from unittest.mock import patch

from xtqmt_mcp.market_data import _query_tick_payload, XtQuantMarketDataProvider
from xtqmt_mcp.policy import DataPolicy
from xtqmt_mcp.types import DataOrigin


class _FakeXtData:
    def __init__(self) -> None:
        self.field_list: list[str] = []

    def get_market_data(self, *, field_list, stock_list, period, start_time, end_time, count, dividend_type, fill_data):
        del stock_list, period, start_time, end_time, count, dividend_type, fill_data
        self.field_list = list(field_list)
        return {"000001.SZ": [{"lastPrice": 1.0, "bidPrice": [0.999], "askPrice": [1.001], "time": "20260525130000"}]}


class MarketDataTickPayloadTests(unittest.TestCase):
    def test_tick_payload_queries_book_fields_for_l1_pricing(self) -> None:
        fake = _FakeXtData()

        payload = _query_tick_payload(fake, "000001.SZ", "20260525")

        self.assertEqual(payload[0]["lastPrice"], 1.0)
        self.assertIn("bidPrice", fake.field_list)
        self.assertIn("askPrice", fake.field_list)

    def test_get_full_tick_fallback_is_labeled_and_preserves_five_level_book(self) -> None:
        class _FallbackXtData:
            def get_market_data(
                self,
                *,
                field_list,
                stock_list,
                period,
                start_time,
                end_time,
                count,
                dividend_type,
                fill_data,
            ):
                del field_list, stock_list, period, start_time, end_time, count, dividend_type, fill_data
                return {"000001.SZ": []}

            def get_full_tick(self, code_list):
                self.code_list = list(code_list)
                return {
                    "000001.SZ": {
                        "lastPrice": 1.795,
                        "lastClose": 1.790,
                        "time": "20260624130739000",
                        "bidPrice": [1.795, 1.794, 1.793, 1.792, 1.791],
                        "askPrice": [1.796, 1.797, 1.798, 1.799, 1.800],
                    }
                }

        xtdata = _FallbackXtData()
        provider = XtQuantMarketDataProvider(DataPolicy())

        with patch("xtqmt_mcp.market_data._require_xtdata", return_value=xtdata):
            event = provider.latest_online_event("000001.SZ", date(2026, 6, 24), "tick")

        self.assertIsNotNone(event)
        self.assertEqual(event.source, DataOrigin.GET_FULL_TICK)
        self.assertEqual(event.bid1, 1.795)
        self.assertEqual(event.bid5, 1.791)
        self.assertEqual(event.ask1, 1.796)
        self.assertEqual(event.ask5, 1.800)

    def test_get_full_tick_is_preferred_over_tick_cache_for_no_fill_l1(self) -> None:
        class _PreferredXtData:
            def subscribe_quote(self, *args, **kwargs):
                del args, kwargs
                return 1

            def unsubscribe_quote(self, seq):
                self.unsubscribed = seq

            def get_market_data(
                self,
                *,
                field_list,
                stock_list,
                period,
                start_time,
                end_time,
                count,
                dividend_type,
                fill_data,
            ):
                del field_list, stock_list, period, start_time, end_time, count, dividend_type, fill_data
                return {
                    "000001.SZ": [
                        {
                            "lastPrice": 1.700,
                            "lastClose": 1.690,
                            "time": "20260624130730000",
                            "bidPrice": [1.700, 1.699, 1.698, 1.697, 1.696],
                            "askPrice": [1.701, 1.702, 1.703, 1.704, 1.705],
                        }
                    ]
                }

            def get_full_tick(self, code_list):
                self.code_list = list(code_list)
                return {
                    "000001.SZ": {
                        "lastPrice": 1.810,
                        "lastClose": 1.790,
                        "time": "20260624132203000",
                        "bidPrice": [1.810, 1.809, 1.808, 1.807, 1.806],
                        "askPrice": [1.811, 1.812, 1.813, 1.814, 1.815],
                    }
                }

        xtdata = _PreferredXtData()
        provider = XtQuantMarketDataProvider(DataPolicy())

        with patch("xtqmt_mcp.market_data._require_xtdata", return_value=xtdata):
            event = provider.latest_online_event("000001.SZ", date(2026, 6, 24), "tick")

        self.assertIsNotNone(event)
        self.assertEqual(event.source, DataOrigin.GET_FULL_TICK)
        self.assertEqual(event.last_price, 1.810)
        self.assertEqual(event.bid5, 1.806)
        self.assertEqual(event.ask5, 1.815)


if __name__ == "__main__":
    unittest.main()
