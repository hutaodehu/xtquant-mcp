from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.trade_gateway.config import load_trade_gateway_config


class TradeGatewayConfigTests(unittest.TestCase):
    def test_load_example_config(self) -> None:
        cfg = load_trade_gateway_config(ROOT / "configs" / "trade_gateway.example.yaml")
        self.assertEqual(cfg.identity.server_name, "xtqmtTradeGateway")
        self.assertEqual(cfg.transport.bind_port, 8765)
        self.assertEqual(cfg.bundle.bundle_root, r"D:\xtquant-mcp\vendor\xtquant_250807")
        self.assertTrue(cfg.trade_ops.auto_account)
        self.assertEqual(cfg.login.port_num, 58610)
        self.assertEqual(cfg.trade_ops.kill_switch_file, r"D:\xtquant-mcp\instance\prod\control\trade_kill_switch.flag")


if __name__ == "__main__":
    unittest.main()
