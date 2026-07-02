from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "check_packet_readiness.ps1"
PWSH_UTF8 = Path("scripts/pwsh_utf8.sh")


def _script_windows_path(path: Path) -> str:
    result = subprocess.run(
        ["wslpath", "-w", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _invoke_readiness_script(**kwargs: str) -> dict[str, object]:
    script_windows_path = _script_windows_path(SCRIPT_PATH)
    escaped_script_path = script_windows_path.replace("'", "''")
    command_parts = [f"& '{escaped_script_path}'"]
    for key, value in kwargs.items():
        escaped = value.replace("'", "''")
        command_parts.append(f"-{key} {escaped}")
    command = [
        str(PWSH_UTF8),
        "-Command",
        " ".join(command_parts) + " | ConvertTo-Json -Depth 20 -Compress",
    ]
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _ps_bool(value: bool) -> str:
    return "$true" if value else "$false"


class ControllerPacketReadinessScriptTests(unittest.TestCase):
    def test_runtime_fresh_authority_can_authorize_packet_when_legacy_native_probe_failed(self) -> None:
        payload = _invoke_readiness_script(
            MarketWindowOpen=_ps_bool(True),
            TradeHealthOk=_ps_bool(True),
            DataHealthOk=_ps_bool(True),
            CleanWindowOk=_ps_bool(True),
            PreflightSessionPlanOk=_ps_bool(True),
            NativeProbeOk=_ps_bool(False),
            NativeProbeSamePlanOk=_ps_bool(False),
            HostRecoveryAttempted=_ps_bool(True),
            HostRecoveryOk=_ps_bool(False),
            RuntimeSamePlanOk=_ps_bool(True),
            RuntimeProbeCompleteOk=_ps_bool(True),
            FreshConnectVerified=_ps_bool(True),
            WriteAuthorityReady=_ps_bool(True),
            PreflightTransportOk=_ps_bool(True),
            SessionPlanVersion="v1:2101,2100,2111",
        )

        self.assertEqual(payload["status"], "go")
        self.assertTrue(payload["go"])
        self.assertEqual(payload["no_go_reason"], "")
        self.assertTrue(payload["gate_checks"]["runtime_write_authority_ready"])
        self.assertFalse(payload["gate_checks"]["legacy_native_probe_ready"])
        self.assertFalse(payload["gate_checks"]["legacy_host_recovery_ready"])

    def test_market_window_closed_still_blocks_even_with_runtime_fresh_authority(self) -> None:
        payload = _invoke_readiness_script(
            MarketWindowOpen=_ps_bool(False),
            TradeHealthOk=_ps_bool(True),
            DataHealthOk=_ps_bool(True),
            CleanWindowOk=_ps_bool(True),
            PreflightSessionPlanOk=_ps_bool(True),
            NativeProbeOk=_ps_bool(False),
            NativeProbeSamePlanOk=_ps_bool(False),
            HostRecoveryAttempted=_ps_bool(False),
            HostRecoveryOk=_ps_bool(True),
            RuntimeSamePlanOk=_ps_bool(True),
            RuntimeProbeCompleteOk=_ps_bool(True),
            FreshConnectVerified=_ps_bool(True),
            WriteAuthorityReady=_ps_bool(True),
            PreflightTransportOk=_ps_bool(True),
            SessionPlanVersion="v1:2101,2100,2111",
        )

        self.assertEqual(payload["status"], "no_go")
        self.assertFalse(payload["go"])
        self.assertEqual(payload["no_go_reason"], "market_window_closed")


if __name__ == "__main__":
    unittest.main()
