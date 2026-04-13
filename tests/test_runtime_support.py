from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.runtime_support import AutoAccountResolutionError, resolve_account_for_ops


class ResolveAccountForOpsTests(unittest.TestCase):
    def test_auto_account_continues_after_candidate_discovery_failure(self) -> None:
        calls: list[int] = []

        def _discover(**kwargs: object) -> list[str]:
            session_id = int(kwargs["session_id"])
            calls.append(session_id)
            if session_id == 100:
                raise RuntimeError("xttrader connect failed: -1")
            if session_id == 101:
                return ["ACC001"]
            return []

        resolved = resolve_account_for_ops(
            qmt_userdata="D:\\broker\\userdata",
            account_id="",
            auto_account=True,
            session_id=100,
            session_candidates=(100, 101, 111),
            discover_stock_account_ids=_discover,
        )

        self.assertEqual(calls, [100, 101])
        self.assertEqual(resolved.account_id, "ACC001")
        self.assertEqual(resolved.session_id, 101)

    def test_auto_account_failure_surfaces_candidate_level_diagnostics(self) -> None:
        def _discover(**kwargs: object) -> list[str]:
            session_id = int(kwargs["session_id"])
            if session_id == 100:
                raise RuntimeError("xttrader connect failed: -1")
            if session_id == 101:
                return []
            raise RuntimeError("xttrader connect failed: -2")

        with self.assertRaises(AutoAccountResolutionError) as ctx:
            resolve_account_for_ops(
                qmt_userdata="D:\\broker\\userdata",
                account_id="",
                auto_account=True,
                session_id=100,
                session_candidates=(100, 101, 111),
                discover_stock_account_ids=_discover,
            )

        message = str(ctx.exception)
        self.assertIn("auto_account discovery failed across session candidates", message)
        self.assertIn("session_id=100 error=xttrader connect failed: -1", message)
        self.assertIn("session_id=101 no_accounts_discovered", message)
        self.assertIn("session_id=111 error=xttrader connect failed: -2", message)


if __name__ == "__main__":
    unittest.main()
