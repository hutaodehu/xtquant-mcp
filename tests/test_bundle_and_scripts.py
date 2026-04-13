from __future__ import annotations

from pathlib import Path
import runpy
import sys
import shutil
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.bundle import validate_xtquant_bundle
from xtqmt_mcp.settings import XtquantBundleConfig


TEST_TMP_ROOT = ROOT / ".tmp" / "tests"
TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)


class _WorkspaceTempDir:
    def __init__(self) -> None:
        self.path = TEST_TMP_ROOT / f"case_{uuid.uuid4().hex}"

    def __enter__(self) -> str:
        self.path.mkdir(parents=True, exist_ok=False)
        return str(self.path)

    def __exit__(self, exc_type, exc, tb) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


class BundleAndScriptTests(unittest.TestCase):
    def test_validate_bundle_missing_files(self) -> None:
        with _WorkspaceTempDir() as temp_dir:
            cfg = XtquantBundleConfig(bundle_root=temp_dir, abi_tag="cp313-win_amd64")
            result = validate_xtquant_bundle(cfg)
            self.assertFalse(result.ok)
            self.assertGreaterEqual(len(result.missing_files), 1)

    def test_runner_scripts_import(self) -> None:
        for relative_path in (
            "scripts/run_trade_gateway_http.py",
            "scripts/run_data_gateway_http.py",
            "scripts/verify_xtquant_bundle.py",
        ):
            globals_dict = runpy.run_path(str(ROOT / relative_path))
            self.assertIn("main", globals_dict)


if __name__ == "__main__":
    unittest.main()
