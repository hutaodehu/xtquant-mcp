from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.miniqmt_login import desktop_harness
from xtqmt_mcp.miniqmt_login.desktop_harness import (
    ControlDescriptor,
    WindowDescriptor,
    WindowsDesktopHarness,
    _classify_window_descriptor,
)


class _EmptyDesktop:
    def windows(self, process: int, visible_only: bool = False):
        return []


class MiniQmtDesktopHarnessTests(unittest.TestCase):
    def test_observe_defaults_to_unconfigured_port_instead_of_legacy_58610(self) -> None:
        harness = WindowsDesktopHarness(screenshot_dir=str(ROOT / "instance" / "test_tmp" / "miniqmt_harness"))
        observed_ports: list[int] = []

        def fake_port_ready(self, host: str = "127.0.0.1", port: int = 0, timeout_ms: int = 300) -> bool:
            observed_ports.append(int(port))
            return False

        with (
            patch.object(desktop_harness, "Desktop", None),
            patch.object(WindowsDesktopHarness, "list_process_ids", return_value=()),
            patch.object(WindowsDesktopHarness, "port_ready", fake_port_ready),
            patch.object(WindowsDesktopHarness, "is_interactive_desktop", return_value=True),
            patch.object(WindowsDesktopHarness, "capture_screenshot_details", return_value=("", False, "")),
        ):
            observation = harness.observe()

        self.assertEqual(observed_ports, [0])
        self.assertFalse(observation.port_ready)
        self.assertEqual(observation.evidence["port_num"], 0)

    def test_configured_58610_can_be_reported_tcp_ready_when_socket_accepts(self) -> None:
        harness = WindowsDesktopHarness(screenshot_dir=str(ROOT / "instance" / "test_tmp" / "miniqmt_harness"))

        class _FakeSocket:
            def settimeout(self, _timeout: float) -> None:
                return None

            def connect(self, _endpoint: tuple[str, int]) -> None:
                return None

            def close(self) -> None:
                return None

        with patch.object(desktop_harness.socket, "socket", return_value=_FakeSocket()):
            self.assertTrue(harness.port_ready(port=58610))

        with (
            patch.object(desktop_harness, "Desktop", None),
            patch.object(WindowsDesktopHarness, "list_process_ids", return_value=()),
            patch.object(WindowsDesktopHarness, "port_ready", return_value=False),
            patch.object(WindowsDesktopHarness, "is_interactive_desktop", return_value=True),
            patch.object(WindowsDesktopHarness, "capture_screenshot_details", return_value=("", False, "")),
        ):
            observation = harness.observe(port_num=58610)
        self.assertFalse(observation.port_ready)
        self.assertFalse(observation.evidence.get("legacy_port_detected", False))
        self.assertEqual(observation.evidence["blocking_reason"], "")

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

    def test_main_trade_window_with_login_status_controls_is_not_login_candidate(self) -> None:
        descriptor = WindowDescriptor(
            handle=303,
            process_id=10392,
            title="SAMPLE_ACCOUNT - 国金证券QMT交易端 2.0.8.300",
            class_name="Qt5QWindowIcon",
            controls=(
                ControlDescriptor("ComboBox", "证券账号", (100, 10, 260, 40), True, True),
                ControlDescriptor("Edit", "", (100, 80, 260, 110), True, True),
                ControlDescriptor("Edit", "", (100, 130, 260, 160), True, True),
                ControlDescriptor("Edit", "", (100, 180, 260, 210), True, True),
                ControlDescriptor("Button", "买 入", (100, 230, 180, 260), True, True),
                ControlDescriptor("Button", "刷取资金", (300, 20, 380, 50), True, True),
                ControlDescriptor("Button", "校验密码", (390, 20, 470, 50), True, True),
                ControlDescriptor("Button", "登录状态", (480, 20, 560, 50), True, True),
                ControlDescriptor("Button", "账户状态", (570, 20, 650, 50), True, True),
            ),
            visible=True,
            enabled=True,
        )

        classification = _classify_window_descriptor(descriptor, port_ready=True)

        self.assertFalse(classification.login_candidate)
        self.assertTrue(classification.main_candidate)

    def test_login_form_with_spaced_login_button_remains_login_candidate(self) -> None:
        descriptor = WindowDescriptor(
            handle=404,
            process_id=10392,
            title="国金证券QMT交易端",
            class_name="Dialog",
            controls=(
                ControlDescriptor("Edit", "", (100, 80, 260, 110), True, True),
                ControlDescriptor("Edit", "", (100, 130, 260, 160), True, True),
                ControlDescriptor("Edit", "", (100, 180, 260, 210), True, True),
                ControlDescriptor("Text", "交易密码", (20, 130, 90, 160), True, True),
                ControlDescriptor("Button", "登 录", (100, 230, 180, 260), True, True),
            ),
            visible=True,
            enabled=True,
        )

        classification = _classify_window_descriptor(descriptor, port_ready=True)

        self.assertTrue(classification.login_candidate)
        self.assertFalse(classification.main_candidate)


if __name__ == "__main__":
    unittest.main()
