from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "wake_data_gateway.ps1"
PWSH_COMMAND = os.environ.get("XTQMT_TEST_PWSH", "pwsh")
SCRIPT_ENTRY_MARKER = "$python = Resolve-PythonExe -RequestedPythonExe $PythonExe"


def _script_windows_path(path: Path) -> str:
    if os.name == "nt":
        return str(path)
    result = subprocess.run(
        ["wslpath", "-w", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _function_prelude() -> str:
    content = SCRIPT_PATH.read_text(encoding="utf-8")
    function_start = content.find('$ErrorActionPreference = "Stop"')
    marker_index = content.find(SCRIPT_ENTRY_MARKER)
    if function_start < 0:
        raise AssertionError('未找到函数定义起点: $ErrorActionPreference = "Stop"')
    if marker_index < 0:
        raise AssertionError(f"未找到脚本入口标记: {SCRIPT_ENTRY_MARKER}")
    return content[function_start:marker_index]


def _invoke_test_expected_health(health: dict[str, object]) -> bool:
    prelude = _function_prelude()
    prelude_path = ROOT / ".tmp" / "tests" / "wake_data_gateway_prelude.ps1"
    health_path = ROOT / ".tmp" / "tests" / "wake_data_gateway_health.json"
    prelude_path.parent.mkdir(parents=True, exist_ok=True)
    prelude_path.write_text(prelude, encoding="utf-8")
    health_path.write_text(json.dumps(health, ensure_ascii=False), encoding="utf-8")

    prelude_windows_path = _script_windows_path(prelude_path)
    health_windows_path = _script_windows_path(health_path)
    escaped_prelude = prelude_windows_path.replace("'", "''")
    escaped_health = health_windows_path.replace("'", "''")
    command = [
        PWSH_COMMAND,
        "-Command",
        (
            f". '{escaped_prelude}'; "
            f"$health = Get-Content -LiteralPath '{escaped_health}' -Raw -Encoding UTF8 | ConvertFrom-Json -Depth 20; "
            "[bool](Test-ExpectedHealth "
            "-Health $health "
            "-ServerName 'xtqmtDataGateway' "
            "-HealthUrl 'http://127.0.0.1:8766/healthz' "
            "-RequiredToolNames $ExpectedToolNames) | ConvertTo-Json -Compress"
        ),
    ]
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


class WakeDataGatewayScriptTests(unittest.TestCase):
    def test_get_listener_pids_runs_without_shell_netstat_alias(self) -> None:
        prelude = _function_prelude()
        prelude_path = ROOT / ".tmp" / "tests" / "wake_data_gateway_listener_prelude.ps1"
        prelude_path.parent.mkdir(parents=True, exist_ok=True)
        prelude_path.write_text(prelude, encoding="utf-8")

        prelude_windows_path = _script_windows_path(prelude_path)
        escaped_prelude = prelude_windows_path.replace("'", "''")
        command = [
            PWSH_COMMAND,
            "-Command",
            (
                f". '{escaped_prelude}'; "
                "(@(Get-ListenerPids -Port 9)).Count | ConvertTo-Json -Compress"
            ),
        ]
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(json.loads(result.stdout), 0)

    def test_expected_health_accepts_modern_tool_surface(self) -> None:
        health = {
            "server_name": "xtqmtDataGateway",
            "health_path": "/healthz",
            "bind_port": 8766,
            "enabled_tools": [
                "gateway.health",
                "calendar.resolve_trade_day",
                "integrity.plan",
                "sector.list",
                "sector.members_at",
                "sector.change_history",
                "market.snapshot.batch",
                "market.history.get_bars",
                "bulk.sync_job.submit",
                "bulk.sync_job.status",
                "bulk.sync_job.cancel",
                "artifact.manifest",
                "qlib.health.check",
                "qlib.acceptance.check",
            ],
        }
        self.assertTrue(_invoke_test_expected_health(health))

    def test_expected_health_rejects_legacy_tool_surface_even_when_server_name_matches(self) -> None:
        legacy_health = {
            "server_name": "xtqmtDataGateway",
            "health_path": "/healthz",
            "bind_port": 8766,
            "enabled_tools": [
                "xtdata.status",
                "xtdata.calendar.query",
                "xtdata.download.submit",
                "xtdata.download.status",
                "xtdata.download.cancel",
            ],
        }
        self.assertFalse(_invoke_test_expected_health(legacy_health))


if __name__ == "__main__":
    unittest.main()
