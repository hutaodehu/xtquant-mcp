from __future__ import annotations

import sys
import json
import subprocess
import unittest
from pathlib import Path
import shutil
import uuid


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_SCRIPTS = REPO_ROOT / ".agents" / "skills" / "spec-task-harness" / "scripts"
if str(HARNESS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(HARNESS_SCRIPTS))

from harness_common import filename_timestamp_value, latest_artifact_for_task, load_task_states


_TEMP_ROOT = REPO_ROOT / ".tmp" / "tests"
_TEMP_ROOT.mkdir(parents=True, exist_ok=True)


class _WorkspaceTempDir:
    def __init__(self) -> None:
        self.path = _TEMP_ROOT / f"case_{uuid.uuid4().hex}"

    def __enter__(self) -> str:
        self.path.mkdir(parents=True, exist_ok=False)
        return str(self.path)

    def __exit__(self, exc_type, exc, tb) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


def write_artifact(path: Path, task_id: str, decision: str = "pass", backticked: bool = False) -> None:
    decision_value = f"`{decision}`" if backticked else decision
    path.write_text(
        "\n".join(
            [
                "# Artifact",
                "",
                f"Task ID: {task_id}",
                "Role: review",
                "Date: 2026-03-30T00:00:00+08:00",
                "",
                "## Notes",
                "",
                "latest artifact fixture",
                "",
                f"- Decision: {decision_value}",
            ]
        ),
        encoding="utf-8",
    )


def write_task_card(path: Path, task_id: str, overrides: dict[str, str] | None = None) -> None:
    fields = {
        "Task ID": task_id,
        "Title": "Review decision parser regression fixture",
        "Type": "bug",
        "Priority": "P1",
        "Owner Role": "dev",
        "Current Role": "dev",
        "Status": "Ready",
        "Blocking Reason": "",
        "Repo Spec Link": "[MCP_DESIGN.md](../MCP_DESIGN.md)",
        "Acceptance Gate": "G0",
        "Change Package Link": "[VAL-002.md](../change_packages/VAL-002.md)",
        "Evidence Pack Link": "[VAL-002-test-20260330-142745.md](../evidence_packs/VAL-002-test-20260330-142745.md)",
        "Review Pack Link": "",
        "Env Snapshot Link": "N/A",
        "Verifier": "unittest",
        "Merge Owner": "controller",
        "Review Result": "pending",
        "Depends On": "",
        "Lane": "trade",
        "Risk Class": "medium",
        "Write Scope": "ops.review_pack_parsing",
        "Automation Policy": "auto_safe",
        "Execution Class": "handoff_required",
    }
    for key, value in (overrides or {}).items():
        fields[key] = value
    lines = [f"{key}: {value}" for key, value in fields.items()]
    lines.extend(["", "## Goal", "", f"Fixture for {task_id}"])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_change_pack(path: Path, task_id: str) -> None:
    path.write_text(
        "\n".join(
            [
                "# ChangePack",
                "",
                f"Task ID: {task_id}",
                "Role: dev",
                "Date: 2026-03-30T00:00:00+08:00",
                "Branch/Commit: test",
                "Stage: implemented",
                "",
                "## Goal",
                "",
                "fixture",
            ]
        ),
        encoding="utf-8",
    )


def write_evidence_pack(path: Path, task_id: str, conclusion: str = "pass") -> None:
    path.write_text(
        "\n".join(
            [
                "# EvidencePack",
                "",
                f"Task ID: {task_id}",
                "Role: test",
                "Date: 2026-03-30T00:00:00+08:00",
                f"Conclusion: {conclusion}",
                "",
                "## Notes",
                "",
                "fixture",
            ]
        ),
        encoding="utf-8",
    )


class SpecTaskHarnessArtifactOrderingTests(unittest.TestCase):
    def test_filename_timestamp_value_normalizes_mixed_styles(self) -> None:
        with _WorkspaceTempDir() as tmp:
            root = Path(tmp)
            compact = root / "VAL-002-review-202603300701.md"
            hyphenated = root / "VAL-002-review-20260330-143606-live-gateway-rerun-orders-fallback.md"
            for path in (compact, hyphenated):
                write_artifact(path, "VAL-002")

            self.assertEqual(filename_timestamp_value(compact), 20260330070100)
            self.assertEqual(filename_timestamp_value(hyphenated), 20260330143606)
            self.assertGreater(filename_timestamp_value(hyphenated), filename_timestamp_value(compact))

    def test_latest_artifact_for_task_prefers_later_hyphenated_timestamp(self) -> None:
        with _WorkspaceTempDir() as tmp:
            review_dir = Path(tmp)
            older = review_dir / "VAL-002-review-202603300701.md"
            newer = review_dir / "VAL-002-review-20260330-143606-live-gateway-rerun-orders-fallback.md"
            write_artifact(older, "VAL-002")
            write_artifact(newer, "VAL-002")

            latest = latest_artifact_for_task(review_dir, "VAL-002")

            self.assertIsNotNone(latest)
            self.assertEqual(Path(latest.path).name, newer.name)

    def test_latest_artifact_for_task_parses_backticked_review_decisions(self) -> None:
        with _WorkspaceTempDir() as tmp:
            review_dir = Path(tmp) / "reviews"
            review_dir.mkdir()
            for decision in ("pass", "needs_fix", "blocked"):
                with self.subTest(decision=decision):
                    review = review_dir / f"OPS-004-review-20260330-143606-{decision}.md"
                    write_artifact(review, "OPS-004", decision=decision, backticked=True)

                    latest = latest_artifact_for_task(review_dir, "OPS-004")

                    self.assertIsNotNone(latest)
                    self.assertEqual(latest.fields.get("Decision"), decision)
                    review.unlink()

    def test_load_task_states_restores_closeout_from_latest_backticked_review(self) -> None:
        with _WorkspaceTempDir() as tmp:
            repo_root = Path(tmp)
            task_cards = repo_root / "docs" / "task_cards"
            change_packages = repo_root / "docs" / "change_packages"
            evidence_packs = repo_root / "docs" / "evidence_packs"
            reviews = repo_root / "docs" / "reviews"
            env_snapshots = repo_root / "docs" / "env_snapshots"
            for directory in (task_cards, change_packages, evidence_packs, reviews, env_snapshots):
                directory.mkdir(parents=True, exist_ok=True)

            write_task_card(task_cards / "VAL-002.md", "VAL-002")
            write_change_pack(change_packages / "VAL-002.md", "VAL-002")
            write_evidence_pack(evidence_packs / "VAL-002-test-20260330-142745.md", "VAL-002")
            write_artifact(reviews / "VAL-002-review-202603300701.md", "VAL-002", decision="blocked")
            latest_review = reviews / "VAL-002-review-20260330-143606-live-gateway-rerun-orders-fallback.md"
            write_artifact(latest_review, "VAL-002", decision="pass", backticked=True)

            task = {item.task_id: item for item in load_task_states(repo_root)}["VAL-002"]

            self.assertEqual(Path(task.latest_review.path).name, latest_review.name)
            self.assertEqual(task.latest_review_decision, "pass")
            self.assertEqual(task.local_stage, "reviewed_pass_local")
            self.assertEqual(task.controller_action, "controller_closeout")

    def test_validate_taskcard_rejects_incomplete_controller_direct_policy(self) -> None:
        with _WorkspaceTempDir() as tmp:
            repo_root = Path(tmp)
            task_cards = repo_root / "docs" / "task_cards"
            change_packages = repo_root / "docs" / "change_packages"
            task_cards.mkdir(parents=True, exist_ok=True)
            change_packages.mkdir(parents=True, exist_ok=True)

            write_task_card(
                task_cards / "VAL-003.md",
                "VAL-003",
                overrides={
                    "Type": "investigation",
                    "Owner Role": "test",
                    "Current Role": "test",
                    "Acceptance Gate": "G4",
                    "Lane": "validation",
                    "Risk Class": "high",
                    "Automation Policy": "manual_gate",
                    "Execution Class": "test_only",
                    "Controller Test Policy": "controller_direct_required",
                    "Execution Packet Side": "BUY",
                    "Execution Packet Symbol": "515880.SH",
                },
            )
            script = HARNESS_SCRIPTS / "validate_taskcard.py"
            result = subprocess.run(
                [sys.executable, str(script), "--repo-root", str(repo_root), "--task-id", "VAL-003"],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Execution Packet Qty", result.stdout)

    def test_validate_taskcard_dump_json_emits_controller_direct_contract(self) -> None:
        with _WorkspaceTempDir() as tmp:
            repo_root = Path(tmp)
            task_cards = repo_root / "docs" / "task_cards"
            change_packages = repo_root / "docs" / "change_packages"
            task_cards.mkdir(parents=True, exist_ok=True)
            change_packages.mkdir(parents=True, exist_ok=True)

            write_task_card(
                task_cards / "VAL-003.md",
                "VAL-003",
                overrides={
                    "Type": "investigation",
                    "Owner Role": "test",
                    "Current Role": "review",
                    "Acceptance Gate": "G4",
                    "Lane": "validation",
                    "Risk Class": "high",
                    "Automation Policy": "manual_gate",
                    "Execution Class": "test_only",
                    "Controller Test Policy": "controller_direct_required",
                    "Execution Packet Side": "BUY",
                    "Execution Packet Symbol": "515880.SH",
                    "Execution Packet Qty": "100",
                    "Execution Packet Price Mode": "l1_protect",
                    "Execution Packet Cancel Timeout": "30s",
                    "Trade Config Path": r"D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml",
                },
            )
            script = HARNESS_SCRIPTS / "validate_taskcard.py"
            result = subprocess.run(
                [sys.executable, str(script), "--repo-root", str(repo_root), "--task-id", "VAL-003", "--dump-json"],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["controller_test_policy"], "controller_direct_required")
            self.assertEqual(payload["packet"]["side"], "BUY")
            self.assertEqual(payload["packet"]["qty"], 100)
            self.assertEqual(
                payload["trade_config_path"],
                r"D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml",
            )

    def test_select_next_safe_tasks_keeps_controller_direct_live_test_non_dispatchable(self) -> None:
        with _WorkspaceTempDir() as tmp:
            repo_root = Path(tmp)
            task_cards = repo_root / "docs" / "task_cards"
            change_packages = repo_root / "docs" / "change_packages"
            task_cards.mkdir(parents=True, exist_ok=True)
            change_packages.mkdir(parents=True, exist_ok=True)

            write_task_card(
                task_cards / "VAL-003.md",
                "VAL-003",
                overrides={
                    "Type": "investigation",
                    "Owner Role": "test",
                    "Current Role": "test",
                    "Acceptance Gate": "G4",
                    "Lane": "validation",
                    "Risk Class": "high",
                    "Automation Policy": "manual_gate",
                    "Execution Class": "test_only",
                    "Controller Test Policy": "controller_direct_required",
                    "Execution Packet Side": "BUY",
                    "Execution Packet Symbol": "515880.SH",
                    "Execution Packet Qty": "100",
                    "Execution Packet Price Mode": "l1_protect",
                    "Execution Packet Cancel Timeout": "30s",
                },
            )
            script = HARNESS_SCRIPTS / "select_next_safe_tasks.py"
            result = subprocess.run(
                [sys.executable, str(script), "--repo-root", str(repo_root)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["controller_action"], "manual_resume_required")
            self.assertEqual(payload["dispatchable_candidates"], [])


if __name__ == "__main__":
    unittest.main()
