from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.config_utils import load_yaml_payload
from xtqmt_mcp.data_gateway.config import DEFAULT_TOOL_NAMES, load_data_gateway_config


class DataGatewayConfigTests(unittest.TestCase):
    def test_load_example_config(self) -> None:
        cfg = load_data_gateway_config(ROOT / "configs" / "data_gateway.example.yaml")
        self.assertEqual(cfg.identity.server_name, "xtqmtDataGateway")
        self.assertEqual(cfg.transport.bind_port, 8766)
        self.assertEqual(cfg.bundle.bundle_root, r"C:\xtquant-mcp-example\vendor\xtquant_250807")
        self.assertEqual(cfg.service.max_concurrent_jobs, 1)
        self.assertEqual(cfg.qmt.xtdata_port, 0)
        self.assertEqual(cfg.enabled_tools, DEFAULT_TOOL_NAMES)
        self.assertEqual(cfg.service.plans_root, r"C:\xtquant-mcp-example\instance\prod\artifacts\data_plans")
        self.assertEqual(cfg.service.cache_root, r"C:\xtquant-mcp-example\instance\prod\artifacts\data_cache")
        self.assertEqual(cfg.service.metadata_path, r"C:\xtquant-mcp-example\instance\prod\artifacts\data_cache\integrity_state.json")
        self.assertEqual(cfg.service.windows_qlib_root, r"C:\xtquant-mcp-example\qlib_data\xtdata_export_local")
        self.assertEqual(cfg.service.wsl_qlib_root, "/opt/xtquant-mcp-example/qlib_data/xtdata_export_local")
        self.assertEqual(cfg.service.wsl_distro_name, "")
        self.assertEqual(cfg.service.stale_job_seconds, 300)

    def test_example_config_explicitly_pins_modern_schema_fields(self) -> None:
        payload = load_yaml_payload(ROOT / "configs" / "data_gateway.example.yaml", required=True)
        server_payload = payload.get("server") or {}
        data_payload = payload.get("data") or {}

        self.assertEqual(tuple(server_payload.get("enabled_tools") or ()), DEFAULT_TOOL_NAMES)
        self.assertIn("plans_root", data_payload)
        self.assertIn("cache_root", data_payload)
        self.assertIn("metadata_path", data_payload)
        self.assertIn("windows_qlib_root", data_payload)
        self.assertIn("wsl_qlib_root", data_payload)
        self.assertIn("wsl_distro_name", data_payload)
        self.assertIn("stale_job_seconds", data_payload)
        self.assertNotEqual((payload.get("qmt") or {}).get("xtdata_port"), 58610)


if __name__ == "__main__":
    unittest.main()
