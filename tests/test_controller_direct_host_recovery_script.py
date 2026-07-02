from __future__ import annotations

from io import BytesIO, TextIOWrapper
from pathlib import Path
import importlib.util
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "controller_direct_host_recovery.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("controller_direct_host_recovery_script", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load controller_direct_host_recovery.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ControllerDirectHostRecoveryScriptTests(unittest.TestCase):
    def test_main_reconfigures_stdout_for_non_ascii_paths(self) -> None:
        module = _load_script_module()
        root = Path(tempfile.mkdtemp(prefix="国金证券QMT交易端_", dir="/tmp"))
        try:
            (root / "down_queue_win_2101").write_text("", encoding="utf-8")
            original_stdout = sys.stdout
            capture = TextIOWrapper(BytesIO(), encoding="ascii", errors="strict")
            sys.stdout = capture
            try:
                exit_code = module.main(
                    [
                        "inspect",
                        "--user-data-path",
                        str(root),
                        "--sessions",
                        "2101",
                    ]
                )
                capture.flush()
            finally:
                sys.stdout = original_stdout

            output = capture.buffer.getvalue().decode("utf-8")
            self.assertEqual(exit_code, 0)
            self.assertIn("国金证券QMT交易端_", output)
            self.assertIn("down_queue_win_2101", output)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
