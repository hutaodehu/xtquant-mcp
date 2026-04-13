from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.miniqmt_login import desktop_harness
from xtqmt_mcp.miniqmt_login.desktop_harness import WindowDescriptor, WindowsDesktopHarness


class _EmptyDesktop:
    def windows(self, process: int, visible_only: bool = False):
        return []


class MiniQmtDesktopHarnessTests(unittest.TestCase):
    def test_observe_uses_host_window_fallback_when_pywinauto_returns_none(self) -> None:
        harness = WindowsDesktopHarness(screenshot_dir=str(ROOT / "instance" / "test_tmp" / "miniqmt_harness"))
        host_window = WindowDescriptor(
            handle=101,
            process_id=4321,
            title="XtMiniQMT 交易端",
            class_name="Afx:400000:8:10011:0:0",
            controls=(),
            visible=True,
            enabled=True,
        )
        with (
            patch.object(desktop_harness, "Desktop", object()),
            patch.object(WindowsDesktopHarness, "_desktop", return_value=_EmptyDesktop()),
            patch.object(WindowsDesktopHarness, "list_process_ids", return_value=(4321,)),
            patch.object(WindowsDesktopHarness, "port_ready", return_value=False),
            patch.object(WindowsDesktopHarness, "is_interactive_desktop", return_value=True),
            patch.object(WindowsDesktopHarness, "_host_window_descriptors", return_value=[host_window]),
            patch.object(WindowsDesktopHarness, "capture_screenshot_details", return_value=("C:\\temp\\miniqmt_host.png", True, "")),
        ):
            observation = harness.observe()

        self.assertFalse(observation.login_window_found)
        self.assertTrue(observation.main_window_found)
        self.assertEqual(observation.window_handle, 101)
        self.assertEqual(observation.window_title, "XtMiniQMT 交易端")
        self.assertEqual(observation.window_titles, ("XtMiniQMT 交易端",))
        self.assertEqual(observation.screenshot_path, "C:\\temp\\miniqmt_host.png")
        self.assertTrue(observation.evidence["interactive_desktop"])
        self.assertEqual(observation.evidence["pywinauto_window_count"], 0)
        self.assertTrue(observation.evidence["host_window_fallback_used"])
        self.assertEqual(
            observation.evidence["host_visible_windows"],
            [
                {
                    "handle": 101,
                    "process_id": 4321,
                    "title": "XtMiniQMT 交易端",
                    "class_name": "Afx:400000:8:10011:0:0",
                    "visible": True,
                    "enabled": True,
                }
            ],
        )
        self.assertEqual(observation.evidence["selected_main_title"], "XtMiniQMT 交易端")
        self.assertEqual(observation.evidence["selected_login_title"], "")
        self.assertEqual(len(observation.evidence["window_classifications"]), 1)
        self.assertIn("class=Afx:400000:8:10011:0:0", observation.evidence["window_classifications"][0])
        self.assertTrue(observation.evidence["screenshot_capture_attempted"])
        self.assertEqual(observation.evidence["screenshot_capture_error"], "")

    def test_observe_reports_screenshot_failure_in_evidence(self) -> None:
        harness = WindowsDesktopHarness(screenshot_dir=str(ROOT / "instance" / "test_tmp" / "miniqmt_harness"))
        host_window = WindowDescriptor(
            handle=202,
            process_id=9876,
            title="XtMiniQMT 交易端",
            class_name="Qt5152QWindowIcon",
            controls=(),
            visible=True,
            enabled=True,
        )
        with (
            patch.object(desktop_harness, "Desktop", object()),
            patch.object(WindowsDesktopHarness, "_desktop", return_value=_EmptyDesktop()),
            patch.object(WindowsDesktopHarness, "list_process_ids", return_value=(9876,)),
            patch.object(WindowsDesktopHarness, "port_ready", return_value=False),
            patch.object(WindowsDesktopHarness, "is_interactive_desktop", return_value=True),
            patch.object(WindowsDesktopHarness, "_host_window_descriptors", return_value=[host_window]),
            patch.object(
                WindowsDesktopHarness,
                "capture_screenshot_details",
                return_value=("", True, "grab_failed: access denied"),
            ),
        ):
            observation = harness.observe()

        self.assertEqual(observation.screenshot_path, "")
        self.assertTrue(observation.main_window_found)
        self.assertTrue(observation.evidence["host_window_fallback_used"])
        self.assertTrue(observation.evidence["screenshot_capture_attempted"])
        self.assertEqual(observation.evidence["screenshot_capture_error"], "grab_failed: access denied")


if __name__ == "__main__":
    unittest.main()
