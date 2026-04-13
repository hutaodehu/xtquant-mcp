from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import time
from typing import Any

from xtqmt_mcp.trade_ops import TradeOpsResult


_ERROR_META: dict[str, tuple[str, bool]] = {
    "server_env_not_ready": ("environment", False),
    "xtquant_import_failed": ("environment", False),
    "miniqmt_not_logged_in": ("environment", True),
    "account_asset_unavailable": ("environment", True),
    "session_warm_failed": ("environment", True),
    "session_not_ready": ("environment", True),
    "session_closed": ("environment", False),
    "probe_connection_unavailable": ("connectivity", True),
    "probe_connection_failed": ("connectivity", True),
    "qmt_read_precheck_failed": ("environment", True),
    "qmt_precheck_failed": ("environment", True),
    "write_permission_precheck_failed": ("environment", True),
    "connect_failed": ("connectivity", True),
    "subscribe_failed": ("connectivity", True),
    "snapshot_not_ready": ("connectivity", True),
    "connect_gate_failed": ("connectivity", True),
    "l1_snapshot_unavailable": ("market_data", True),
    "l1_price_missing": ("market_data", True),
    "depth_levels_unavailable": ("market_data", False),
    "guard_token_missing": ("risk", False),
    "invalid_price_mode": ("validation", False),
    "limit_price_requires_fixed_mode": ("validation", False),
    "limit_price_required": ("validation", False),
    "limit_price_non_positive": ("validation", False),
    "invalid_quantity": ("validation", False),
    "invalid_broker_order_id": ("validation", False),
    "market_closed": ("risk", False),
    "kill_switch_on": ("risk", False),
    "kill_switch_unconfigured": ("risk", False),
    "insufficient_cash": ("risk", False),
    "insufficient_sellable": ("risk", False),
    "order_not_found": ("broker", False),
    "order_not_cancelable": ("broker", False),
    "submit_exception": ("broker", True),
    "submit_failed": ("broker", True),
    "cancel_exception": ("broker", True),
}


def _infer_meta(code: str, *, default_category: str = "environment") -> tuple[str, bool]:
    if code in _ERROR_META:
        return _ERROR_META[code]
    if code.startswith("invalid_") or code.endswith("_required"):
        return ("validation", False)
    if code.startswith("insufficient_"):
        return ("risk", False)
    if code.endswith("_exception") or code.endswith("_failed"):
        return ("broker", True)
    return (default_category, False)


def _build_error(code: str, message: str, *, default_category: str = "environment") -> dict[str, Any]:
    category, retryable = _infer_meta(str(code or "server_env_not_ready"), default_category=default_category)
    return {
        "code": str(code or "server_env_not_ready"),
        "message": str(message or code or "gateway call failed"),
        "category": category,
        "retryable": bool(retryable),
    }


def envelope_from_trade_result(
    *,
    tool: str,
    result: TradeOpsResult,
    trace_id: str,
    started_at: float,
    artifacts: list[str],
    warnings: list[str] | None = None,
    server_ts: str | None = None,
) -> dict[str, Any]:
    payload = dict(result.payload or {})
    ok = bool(result.ok)
    warning_list = list(warnings or [])
    if payload.get("persist_ok") is False and "order_state_persist_failed" not in warning_list:
        warning_list.append("order_state_persist_failed")
    error = None
    if not ok:
        error_code = str(payload.get("error") or payload.get("code") or "server_env_not_ready")
        error_message = str(payload.get("message") or error_code)
        default_category = "connectivity" if tool == "probe.connection" else "environment"
        error = _build_error(error_code, error_message, default_category=default_category)
    return {
        "ok": ok,
        "tool": tool,
        "data": payload,
        "error": error,
        "audit": {
            "trace_id": trace_id,
            "server_ts": server_ts or datetime.now().isoformat(timespec="seconds"),
            "duration_ms": int(max(0.0, (time.monotonic() - started_at) * 1000.0)),
            "artifacts": list(artifacts),
        },
        "warnings": warning_list,
    }


def envelope_from_login_payload(
    *,
    tool: str,
    payload: dict[str, Any],
    trace_id: str,
    started_at: float,
    artifacts: list[str],
    warnings: list[str] | None = None,
    server_ts: str | None = None,
) -> dict[str, Any]:
    data = dict(payload or {})
    ok = bool(data.get("ok", False))
    error = None
    if not ok:
        error = _build_error(
            "miniqmt_not_logged_in",
            str(data.get("message") or data.get("status") or "MiniQMT login not ready"),
            default_category="environment",
        )
    return {
        "ok": ok,
        "tool": tool,
        "data": data,
        "error": error,
        "audit": {
            "trace_id": trace_id,
            "server_ts": server_ts or datetime.now().isoformat(timespec="seconds"),
            "duration_ms": int(max(0.0, (time.monotonic() - started_at) * 1000.0)),
            "artifacts": list(artifacts),
        },
        "warnings": list(warnings or []),
    }


def envelope_from_exception(
    *,
    tool: str,
    trace_id: str,
    started_at: float,
    error_code: str,
    message: str,
    artifacts: list[str],
    warnings: list[str] | None = None,
    server_ts: str | None = None,
    data: dict[str, Any] | None = None,
    default_category: str = "environment",
) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": tool,
        "data": dict(data or {}),
        "error": _build_error(error_code, message, default_category=default_category),
        "audit": {
            "trace_id": trace_id,
            "server_ts": server_ts or datetime.now().isoformat(timespec="seconds"),
            "duration_ms": int(max(0.0, (time.monotonic() - started_at) * 1000.0)),
            "artifacts": list(artifacts),
        },
        "warnings": list(warnings or []),
    }


def call_log_path(call_log_root: str, call_log_name: str, now: datetime | None = None) -> Path:
    stamp = now or datetime.now()
    daily_dir = Path(call_log_root) / stamp.strftime("%Y%m%d")
    return daily_dir / call_log_name


def append_call_log(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fd:
        fd.write(json.dumps(entry, ensure_ascii=False, sort_keys=True))
        fd.write("\n")

