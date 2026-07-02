from __future__ import annotations

from pathlib import Path
import unittest

from xtqmt_mcp.trade_write_authority import build_trade_write_authority_report


def _typed_source(**overrides: object) -> dict[str, object]:
    source: dict[str, object] = {
        "report_type": "trade_write_authority_source",
        "task_id": "VAL-003",
        "packet_id": "packet-20260413-001",
        "trace_id": "trace-001",
        "diag_probe_ref": "C:/xtquant-mcp-example/instance/prod/state/trade_resources/diag_probe_latest.json",
        "controller_judgment_ref": "C:/xtquant-mcp-example/repo/docs/reviews/VAL-003-controller-judgment.md",
        "review_ref": "C:/xtquant-mcp-example/repo/docs/reviews/VAL-003-review-20260411.md",
        "formal_truth_snapshot_ref": "C:/xtquant-mcp-example/repo/.tmp/spec-task-harness/val-003-artifact-snapshot.json",
        "env_snapshot_ref": "C:/xtquant-mcp-example/repo/docs/env_snapshots/VAL-003-controller-direct-live.md",
        "evidence_pack_ref": "C:/xtquant-mcp-example/repo/docs/evidence_packs/VAL-003-test-controller-direct-live.md",
        "runtime_capture_ref": "C:/xtquant-mcp-example/repo/.tmp/spec-task-harness/val-003-runtime.json",
        "packet_readiness_ref": "C:/xtquant-mcp-example/repo/.tmp/spec-task-harness/val-003-packet-readiness.json",
        "formal_closeout_state": {
            "trade_lane_write_closed": False,
            "trade_lane_write_state": "open",
            "task_id": "VAL-003",
            "status": "Blocked",
            "gate": "G4",
            "reason": "connect_gate_failed",
        },
    }
    source.update(overrides)
    return source


def _diag_probe(**overrides: object) -> dict[str, object]:
    probe: dict[str, object] = {
        "reason": "write_connect_failed",
        "read_only_ready": True,
        "write_permission_ready": False,
        "probe_complete_verdict": True,
        "write_permission_block_reason": "write_connect_failed",
        "same_plan_verdict": True,
        "fresh_connect_verified": False,
        "session_plan_version": "v1:2101,2100,2111",
        "resource_trace_id": "trace-001",
        "resource_server_ts": "2026-04-13T14:58:45+08:00",
        "session_id": "2101",
        "observed_probe_session_id": "2101",
        "write_session_alignment": {
            "resolved_session_id": "2101",
            "observed_probe_session_id": "2101",
            "same_plan_reason": "same_session",
            "effective_session_plan": [2101, 2100, 2111],
        },
    }
    probe.update(overrides)
    return probe


def _controller_judgment_markdown() -> str:
    return """
## Judgment

- Summary: fresh packet captured and waiting for review
- Executed Test Role Work: yes
- Next Step: independent review is still required before closeout
"""


class TradeWriteAuthorityTests(unittest.TestCase):
    def test_build_trade_write_authority_report_uses_typed_source_not_current_status_markdown(self) -> None:
        report = build_trade_write_authority_report(
            diag_probe=_diag_probe(),
            authority_source=_typed_source(),
            diag_probe_path=Path("C:/xtquant-mcp-example/instance/prod/state/trade_resources/diag_probe_latest.json"),
            controller_judgment_markdown=_controller_judgment_markdown(),
        )

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["blocking_reason"], "connect_gate_failed")
        self.assertFalse(report["formal_trade_write_closed"])
        self.assertEqual(report["formal_task_posture"]["status"], "Blocked")
        self.assertEqual(report["current_truth_source"], "typed_authority_source")

    def test_build_trade_write_authority_report_keeps_specific_blocker_when_review_ref_pending_on_reopen_packet(self) -> None:
        report = build_trade_write_authority_report(
            diag_probe=_diag_probe(),
            authority_source=_typed_source(review_ref=""),
            diag_probe_path=Path("C:/xtquant-mcp-example/instance/prod/state/trade_resources/diag_probe_latest.json"),
            controller_judgment_markdown=_controller_judgment_markdown(),
        )

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["blocking_reason"], "connect_gate_failed")
        self.assertIn("review_ref", report["warnings"])

    def test_build_trade_write_authority_report_fails_closed_when_review_ref_missing_for_closed_packet(self) -> None:
        report = build_trade_write_authority_report(
            diag_probe=_diag_probe(
                reason="ok",
                write_permission_ready=True,
                write_permission_block_reason="",
                fresh_connect_verified=True,
                resource_trace_id="trace-green",
            ),
            authority_source=_typed_source(
                review_ref="",
                trace_id="trace-green",
                formal_closeout_state={
                    "trade_lane_write_closed": True,
                    "trade_lane_write_state": "closed",
                    "task_id": "VAL-003",
                    "status": "Accepted",
                    "gate": "G4",
                    "reason": "ok",
                },
            ),
            diag_probe_path=Path("C:/xtquant-mcp-example/instance/prod/state/trade_resources/diag_probe_latest.json"),
            controller_judgment_markdown="""
## Judgment

- Summary: fresh packet plus fresh review allow closeout
- Executed Test Role Work: yes
- Next Step: independent review passed
""",
        )

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["blocking_reason"], "authority_source_incomplete")
        self.assertIn("review_ref", report["warnings"])

    def test_build_trade_write_authority_report_fails_closed_when_trace_id_mismatches_probe(self) -> None:
        report = build_trade_write_authority_report(
            diag_probe=_diag_probe(resource_trace_id="trace-other"),
            authority_source=_typed_source(trace_id="trace-expected"),
            diag_probe_path=Path("C:/xtquant-mcp-example/instance/prod/state/trade_resources/diag_probe_latest.json"),
            controller_judgment_markdown=_controller_judgment_markdown(),
        )

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["blocking_reason"], "authority_source_trace_mismatch")
        self.assertEqual(report["current_truth_source"], "typed_authority_source")

    def test_build_trade_write_authority_report_passes_only_when_typed_source_and_runtime_truth_both_green(self) -> None:
        report = build_trade_write_authority_report(
            diag_probe=_diag_probe(
                reason="ok",
                write_permission_ready=True,
                write_permission_block_reason="",
                fresh_connect_verified=True,
                resource_trace_id="trace-green",
            ),
            authority_source=_typed_source(
                trace_id="trace-green",
                formal_closeout_state={
                    "trade_lane_write_closed": True,
                    "trade_lane_write_state": "closed",
                    "task_id": "VAL-003",
                    "status": "Accepted",
                    "gate": "G4",
                    "reason": "ok",
                },
            ),
            diag_probe_path=Path("C:/xtquant-mcp-example/instance/prod/state/trade_resources/diag_probe_latest.json"),
            controller_judgment_markdown="""
## Judgment

- Summary: fresh packet plus fresh review allow closeout
- Executed Test Role Work: yes
- Next Step: independent review passed
""",
        )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["blocking_reason"], "")
        self.assertTrue(report["formal_trade_write_closed"])
        self.assertTrue(report["fresh_connect_verified"])

    def test_build_trade_write_authority_report_fails_closed_when_authority_source_is_missing(self) -> None:
        report = build_trade_write_authority_report(
            diag_probe=_diag_probe(),
            authority_source={},
            diag_probe_path=Path("C:/xtquant-mcp-example/instance/prod/state/trade_resources/diag_probe_latest.json"),
            controller_judgment_markdown=_controller_judgment_markdown(),
        )

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["blocking_reason"], "authority_source_incomplete")
        self.assertIn("packet_id", report["warnings"])

    def test_build_trade_write_authority_report_fails_closed_when_packet_id_is_missing(self) -> None:
        report = build_trade_write_authority_report(
            diag_probe=_diag_probe(),
            authority_source=_typed_source(packet_id=""),
            diag_probe_path=Path("C:/xtquant-mcp-example/instance/prod/state/trade_resources/diag_probe_latest.json"),
            controller_judgment_markdown=_controller_judgment_markdown(),
        )

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["blocking_reason"], "authority_source_incomplete")
        self.assertIn("packet_id", report["warnings"])

    def test_build_trade_write_authority_report_fails_closed_when_controller_judgment_content_is_missing(self) -> None:
        report = build_trade_write_authority_report(
            diag_probe=_diag_probe(),
            authority_source=_typed_source(),
            diag_probe_path=Path("C:/xtquant-mcp-example/instance/prod/state/trade_resources/diag_probe_latest.json"),
            controller_judgment_markdown="",
        )

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["blocking_reason"], "authority_source_incomplete")
        self.assertIn("controller_judgment_content", report["warnings"])

    def test_build_trade_write_authority_report_uses_session_resolution_fallback_for_timeout_probe(self) -> None:
        report = build_trade_write_authority_report(
            diag_probe={
                "reason": "runtime_same_plan_not_ready",
                "read_only_ready": False,
                "write_permission_ready": False,
                "probe_complete_verdict": False,
                "write_permission_block_reason": "session_start_timeout",
                "same_plan_verdict": False,
                "fresh_connect_verified": False,
                "resource_trace_id": "trace-timeout",
                "resource_server_ts": "2026-04-13T15:01:00+08:00",
                "session_resolution": {
                    "configured_session_id": 2111,
                    "resolved_base_session_id": 2111,
                    "resolved_session_id": 2111,
                    "configured_session_candidates": [2111, 2100, 2101],
                    "effective_session_plan": [2111, 2100, 2101],
                },
            },
            authority_source=_typed_source(trace_id="trace-timeout"),
            diag_probe_path=Path("C:/xtquant-mcp-example/instance/prod/state/trade_resources/diag_probe_latest.json"),
            controller_judgment_markdown=_controller_judgment_markdown(),
        )

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["blocking_reason"], "connect_gate_failed")
        self.assertEqual(report["session_plan_version"], "v1:2111,2100,2101")
        self.assertEqual(report["resolved_session_id"], "2111")
        self.assertFalse(report["same_plan_verdict"])
        self.assertFalse(report["probe_complete_verdict"])
        self.assertFalse(report["fresh_connect_verified"])


if __name__ == "__main__":
    unittest.main()
