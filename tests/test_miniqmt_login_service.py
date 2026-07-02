from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.miniqmt_login.contracts import MiniQmtLoginConfig, MiniQmtLoginStatus
from xtqmt_mcp.miniqmt_login.desktop_harness import ActionResult, DesktopObservation, LaunchResult
from xtqmt_mcp.miniqmt_login.service import ensure_miniqmt_logged_in


class _FakeHarness:
    def __init__(self, observations: list[DesktopObservation]) -> None:
        self._observations = list(observations)
        self._index = 0

    def is_interactive_desktop(self) -> bool:
        return True

    def observe(self, **_: object) -> DesktopObservation:
        if self._index < len(self._observations):
            observation = self._observations[self._index]
            self._index += 1
            return observation
        return self._observations[-1]

    def launch_or_attach(self, _: str) -> LaunchResult:
        return LaunchResult(
            ok=True,
            process_id=12345,
            started=False,
            already_running=True,
            message="already running",
        )

    def submit_saved_password(self, _: DesktopObservation, __: str) -> ActionResult:
        return ActionResult(ok=False, code="unexpected", message="submit should not be called")


class MiniQmtLoginServiceTests(unittest.TestCase):
    def _config(self) -> MiniQmtLoginConfig:
        return MiniQmtLoginConfig(
            qmt_exe=__file__,
            qmt_userdata=__file__,
            account_id="ACC001",
            login_timeout_seconds=1,
            startup_grace_seconds=0,
        )

    def test_main_window_without_ready_probe_is_not_treated_as_already_logged_in(self) -> None:
        readiness_calls: list[dict[str, object]] = []

        def readiness_probe(_: MiniQmtLoginConfig) -> dict[str, object]:
            readiness_calls.append({"called": True})
            return {"ok": False, "reason": "trade_channel_not_ready"}

        harness = _FakeHarness(
            [
                DesktopObservation(
                    process_id=12345,
                    window_title="XtMiniQmt",
                    main_window_found=True,
                    login_window_found=False,
                    port_ready=True,
                )
            ]
        )

        result = ensure_miniqmt_logged_in(
            self._config(),
            harness=harness,
            credential_reader=lambda _: None,
            readiness_probe=readiness_probe,
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.status, MiniQmtLoginStatus.LOGIN_WINDOW_NOT_FOUND)
        self.assertTrue(readiness_calls)

    def test_main_window_with_ready_probe_can_still_be_treated_as_already_logged_in(self) -> None:
        harness = _FakeHarness(
            [
                DesktopObservation(
                    process_id=12345,
                    window_title="ACC001 - 国金证券QMT交易端 2.0.8.300",
                    main_window_found=True,
                    login_window_found=False,
                    port_ready=True,
                )
            ]
        )

        result = ensure_miniqmt_logged_in(
            self._config(),
            harness=harness,
            credential_reader=lambda _: None,
            readiness_probe=lambda _: {"ok": True, "reason": "trade_channel_ready"},
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.status, MiniQmtLoginStatus.ALREADY_LOGGED_IN)


if __name__ == "__main__":
    unittest.main()
