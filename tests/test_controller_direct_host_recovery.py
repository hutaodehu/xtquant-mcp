from __future__ import annotations

from pathlib import Path
import shutil
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.controller_direct_host_recovery import (
    cleanup_session_residue,
    list_session_residue,
    snapshot_host_recovery_state,
)


class ControllerDirectHostRecoveryTests(unittest.TestCase):
    def _work_root(self, name: str) -> Path:
        root = ROOT / "instance" / "test_tmp" / name
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def test_list_session_residue_only_returns_matching_session_patterns(self) -> None:
        root = self._work_root("controller_direct_host_recovery_list")
        try:
            (root / "down_queue_win_2100").write_text("", encoding="utf-8")
            (root / "lock_down_queue_win_2100").write_text("", encoding="utf-8")
            (root / "down_queue_win_2100__mutex").write_text("", encoding="utf-8")
            (root / "down_queue_win_2101").write_text("", encoding="utf-8")
            (root / "down_queue_win_9999").write_text("", encoding="utf-8")
            (root / "lock_down_queue_win_abc").write_text("", encoding="utf-8")
            (root / "unrelated.txt").write_text("", encoding="utf-8")

            entries = list_session_residue(root, [2100, 2101])

            self.assertEqual(
                [item["name"] for item in entries],
                [
                    "down_queue_win_2100",
                    "down_queue_win_2100__mutex",
                    "down_queue_win_2101",
                    "lock_down_queue_win_2100",
                ],
            )
            self.assertTrue(all(item["session_id"] in {2100, 2101} for item in entries))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_cleanup_session_residue_deletes_only_requested_session_files(self) -> None:
        root = self._work_root("controller_direct_host_recovery_cleanup")
        try:
            protected = root / "down_queue_win_9999"
            delete_one = root / "down_queue_win_2100"
            delete_two = root / "lock_down_queue_win_2100"
            protected.write_text("", encoding="utf-8")
            delete_one.write_text("", encoding="utf-8")
            delete_two.write_text("", encoding="utf-8")

            report = cleanup_session_residue(root, [2100])

            self.assertEqual(report["deleted_count"], 2)
            self.assertFalse(delete_one.exists())
            self.assertFalse(delete_two.exists())
            self.assertTrue(protected.exists())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_snapshot_host_recovery_state_collects_logs_and_residue(self) -> None:
        root = self._work_root("controller_direct_host_recovery_snapshot")
        try:
            log_dir = root / "log"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "XtMiniQmt_20260409.log"
            log_file.write_text("line-1\nline-2\nline-3\n", encoding="utf-8")
            residue = root / "down_queue_win_2100"
            residue.write_text("", encoding="utf-8")

            snapshot = snapshot_host_recovery_state(root, [2100], log_tail_lines=2)

            self.assertEqual(snapshot["user_data_path"], str(root))
            self.assertEqual(snapshot["session_ids"], [2100])
            self.assertEqual(len(snapshot["residue"]), 1)
            self.assertEqual(snapshot["logs"][0]["name"], "XtMiniQmt_20260409.log")
            self.assertEqual(snapshot["logs"][0]["tail"], ["line-2", "line-3"])
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
