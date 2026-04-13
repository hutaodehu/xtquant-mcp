from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from typing import Any


def is_prod_state_scope(state_root: str | Path) -> bool:
    parts = tuple(str(part).lower() for part in Path(state_root).parts)
    for idx in range(0, max(0, len(parts) - 2)):
        if parts[idx : idx + 3] == ("instance", "prod", "state"):
            return True
    return False


def state_scope_label(state_root: str | Path) -> str:
    return "prod" if is_prod_state_scope(state_root) else "non_prod"


def resource_truth_metadata(
    *,
    state_root: str | Path,
    authority: str,
    resource_path: str = "",
    server_ts: str = "",
    trace_id: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    emitted_at = now or datetime.now()
    state_scope = state_scope_label(state_root)
    path_text = str(resource_path or "").strip()
    cached_at = ""
    state_age_seconds: int | None = None
    if path_text:
        candidate = Path(path_text)
        if candidate.exists():
            cached_at_dt = datetime.fromtimestamp(candidate.stat().st_mtime)
            cached_at = cached_at_dt.isoformat(timespec="seconds")
            state_age_seconds = max(0, int((emitted_at - cached_at_dt).total_seconds()))

    freshness_status = authority
    if authority == "cached_last_known_state" and state_age_seconds is None:
        freshness_status = "cached_state_unknown_age"
    resource_server_ts = str(server_ts or "")
    if (not resource_server_ts) and authority == "live_runtime_truth":
        resource_server_ts = emitted_at.isoformat(timespec="seconds")

    return {
        "state_scope": state_scope,
        "freshness_status": freshness_status,
        "resource_authority": authority,
        "resource_emitted_at": emitted_at.isoformat(timespec="seconds"),
        "resource_cached_at": cached_at,
        "state_age_seconds": state_age_seconds,
        "resource_path": path_text,
        "resource_trace_id": str(trace_id or ""),
        "resource_server_ts": resource_server_ts,
    }


def health_runtime_truth_payload(
    *,
    server_name: str,
    bind_host: str,
    bind_port: int,
    config_path: str,
    audit_root: str,
    audit_filename: str,
    state_root: str | Path,
    artifact_root: str | Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    emitted_at = now or datetime.now()
    latest_audit_path = ""
    latest_audit_ts = ""
    latest_audit_age_seconds: int | None = None
    root = Path(audit_root)
    if root.exists():
        candidates = sorted(root.rglob(audit_filename), key=lambda item: item.stat().st_mtime, reverse=True)
        if candidates:
            latest = candidates[0]
            latest_dt = datetime.fromtimestamp(latest.stat().st_mtime)
            latest_audit_path = str(latest)
            latest_audit_ts = latest_dt.isoformat(timespec="seconds")
            latest_audit_age_seconds = max(0, int((emitted_at - latest_dt).total_seconds()))

    return {
        "server_ts": emitted_at.isoformat(timespec="seconds"),
        "freshness_status": "live_process_health",
        "process_identity": {
            "server_name": str(server_name or ""),
            "process_id": int(os.getpid()),
            "listener": f"{bind_host}:{int(bind_port)}",
            "config_path": str(config_path or ""),
        },
        "latest_audit_log": {
            "path": latest_audit_path,
            "server_ts": latest_audit_ts,
            "age_seconds": latest_audit_age_seconds,
        },
        "evidence_scope": state_scope_label(state_root),
        "evidence_state_root": str(state_root),
        "evidence_artifact_root": str(artifact_root),
    }
