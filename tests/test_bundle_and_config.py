from __future__ import annotations

from pathlib import Path
import shutil
import unittest
import uuid

from xtqmt_mcp.bundle import validate_xtquant_bundle, write_vendor_pth
from xtqmt_mcp.trade_gateway.config import load_trade_gateway_config
from xtqmt_mcp.data_gateway.config import load_data_gateway_config
from xtqmt_mcp.settings import XtquantBundleConfig


ROOT = Path(__file__).resolve().parents[1]
_TEMP_ROOT = ROOT / ".tmp" / "tests"
_TEMP_ROOT.mkdir(parents=True, exist_ok=True)


class _WorkspaceTempDir:
    def __init__(self) -> None:
        self.path = _TEMP_ROOT / f"case_{uuid.uuid4().hex}"

    def __enter__(self) -> str:
        self.path.mkdir(parents=True, exist_ok=False)
        return str(self.path)

    def __exit__(self, exc_type, exc, tb) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


class BundleAndConfigTests(unittest.TestCase):
    def test_validate_bundle_and_write_pth(self) -> None:
        with _WorkspaceTempDir() as tmp:
            root = Path(tmp)
            package_root = root / "xtquant"
            package_root.mkdir(parents=True)
            for name in (
                "xtpythonclient.cp313-win_amd64.pyd",
                "datacenter.cp313-win_amd64.pyd",
                "datacenter_shared.dll",
            ):
                (package_root / name).write_text("", encoding="utf-8")

            cfg = XtquantBundleConfig(bundle_root=str(root), abi_tag="cp313-win_amd64")
            result = validate_xtquant_bundle(cfg)
            self.assertTrue(result.ok)
            self.assertEqual(result.package_root, str(package_root))

            site_packages = root / "site-packages"
            pth_path = write_vendor_pth(cfg, site_packages)
            self.assertEqual(pth_path.read_text(encoding="utf-8").strip(), str(root))

    def test_load_trade_gateway_config(self) -> None:
        with _WorkspaceTempDir() as tmp:
            root = Path(tmp)
            config_path = root / "trade.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "server:",
                        "  server_name: customTrade",
                        "runtime:",
                        "  python_home: C:\\Python313\\python.exe",
                        "  venv_path: D:\\xtquant-mcp\\venv313",
                        "bundle:",
                        "  bundle_root: D:\\xtquant-mcp\\vendor\\xtquant_250807",
                        "transport:",
                        "  bind_port: 9001",
                        "qmt:",
                        "  qmt_exe: D:\\QMT\\XtMiniQmt.exe",
                        "trade:",
                        "  account_id: ACC001",
                        "  output_dir: D:\\xtquant-mcp\\instance\\prod\\artifacts\\trade_ops",
                        "login:",
                        "  credential_target: xtqmt/miniqmt/default",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            cfg = load_trade_gateway_config(config_path)
            self.assertEqual(cfg.identity.server_name, "customTrade")
            self.assertEqual(cfg.transport.bind_port, 9001)
            self.assertEqual(cfg.qmt.qmt_exe, r"D:\QMT\XtMiniQmt.exe")
            self.assertEqual(cfg.trade_ops.account_id, "ACC001")
            self.assertEqual(cfg.login.credential_target, "xtqmt/miniqmt/default")

    def test_load_data_gateway_config(self) -> None:
        with _WorkspaceTempDir() as tmp:
            root = Path(tmp)
            config_path = root / "data.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "server:",
                        "  server_name: customData",
                        "bundle:",
                        "  bundle_root: D:\\xtquant-mcp\\vendor\\xtquant_250807",
                        "transport:",
                        "  bind_port: 9002",
                        "data:",
                        "  jobs_root: D:\\xtquant-mcp\\instance\\prod\\state\\data_jobs",
                        "  subscriptions_root: D:\\xtquant-mcp\\instance\\prod\\state\\subscriptions",
                        "  max_concurrent_jobs: 2",
                        "  max_query_symbols: 50",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            cfg = load_data_gateway_config(config_path)
            self.assertEqual(cfg.identity.server_name, "customData")
            self.assertEqual(cfg.transport.bind_port, 9002)
            self.assertEqual(cfg.service.max_concurrent_jobs, 2)
            self.assertEqual(cfg.service.max_query_symbols, 50)


if __name__ == "__main__":
    unittest.main()
