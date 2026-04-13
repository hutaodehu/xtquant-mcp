from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.data_gateway.config import load_data_gateway_config


class DataGatewayConfigTests(unittest.TestCase):
    def test_load_example_config(self) -> None:
        cfg = load_data_gateway_config(ROOT / "configs" / "data_gateway.example.yaml")
        self.assertEqual(cfg.identity.server_name, "xtqmtDataGateway")
        self.assertEqual(cfg.transport.bind_port, 8766)
        self.assertEqual(cfg.bundle.bundle_root, r"D:\xtquant-mcp\vendor\xtquant_250807")
        self.assertEqual(cfg.service.max_concurrent_jobs, 1)
        self.assertEqual(cfg.qmt.xtdata_port, 58610)


if __name__ == "__main__":
    unittest.main()
