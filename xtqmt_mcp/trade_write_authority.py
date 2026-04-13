from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .session_resolution import build_session_plan_version

DEFAULT_REPO_ROOT = Path("D:/xtquant-mcp/repo")
DEFAULT_INSTANCE_ROOT = Path("D:/xtquant-mcp/instance/prod")
DEFAULT_DIAG_PROBE_PATH = DEFAULT_INSTANCE_ROOT / "state" / "trade_resources" / "diag_probe_latest.json"
DEFAULT_AUTHORITY_SOURCE_PATH = DEFAULT_INSTANCE_ROOT / "state" / "trade_resources" / "trade_write_authority_source_latest.json"
DEFAULT_OUTPUT_PATH = DEFAULT_INSTANCE_ROOT / "state" / "trade_resources" / "trade_write_authority_latest.json"

_REQUIRED_SOURCE_FIELDS = (
    "packet_id",
    "trace_id",
    "diag_probe_ref",
    "controller_judgment_ref",
    "formal_truth_snapshot_ref",
    "formal_closeout_state",
)
_REQUIRED_FORMAL_FIELDS = (
    "trade_lane_write_closed",
    "trade_lane_write_state",
    "task_id",
    "status",
    "gate",
    "reason",
)


def _load_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload) if isinstance(payload, dict) else {}


def _load_text(path: Path | None) -> str:
    if path is None or (not path.exists()):
        return ""
    return path.read_text(encoding="utf-8")


def _parse_controller_judgment(markdown: str) -> dict[str, Any]:
    summary_match = re.search(r"- Summary:\s*(.+)", markdown)
    executed_match = re.search(r"- Executed Test Role Work:\s*(.+)", markdown)
    next_step_match = re.search(r"- Next Step:\s*(.+)", markdown)

    summary = str(summary_match.group(1).strip() if summary_match else "")
    executed_text = str(executed_match.group(1).strip() if executed_match else "").lower()
    next_step = str(next_step_match.group(1).strip() if next_step_match else "")

    executed_test: bool | None
    if executed_text in {"yes", "true"}:
        executed_test = True
    elif executed_text in {"no", "false"}:
        executed_test = False
    else:
        executed_test = None

    no_go = bool((executed_test is False) or ("no-go" in next_step.lower()) or ("stop" in summary.lower()))
    return {
        "summary": summary,
        "executed_test": executed_test,
        "next_step": next_step,
        "no_go": no_go,
    }


def _resolve_ref_path(base_path: Path, ref: str) -> Path | None:
    token = str(ref or "").strip()
    if not token:
        return None
    candidate = Path(token)
    if candidate.is_absolute():
        return candidate
    return (base_path.parent / candidate).resolve()


def _normalize_authority_source(authority_source: dict[str, Any]) -> dict[str, Any]:
    payload = dict(authority_source or {})
    payload["formal_closeout_state"] = dict(payload.get("formal_closeout_state") or {})
    payload["artifact_refs"] = dict(payload.get("artifact_refs") or {})
    return payload


def _authority_source_missing_fields(authority_source: dict[str, Any]) -> list[str]:
    payload = _normalize_authority_source(authority_source)
    missing: list[str] = []
    for field in _REQUIRED_SOURCE_FIELDS:
        value = payload.get(field)
        if isinstance(value, dict):
            if not value:
                missing.append(field)
            continue
        if not str(value or "").strip():
            missing.append(field)

    formal_closeout_state = dict(payload.get("formal_closeout_state") or {})
    review_ref = str(payload.get("review_ref") or "").strip()
    for field in _REQUIRED_FORMAL_FIELDS:
        value = formal_closeout_state.get(field)
        if field == "trade_lane_write_closed":
            if value not in {True, False}:
                missing.append(f"formal_closeout_state.{field}")
            continue
        if not str(value or "").strip():
            missing.append(f"formal_closeout_state.{field}")
    if formal_closeout_state.get("trade_lane_write_closed") is True and not review_ref:
        missing.append("review_ref")
    return missing


def _authority_source_pending_warnings(authority_source: dict[str, Any]) -> list[str]:
    payload = _normalize_authority_source(authority_source)
    formal_closeout_state = dict(payload.get("formal_closeout_state") or {})
    if formal_closeout_state.get("trade_lane_write_closed") is False and not str(payload.get("review_ref") or "").strip():
        return ["review_ref"]
    return []


def _formal_truth_from_source(authority_source: dict[str, Any]) -> dict[str, Any]:
    formal_closeout_state = dict(_normalize_authority_source(authority_source).get("formal_closeout_state") or {})
    return {
        "trade_lane_write_closed": bool(formal_closeout_state.get("trade_lane_write_closed", False)),
        "trade_lane_write_state": str(formal_closeout_state.get("trade_lane_write_state") or "unknown"),
        "task_id": str(formal_closeout_state.get("task_id") or "VAL-003"),
        "task_status": str(formal_closeout_state.get("status") or ""),
        "task_gate": str(formal_closeout_state.get("gate") or ""),
        "blocking_reason": str(formal_closeout_state.get("reason") or ""),
        "review_decision": str(formal_closeout_state.get("review_decision") or ""),
    }


def build_trade_write_authority_report(
    *,
    diag_probe: dict[str, Any],
    authority_source: dict[str, Any],
    diag_probe_path: Path,
    authority_source_path: Path | None = None,
    controller_judgment_markdown: str = "",
    controller_judgment_path: Path | None = None,
) -> dict[str, Any]:
    authority_source = _normalize_authority_source(authority_source)
    formal_truth = _formal_truth_from_source(authority_source)
    controller_judgment = _parse_controller_judgment(controller_judgment_markdown)

    same_plan_verdict = bool(diag_probe.get("same_plan_verdict", False))
    fresh_connect_verified = bool(diag_probe.get("fresh_connect_verified", False))
    read_only_ready = bool(diag_probe.get("read_only_ready", False))
    probe_complete_verdict = bool(diag_probe.get("probe_complete_verdict", False))
    write_permission_ready = bool(diag_probe.get("write_permission_ready", False))
    same_plan_reason = str(((diag_probe.get("write_session_alignment") or {}).get("same_plan_reason") or "")).strip()
    diag_blocking_reason = str(diag_probe.get("write_permission_block_reason") or diag_probe.get("reason") or "").strip()
    session_plan_version = str(diag_probe.get("session_plan_version") or "").strip() or build_session_plan_version(
        ((diag_probe.get("write_session_alignment") or {}).get("effective_session_plan") or diag_probe.get("effective_session_plan"))
    )

    warnings: list[str] = []
    blocking_reason = ""
    missing_fields = _authority_source_missing_fields(authority_source)
    warnings.extend(_authority_source_pending_warnings(authority_source))
    source_trace_id = str(authority_source.get("trace_id") or "").strip()
    diag_trace_id = str(diag_probe.get("resource_trace_id") or "").strip()
    if not diag_trace_id:
        missing_fields.append("diag_probe.resource_trace_id")
    if not str(controller_judgment_markdown or "").strip():
        missing_fields.append("controller_judgment_content")

    if missing_fields:
        blocking_reason = "authority_source_incomplete"
        warnings.extend(missing_fields)
    elif source_trace_id and diag_trace_id and source_trace_id != diag_trace_id:
        blocking_reason = "authority_source_trace_mismatch"
        warnings.extend([f"source_trace_id={source_trace_id}", f"diag_probe_trace_id={diag_trace_id}"])
    elif not formal_truth["trade_lane_write_closed"]:
        blocking_reason = formal_truth["blocking_reason"] or diag_blocking_reason or "formal_trade_write_lane_not_closed"
    elif bool(controller_judgment.get("no_go", False)):
        blocking_reason = formal_truth["blocking_reason"] or "controller_direct_no_go"
        warnings.append("controller_direct_packet_stopped_before_order_place")
    elif not read_only_ready:
        blocking_reason = str(diag_probe.get("reason") or "trade_read_not_ready").strip() or "trade_read_not_ready"
    elif not same_plan_verdict:
        blocking_reason = same_plan_reason or "write_session_mismatch"
    elif not probe_complete_verdict:
        blocking_reason = "probe_complete_verdict_missing"
    elif not fresh_connect_verified:
        blocking_reason = "fresh_connect_not_verified"
    elif not write_permission_ready:
        blocking_reason = diag_blocking_reason or "trade_write_authority_failed"

    ready = not blocking_reason
    resolved_session_id = str(
        ((diag_probe.get("write_session_alignment") or {}).get("resolved_session_id") or diag_probe.get("session_id") or "")
    ).strip()
    observed_probe_session_id = str(
        diag_probe.get("observed_probe_session_id")
        or ((diag_probe.get("write_session_alignment") or {}).get("observed_probe_session_id") or "")
    ).strip()
    resource_server_ts = str(diag_probe.get("resource_server_ts") or "").strip()

    evidence_refs = [
        str(diag_probe_path),
        str(authority_source_path or ""),
        str(authority_source.get("diag_probe_ref") or ""),
        str(authority_source.get("controller_judgment_ref") or ""),
        str(authority_source.get("review_ref") or ""),
        str(authority_source.get("formal_truth_snapshot_ref") or ""),
        str(authority_source.get("env_snapshot_ref") or ""),
        str(authority_source.get("evidence_pack_ref") or ""),
        str(authority_source.get("runtime_capture_ref") or ""),
        str(authority_source.get("packet_readiness_ref") or ""),
    ]
    current_truth_ref = str(authority_source_path or authority_source.get("packet_id") or "").strip()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "report_type": "trade_write_authority",
        "status": "pass" if ready else "fail",
        "blocking_reason": blocking_reason,
        "current_truth_source": "typed_authority_source",
        "current_truth_ref": current_truth_ref,
        "packet_id": str(authority_source.get("packet_id") or ""),
        "trace_id": source_trace_id,
        "same_plan_verdict": same_plan_verdict,
        "same_plan_reason": same_plan_reason,
        "fresh_connect_verified": fresh_connect_verified,
        "read_only_ready": read_only_ready,
        "probe_complete_verdict": probe_complete_verdict,
        "write_permission_ready": write_permission_ready,
        "session_plan_version": session_plan_version,
        "resolved_session_id": resolved_session_id,
        "observed_probe_session_id": observed_probe_session_id,
        "resource_trace_id": diag_trace_id,
        "resource_server_ts": resource_server_ts,
        "diag_probe_reason": str(diag_probe.get("reason") or "").strip(),
        "diag_probe_blocking_reason": diag_blocking_reason,
        "controller_direct_no_go": bool(controller_judgment.get("no_go", False)),
        "controller_direct_executed_test": controller_judgment.get("executed_test"),
        "controller_direct_summary": str(controller_judgment.get("summary") or ""),
        "formal_trade_write_closed": bool(formal_truth["trade_lane_write_closed"]),
        "formal_trade_write_state": str(formal_truth["trade_lane_write_state"]),
        "formal_task_posture": {
            "task_id": str(formal_truth["task_id"]),
            "status": str(formal_truth["task_status"]),
            "gate": str(formal_truth["task_gate"]),
            "reason": str(formal_truth["blocking_reason"]),
            "review_decision": str(formal_truth["review_decision"]),
        },
        "warnings": list(dict.fromkeys(item for item in warnings if str(item).strip())),
        "evidence_refs": list(dict.fromkeys(ref for ref in evidence_refs if ref)),
        "source_reports": {
            "authority_source_path": str(authority_source_path or ""),
            "diag_probe_path": str(diag_probe_path),
            "diag_probe_ref": str(authority_source.get("diag_probe_ref") or ""),
            "review_ref": str(authority_source.get("review_ref") or ""),
            "controller_judgment_ref": str(authority_source.get("controller_judgment_ref") or ""),
            "controller_judgment_path": str(controller_judgment_path or ""),
            "formal_truth_snapshot_ref": str(authority_source.get("formal_truth_snapshot_ref") or ""),
            "env_snapshot_ref": str(authority_source.get("env_snapshot_ref") or ""),
            "evidence_pack_ref": str(authority_source.get("evidence_pack_ref") or ""),
            "runtime_capture_ref": str(authority_source.get("runtime_capture_ref") or ""),
            "packet_readiness_ref": str(authority_source.get("packet_readiness_ref") or ""),
        },
    }


def build_from_paths(
    *,
    authority_source_path: Path = DEFAULT_AUTHORITY_SOURCE_PATH,
    diag_probe_path: Path | None = None,
) -> dict[str, Any]:
    resolved_authority_source_path = authority_source_path.expanduser().resolve()
    authority_source = _load_json_dict(resolved_authority_source_path)
    resolved_diag_probe_path = (
        diag_probe_path.expanduser().resolve()
        if diag_probe_path is not None
        else _resolve_ref_path(resolved_authority_source_path, str(authority_source.get("diag_probe_ref") or ""))
    )
    if resolved_diag_probe_path is None:
        resolved_diag_probe_path = DEFAULT_DIAG_PROBE_PATH.resolve()
    controller_judgment_path = _resolve_ref_path(
        resolved_authority_source_path,
        str(authority_source.get("controller_judgment_ref") or ""),
    )
    return build_trade_write_authority_report(
        diag_probe=_load_json_dict(resolved_diag_probe_path),
        authority_source=authority_source,
        diag_probe_path=resolved_diag_probe_path,
        authority_source_path=resolved_authority_source_path,
        controller_judgment_markdown=_load_text(controller_judgment_path),
        controller_judgment_path=controller_judgment_path,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 trade_write_authority_latest.json")
    parser.add_argument("--instance-root", type=Path, default=DEFAULT_INSTANCE_ROOT)
    parser.add_argument("--authority-source-path", type=Path, default=None)
    parser.add_argument("--diag-probe-path", type=Path, default=None)
    parser.add_argument("--current-status-path", type=Path, default=None)
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument("--print-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    instance_root = args.instance_root.expanduser().resolve()
    authority_source_path = (
        args.authority_source_path.expanduser().resolve()
        if args.authority_source_path is not None
        else (instance_root / "state" / "trade_resources" / "trade_write_authority_source_latest.json").resolve()
    )
    diag_probe_path = args.diag_probe_path.expanduser().resolve() if args.diag_probe_path is not None else None
    output_path = (
        args.output_path.expanduser().resolve()
        if args.output_path is not None
        else (instance_root / "state" / "trade_resources" / "trade_write_authority_latest.json").resolve()
    )
    report = build_from_paths(authority_source_path=authority_source_path, diag_probe_path=diag_probe_path)
    if not args.print_only:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
