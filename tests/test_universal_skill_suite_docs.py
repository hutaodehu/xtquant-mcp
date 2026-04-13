from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNIVERSAL_ROOT = ROOT / "docs" / "universal_skills"
SKILLS_ROOT = ROOT / ".agents" / "skills"

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def iter_relative_markdown_targets(path: Path) -> list[Path]:
    targets: list[Path] = []
    for raw in LINK_RE.findall(path.read_text(encoding="utf-8")):
        target = raw.strip()
        if not target or "://" in target or target.startswith("#"):
            continue
        target = target.split("#", 1)[0].strip("<>")
        if not target:
            continue
        targets.append((path.parent / target).resolve())
    return targets


class UniversalSkillSuiteDocsTests(unittest.TestCase):
    def test_core_universal_docs_exist(self) -> None:
        for relative in (
            "docs/universal_skills/README.md",
            "docs/universal_skills/ADAPTIVE_DELIVERY_SUITE_DESIGN.md",
            "docs/universal_skills/ADAPTIVE_DELIVERY_SUITE_MANUAL.md",
            "docs/universal_skills/ADAPTIVE_DELIVERY_SUITE_REVIEW_20260330.md",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).exists(), relative)

    def test_relative_markdown_links_resolve(self) -> None:
        markdown_files = list(UNIVERSAL_ROOT.rglob("*.md"))
        self.assertGreater(len(markdown_files), 0)
        for path in markdown_files:
            for target in iter_relative_markdown_targets(path):
                with self.subTest(path=str(path.relative_to(ROOT)), target=str(target)):
                    self.assertTrue(target.exists(), f"{path} -> {target} does not exist")

    def test_skill_scaffolding_exists_for_universal_suite(self) -> None:
        for skill_name in (
            "workflow-router",
            "acceptance-analysis",
            "evidence-gate",
            "mode-analyze-only",
            "mode-fast-loop",
            "mode-gated-change",
            "mode-live-rollout",
        ):
            skill_root = SKILLS_ROOT / skill_name
            with self.subTest(skill=skill_name):
                self.assertTrue((skill_root / "SKILL.md").exists())
                self.assertTrue((skill_root / "agents" / "openai.yaml").exists())
                self.assertTrue((skill_root / "references" / "README.md").exists())
                self.assertTrue((skill_root / "examples" / "README.md").exists())

    def test_examples_readme_listed_files_exist(self) -> None:
        expected = (
            "docs_only_fast_loop.yaml",
            "pure_logic_bugfix_fast_loop.yaml",
            "public_api_change_gated_change.yaml",
            "cross_module_refactor_gated_change.yaml",
            "schema_migration_live_rollout.yaml",
            "trade_order_place_live_rollout.yaml",
            "agent_tool_routing_gated_change.yaml",
            "missing_contract_analyze_only.yaml",
            "stale_runtime_evidence_live_rollout.yaml",
            "broker_session_volatility_gated_change.yaml",
            "tool_permission_drift_gated_change.yaml",
            "background_agent_remote_write_live_rollout.yaml",
            "multi_agent_handoff_authority_gap_gated_change.yaml",
            "deterministic_quant_factor_fast_loop_worked_example.yaml",
            "stale_runtime_evidence_live_rollout_worked_example.yaml",
            "multi_agent_controlled_opt_in_gated_change.yaml",
            "plugin_packaging_decision_analyze_only.yaml",
            "contract_missing_recovery_analyze_only.yaml",
        )
        for name in expected:
            with self.subTest(name=name):
                self.assertTrue((UNIVERSAL_ROOT / "examples" / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
