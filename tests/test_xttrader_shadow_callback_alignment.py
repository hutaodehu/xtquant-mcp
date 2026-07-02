from __future__ import annotations

from pathlib import Path
import shutil
import sys
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "pandas" not in sys.modules:
    pandas_stub = types.ModuleType("pandas")
    pandas_stub.DataFrame = lambda rows=None: rows
    sys.modules["pandas"] = pandas_stub

from xtqmt_mcp.adapters.xttrader_shadow import XtTraderShadowAdapter, XtTraderShadowConfig


class _ConstructorCallbackTrader:
    instances: list["_ConstructorCallbackTrader"] = []

    def __init__(self, user_data_path: str, session_id: int, callback=None) -> None:
        self.user_data_path = user_data_path
        self.session_id = session_id
        self.callback = callback
        self.started = False
        self.subscribed = False
        _ConstructorCallbackTrader.instances.append(self)

    def register_callback(self, callback) -> None:
        self.callback = callback

    def start(self) -> None:
        self.started = True

    def connect(self) -> int:
        return 0 if self.callback is not None else -1

    def subscribe(self, _account) -> int:
        self.subscribed = True
        return 0

    def unsubscribe(self, _account) -> None:
        return None

    def stop(self) -> None:
        return None


class _FakeStockAccount:
    def __init__(self, account_id: str, account_type: str = "STOCK") -> None:
        self.account_id = account_id
        self.account_type = account_type


class XtTraderShadowCallbackAlignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work_root = Path("/tmp") / "xtquant_mcp_shadow_callback_alignment"
        shutil.rmtree(self.work_root, ignore_errors=True)
        self.work_root.mkdir(parents=True, exist_ok=True)
        (self.work_root / "up_queue_xtquant").write_text("", encoding="utf-8")
        _ConstructorCallbackTrader.instances.clear()

    def tearDown(self) -> None:
        shutil.rmtree(self.work_root, ignore_errors=True)
        _ConstructorCallbackTrader.instances.clear()

    def test_connect_uses_constructor_callback_when_available(self) -> None:
        xttrader_module = types.ModuleType("xtquant.xttrader")
        xttrader_module.XtQuantTrader = _ConstructorCallbackTrader
        xttrader_module.XtQuantTraderCallback = type("XtQuantTraderCallback", (), {})

        xttype_module = types.ModuleType("xtquant.xttype")
        xttype_module.StockAccount = _FakeStockAccount

        xtquant_package = types.ModuleType("xtquant")
        xtquant_package.xttrader = xttrader_module
        xtquant_package.xttype = xttype_module

        adapter = XtTraderShadowAdapter(
            XtTraderShadowConfig(
                user_data_path=str(self.work_root),
                account_id="ACC001",
                session_id=2101,
                session_candidates=(2101,),
                register_callback=True,
                connect_retries=1,
                connect_retry_interval_seconds=0,
                connect_cooldown_seconds=0,
                require_up_queue_file=True,
                max_session_attempts=1,
            )
        )

        with mock.patch.dict(
            sys.modules,
            {
                "xtquant": xtquant_package,
                "xtquant.xttrader": xttrader_module,
                "xtquant.xttype": xttype_module,
            },
        ), mock.patch("xtqmt_mcp.adapters.xttrader_shadow.ensure_xtquant_on_path", lambda: None):
            adapter.connect()

        self.assertTrue(adapter._connected)
        self.assertEqual(adapter.active_session_id(), 2101)
        self.assertEqual(len(_ConstructorCallbackTrader.instances), 1)
        self.assertIsNotNone(_ConstructorCallbackTrader.instances[0].callback)


if __name__ == "__main__":
    unittest.main()
