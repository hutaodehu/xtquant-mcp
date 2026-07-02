from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import importlib
import inspect
import json
import os
from pathlib import Path
from queue import Empty, Queue
import sys
from threading import RLock, Thread
import time
from typing import Any, Callable, Protocol

from xtqmt_mcp.bundle import ensure_bundle_package_on_sys_path, validate_xtquant_bundle, xtquant_import_spec
from xtqmt_mcp.legacy_ports import (
    annotate_legacy_port,
    coerce_port,
    legacy_port_fields,
)
from xtqmt_mcp.runtime_support import port_ready

from .config import DataGatewayConfig
from .jobs import DownloadJobManager, DownloadJobRequest
from .qlib_runtime import (
    DEFAULT_LOCAL_QLIB_DIR_WINDOWS,
    DEFAULT_QLIB_DIR_WSL,
    DEFAULT_ROUTE_POLICY,
    RoutePolicy,
    _json_dump,
    _json_load,
    apply_residuals_to_acceptance,
    assess_qlib_acceptance,
    build_acceptance_verdict,
    build_integrity_plan,
    check_qlib_health,
    find_listen_port_from_logs,
    host_path_to_local,
    import_parquet_chunk,
    normalize_code,
    pull_history_chunk,
    required_manifest_files,
    resolve_core_indices_symbols,
    resolve_health_symbols_for_scope,
    resolve_runtime_qlib_path,
    inspect_trade_day,
    resolve_trade_day,
    resolve_universe,
    scan_changed_files,
    summarize_residuals,
    sync_manifest_files,
    upsert_metadata,
)


DEFAULT_INSTRUMENT_SECTORS: tuple[str, ...] = ("沪深A股", "上证A股", "深证A股", "北证A股")
SUBSCRIPTION_LEASE_GRACE_SECONDS = 15
SUBSCRIPTION_LEASE_STALE_SECONDS = 60
SUBSCRIPTION_RECONNECT_STRATEGY = "explicit_rebuild_required"


class XtDataBackend(Protocol):
    def get_sector_list(self) -> list[str]: ...
    def get_stock_list_in_sector(self, sector_name: str, real_timetag: Any = -1) -> list[str]: ...
    def get_instrument_detail_list(self, stock_list: list[str], iscomplete: bool = False) -> dict[str, dict[str, Any]]: ...
    def get_trading_dates(self, market: str, start_time: str = "", end_time: str = "", count: int = -1) -> list[Any]: ...
    def get_trading_calendar(self, market: str, start_time: str = "", end_time: str = "") -> list[Any]: ...
    def get_full_tick(self, code_list: list[str]) -> dict[str, Any]: ...
    def get_market_data_ex(self, field_list: list[str], stock_list: list[str], period: str, start_time: str = "", end_time: str = "", count: int = -1, dividend_type: str = "none", fill_data: bool = True) -> dict[str, Any]: ...
    def get_market_data(self, field_list: list[str], stock_list: list[str], period: str, start_time: str = "", end_time: str = "", count: int = -1, dividend_type: str = "none", fill_data: bool = True) -> Any: ...
    def download_history_data2(self, stock_list: list[str], period: str, start_time: str = "", end_time: str = "", callback: Callable[[dict[str, Any]], bool] | None = None, incrementally: bool | None = None) -> dict[str, Any]: ...
    def stop_download(self) -> None: ...
    def subscribe_quote2(self, stock_code: str, period: str = "tick", start_time: str = "", end_time: str = "", count: int = 0, dividend_type: str | None = None, callback: Callable[[dict[str, Any]], None] | None = None) -> int: ...
    def subscribe_quote(self, stock_code: str, period: str = "tick", start_time: str = "", end_time: str = "", count: int = 0, callback: Callable[[dict[str, Any]], None] | None = None) -> int: ...
    def unsubscribe_quote(self, seq: int) -> None: ...


class XtDataUnavailable(RuntimeError):
    def __init__(self, code: str, message: str, *, category: str = "environment", retryable: bool = False) -> None:
        super().__init__(message)
        self.code = str(code or "xtdata_unavailable")
        self.message = str(message or code or "xtdata unavailable")
        self.category = str(category or "environment")
        self.retryable = bool(retryable)


@dataclass(frozen=True)
class DataToolResult:
    ok: bool
    payload: dict[str, Any] = field(default_factory=dict)
    code: str = ""
    message: str = ""
    category: str = "environment"
    retryable: bool = False
    warnings: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()


@dataclass
class SubscriptionState:
    subscription_id: str
    codes: tuple[str, ...]
    period: str
    created_at: str
    start_time: str = ""
    end_time: str = ""
    count: int = 0
    dividend_type: str = "none"
    seqs: dict[str, int] = field(default_factory=dict)
    status: str = "running"
    event_count: int = 0
    last_event_at: str = ""
    last_event: dict[str, Any] = field(default_factory=dict)
    stop_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "subscription_id": self.subscription_id,
            "codes": list(self.codes),
            "period": self.period,
            "created_at": self.created_at,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "count": int(self.count),
            "dividend_type": self.dividend_type,
            "seqs": dict(self.seqs or {}),
            "status": self.status,
            "event_count": int(self.event_count),
            "last_event_at": self.last_event_at,
            "last_event": dict(self.last_event or {}),
            "stop_reason": self.stop_reason,
        }


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _clean_codes(values: Any, *, max_count: int) -> tuple[str, ...]:
    if isinstance(values, str):
        tokens = [part.strip() for part in values.split(",")]
    elif isinstance(values, (list, tuple, set)):
        tokens = [str(item).strip() for item in values]
    else:
        tokens = []
    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        code = token.upper()
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
        if len(out) >= max_count:
            break
    return tuple(out)


def _clean_sector_names(values: Any, *, max_count: int) -> tuple[str, ...]:
    if isinstance(values, str):
        tokens = [values]
    elif isinstance(values, (list, tuple, set)):
        tokens = [str(item).strip() for item in values]
    else:
        tokens = []
    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        name = str(token or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
        if len(out) >= max_count:
            break
    return tuple(out)


def _normalize_yyyymmdd(value: Any) -> str:
    text = _safe_str(value)
    if not text:
        return ""
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        digits = text[:10].replace("-", "")
        return digits if len(digits) == 8 and digits.isdigit() else ""
    digits_only = "".join(ch for ch in text if ch.isdigit())
    if len(digits_only) >= 8 and digits_only[:2] in {"19", "20"}:
        return digits_only[:8]
    normalized = _safe_str(_time_like_to_text(value))
    if len(normalized) >= 10 and normalized[4] == "-" and normalized[7] == "-":
        digits = normalized[:10].replace("-", "")
        return digits if len(digits) == 8 and digits.isdigit() else ""
    digits_only = "".join(ch for ch in normalized if ch.isdigit())
    if len(digits_only) >= 8 and digits_only[:2] in {"19", "20"}:
        return digits_only[:8]
    return ""


def _coerce_limit(value: Any, *, default: int, max_limit: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = int(default)
    return max(1, min(parsed or int(default), int(max_limit)))


def _split_stock_change_codes(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        raw_tokens: list[str] = []
        for item in value:
            raw_tokens.extend(_split_stock_change_codes(item))
        tokens = raw_tokens
    else:
        text = _safe_str(value)
        if not text:
            return ()
        for char in "[](){}\"'":
            text = text.replace(char, " ")
        tokens = []
        current: list[str] = []
        delimiters = {",", ";", "|", "\t", "\r", "\n", " ", "，", "、", "；"}
        for char in text:
            if char in delimiters:
                token = "".join(current).strip()
                if token:
                    tokens.append(token)
                current = []
            else:
                current.append(char)
        token = "".join(current).strip()
        if token:
            tokens.append(token)
    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        code = _safe_str(token).upper()
        if not code or code.lower() in {"none", "null", "nan"}:
            continue
        if not any(ch.isdigit() for ch in code):
            continue
        if code in seen:
            continue
        seen.add(code)
        out.append(code)
    return tuple(out)


def _record_first_value(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    lowered = {str(key).strip().lower(): value for key, value in record.items()}
    for key in keys:
        if key in record:
            return record[key]
        lowered_key = key.lower()
        if lowered_key in lowered:
            return lowered[lowered_key]
    return ""


def _sector_matches_category(name: str, category: str) -> bool:
    if not category:
        return True
    lower = name.lower()
    upper = name.upper()
    token = category.lower()
    if token in {"ths", "同花顺"}:
        return upper.startswith("THS") or "同花顺" in name or "ths" in lower
    if token in {"gn", "concept", "概念"}:
        return upper.startswith("GN") or "概念" in name or "gn" in lower
    if token in {"sw", "申万"}:
        return upper.startswith("SW") or "申万" in name or "sw" in lower
    if token in {"csrc", "证监会"}:
        return "证监会" in name or "csrc" in lower
    return token in lower


def _merge_arguments(arguments: dict[str, Any] | None, kwargs: dict[str, Any]) -> dict[str, Any]:
    merged = dict(arguments or {})
    merged.update(kwargs)
    return merged


def _normalize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        try:
            return isoformat()
        except Exception:
            pass
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _normalize_value(item())
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            return _normalize_value(tolist())
        except Exception:
            pass
    return str(value)


def _normalize_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _normalize_value(value) for key, value in mapping.items()}


def _merge_residual_item(residuals_by_symbol: dict[str, dict[str, Any]], payload: dict[str, Any]) -> None:
    symbol = normalize_code(_safe_str(payload.get("symbol", "")))
    if not symbol:
        return
    entry = residuals_by_symbol.setdefault(symbol, {"symbol": symbol})
    classification = _safe_str(payload.get("classification", ""))
    if classification:
        entry["classification"] = classification
    for key in ("periods_missing", "periods_stale"):
        values = [str(item).strip() for item in payload.get(key, []) if str(item).strip()]
        if not values:
            continue
        merged = set(str(item).strip() for item in entry.get(key, []) if str(item).strip())
        merged.update(values)
        entry[key] = sorted(merged)
    for key in ("reason", "last_bar_time", "target_trade_day"):
        value = _safe_str(payload.get(key, ""))
        if value:
            entry[key] = value


def _time_like_to_text(value: Any) -> str:
    normalized = _normalize_value(value)
    if normalized in (None, ""):
        return ""
    text = str(normalized)
    if text.isdigit():
        digits = len(text)
        if digits >= 13:
            try:
                return datetime.fromtimestamp(int(text[:13]) / 1000.0).isoformat(timespec="seconds")
            except Exception:
                return text
        if digits == 8:
            try:
                return datetime.strptime(text, "%Y%m%d").date().isoformat()
            except Exception:
                return text
    return text


def _frame_records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    reset_index = getattr(frame, "reset_index", None)
    if callable(reset_index):
        try:
            temp = reset_index()
            raw_columns = getattr(temp, "columns", None)
            columns = list(raw_columns) if raw_columns is not None else []
            if "index" in columns and "time" not in columns:
                temp = temp.rename(columns={"index": "time"})
            return [_normalize_mapping(dict(item)) for item in temp.to_dict(orient="records") if isinstance(item, dict)]
        except Exception:
            pass
    if isinstance(frame, list):
        return [_normalize_mapping(dict(item)) for item in frame if isinstance(item, dict)]
    if isinstance(frame, dict):
        return [_normalize_mapping(frame)]
    return []


def _progress_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(value)
    except Exception:
        return int(default)
    return parsed if parsed >= 0 else int(default)


def _format_chunk_progress_message(
    stage: str,
    period: str,
    *,
    cursor: Any,
    next_cursor: Any,
    chunk_batch_size: Any,
    symbols_total: Any,
    rows: Any | None = None,
    symbols_in_chunk: Any | None = None,
    imported_symbols_count: Any | None = None,
    changed_files_count: Any | None = None,
) -> str:
    cursor_value = _progress_int(cursor, 0)
    chunk_size = max(1, _progress_int(chunk_batch_size, 1))
    total_symbols = max(chunk_size, _progress_int(symbols_total, chunk_size))
    chunk_no = min((cursor_value // chunk_size) + 1, max(1, (total_symbols + chunk_size - 1) // chunk_size))
    chunk_total = max(1, (total_symbols + chunk_size - 1) // chunk_size)

    parts = [f"{stage}:{period}", f"chunk={chunk_no}/{chunk_total}", f"cursor={cursor_value}"]
    if rows is not None:
        parts.append(f"rows={_progress_int(rows, 0)}")
    if symbols_in_chunk is not None:
        parts.append(f"symbols={_progress_int(symbols_in_chunk, 0)}")
    if imported_symbols_count is not None:
        parts.append(f"imported={_progress_int(imported_symbols_count, 0)}")
    if changed_files_count is not None:
        parts.append(f"changed={_progress_int(changed_files_count, 0)}")
    if next_cursor is None:
        parts.append("next=done")
    else:
        parts.append(f"next={_progress_int(next_cursor, cursor_value)}")
    return " ".join(parts)


def _parse_progress_time(raw: Any) -> datetime | None:
    token = _safe_str(raw)
    if not token:
        return None
    try:
        return datetime.fromisoformat(token.replace("Z", "+00:00"))
    except ValueError:
        return None


def _local_timezone() -> Any:
    return datetime.now().astimezone().tzinfo


def _coerce_progress_time(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=_local_timezone())
    return value.astimezone(_local_timezone())


def _elapsed_progress_seconds(now_dt: datetime | None, previous_dt: datetime | None) -> int:
    now_value = _coerce_progress_time(now_dt)
    previous_value = _coerce_progress_time(previous_dt)
    if now_value is None or previous_value is None:
        return 0
    return max(0, int((now_value - previous_value).total_seconds()))


def _phase_elapsed_seconds(progress_samples: list[dict[str, Any]], *, current_phase: str, now_raw: Any) -> int:
    phase = _safe_str(current_phase)
    if not phase:
        return 0
    phase_started_at: datetime | None = None
    for sample in progress_samples:
        sample_phase = _progress_phase(str(sample.get("message") or ""), sample.get("current_phase"))
        if sample_phase != phase:
            continue
        parsed = _parse_progress_time(sample.get("ts"))
        if parsed is not None and phase_started_at is None:
            phase_started_at = parsed
    return _elapsed_progress_seconds(_parse_progress_time(now_raw), phase_started_at)


def _max_progress_int(progress_samples: list[dict[str, Any]], key: str) -> int:
    values: list[int] = []
    for sample in progress_samples:
        if key in sample:
            values.append(_progress_int(sample.get(key), 0))
    return max(values) if values else 0


def _last_progress_list(progress_samples: list[dict[str, Any]], key: str) -> list[Any]:
    for sample in reversed(progress_samples):
        value = sample.get(key)
        if isinstance(value, list):
            return list(value)
    return []


def _progress_phase(message: str, explicit_phase: Any = "") -> str:
    phase = _safe_str(explicit_phase)
    if phase:
        return phase
    prefix = _safe_str(message).split(":", 1)[0].strip().lower()
    if prefix == "pull":
        return "download"
    if prefix in {"download", "import", "materialize", "sync_wsl", "manifest", "acceptance"}:
        return prefix
    return prefix


def _expected_next_for_phase(phase: str, *, terminal: bool = False) -> str:
    if terminal:
        return "terminal"
    return {
        "download": "import",
        "import": "materialize",
        "materialize": "sync_wsl:start",
        "sync_wsl": "manifest:start",
        "manifest": "acceptance:start",
        "acceptance": "terminal",
    }.get(_safe_str(phase), "")


def _ticks_to_rows(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, dict):
        return [_normalize_mapping(payload)]
    if isinstance(payload, list):
        return [_normalize_mapping(dict(item)) for item in payload if isinstance(item, dict)]
    dtype = getattr(payload, "dtype", None)
    names = tuple(getattr(dtype, "names", ()) or ())
    if names:
        rows: list[dict[str, Any]] = []
        for row in payload:
            item: dict[str, Any] = {}
            for name in names:
                try:
                    item[str(name)] = _normalize_value(row[name])
                except Exception:
                    item[str(name)] = None
            rows.append(item)
        return rows
    return []


def _to_endpoint(host: str, port: int, *, source: str, port_ready_state: bool | None) -> dict[str, Any]:
    payload = {
        "host": _safe_str(host) or "127.0.0.1",
        "port": coerce_port(port, 0),
        "source": str(source or "configured"),
        "port_ready": None if port_ready_state is None else bool(port_ready_state),
    }
    return annotate_legacy_port(payload, payload["port"])


def _redact_legacy_endpoint(endpoint: Any) -> dict[str, Any]:
    return dict(endpoint) if isinstance(endpoint, dict) else {}


def _redact_legacy_port_evidence(port_evidence: Any) -> dict[str, Any]:
    if not isinstance(port_evidence, dict):
        return {}
    payload: dict[str, Any] = {}
    for key, value in port_evidence.items():
        if key in {"configured_endpoint", "resolved_runtime_endpoint"}:
            payload[str(key)] = _redact_legacy_endpoint(value)
        else:
            payload[str(key)] = value
    return payload


def _redact_legacy_job_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    payload = dict(result)
    if "port_evidence" in payload:
        payload["port_evidence"] = _redact_legacy_port_evidence(payload.get("port_evidence"))
    manifest = payload.get("manifest")
    if isinstance(manifest, dict) and "port_evidence" in manifest:
        manifest_payload = dict(manifest)
        manifest_payload["port_evidence"] = _redact_legacy_port_evidence(manifest.get("port_evidence"))
        payload["manifest"] = manifest_payload
    return payload


def _xtdatacenter_listen_default_port(config: DataGatewayConfig) -> int:
    try:
        ensure_bundle_package_on_sys_path(config.bundle)
        module = importlib.import_module("xtquant.xtdatacenter")
        listen_fn = getattr(module, "listen", None)
        if not callable(listen_fn):
            return 0
        signature = inspect.signature(listen_fn)
        default_value = signature.parameters.get("port").default
        return coerce_port(default_value, 0)
    except Exception:
        return 0


def _candidate_log_dirs(qmt_userdata: str) -> list[Path]:
    if not _safe_str(qmt_userdata):
        return []
    root = Path(qmt_userdata).expanduser()
    return [root / "log", root / "userdata_mini" / "log"]


def _resolve_xtdata_endpoint(
    config: DataGatewayConfig,
    *,
    probe_connect: bool,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    host = _safe_str(config.qmt.xtdata_host) or "127.0.0.1"
    configured_port = coerce_port(config.qmt.xtdata_port, 0)
    resolved_port = configured_port
    resolved_source = "configured" if configured_port > 0 else "unconfigured"
    env_port = ""
    for name in ("XTDATA_PORT", "QMT_XTDATA_PORT"):
        value = _safe_str(os.environ.get(name, "")) if "os" in globals() else ""
        if value.isdigit():
            env_port = value
            resolved_port = int(value)
            resolved_source = f"env:{name}"
            break
    log_path = ""
    if not env_port and _safe_str(config.qmt.qmt_userdata):
        for candidate in _candidate_log_dirs(config.qmt.qmt_userdata):
            port_value, hit = find_listen_port_from_logs(candidate)
            if port_value:
                resolved_port = int(port_value)
                resolved_source = "log_probe"
                log_path = hit
                break

    if resolved_port <= 0:
        default_port = _xtdatacenter_listen_default_port(config)
        if default_port > 0:
            resolved_port = default_port
            resolved_source = "xtdatacenter.listen_default"
    port_state = (
        port_ready(host=host, port=resolved_port)
        if probe_connect and resolved_port > 0
        else False if probe_connect else None
    )
    configured_endpoint = _to_endpoint(host, configured_port, source="configured", port_ready_state=None)
    resolved_runtime_endpoint = _to_endpoint(
        host,
        resolved_port,
        source="connectivity_probe" if probe_connect else resolved_source,
        port_ready_state=port_state,
    )
    resolved_runtime_endpoint["port_source"] = resolved_source
    if log_path:
        resolved_runtime_endpoint["port_source_log"] = log_path
    resolved_runtime_endpoint["matches_configured"] = (
        resolved_runtime_endpoint["host"] == configured_endpoint["host"]
        and int(resolved_runtime_endpoint["port"]) == int(configured_endpoint["port"])
    )
    configured_endpoint.update(legacy_port_fields(configured_port))
    resolved_runtime_endpoint.update(legacy_port_fields(resolved_port))
    connectivity_ready = (bool(port_state) if probe_connect else True) and resolved_port > 0
    return configured_endpoint, resolved_runtime_endpoint, connectivity_ready


def _parse_iso_datetime(value: Any) -> datetime | None:
    text = _safe_str(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _elapsed_seconds(now_dt: datetime | None, then_dt: datetime | None) -> int | None:
    if now_dt is None or then_dt is None:
        return None
    delta = int((now_dt - then_dt).total_seconds())
    return max(0, delta)


def _count_by_reason(items: list[dict[str, Any]], *, field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        reason = _safe_str(item.get(field))
        if not reason:
            continue
        counts[reason] = int(counts.get(reason, 0) or 0) + 1
    return counts


class DefaultXtDataBackend:
    def __init__(self, config: DataGatewayConfig) -> None:
        self._config = config

    def _load_module(self, *, require_connect: bool) -> Any:
        bundle_result = validate_xtquant_bundle(self._config.bundle)
        if not bundle_result.ok:
            raise XtDataUnavailable(
                "bundle_invalid",
                f"xtquant bundle invalid: {', '.join(bundle_result.missing_files) or bundle_result.package_root}",
                category="environment",
            )
        try:
            module = importlib.import_module("xtquant.xtdata")
        except Exception:
            ensure_bundle_package_on_sys_path(self._config.bundle)
            module = importlib.import_module("xtquant.xtdata")
        try:
            setattr(module, "enable_hello", False)
        except Exception:
            pass
        if require_connect:
            _, endpoint, endpoint_ready = _resolve_xtdata_endpoint(self._config, probe_connect=True)
            host = _safe_str(endpoint.get("host")) or "127.0.0.1"
            port = coerce_port(endpoint.get("port"), 0)
            if port <= 0:
                raise XtDataUnavailable(
                    "xtdata_port_unresolved",
                    "xtdata runtime endpoint is unresolved",
                    category="connectivity",
                    retryable=True,
                )
            if not endpoint_ready:
                raise XtDataUnavailable(
                    "xtdata_port_not_ready",
                    f"xtdata port not ready: {host}:{port}",
                    category="connectivity",
                    retryable=True,
                )
            try:
                module.connect(host, port)
            except Exception as exc:
                raise XtDataUnavailable(
                    "xtdata_connect_failed",
                    str(exc),
                    category="connectivity",
                    retryable=True,
                ) from exc
        return module

    def get_sector_list(self) -> list[str]:
        return list(self._load_module(require_connect=True).get_sector_list() or [])

    def get_stock_list_in_sector(self, sector_name: str, real_timetag: Any = -1) -> list[str]:
        return list(self._load_module(require_connect=True).get_stock_list_in_sector(sector_name, real_timetag) or [])

    def get_instrument_detail_list(self, stock_list: list[str], iscomplete: bool = False) -> dict[str, dict[str, Any]]:
        return dict(self._load_module(require_connect=True).get_instrument_detail_list(stock_list, iscomplete) or {})

    def get_trading_dates(self, market: str, start_time: str = "", end_time: str = "", count: int = -1) -> list[Any]:
        return list(self._load_module(require_connect=True).get_trading_dates(market, start_time, end_time, count) or [])

    def get_trading_calendar(self, market: str, start_time: str = "", end_time: str = "") -> list[Any]:
        return list(self._load_module(require_connect=True).get_trading_calendar(market, start_time, end_time) or [])

    def get_full_tick(self, code_list: list[str]) -> dict[str, Any]:
        return dict(self._load_module(require_connect=True).get_full_tick(code_list) or {})

    def get_market_data_ex(
        self,
        field_list: list[str],
        stock_list: list[str],
        period: str,
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        dividend_type: str = "none",
        fill_data: bool = True,
    ) -> dict[str, Any]:
        return dict(self._load_module(require_connect=True).get_market_data_ex(field_list, stock_list, period, start_time, end_time, count, dividend_type, fill_data) or {})

    def get_market_data(
        self,
        field_list: list[str],
        stock_list: list[str],
        period: str,
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        dividend_type: str = "none",
        fill_data: bool = True,
    ) -> Any:
        return self._load_module(require_connect=True).get_market_data(field_list, stock_list, period, start_time, end_time, count, dividend_type, fill_data)

    def download_history_data2(
        self,
        stock_list: list[str],
        period: str,
        start_time: str = "",
        end_time: str = "",
        callback: Callable[[dict[str, Any]], bool] | None = None,
        incrementally: bool | None = None,
    ) -> dict[str, Any]:
        return dict(self._load_module(require_connect=True).download_history_data2(stock_list, period, start_time, end_time, callback, incrementally) or {})

    def stop_download(self) -> None:
        client = self._load_module(require_connect=True).get_client()
        stop_fn = getattr(client, "stop_supply_history_data2", None)
        if callable(stop_fn):
            stop_fn()

    def subscribe_quote2(
        self,
        stock_code: str,
        period: str = "tick",
        start_time: str = "",
        end_time: str = "",
        count: int = 0,
        dividend_type: str | None = None,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> int:
        return int(self._load_module(require_connect=True).subscribe_quote2(stock_code, period, start_time, end_time, count, dividend_type, callback))

    def subscribe_quote(
        self,
        stock_code: str,
        period: str = "tick",
        start_time: str = "",
        end_time: str = "",
        count: int = 0,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> int:
        return int(self._load_module(require_connect=True).subscribe_quote(stock_code, period, start_time, end_time, count, callback))

    def unsubscribe_quote(self, seq: int) -> None:
        self._load_module(require_connect=True).unsubscribe_quote(int(seq))


class LoaderXtDataBackend:
    def __init__(self, loader: Callable[[bool], Any]) -> None:
        self._loader = loader

    def _module(self, require_connect: bool) -> Any:
        return self._loader(bool(require_connect))

    def get_sector_list(self) -> list[str]:
        fn = getattr(self._module(True), "get_sector_list", None)
        if not callable(fn):
            return []
        return list(fn() or [])

    def get_stock_list_in_sector(self, sector_name: str, real_timetag: Any = -1) -> list[str]:
        module = self._module(True)
        return list(module.get_stock_list_in_sector(sector_name, real_timetag) or [])

    def get_instrument_detail_list(self, stock_list: list[str], iscomplete: bool = False) -> dict[str, dict[str, Any]]:
        module = self._module(True)
        fn = getattr(module, "get_instrument_detail_list", None)
        if callable(fn):
            return dict(fn(stock_list, iscomplete) or {})
        single = getattr(module, "get_instrument_detail")
        return {code: dict(single(code, iscomplete) or {}) for code in stock_list}

    def get_trading_dates(self, market: str, start_time: str = "", end_time: str = "", count: int = -1) -> list[Any]:
        return list(self._module(True).get_trading_dates(market, start_time, end_time, count) or [])

    def get_trading_calendar(self, market: str, start_time: str = "", end_time: str = "") -> list[Any]:
        return list(self._module(True).get_trading_calendar(market, start_time, end_time) or [])

    def get_full_tick(self, code_list: list[str]) -> dict[str, Any]:
        return dict(self._module(True).get_full_tick(code_list) or {})

    def get_market_data_ex(
        self,
        field_list: list[str],
        stock_list: list[str],
        period: str,
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        dividend_type: str = "none",
        fill_data: bool = True,
    ) -> dict[str, Any]:
        module = self._module(True)
        fn = getattr(module, "get_market_data_ex")
        return dict(
            fn(
                field_list=field_list,
                stock_list=stock_list,
                period=period,
                start_time=start_time,
                end_time=end_time,
                count=count,
                dividend_type=dividend_type,
                fill_data=fill_data,
            )
            or {}
        )

    def get_market_data(
        self,
        field_list: list[str],
        stock_list: list[str],
        period: str,
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        dividend_type: str = "none",
        fill_data: bool = True,
    ) -> Any:
        module = self._module(True)
        fn = getattr(module, "get_market_data", None)
        if callable(fn):
            return fn(field_list, stock_list, period, start_time, end_time, count, dividend_type, fill_data)
        fallback = getattr(module, "get_market_data_ex", None) or getattr(module, "get_local_data")
        return fallback(
            field_list=field_list,
            stock_list=stock_list,
            period=period,
            start_time=start_time,
            end_time=end_time,
            count=count,
            dividend_type=dividend_type,
            fill_data=fill_data,
        )

    def download_history_data2(
        self,
        stock_list: list[str],
        period: str,
        start_time: str = "",
        end_time: str = "",
        callback: Callable[[dict[str, Any]], bool] | None = None,
        incrementally: bool | None = None,
    ) -> dict[str, Any]:
        return dict(self._module(True).download_history_data2(stock_list, period, start_time, end_time, callback, incrementally) or {})

    def stop_download(self) -> None:
        client = self._module(True).get_client()
        stop_fn = getattr(client, "stop_supply_history_data2", None)
        if callable(stop_fn):
            stop_fn()

    def subscribe_quote2(
        self,
        stock_code: str,
        period: str = "tick",
        start_time: str = "",
        end_time: str = "",
        count: int = 0,
        dividend_type: str | None = None,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> int:
        return int(self._module(True).subscribe_quote2(stock_code, period, start_time, end_time, count, dividend_type, callback))

    def subscribe_quote(
        self,
        stock_code: str,
        period: str = "tick",
        start_time: str = "",
        end_time: str = "",
        count: int = 0,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> int:
        module = self._module(True)
        fn = getattr(module, "subscribe_quote", None)
        if callable(fn):
            return int(fn(stock_code, period, start_time, end_time, count, callback))
        return int(self.subscribe_quote2(stock_code, period, start_time, end_time, count, None, callback))

    def unsubscribe_quote(self, seq: int) -> None:
        self._module(True).unsubscribe_quote(int(seq))


class DataGatewayService:
    def __init__(
        self,
        config: DataGatewayConfig,
        *,
        backend: XtDataBackend | None = None,
        xtdata_loader: Callable[[bool], Any] | None = None,
        now_fn: Callable[[], str] = lambda: datetime.now().isoformat(timespec="seconds"),
        uuid_factory: Callable[[], str] | None = None,
    ) -> None:
        self._config = config
        self._backend = backend or (LoaderXtDataBackend(xtdata_loader) if xtdata_loader is not None else DefaultXtDataBackend(config))
        self._now_fn = now_fn
        self._uuid_factory = uuid_factory or (lambda: f"xtdata-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}")
        self._lock = RLock()
        self._subscriptions_root = Path(config.service.subscriptions_root).expanduser().resolve()
        self._subscriptions_root.mkdir(parents=True, exist_ok=True)
        self._subscriptions: dict[str, SubscriptionState] = {}
        self._subscription_callbacks: dict[str, Callable[[dict[str, Any]], None]] = {}
        self._load_subscriptions()
        self._jobs = DownloadJobManager(
            config.service.jobs_root,
            run_download=self._run_download_job,
            cancel_download=self._cancel_download_job,
            max_concurrent_jobs=config.service.max_concurrent_jobs,
        )

    def _resolve_runtime_endpoint(self, *, probe_connect: bool) -> tuple[dict[str, Any], dict[str, Any], bool]:
        return _resolve_xtdata_endpoint(self._config, probe_connect=probe_connect)

    def _subscription_lease_payload(
        self,
        state: SubscriptionState,
        *,
        callback_registered: bool,
        configured_endpoint: dict[str, Any],
        resolved_runtime_endpoint: dict[str, Any],
        connection_alive: bool,
        now_text: str,
    ) -> dict[str, Any]:
        now_dt = _parse_iso_datetime(now_text)
        created_dt = _parse_iso_datetime(state.created_at)
        last_event_dt = _parse_iso_datetime(state.last_event_at)
        created_age_seconds = _elapsed_seconds(now_dt, created_dt)
        last_event_age_seconds = _elapsed_seconds(now_dt, last_event_dt)
        callback_loop_alive = bool(state.status == "running" and callback_registered and bool(state.seqs))
        observed_event = bool(int(state.event_count) > 0 and last_event_dt is not None)
        no_recent_event = False
        if state.status == "running":
            if int(state.event_count) <= 0:
                no_recent_event = created_age_seconds is not None and created_age_seconds > SUBSCRIPTION_LEASE_GRACE_SECONDS
            else:
                no_recent_event = last_event_age_seconds is not None and last_event_age_seconds > SUBSCRIPTION_LEASE_STALE_SECONDS

        lease_state = "active"
        rebuild_reason = ""
        if state.status != "running":
            lease_state = "stopped"
            rebuild_reason = state.stop_reason or "lease_stopped"
        elif not callback_loop_alive:
            lease_state = "stale"
            rebuild_reason = "callback_loop_not_alive"
        elif not connection_alive:
            lease_state = "stale"
            rebuild_reason = "xtdata_connection_lost"
        elif no_recent_event and int(state.event_count) <= 0:
            lease_state = "stale"
            rebuild_reason = "lease_never_observed_event"
        elif no_recent_event:
            lease_state = "stale"
            rebuild_reason = "lease_stale_no_recent_events"

        needs_rebuild = lease_state != "active"
        recovery_action = SUBSCRIPTION_RECONNECT_STRATEGY if needs_rebuild else "hold_lease"
        stop_reason = state.stop_reason or ""
        payload = state.as_dict()
        payload.update(
            {
                "experimental": True,
                "capability": {
                    "name": "xtdata.subscribe",
                    "model": "subscription_lease",
                    "stability": "experimental",
                    "proven_live_reconnect": False,
                    "reconnect_strategy": SUBSCRIPTION_RECONNECT_STRATEGY,
                },
                "configured_endpoint": dict(configured_endpoint),
                "resolved_runtime_endpoint": dict(resolved_runtime_endpoint),
                "lease_state": lease_state,
                "callback_registered": bool(callback_registered),
                "callback_loop_alive": bool(callback_loop_alive),
                "connection_alive": bool(connection_alive),
                "observed_event": bool(observed_event),
                "created_age_seconds": created_age_seconds,
                "last_event_age_seconds": last_event_age_seconds,
                "needs_rebuild": bool(needs_rebuild),
                "rebuild_reason": rebuild_reason or "ok",
                "recovery_action": recovery_action,
                "reconnect_strategy": SUBSCRIPTION_RECONNECT_STRATEGY,
                "health": {
                    "callback_loop_alive": bool(callback_loop_alive),
                    "connection_alive": bool(connection_alive),
                    "observed_event": bool(observed_event),
                    "last_event_at": state.last_event_at,
                    "last_event_age_seconds": last_event_age_seconds,
                    "created_age_seconds": created_age_seconds,
                    "needs_rebuild": bool(needs_rebuild),
                    "reason": rebuild_reason or "ok",
                },
                "recovery": {
                    "lease_state": lease_state,
                    "needs_rebuild": bool(needs_rebuild),
                    "rebuild_reason": rebuild_reason or "ok",
                    "recovery_action": recovery_action,
                    "reconnect_strategy": SUBSCRIPTION_RECONNECT_STRATEGY,
                    "proven_live_reconnect": False,
                    "callback_registered": bool(callback_registered),
                    "callback_loop_alive": bool(callback_loop_alive),
                    "connection_alive": bool(connection_alive),
                    "observed_event": bool(observed_event),
                    "stop_reason": stop_reason,
                    "last_event_at": state.last_event_at,
                    "last_event_age_seconds": last_event_age_seconds,
                    "created_age_seconds": created_age_seconds,
                    "resolved_runtime_endpoint": dict(resolved_runtime_endpoint),
                },
            }
        )
        return payload

    def _drop_subscription(self, subscription_id: str) -> None:
        with self._lock:
            self._subscriptions.pop(subscription_id, None)
            self._subscription_callbacks.pop(subscription_id, None)
        try:
            self._subscription_path(subscription_id).unlink(missing_ok=True)
        except Exception:
            pass

    def status(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        probe_connect = bool(arguments.get("probe_connect", True))
        probe_basic_query_requested = bool(arguments.get("probe_basic_query", True))
        probe_basic_query = True
        probe_metadata = bool(arguments.get("probe_metadata", True))
        probe_import = bool(arguments.get("probe_import", False))

        bundle_state = validate_xtquant_bundle(self._config.bundle)
        import_spec = xtquant_import_spec(self._config.bundle)
        import_spec_found = bool(import_spec)
        configured_endpoint, resolved_runtime_endpoint, connectivity_ready = self._resolve_runtime_endpoint(probe_connect=probe_connect)
        host = str(resolved_runtime_endpoint["host"])
        port = coerce_port(resolved_runtime_endpoint.get("port"), 0)
        legacy_port_detected = False

        import_ready = bool(bundle_state.ok and import_spec_found)
        import_error = ""
        if import_ready and probe_import:
            try:
                ensure_bundle_package_on_sys_path(self._config.bundle)
                importlib.import_module("xtquant.xtdata")
            except Exception as exc:
                import_error = str(exc)
                import_ready = False

        basic_query_ready = False
        basic_query_error = ""
        basic_query_sample_count = 0
        if import_ready and connectivity_ready:
            if not probe_basic_query:
                basic_query_ready = True
            else:
                try:
                    sample_days = self._backend.get_trading_dates("SH", count=1)
                    basic_query_sample_count = len(sample_days or [])
                    basic_query_ready = True
                except Exception as exc:
                    basic_query_error = str(exc)

        metadata_ready = False
        metadata_error = ""
        metadata_count = 0
        if import_ready and connectivity_ready:
            if not probe_metadata:
                metadata_ready = True
            else:
                try:
                    metadata = self._backend.get_sector_list()
                    metadata_count = len(metadata or [])
                    metadata_ready = metadata_count > 0
                except Exception as exc:
                    metadata_error = str(exc)

        jobs_payload = {
            "active": [self._format_bulk_job_status(item, include_result=False) for item in self._jobs.list_active()],
            "recent": [self._format_bulk_job_status(item, include_result=False) for item in self._jobs.list_all()[:5]],
        }
        subscriptions_payload = self.list_subscriptions_payload({"probe_connect": probe_connect})
        lease_items = list(subscriptions_payload.get("items", []))
        lease_running = int(subscriptions_payload.get("running_count", 0) or 0)
        lease_stopped = int(subscriptions_payload.get("stopped_count", 0) or 0)

        layers = {
            "import": {
                "ready": bool(import_ready),
                "blocking": True,
                "bundle_ok": bool(bundle_state.ok),
                "import_spec_found": import_spec_found,
                "import_spec_origin": str(getattr(import_spec, "origin", "") or ""),
                "probe_mode": "runtime_import" if probe_import else "spec_only",
                "error": import_error,
            },
            "connectivity": {
                "ready": bool(connectivity_ready),
                "blocking": True,
                "endpoint": dict(resolved_runtime_endpoint),
                "probe_enabled": bool(probe_connect),
            },
            "basic_query": {
                "ready": bool(basic_query_ready),
                "blocking": True,
                "probe_enabled": bool(probe_basic_query),
                "probe_requested": bool(probe_basic_query_requested),
                "required_for_ready": True,
                "sample_query": "get_trading_dates(SH,count=1)",
                "sample_count": int(basic_query_sample_count),
                "error": basic_query_error,
            },
            "metadata": {
                "ready": bool(metadata_ready),
                "blocking": False,
                "probe_enabled": bool(probe_metadata),
                "sector_count": int(metadata_count),
                "error": metadata_error,
            },
            "job": {
                "ready": True,
                "blocking": False,
                "active_count": len(jobs_payload["active"]),
                "recent_count": len(jobs_payload["recent"]),
            },
            "lease": {
                "ready": True,
                "blocking": False,
                "subscription_count": int(subscriptions_payload.get("count", 0) or 0),
                "active_count": int(subscriptions_payload.get("active_count", 0) or 0),
                "running_count": int(lease_running),
                "stopped_count": int(lease_stopped),
                "stale_count": int(subscriptions_payload.get("stale_count", 0) or 0),
                "needs_rebuild_count": int(subscriptions_payload.get("needs_rebuild_count", 0) or 0),
                "rebuild_reasons": dict(subscriptions_payload.get("rebuild_reasons") or {}),
                "reconnect_strategy": SUBSCRIPTION_RECONNECT_STRATEGY,
                "proven_live_reconnect": False,
            },
        }

        ready = bool(import_ready and connectivity_ready and basic_query_ready)
        reason = "ok"
        if not bundle_state.ok:
            reason = "bundle_invalid"
        elif not import_spec_found:
            reason = "xtdata_import_spec_missing"
        elif not import_ready:
            reason = "xtdata_import_failed"
        elif not connectivity_ready:
            reason = "xtdata_port_unresolved" if port <= 0 else "xtdata_port_not_ready"
        elif not basic_query_ready:
            reason = "xtdata_basic_query_failed"
        elif not metadata_ready:
            reason = "metadata_missing"

        warnings: list[str] = []
        if ready and not metadata_ready:
            if metadata_error:
                warnings.append(f"metadata_missing: {metadata_error}")
            else:
                warnings.append("metadata_missing: sector metadata is empty")

        payload = {
            "ready": ready,
            "reason": reason,
            "blocking_reason": "" if ready else reason,
            "legacy_archived_ports": legacy_port_fields()["legacy_archived_ports"],
            "legacy_port_detected": bool(legacy_port_detected),
            "bundle": bundle_state.as_dict(),
            "readiness": {
                "ready": ready,
                "core_blocking_layers": ["import", "connectivity", "basic_query"],
                "non_blocking_layers": ["metadata", "job", "lease"],
                "layers": layers,
            },
            "configured_endpoint": configured_endpoint,
            "resolved_runtime_endpoint": resolved_runtime_endpoint,
            "import_spec_found": import_spec_found,
            "import_ready": bool(import_ready),
            "import_error": import_error,
            "xtdata_port": {
                "host": host,
                "port": port,
                "ready": bool(connectivity_ready and basic_query_ready),
                "tcp_ready": bool(connectivity_ready),
                "native_probe_ready": bool(basic_query_ready),
                "legacy_port_detected": bool(legacy_port_detected),
                "blocking_reason": "",
            },
            "runtime": {
                "python_executable": str(sys.executable),
                "python_version": str(sys.version.split()[0]),
                "config_path": self._config.config_path,
            },
            "jobs": jobs_payload,
            "subscriptions": subscriptions_payload,
        }
        if ready:
            return DataToolResult(ok=True, payload=payload, warnings=tuple(warnings))
        if reason == "bundle_invalid":
            return DataToolResult(ok=False, payload=payload, code="bundle_invalid", message="xtquant bundle validation failed", category="environment")
        if reason == "xtdata_import_spec_missing":
            return DataToolResult(ok=False, payload=payload, code="xtdata_import_spec_missing", message="xtdata import spec not found", category="environment")
        if reason == "xtdata_import_failed":
            return DataToolResult(ok=False, payload=payload, code="xtdata_import_failed", message=import_error or "xtdata import failed", category="environment")
        if reason == "xtdata_port_unresolved":
            return DataToolResult(ok=False, payload=payload, code="xtdata_port_unresolved", message="xtdata runtime endpoint is unresolved", category="connectivity", retryable=True)
        if reason == "xtdata_port_not_ready":
            return DataToolResult(ok=False, payload=payload, code="xtdata_port_not_ready", message=f"xtdata port not ready: {host}:{port}", category="connectivity", retryable=True)
        return DataToolResult(ok=False, payload=payload, code="xtdata_basic_query_failed", message=basic_query_error or "xtdata basic query failed", category="connectivity", retryable=True)

    def status_summary(self) -> DataToolResult:
        return self.gateway_health()

    def gateway_health(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        return self.status(arguments, **kwargs)

    def calendar_resolve_trade_day(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        target_date = _safe_str(arguments.get("target_date", ""))
        if not target_date:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="calendar.resolve_trade_day.target_date is required", category="validation")
        payload = inspect_trade_day(
            self._backend,
            target_date,
            calendar_roots=(self._config.service.wsl_qlib_root, self._config.service.windows_qlib_root),
            wsl_distro_name=self._config.service.wsl_distro_name,
        )
        warnings = tuple(str(item).strip() for item in list(payload.get("warnings") or []) if str(item).strip())
        if not bool(payload.get("is_target_trade_day", False)):
            resolved_target = str(payload.get("target_date") or target_date).strip() or target_date
            official_status_code = str(payload.get("official_status_code") or "").strip()
            if official_status_code == "official_calendar_unreachable":
                return DataToolResult(
                    ok=False,
                    payload=payload,
                    code="official_calendar_unreachable",
                    message=str(payload.get("official_summary") or "官方在线双源不可达"),
                    category="connectivity",
                    retryable=True,
                    warnings=warnings,
                )
            if official_status_code == "official_calendar_conflict":
                return DataToolResult(
                    ok=False,
                    payload=payload,
                    code="official_calendar_conflict",
                    message=str(payload.get("official_summary") or "官方在线双源交易日历结论冲突"),
                    category="validation",
                    retryable=False,
                    warnings=warnings,
                )
            return DataToolResult(
                ok=False,
                payload=payload,
                code="target_date_not_trade_day",
                message=f"目标日期 {resolved_target} 未被确认是交易日",
                category="validation",
                warnings=warnings,
            )
        return DataToolResult(ok=True, payload=payload, warnings=warnings)

    def integrity_plan(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        target_date = _safe_str(arguments.get("target_date", ""))
        if not target_date:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="integrity.plan.target_date is required", category="validation")
        raw_periods = arguments.get("periods", ["1d"])
        periods = [str(item).strip() for item in raw_periods if str(item).strip()] if isinstance(raw_periods, (list, tuple)) else ["1d"]
        mode = _safe_str(arguments.get("mode", "tail")) or "tail"
        lookback_trading_days = int(arguments.get("lookback_trading_days", 20) or 20)
        symbols_scope = _safe_str(arguments.get("symbols_scope", "all_a")) or "all_a"
        plan = build_integrity_plan(
            self._backend,
            target_date=target_date,
            periods=periods,
            mode=mode,
            lookback_trading_days=lookback_trading_days,
            symbols_scope=symbols_scope,
            metadata_path=Path(self._config.service.metadata_path),
            route_policy=RoutePolicy(
                max_symbols_mcp=int(arguments.get("max_symbols_mcp", DEFAULT_ROUTE_POLICY.max_symbols_mcp) or DEFAULT_ROUTE_POLICY.max_symbols_mcp),
                max_trading_days_mcp=int(arguments.get("max_trading_days_mcp", DEFAULT_ROUTE_POLICY.max_trading_days_mcp) or DEFAULT_ROUTE_POLICY.max_trading_days_mcp),
                max_estimated_bars_mcp=int(arguments.get("max_estimated_bars_mcp", DEFAULT_ROUTE_POLICY.max_estimated_bars_mcp) or DEFAULT_ROUTE_POLICY.max_estimated_bars_mcp),
            ),
            plans_root=Path(self._config.service.plans_root),
            cache_root=Path(self._config.service.cache_root),
            calendar_roots=(self._config.service.wsl_qlib_root, self._config.service.windows_qlib_root),
            wsl_distro_name=self._config.service.wsl_distro_name,
        )
        return DataToolResult(ok=True, payload=plan)

    def bulk_sync_job_submit(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        target_date = _safe_str(arguments.get("target_date", ""))
        if not target_date:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="bulk.sync_job.submit.target_date is required", category="validation")
        raw_periods = arguments.get("periods", ["1d"])
        periods = tuple(str(item).strip() for item in raw_periods if str(item).strip()) if isinstance(raw_periods, (list, tuple)) else ("1d",)
        if not periods:
            periods = ("1d",)
        local_qlib_dir = _safe_str(arguments.get("local_qlib_dir", "")) or self._config.service.windows_qlib_root or DEFAULT_LOCAL_QLIB_DIR_WINDOWS
        wsl_qlib_dir = _safe_str(arguments.get("wsl_qlib_dir", "")) or self._config.service.wsl_qlib_root or DEFAULT_QLIB_DIR_WSL
        raw_future_day_calendar = arguments.get("future_day_calendar", [])
        if isinstance(raw_future_day_calendar, (list, tuple)):
            future_day_calendar = tuple(str(item).strip() for item in raw_future_day_calendar if str(item).strip())
        else:
            future_day_calendar = tuple()
        calendar_snapshot_year = int(arguments.get("calendar_snapshot_year", 0) or 0)
        try:
            payload = self._jobs.submit(
                DownloadJobRequest(
                    job_kind="bulk_sync",
                    codes=(),
                    period=periods[0],
                    start_time=_safe_str(arguments.get("start_time", "")),
                    end_time=_safe_str(arguments.get("end_time", "")),
                    incrementally=arguments.get("incrementally"),
                    target_date=target_date,
                    periods=periods,
                    symbols_scope=_safe_str(arguments.get("symbols_scope", "all_a")) or "all_a",
                    local_qlib_dir=local_qlib_dir,
                    wsl_qlib_dir=wsl_qlib_dir,
                    adjusted_mode=_safe_str(arguments.get("adjusted_mode", "raw_with_factor")) or "raw_with_factor",
                    calendar_snapshot_year=calendar_snapshot_year,
                    future_day_calendar=future_day_calendar,
                )
            )
        except RuntimeError as exc:
            return DataToolResult(ok=False, payload={"active": self._jobs.list_active()}, code=str(exc), message=str(exc), category="queue", retryable=True)
        response = self.bulk_sync_job_status({"job_id": str(payload.get("job_id") or "")}).payload
        return DataToolResult(ok=True, payload=response, artifacts=tuple(response.get("artifacts", [])))

    def bulk_sync_job_status(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        job_id = _safe_str(arguments.get("job_id", ""))
        if not job_id:
            active = [self._format_bulk_job_status(item) for item in self._jobs.list_active()]
            recent = [self._format_bulk_job_status(item) for item in self._jobs.list_all()[:20]]
            return DataToolResult(ok=True, payload={"active": active, "recent": recent})
        try:
            payload = self._format_bulk_job_status(self._jobs.status(job_id))
        except KeyError:
            return DataToolResult(ok=False, payload={}, code="bulk_job_not_found", message=f"bulk job not found: {job_id}", category="validation")
        return DataToolResult(ok=payload.get("state") != "failed", payload=payload, code="bulk_sync_failed" if payload.get("state") == "failed" else "")

    def bulk_sync_job_cancel(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        job_id = _safe_str(arguments.get("job_id", ""))
        if not job_id:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="bulk.sync_job.cancel.job_id is required", category="validation")
        try:
            payload = self._format_bulk_job_status(self._jobs.cancel(job_id))
        except KeyError:
            return DataToolResult(ok=False, payload={}, code="bulk_job_not_found", message=f"bulk job not found: {job_id}", category="validation")
        return DataToolResult(ok=payload.get("state") != "failed", payload=payload, code="bulk_sync_failed" if payload.get("state") == "failed" else "")

    def artifact_manifest(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        job_id = _safe_str(arguments.get("job_id", ""))
        if not job_id:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="artifact.manifest.job_id is required", category="validation")
        status_payload = self.bulk_sync_job_status({"job_id": job_id}).payload
        manifest_path = _safe_str(status_payload.get("manifest_path", ""))
        if not manifest_path:
            return DataToolResult(ok=False, payload={}, code="manifest_not_ready", message=f"job_id={job_id} 尚未生成 manifest", category="state", retryable=True)
        manifest = _json_load(host_path_to_local(manifest_path))
        return DataToolResult(ok=True, payload=manifest)

    def qlib_health_check(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        qlib_dir = _safe_str(arguments.get("qlib_dir", ""))
        period = _safe_str(arguments.get("period", ""))
        if not qlib_dir or not period:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="qlib.health.check 需要 qlib_dir 和 period", category="validation")
        try:
            payload = check_qlib_health(
                qlib_dir,
                period,
                symbols=[str(item) for item in arguments.get("symbols", []) if str(item).strip()] if isinstance(arguments.get("symbols"), (list, tuple)) else None,
                wsl_distro_name=self._config.service.wsl_distro_name,
            )
        except ValueError as exc:
            return DataToolResult(ok=False, payload={}, code="validation_error", message=str(exc), category="validation")
        return DataToolResult(ok=True, payload=payload)

    def qlib_acceptance_check(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        qlib_dir = _safe_str(arguments.get("qlib_dir", ""))
        target_trade_day = _safe_str(arguments.get("target_trade_day", ""))
        raw_periods = arguments.get("periods", ["1d"])
        periods = [str(item).strip() for item in raw_periods if str(item).strip()] if isinstance(raw_periods, (list, tuple)) else ["1d"]
        if not qlib_dir or not target_trade_day:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="qlib.acceptance.check 需要 qlib_dir 和 target_trade_day", category="validation")
        try:
            acceptance_summary = assess_qlib_acceptance(
                qlib_dir=qlib_dir,
                periods=periods,
                target_trade_day=target_trade_day,
                wsl_distro_name=self._config.service.wsl_distro_name,
            )
        except ValueError as exc:
            return DataToolResult(ok=False, payload={}, code="validation_error", message=str(exc), category="validation")
        residual_summary = summarize_residuals(arguments.get("residuals", []) if isinstance(arguments.get("residuals"), list) else [])
        acceptance_summary = apply_residuals_to_acceptance(acceptance_summary, residual_summary)
        verdict = build_acceptance_verdict(acceptance_summary, residual_summary)
        payload = {
            "verdict": verdict,
            "qlib_dir": qlib_dir,
            "target_trade_day": target_trade_day,
            "periods": periods,
            "acceptance_summary": acceptance_summary,
            "residual_summary": residual_summary,
        }
        return DataToolResult(ok=verdict != "fail", payload=payload, code="qlib_acceptance_failed" if verdict == "fail" else "")

    def instruments_search(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        query = _safe_str(arguments.get("query", "")).lower()
        raw_sectors = arguments.get("sectors", [])
        sectors = tuple(str(item).strip() for item in raw_sectors if str(item).strip()) if isinstance(raw_sectors, (list, tuple)) else ()
        sectors = sectors or DEFAULT_INSTRUMENT_SECTORS
        limit = max(1, min(int(arguments.get("limit", 50) or 50), 500))
        iscomplete = bool(arguments.get("is_complete", False))
        codes: list[str] = []
        seen: set[str] = set()
        sector_members: dict[str, set[str]] = {}
        for sector in sectors:
            members = {_safe_str(code).upper() for code in self._backend.get_stock_list_in_sector(sector) if _safe_str(code)}
            sector_members[sector] = members
            for code in members:
                if code in seen:
                    continue
                seen.add(code)
                codes.append(code)
        details = self._backend.get_instrument_detail_list(codes, iscomplete=iscomplete)
        items: list[dict[str, Any]] = []
        for code in codes:
            detail = dict(details.get(code) or {})
            name = _safe_str(detail.get("InstrumentName") or detail.get("StockName") or detail.get("ProductName") or detail.get("Name"))
            if query and (query not in code.lower()) and (query not in name.lower()):
                continue
            items.append(
                {
                    "code": code,
                    "name": name,
                    "exchange": _safe_str(detail.get("ExchangeCode") or detail.get("market")),
                    "instrument_type": _safe_str(detail.get("InstrumentType") or detail.get("ProductID") or detail.get("ProductType")),
                    "sector_hits": [sector for sector, members in sector_members.items() if code in members],
                    "detail": _normalize_mapping(detail) if iscomplete else _normalize_mapping({key: detail.get(key) for key in ("InstrumentName", "ExchangeCode", "OpenDate", "ExpireDate", "InstrumentType", "ProductID", "IsTrading") if key in detail}),
                }
            )
            if len(items) >= limit:
                break
        return DataToolResult(ok=True, payload={"query": query, "sectors": list(sectors), "count": len(items), "items": items, "rows": items})

    def sector_list(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        keyword = _safe_str(arguments.get("keyword", "")).lower()
        category = _safe_str(arguments.get("category", ""))
        limit = _coerce_limit(arguments.get("limit", 500), default=500, max_limit=5000)
        raw_names = _clean_sector_names(self._backend.get_sector_list(), max_count=20000)
        items: list[dict[str, Any]] = []
        matched_count = 0
        for sector_name in raw_names:
            haystack = sector_name.lower()
            if keyword and keyword not in haystack:
                continue
            if not _sector_matches_category(sector_name, category):
                continue
            matched_count += 1
            if len(items) >= limit:
                continue
            items.append(
                {
                    "sector_name": sector_name,
                    "source": "xtdata.get_sector_list",
                    "contains_add_date": False,
                    "contains_effective_date": False,
                }
            )
        date_semantics = (
            "membership_snapshot_only: xtdata.get_sector_list returns sector names only; "
            "use sector.change_history stocklistchange events for add/remove dates"
        )
        payload = {
            "keyword": keyword,
            "category": category,
            "available_count": len(raw_names),
            "matched_count": matched_count,
            "count": len(items),
            "limit": limit,
            "date_semantics": date_semantics,
            "items": items,
            "rows": items,
        }
        return DataToolResult(ok=True, payload=payload)

    def sector_members_at(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        sector_name = _safe_str(arguments.get("sector_name", ""))
        if not sector_name:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="sector.members_at 需要 sector_name", category="validation")
        asof_raw = _safe_str(arguments.get("asof_date", arguments.get("date", "")))
        asof_date = ""
        real_timetag: Any = -1
        if asof_raw:
            asof_date = _normalize_yyyymmdd(asof_raw)
            if not asof_date:
                return DataToolResult(ok=False, payload={"field": "asof_date", "value": asof_raw}, code="validation_error", message="asof_date must be YYYYMMDD or YYYY-MM-DD", category="validation")
            real_timetag = asof_date
        limit = _coerce_limit(arguments.get("limit", self._config.service.max_query_symbols), default=self._config.service.max_query_symbols, max_limit=20000)
        members = _split_stock_change_codes(self._backend.get_stock_list_in_sector(sector_name, real_timetag=real_timetag))
        rows = [{"sector_name": sector_name, "stock_code": code} for code in members[:limit]]
        date_semantics = (
            "membership_as_of: xtdata.get_stock_list_in_sector(real_timetag) returns the member list for that target time; "
            "it does not return per-stock add_date/effective_date"
            if asof_date
            else "latest_membership_snapshot_only: no asof_date was provided; do not use this result as historical labels"
        )
        payload = {
            "sector_name": sector_name,
            "asof_date": asof_date,
            "real_timetag": real_timetag,
            "point_in_time": bool(asof_date),
            "contains_add_date": False,
            "contains_effective_date": False,
            "date_semantics": date_semantics,
            "count": len(rows),
            "total_count": len(members),
            "limit": limit,
            "items": rows,
            "rows": rows,
            "backtest_guard": "membership_check_only_not_join_date",
        }
        warnings = ("latest_label_snapshot_used_for_history is fail_design without stocklistchange events",) if not asof_date else ()
        return DataToolResult(ok=True, payload=payload, warnings=warnings)

    def sector_change_history(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        sector_name = _safe_str(arguments.get("sector_name", ""))
        if not sector_name:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="sector.change_history 需要 sector_name", category="validation")
        start_raw = _safe_str(arguments.get("start_date", arguments.get("start_time", "")))
        end_raw = _safe_str(arguments.get("end_date", arguments.get("end_time", "")))
        start_date = _normalize_yyyymmdd(start_raw) if start_raw else ""
        end_date = _normalize_yyyymmdd(end_raw) if end_raw else ""
        if start_raw and not start_date:
            return DataToolResult(ok=False, payload={"field": "start_date", "value": start_raw}, code="validation_error", message="start_date must be YYYYMMDD or YYYY-MM-DD", category="validation")
        if end_raw and not end_date:
            return DataToolResult(ok=False, payload={"field": "end_date", "value": end_raw}, code="validation_error", message="end_date must be YYYYMMDD or YYYY-MM-DD", category="validation")
        limit = _coerce_limit(arguments.get("limit", 5000), default=5000, max_limit=50000)
        base_payload = {
            "sector_name": sector_name,
            "start_date": start_date,
            "end_date": end_date,
            "source_period": "stocklistchange",
            "source": "xtdata.get_market_data_ex",
            "raw_row_count": 0,
            "date_available": False,
            "backtest_guard": "effective_date_lte_decision_date_only",
            "failure_policy": "do_not_backfill_latest_membership",
            "reason": "source_not_point_in_time",
            "count": 0,
            "limit": limit,
            "items": [],
            "rows": [],
        }
        try:
            raw = self._backend.get_market_data_ex([], [sector_name], "stocklistchange", start_date, end_date, -1, "none", False)
        except Exception as exc:
            payload = dict(base_payload)
            payload["source_error"] = str(exc)
            return DataToolResult(
                ok=False,
                payload=payload,
                code="point_in_time_source_missing",
                message=f"stocklistchange unavailable: {exc}",
                category="environment",
                retryable=True,
                warnings=("latest_label_snapshot_used_for_history is fail_design",),
            )
        raw_frame: Any = raw
        if isinstance(raw, dict):
            if sector_name in raw:
                raw_frame = raw.get(sector_name)
            elif len(raw) == 1:
                raw_frame = next(iter(raw.values()))
        records = _frame_records(raw_frame)
        add_keys = ("0", "add", "in", "stock_in", "add_stock", "added", "调入成份股", "调入", "加入")
        remove_keys = ("1", "remove", "out", "stock_out", "remove_stock", "removed", "调出成份股", "调出", "剔除")
        observed_at = _safe_str(self._now_fn())
        events: list[dict[str, Any]] = []
        for record in records:
            effective_date = _normalize_yyyymmdd(record.get("time") or record.get("date") or record.get("datetime") or record.get("trade_date"))
            for action, keys in (("add", add_keys), ("remove", remove_keys)):
                codes = _split_stock_change_codes(_record_first_value(record, keys))
                for code in codes:
                    if not effective_date:
                        continue
                    events.append(
                        {
                            "sector_name": sector_name,
                            "stock_code": code,
                            "action": action,
                            "effective_date": effective_date,
                            "source_period": "stocklistchange",
                            "observed_at": observed_at,
                        }
                    )
                    if len(events) >= limit:
                        break
                if len(events) >= limit:
                    break
            if len(events) >= limit:
                break
        base_payload.update(
            {
                "raw_row_count": len(records),
                "date_available": bool(events),
                "reason": "source_not_point_in_time" if not events else "",
                "count": len(events),
                "items": events,
                "rows": events,
            }
        )
        if not events:
            return DataToolResult(
                ok=False,
                payload=base_payload,
                code="point_in_time_source_missing",
                message="stocklistchange did not return parseable add/remove events; latest sector members must not be backfilled into history",
                category="validation",
                warnings=("latest_label_snapshot_used_for_history is fail_design",),
            )
        return DataToolResult(ok=True, payload=base_payload)

    def calendar_query(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        market = _safe_str(arguments.get("market", "SH")) or "SH"
        start_time = _safe_str(arguments.get("start_time", ""))
        end_time = _safe_str(arguments.get("end_time", ""))
        count = int(arguments.get("count", -1) or -1)
        mode = _safe_str(arguments.get("mode", "dates")).lower() or "dates"
        values = self._backend.get_trading_calendar(market, start_time, end_time) if mode == "calendar" else self._backend.get_trading_dates(market, start_time, end_time, count)
        return DataToolResult(ok=True, payload={"market": market, "mode": mode, "start_time": start_time, "end_time": end_time, "count": len(values), "trading_days": [_time_like_to_text(item) for item in values]})

    def snapshot_batch(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        codes = _clean_codes(arguments.get("codes"), max_count=self._config.service.max_query_symbols)
        if not codes:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="xtdata.snapshot.batch.codes is required", category="validation")
        raw = self._backend.get_full_tick(list(codes))
        items: list[dict[str, Any]] = []
        rows: list[dict[str, Any]] = []
        for code in codes:
            payload = raw.get(code) if isinstance(raw, dict) else None
            item = _normalize_mapping(dict(payload or {})) if isinstance(payload, dict) else {}
            item["code"] = code
            if "time" in item:
                item["time"] = _time_like_to_text(item.get("time"))
            items.append(item)
            rows.append({"code": code, "snapshot": item})
        return DataToolResult(ok=True, payload={"count": len(items), "items": items, "rows": rows})

    def history_get_bars(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        codes = _clean_codes(arguments.get("codes"), max_count=self._config.service.max_query_symbols)
        if not codes:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="xtdata.history.get_bars.codes is required", category="validation")
        raw_fields = arguments.get("fields", ["open", "high", "low", "close", "volume", "amount"])
        fields = [str(item).strip() for item in raw_fields if str(item).strip()] if isinstance(raw_fields, (list, tuple)) else ["open", "high", "low", "close", "volume", "amount"]
        period = _safe_str(arguments.get("period", "1d")) or "1d"
        start_time = _safe_str(arguments.get("start_time", ""))
        end_time = _safe_str(arguments.get("end_time", ""))
        count = int(arguments.get("count", arguments.get("limit_per_symbol", -1)) or -1)
        dividend_type = _safe_str(arguments.get("dividend_type", "none")) or "none"
        fill_data = bool(arguments.get("fill_data", True))
        data = self._backend.get_market_data_ex(fields, list(codes), period, start_time, end_time, count, dividend_type, fill_data)
        items: dict[str, list[dict[str, Any]]] = {}
        for code in codes:
            records = _frame_records(data.get(code) if isinstance(data, dict) else None)
            for record in records:
                if "time" in record:
                    record["time"] = _time_like_to_text(record.get("time"))
            items[code] = records
        if count > 0:
            items = {code: rows[-count:] for code, rows in items.items()}
        return DataToolResult(ok=True, payload={"codes": list(codes), "period": period, "fields": fields, "start_time": start_time, "end_time": end_time, "count_limit": count, "items": items, "rows": items})

    def history_get_ticks(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        codes = _clean_codes(arguments.get("codes"), max_count=self._config.service.max_query_symbols)
        if not codes:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="xtdata.history.get_ticks.codes is required", category="validation")
        raw_fields = arguments.get("fields", ["time", "lastPrice", "volume", "amount"])
        fields = [str(item).strip() for item in raw_fields if str(item).strip()] if isinstance(raw_fields, (list, tuple)) else ["time", "lastPrice", "volume", "amount"]
        start_time = _safe_str(arguments.get("start_time", ""))
        end_time = _safe_str(arguments.get("end_time", ""))
        count = int(arguments.get("count", arguments.get("limit_per_symbol", -1)) or -1)
        dividend_type = _safe_str(arguments.get("dividend_type", "none")) or "none"
        payload = self._backend.get_market_data(fields, list(codes), "tick", start_time, end_time, count, dividend_type, False)
        items: dict[str, list[dict[str, Any]]] = {}
        if isinstance(payload, dict):
            for code in codes:
                rows = _ticks_to_rows(payload.get(code))
                for row in rows:
                    if "time" in row:
                        row["time"] = _time_like_to_text(row.get("time"))
                items[code] = rows
        if count > 0:
            items = {code: rows[-count:] for code, rows in items.items()}
        return DataToolResult(ok=True, payload={"codes": list(codes), "start_time": start_time, "end_time": end_time, "count_limit": count, "items": items, "rows": items})

    def download_submit(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        codes = _clean_codes(arguments.get("codes"), max_count=self._config.service.max_query_symbols)
        if not codes:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="xtdata.download.submit.codes is required", category="validation")
        try:
            payload = self._jobs.submit(
                DownloadJobRequest(
                    codes=codes,
                    period=_safe_str(arguments.get("period", "1d")) or "1d",
                    start_time=_safe_str(arguments.get("start_time", "")),
                    end_time=_safe_str(arguments.get("end_time", "")),
                    incrementally=arguments.get("incrementally"),
                )
            )
        except RuntimeError as exc:
            return DataToolResult(ok=False, payload={"active": self._jobs.list_active()}, code=str(exc), message=str(exc), category="queue", retryable=True)
        return DataToolResult(ok=True, payload=payload, artifacts=tuple(payload.get("artifacts", [])))

    def download_status(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        job_id = _safe_str(arguments.get("job_id", ""))
        if not job_id:
            return DataToolResult(ok=True, payload={"active": self._jobs.list_active(), "recent": self._jobs.list_all()[:20]})
        try:
            payload = self._jobs.status(job_id)
        except KeyError:
            return DataToolResult(ok=False, payload={}, code="download_job_not_found", message=f"download job not found: {job_id}", category="validation")
        progress = {
            "finished": int(payload.get("progress_finished", 0) or 0),
            "total": int(payload.get("progress_total", 0) or 0),
            "message": str(payload.get("progress_message", "") or ""),
        }
        payload = dict(payload)
        payload["progress"] = progress
        return DataToolResult(ok=payload.get("status") != "failed", payload=payload, code="download_failed" if payload.get("status") == "failed" else "")

    def download_cancel(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        job_id = _safe_str(arguments.get("job_id", ""))
        if not job_id:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="xtdata.download.cancel.job_id is required", category="validation")
        try:
            payload = self._jobs.cancel(job_id)
        except KeyError:
            return DataToolResult(ok=False, payload={}, code="download_job_not_found", message=f"download job not found: {job_id}", category="validation")
        return DataToolResult(ok=True, payload=payload)

    def subscribe_start(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        codes = _clean_codes(arguments.get("codes"), max_count=min(self._config.service.max_query_symbols, 50))
        if not codes:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="xtdata.subscribe.start.codes is required", category="validation")
        subscription_id = self._uuid_factory()
        period = _safe_str(arguments.get("period", "tick")) or "tick"
        start_time = _safe_str(arguments.get("start_time", ""))
        end_time = _safe_str(arguments.get("end_time", ""))
        count = int(arguments.get("count", 0) or 0)
        dividend_type = _safe_str(arguments.get("dividend_type", "none")) or "none"
        state = SubscriptionState(subscription_id=subscription_id, codes=codes, period=period, created_at=self._now_fn(), start_time=start_time, end_time=end_time, count=count, dividend_type=dividend_type)

        def on_data(payload: dict[str, Any]) -> None:
            with self._lock:
                current = self._subscriptions.get(subscription_id)
                if current is None:
                    return
                current.event_count += 1
                current.last_event_at = self._now_fn()
                current.last_event = _normalize_mapping(dict(payload or {})) if isinstance(payload, dict) else {"payload": _normalize_value(payload)}
                self._persist_subscription(current)

        with self._lock:
            self._subscriptions[subscription_id] = state
            self._subscription_callbacks[subscription_id] = on_data
            self._persist_subscription(state)

        seqs: dict[str, int] = {}
        try:
            for code in codes:
                try:
                    seq = self._backend.subscribe_quote2(code, period, start_time, end_time, count, dividend_type, on_data)
                except Exception:
                    seq = self._backend.subscribe_quote(code, period, start_time, end_time, count, on_data)
                if int(seq) > 0:
                    seqs[code] = int(seq)
        except Exception as exc:
            for seq in seqs.values():
                try:
                    self._backend.unsubscribe_quote(seq)
                except Exception:
                    pass
            self._drop_subscription(subscription_id)
            return DataToolResult(ok=False, payload={}, code="subscribe_failed", message=str(exc), category="connectivity", retryable=True)
        if not seqs:
            self._drop_subscription(subscription_id)
            return DataToolResult(ok=False, payload={}, code="subscribe_failed", message="xtdata subscribe returned no valid seq", category="connectivity", retryable=True)
        with self._lock:
            state.seqs = seqs
            self._persist_subscription(state)
            callback_registered = subscription_id in self._subscription_callbacks
        configured_endpoint, resolved_runtime_endpoint, connection_alive = self._resolve_runtime_endpoint(probe_connect=True)
        return DataToolResult(
            ok=True,
            payload=self._subscription_lease_payload(
                state,
                callback_registered=callback_registered,
                configured_endpoint=configured_endpoint,
                resolved_runtime_endpoint=resolved_runtime_endpoint,
                connection_alive=connection_alive,
                now_text=self._now_fn(),
            ),
        )

    def subscribe_stop(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> DataToolResult:
        arguments = _merge_arguments(arguments, kwargs)
        subscription_id = _safe_str(arguments.get("subscription_id", ""))
        if not subscription_id:
            return DataToolResult(ok=False, payload={}, code="validation_error", message="xtdata.subscribe.stop.subscription_id is required", category="validation")
        with self._lock:
            state = self._subscriptions.get(subscription_id)
            if state is None:
                return DataToolResult(ok=False, payload={}, code="subscription_not_found", message=f"subscription not found: {subscription_id}", category="validation")
        for seq in list(state.seqs.values()):
            try:
                self._backend.unsubscribe_quote(int(seq))
            except Exception:
                pass
        with self._lock:
            state.status = "stopped"
            state.stop_reason = "client_stop"
            self._persist_subscription(state)
            self._subscription_callbacks.pop(subscription_id, None)
            callback_registered = subscription_id in self._subscription_callbacks
        configured_endpoint, resolved_runtime_endpoint, connection_alive = self._resolve_runtime_endpoint(probe_connect=True)
        return DataToolResult(
            ok=True,
            payload=self._subscription_lease_payload(
                state,
                callback_registered=callback_registered,
                configured_endpoint=configured_endpoint,
                resolved_runtime_endpoint=resolved_runtime_endpoint,
                connection_alive=connection_alive,
                now_text=self._now_fn(),
            ),
        )

    def list_subscriptions_payload(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        arguments = _merge_arguments(arguments, kwargs)
        probe_connect = bool(arguments.get("probe_connect", True))
        include_stopped = bool(arguments.get("include_stopped", True))
        configured_endpoint, resolved_runtime_endpoint, connection_alive = self._resolve_runtime_endpoint(probe_connect=probe_connect)
        now_text = self._now_fn()
        with self._lock:
            states = list(self._subscriptions.values())
            callback_ids = set(self._subscription_callbacks)
        items = [
            self._subscription_lease_payload(
                state,
                callback_registered=state.subscription_id in callback_ids,
                configured_endpoint=configured_endpoint,
                resolved_runtime_endpoint=resolved_runtime_endpoint,
                connection_alive=connection_alive,
                now_text=now_text,
            )
            for state in states
        ]
        if not include_stopped:
            items = [item for item in items if str(item.get("lease_state", "")) != "stopped"]
        items.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        active_count = sum(1 for item in items if str(item.get("lease_state", "")) == "active")
        stale_count = sum(1 for item in items if str(item.get("lease_state", "")) == "stale")
        stopped_count = sum(1 for item in items if str(item.get("status", "")).lower() != "running")
        running_count = sum(1 for item in items if str(item.get("status", "")).lower() == "running")
        needs_rebuild_count = sum(1 for item in items if bool(item.get("needs_rebuild")))
        rebuild_reasons = _count_by_reason(items, field="rebuild_reason")
        return {
            "experimental": True,
            "capability": {
                "name": "xtdata.subscribe",
                "model": "subscription_lease",
                "stability": "experimental",
                "proven_live_reconnect": False,
                "reconnect_strategy": SUBSCRIPTION_RECONNECT_STRATEGY,
            },
            "configured_endpoint": configured_endpoint,
            "resolved_runtime_endpoint": resolved_runtime_endpoint,
            "count": len(items),
            "active_count": active_count,
            "stale_count": stale_count,
            "stopped_count": stopped_count,
            "running_count": running_count,
            "needs_rebuild_count": needs_rebuild_count,
            "rebuild_reasons": rebuild_reasons,
            "recovery_summary": {
                "active": active_count,
                "stale": stale_count,
                "stopped": stopped_count,
                "needs_rebuild": needs_rebuild_count,
                "rebuild_reasons": rebuild_reasons,
                "reconnect_strategy": SUBSCRIPTION_RECONNECT_STRATEGY,
                "proven_live_reconnect": False,
            },
            "items": items,
        }

    def _format_bulk_job_status(self, payload: dict[str, Any], *, include_result: bool = True) -> dict[str, Any]:
        request = dict(payload.get("request") or {})
        result = _redact_legacy_job_result(payload.get("result") or {})
        progress_samples = [dict(item) for item in payload.get("progress_samples", []) if isinstance(item, dict)]
        last_sample = progress_samples[-1] if progress_samples else {}
        state = str(payload.get("status", "") or "")
        terminal = state in {"completed", "failed", "cancelled", "interrupted"}
        last_progress_message = str(last_sample.get("message") or payload.get("progress_message", "") or "")
        current_phase = _progress_phase(last_progress_message, last_sample.get("current_phase") or payload.get("current_phase"))
        submitted_at = str(payload.get("created_at", "") or "")
        last_progress_at = str(last_sample.get("ts") or payload.get("last_progress_at") or payload.get("started_at") or submitted_at)
        submitted_dt = _parse_progress_time(submitted_at)
        now_dt = _parse_progress_time(self._now_fn())
        last_progress_dt = _parse_progress_time(last_progress_at)
        age_seconds = _elapsed_progress_seconds(now_dt, submitted_dt)
        last_heartbeat_age_seconds = _elapsed_progress_seconds(now_dt, last_progress_dt)
        phase_elapsed_seconds = _phase_elapsed_seconds(progress_samples, current_phase=current_phase, now_raw=self._now_fn())
        stale_threshold_seconds = max(1, int(self._config.service.stale_job_seconds or 300))
        can_cancel = state in {"pending", "running", "cancel_requested"}
        stale_job_detected = bool(can_cancel and last_progress_dt is not None and last_heartbeat_age_seconds >= stale_threshold_seconds)
        recovery_action = ""
        if stale_job_detected and can_cancel:
            recovery_action = "cancel_then_resubmit_same_target"
        elif can_cancel:
            recovery_action = "wait_for_owner_job"
        terminal_artifacts_ready = bool(
            terminal
            and str(result.get("manifest_path", "") or "").strip()
            and str(result.get("acceptance_path", "") or "").strip()
            and bool(dict(result.get("artifact_readiness") or {}).get("ready", False))
        )
        progress = {
            "finished": int(payload.get("progress_finished", 0) or 0),
            "total": int(payload.get("progress_total", 0) or 0),
            "message": str(payload.get("progress_message", "") or ""),
        }
        formatted = {
            "job_id": str(payload.get("job_id", "") or ""),
            "state": state,
            "submitted_at": str(payload.get("created_at", "") or ""),
            "started_at": str(payload.get("started_at", "") or ""),
            "finished_at": str(payload.get("finished_at", "") or ""),
            "target_date": str(request.get("target_date", "") or ""),
            "periods": [str(item) for item in request.get("periods", []) if str(item).strip()] or ([str(request.get("period", "")).strip()] if str(request.get("period", "")).strip() else []),
            "symbols_scope": str(request.get("symbols_scope", "") or ""),
            "local_qlib_dir": str(request.get("local_qlib_dir", "") or self._config.service.windows_qlib_root),
            "wsl_qlib_dir": str(request.get("wsl_qlib_dir", "") or self._config.service.wsl_qlib_root),
            "progress": progress,
            "progress_samples": progress_samples,
            "current_phase": current_phase,
            "last_progress_at": last_progress_at,
            "age_seconds": age_seconds,
            "last_heartbeat_age_seconds": last_heartbeat_age_seconds,
            "stale_job_detected": stale_job_detected,
            "stale_threshold_seconds": stale_threshold_seconds,
            "can_cancel": can_cancel,
            "recovery_action": recovery_action,
            "last_progress_message": last_progress_message,
            "expected_next": str(last_sample.get("expected_next") or _expected_next_for_phase(current_phase, terminal=terminal_artifacts_ready) or ""),
            "terminal_artifacts_ready": terminal_artifacts_ready,
            "split_retry_count": int(result.get("split_retry_count") or payload.get("split_retry_count") or _max_progress_int(progress_samples, "split_retry_count")),
            "download_timeout_count": int(result.get("download_timeout_count") or payload.get("download_timeout_count") or _max_progress_int(progress_samples, "download_timeout_count")),
            "skipped_symbol_count": int(result.get("skipped_symbol_count") or payload.get("skipped_symbol_count") or _max_progress_int(progress_samples, "skipped_symbol_count")),
            "slow_symbols_sample": [
                str(item)
                for item in list(result.get("slow_symbols_sample") or payload.get("slow_symbols_sample") or _last_progress_list(progress_samples, "slow_symbols_sample"))
                if str(item).strip()
            ][:10],
            "current_chunk_size": int(result.get("current_chunk_size") or payload.get("current_chunk_size") or last_sample.get("current_chunk_size") or last_sample.get("symbols_in_chunk") or 0),
            "phase_elapsed_seconds": phase_elapsed_seconds,
            "artifacts": [str(item) for item in payload.get("artifacts", []) if str(item).strip()],
            "warnings": [str(item) for item in payload.get("warnings", []) if str(item).strip()],
            "error": dict(payload.get("error") or {}) if payload.get("error") else None,
            "completion_reason": str(result.get("completion_reason", "process_exit") or "process_exit"),
            "manifest_path": str(result.get("manifest_path", "") or ""),
            "acceptance_path": str(result.get("acceptance_path", "") or ""),
            "artifact_readiness": dict(result.get("artifact_readiness") or {}),
            "acceptance_summary": dict(result.get("acceptance_summary") or {}),
            "residual_summary": dict(result.get("residual_summary") or {}),
            "bundle_evidence": dict(result.get("bundle_evidence") or {}),
            "runtime_evidence": dict(result.get("runtime_evidence") or {}),
            "port_evidence": _redact_legacy_port_evidence(result.get("port_evidence") or {}),
        }
        if result and include_result:
            formatted["result"] = result
        return formatted

    def _run_download_job(self, request: DownloadJobRequest, progress_cb: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        if str(request.job_kind or "").strip() == "bulk_sync":
            return self._run_bulk_sync_job(request, progress_cb)
        result = self._backend.download_history_data2(list(request.codes), request.period, request.start_time, request.end_time, progress_cb, request.incrementally)
        return {
            "codes": list(request.codes),
            "period": request.period,
            "start_time": request.start_time,
            "end_time": request.end_time,
            "incrementally": request.incrementally,
            "result": _normalize_mapping(dict(result or {})),
            "completion_reason": "process_exit",
        }

    def _build_qmt_cache_acceptance(
        self,
        *,
        periods: list[str],
        candidate_symbols: list[str],
        imported_by_period: dict[str, set[str]],
        residual_summary: dict[str, Any],
    ) -> dict[str, Any]:
        accepted_summary = {
            "passed": int(dict(residual_summary or {}).get("disallowed_count") or 0) == 0,
            "blocking_issues": [],
            "warnings": [],
            "candidate_symbols_count": len(candidate_symbols),
            "period_imported_counts": {
                period: len(imported_by_period.get(period, set()))
                for period in periods
            },
        }
        verdict = build_acceptance_verdict(accepted_summary, residual_summary)
        return {
            "node": "qmt_cache",
            "requested_qlib_dir": "",
            "resolved_host_path": "",
            "path_mapping_source": "backend_readback",
            "health": {},
            "health_passed": True,
            "acceptance_summary": accepted_summary,
            "verdict": verdict,
        }

    def _build_qlib_node_acceptance(
        self,
        *,
        node_name: str,
        qlib_dir: str,
        periods: list[str],
        residual_summary: dict[str, Any],
        target_trade_day: str,
        health_symbols: list[str],
    ) -> dict[str, Any]:
        resolved_path, path_mapping = resolve_runtime_qlib_path(
            qlib_dir,
            wsl_distro_name=self._config.service.wsl_distro_name,
        )
        health_payload: dict[str, Any] = {}
        health_passed = True
        for period in periods:
            payload = check_qlib_health(
                qlib_dir,
                period,
                symbols=health_symbols,
                wsl_distro_name=self._config.service.wsl_distro_name,
            )
            health_payload[period] = payload
            health_passed = health_passed and bool(payload.get("passed"))
        acceptance_summary = assess_qlib_acceptance(
            qlib_dir=qlib_dir,
            periods=periods,
            target_trade_day=target_trade_day,
            wsl_distro_name=self._config.service.wsl_distro_name,
        )
        acceptance_summary = apply_residuals_to_acceptance(acceptance_summary, residual_summary)
        verdict = "fail" if not health_passed else build_acceptance_verdict(acceptance_summary, residual_summary)
        return {
            "node": node_name,
            "requested_qlib_dir": qlib_dir,
            "resolved_host_path": str(resolved_path),
            "path_mapping_source": str(path_mapping.get("path_mapping_source") or ""),
            "health": health_payload,
            "health_passed": health_passed,
            "acceptance_summary": acceptance_summary,
            "verdict": verdict,
        }

    @staticmethod
    def _combine_node_verdicts(node_acceptance: dict[str, dict[str, Any]]) -> str:
        verdicts = [str(dict(item or {}).get("verdict") or "fail") for item in dict(node_acceptance or {}).values()]
        if any(verdict == "fail" for verdict in verdicts):
            return "fail"
        if any(verdict == "pass_with_boundary_residuals" for verdict in verdicts):
            return "pass_with_boundary_residuals"
        return "pass"

    def _run_bulk_sync_job(self, request: DownloadJobRequest, progress_cb: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        started_at = datetime.now()
        local_qlib_dir = str(request.local_qlib_dir or self._config.service.windows_qlib_root or DEFAULT_LOCAL_QLIB_DIR_WINDOWS)
        wsl_qlib_dir = str(request.wsl_qlib_dir or self._config.service.wsl_qlib_root or DEFAULT_QLIB_DIR_WSL)
        periods = [str(item).strip() for item in request.periods if str(item).strip()] or [str(request.period or "1d").strip() or "1d"]
        trade_day = resolve_trade_day(
            self._backend,
            request.target_date or request.end_time or request.start_time,
            calendar_roots=(wsl_qlib_dir, local_qlib_dir),
            wsl_distro_name=self._config.service.wsl_distro_name,
        )
        plan = build_integrity_plan(
            self._backend,
            target_date=trade_day["target_trading_day"],
            periods=periods,
            mode="incremental" if len(periods) > 1 or request.start_time else "tail",
            lookback_trading_days=20,
            symbols_scope=request.symbols_scope or "all_a",
            metadata_path=Path(self._config.service.metadata_path),
            plans_root=Path(self._config.service.plans_root),
            cache_root=Path(self._config.service.cache_root),
            calendar_roots=(wsl_qlib_dir, local_qlib_dir),
            wsl_distro_name=self._config.service.wsl_distro_name,
        )
        candidate_symbols = [str(item) for item in plan.get("candidate_symbols", []) if str(item).strip()]
        if not candidate_symbols:
            universe = resolve_universe(self._backend, request.symbols_scope or "all_a", trade_day["target_trading_day"], cache_root=Path(self._config.service.cache_root))
            candidate_symbols = [str(item) for item in universe.get("symbols", []) if str(item).strip()]
        local_root = host_path_to_local(local_qlib_dir)
        local_root.mkdir(parents=True, exist_ok=True)
        metadata_path = Path(self._config.service.metadata_path)
        chunks_root = Path(self._config.service.download_root) / "chunks"
        imported_by_period: dict[str, set[str]] = {period: set() for period in periods}
        residuals_by_symbol: dict[str, dict[str, Any]] = {}
        download_skipped_by_period: dict[str, set[str]] = {period: set() for period in periods}
        changed_files: set[str] = set()
        progress_total = max(1, len(periods) * 2 + 3)
        progress_finished = 0
        default_chunk_batch_size = max(1, min(self._config.service.max_query_symbols, 120))
        minute_chunk_batch_size = max(1, min(default_chunk_batch_size, 30))
        download_timeout_seconds_by_period = {
            "1d": max(1, int(self._config.service.stale_job_seconds or 300)),
            "1m": max(1, int(self._config.service.stale_job_seconds or 300)),
        }
        download_stats: dict[str, Any] = {
            "split_retry_count": 0,
            "download_timeout_count": 0,
            "skipped_symbols": set(),
            "slow_symbols": [],
            "current_chunk_size": 0,
        }

        def emit_progress(message: str, *, phase: str = "", increment: bool = False, **extra: Any) -> bool:
            nonlocal progress_finished
            if increment:
                progress_finished += 1
            current_phase = phase or _progress_phase(message)
            payload = {
                "finished": progress_finished,
                "total": progress_total,
                "message": message,
                "current_phase": current_phase,
                "expected_next": str(extra.pop("expected_next", "") or _expected_next_for_phase(current_phase)),
                "split_retry_count": int(download_stats.get("split_retry_count") or 0),
                "download_timeout_count": int(download_stats.get("download_timeout_count") or 0),
                "skipped_symbol_count": len(download_stats.get("skipped_symbols") or set()),
                "slow_symbols_sample": list(download_stats.get("slow_symbols") or [])[:10],
                "current_chunk_size": int(download_stats.get("current_chunk_size") or 0),
            }
            payload.update(extra)
            return bool(progress_cb(payload))

        def call_download_history_data2(
            *,
            symbols: list[str],
            period: str,
            start_time: str,
            end_time: str,
            callback: Callable[[dict[str, Any]], bool] | None,
            context: str,
        ) -> dict[str, Any]:
            result_queue: Queue[tuple[bool, Any]] = Queue(maxsize=1)
            last_activity = time.monotonic()
            download_timeout_seconds = download_timeout_seconds_by_period.get(period, download_timeout_seconds_by_period["1d"])

            def _progress_callback(payload: dict[str, Any]) -> bool:
                nonlocal last_activity
                last_activity = time.monotonic()
                return bool(callback(payload)) if callback is not None else False

            def _worker() -> None:
                try:
                    result_queue.put(
                        (
                            True,
                            self._backend.download_history_data2(
                                symbols,
                                period,
                                start_time,
                                end_time,
                                _progress_callback if callback is not None else None,
                                request.incrementally,
                            ),
                        )
                    )
                except BaseException as exc:
                    result_queue.put((False, exc))

            thread = Thread(target=_worker, name=f"xtdata-download-{period}", daemon=True)
            thread.start()
            while True:
                try:
                    ok, value = result_queue.get(timeout=min(0.5, float(download_timeout_seconds)))
                    break
                except Empty as exc:
                    if time.monotonic() - last_activity <= float(download_timeout_seconds):
                        continue
                    try:
                        self._backend.stop_download()
                    except Exception:
                        pass
                    download_stats["download_timeout_count"] = int(download_stats.get("download_timeout_count") or 0) + 1
                    raise TimeoutError(f"download_history_data2 idle timeout: {context}") from exc
            if not ok:
                raise value
            return dict(value or {})

        def mark_download_timeout_residual(*, symbol: str, period: str, context: str) -> None:
            normalized_symbol = normalize_code(symbol)
            if not normalized_symbol:
                return
            download_skipped_by_period.setdefault(period, set()).add(normalized_symbol)
            download_stats.setdefault("skipped_symbols", set()).add(normalized_symbol)
            slow_symbols = list(download_stats.get("slow_symbols") or [])
            if normalized_symbol not in slow_symbols:
                slow_symbols.append(normalized_symbol)
            download_stats["slow_symbols"] = slow_symbols[:20]
            _merge_residual_item(
                residuals_by_symbol,
                {
                    "symbol": normalized_symbol,
                    "classification": "vendor_boundary",
                    "periods_missing": [period],
                    "target_trade_day": trade_day["target_trading_day"],
                    "reason": "download_history_data2_idle_timeout",
                    "last_bar_time": context,
                },
            )

        def download_history_chunk_with_recovery(
            *,
            symbols: list[str],
            period: str,
            start_time: str,
            end_time: str,
            cursor: int,
        ) -> None:
            download_stats["current_chunk_size"] = len(symbols)
            try:
                call_download_history_data2(
                    symbols=list(symbols),
                    period=period,
                    start_time=start_time,
                    end_time=end_time,
                    callback=lambda payload, chunk_cursor=cursor: emit_progress(
                        str((payload or {}).get("message", f"download:{period}")),
                        phase="download",
                        period=period,
                        cursor=chunk_cursor,
                    ),
                    context=f"period={period} cursor={cursor} symbols={len(symbols)}",
                )
                return
            except TimeoutError:
                if period != "1m":
                    raise
                if len(symbols) > 1:
                    download_stats["split_retry_count"] = int(download_stats.get("split_retry_count") or 0) + 1
                    midpoint = max(1, len(symbols) // 2)
                    left = list(symbols[:midpoint])
                    right = list(symbols[midpoint:])
                    emit_progress(
                        f"download:{period} split_retry cursor={cursor} symbols={len(symbols)} left={len(left)} right={len(right)} reason=idle_timeout",
                        phase="download",
                        period=period,
                        cursor=cursor,
                        symbols_in_chunk=len(symbols),
                        expected_next=f"download:{period}",
                    )
                    if left:
                        download_history_chunk_with_recovery(symbols=left, period=period, start_time=start_time, end_time=end_time, cursor=cursor)
                    if right:
                        download_history_chunk_with_recovery(symbols=right, period=period, start_time=start_time, end_time=end_time, cursor=cursor + len(left))
                    return
                symbol = normalize_code(symbols[0]) if symbols else ""
                mark_download_timeout_residual(
                    symbol=symbol,
                    period=period,
                    context=f"period={period} cursor={cursor} symbols=1",
                )
                emit_progress(
                    f"download:{period} skip symbol={symbol} reason=idle_timeout",
                    phase="download",
                    period=period,
                    cursor=cursor,
                    symbols_in_chunk=1,
                    expected_next=f"download:{period}",
                )
                return

        for period in periods:
            chunk_batch_size = minute_chunk_batch_size if period == "1m" else default_chunk_batch_size
            if candidate_symbols:
                start_time = request.start_time or (list(plan.get("expected_days") or [])[:1] or [trade_day["target_trading_day"]])[0]
                end_time = request.end_time or trade_day["target_trading_day"]
                if period == "1m":
                    cursor_download = 0
                    while cursor_download < len(candidate_symbols):
                        symbols_chunk = candidate_symbols[cursor_download : cursor_download + minute_chunk_batch_size]
                        next_download_cursor = cursor_download + len(symbols_chunk)
                        next_cursor_value: int | None = next_download_cursor if next_download_cursor < len(candidate_symbols) else None
                        emit_progress(
                            _format_chunk_progress_message(
                                "download",
                                period,
                                cursor=cursor_download,
                                next_cursor=next_cursor_value,
                                chunk_batch_size=chunk_batch_size,
                                symbols_total=len(candidate_symbols),
                                symbols_in_chunk=len(symbols_chunk),
                            ),
                            phase="download",
                            increment=cursor_download == 0,
                            period=period,
                            symbols_in_chunk=len(symbols_chunk),
                            expected_next=f"download:{period}" if next_cursor_value is not None else f"pull:{period}",
                        )
                        download_history_chunk_with_recovery(
                            symbols=list(symbols_chunk),
                            period=period,
                            start_time=start_time,
                            end_time=end_time,
                            cursor=cursor_download,
                        )
                        cursor_download = next_download_cursor
                else:
                    emit_progress(f"download:{period}", phase="download", increment=True, period=period, expected_next=f"pull:{period}")
                    call_download_history_data2(
                        symbols=list(candidate_symbols),
                        period=period,
                        start_time=start_time,
                        end_time=end_time,
                        callback=lambda payload: emit_progress(str((payload or {}).get("message", f"download:{period}")), phase="download", period=period),
                        context=f"period={period} symbols={len(candidate_symbols)}",
                    )
            cursor = 0
            skipped_symbols = download_skipped_by_period.get(period, set())
            symbols_for_pull = [symbol for symbol in candidate_symbols if normalize_code(symbol) not in skipped_symbols]
            while symbols_for_pull:
                chunk = pull_history_chunk(
                    self._backend,
                    symbols=symbols_for_pull,
                    period=period,
                    start_time=request.start_time or (list(plan.get("expected_days") or [])[:1] or [trade_day["target_trading_day"]])[0],
                    end_time=request.end_time or trade_day["target_trading_day"],
                    cursor=cursor,
                    chunk_symbols=chunk_batch_size,
                    adjusted_mode=request.adjusted_mode or "raw_with_factor",
                    metadata_path=metadata_path,
                    chunks_root=chunks_root,
                )
                chunk_cursor = _progress_int(chunk.get("cursor", cursor), cursor)
                chunk_symbols_count = _progress_int(
                    chunk.get("chunk_symbols_count", len(chunk.get("chunk_symbols", []) or [])),
                    chunk_batch_size,
                )
                chunk_symbols_total = _progress_int(chunk.get("symbols_total", len(candidate_symbols)), len(candidate_symbols))
                next_cursor = chunk.get("next_cursor")
                emit_progress(
                    _format_chunk_progress_message(
                        "pull",
                        period,
                        cursor=chunk_cursor,
                        next_cursor=next_cursor,
                        chunk_batch_size=chunk_batch_size,
                        symbols_total=chunk_symbols_total,
                        rows=chunk.get("rows"),
                        symbols_in_chunk=chunk_symbols_count,
                    ),
                    phase="download",
                    period=period,
                    rows=_progress_int(chunk.get("rows"), 0),
                    symbols_in_chunk=chunk_symbols_count,
                    expected_next=f"import:{period}",
                )
                for item in chunk.get("boundary_residuals", []) if isinstance(chunk.get("boundary_residuals"), list) else []:
                    if isinstance(item, dict):
                        _merge_residual_item(residuals_by_symbol, item)
                import_result = import_parquet_chunk(
                    chunk["chunk_path"],
                    local_root,
                    period,
                    backend=self._backend,
                    future_day_calendar=list(request.future_day_calendar or ()),
                    calendar_snapshot_year=int(request.calendar_snapshot_year or 0),
                )
                emit_progress(
                    _format_chunk_progress_message(
                        "import",
                        period,
                        cursor=chunk_cursor,
                        next_cursor=next_cursor,
                        chunk_batch_size=chunk_batch_size,
                        symbols_total=chunk_symbols_total,
                        rows=chunk.get("rows"),
                        symbols_in_chunk=chunk_symbols_count,
                        imported_symbols_count=len(import_result.get("imported_symbols", []) or []),
                        changed_files_count=len(import_result.get("changed_files", []) or []),
                    ),
                    phase="import",
                    period=period,
                    rows=_progress_int(chunk.get("rows"), 0),
                    symbols_in_chunk=chunk_symbols_count,
                    imported_symbols_count=len(import_result.get("imported_symbols", []) or []),
                    changed_files_count=len(import_result.get("changed_files", []) or []),
                    expected_next=f"materialize:{period}" if next_cursor is None else f"pull:{period}",
                )
                imported_by_period[period].update(import_result.get("imported_symbols", []))
                changed_files.update(str(item) for item in import_result.get("changed_files", []) if str(item).strip())
                if import_result.get("metadata_updates"):
                    upsert_metadata(metadata_path, dict(import_result.get("metadata_updates") or {}))
                if next_cursor is None:
                    break
                cursor = int(next_cursor)
            emit_progress(
                f"materialize:{period}",
                phase="materialize",
                increment=True,
                period=period,
                changed_files_count=len(changed_files),
                expected_next="manifest:start",
            )

        emit_progress("manifest:start", phase="manifest", expected_next="manifest:done")
        required_files = required_manifest_files(periods)
        changed_files.update(required_files)
        imported_union = set().union(*imported_by_period.values()) if imported_by_period else set()
        for symbol in candidate_symbols:
            missing = [period for period in periods if symbol not in imported_by_period.get(period, set())]
            if not missing:
                continue
            _merge_residual_item(
                residuals_by_symbol,
                {
                    "symbol": symbol,
                    "periods_missing": missing,
                },
            )
        residual_summary = summarize_residuals(list(residuals_by_symbol.values()))
        health_symbols = resolve_health_symbols_for_scope(request.symbols_scope or "all_a", request_symbols=list(request.codes))
        bundle_evidence = {
            "bundle_root": self._config.bundle.bundle_root,
            "abi_tag": self._config.bundle.abi_tag,
            "package_root": str(self._config.bundle.package_root()),
        }
        configured_endpoint, resolved_runtime_endpoint, _ = self._resolve_runtime_endpoint(probe_connect=True)
        runtime_evidence = {"python_executable": str(sys.executable), "config_path": self._config.config_path}
        manifest = {
            "job_id": "",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "target_date": trade_day["target_trading_day"],
            "periods": periods,
            "symbols_scope": request.symbols_scope or "all_a",
            "local_qlib_dir": str(local_root),
            "local_qlib_dir_windows": local_qlib_dir,
            "wsl_qlib_dir": wsl_qlib_dir,
            "changed_files": sorted(changed_files),
            "required_files": required_files,
            "missing_required_files": [item for item in required_files if item not in changed_files],
            "acceptance_summary": {},
            "residual_summary": {},
            "bundle_evidence": bundle_evidence,
            "runtime_evidence": runtime_evidence,
            "port_evidence": {
                "configured_endpoint": configured_endpoint,
                "resolved_runtime_endpoint": resolved_runtime_endpoint,
            },
        }
        emit_progress(
            "manifest:done",
            phase="manifest",
            increment=True,
            changed_files_count=len(manifest["changed_files"]),
            missing_required_files=list(manifest["missing_required_files"]),
            expected_next="acceptance:start",
        )
        emit_progress("acceptance:start", phase="acceptance", expected_next="sync_wsl:start")
        pre_windows_acceptance = assess_qlib_acceptance(
            qlib_dir=local_qlib_dir,
            periods=periods,
            target_trade_day=trade_day["target_trading_day"],
            wsl_distro_name=self._config.service.wsl_distro_name,
        )
        candidate_symbol_set = {normalize_code(item) for item in candidate_symbols}
        for freq, item in dict(pre_windows_acceptance.get("instrument_end_consistency") or {}).items():
            period = "1m" if freq == "1min" else "1d"
            for example in item.get("target_stale_examples", []) if isinstance(item.get("target_stale_examples"), list) else []:
                if not isinstance(example, dict):
                    continue
                symbol = normalize_code(str(example.get("symbol") or ""))
                if not symbol or symbol in candidate_symbol_set:
                    continue
                _merge_residual_item(
                    residuals_by_symbol,
                    {
                        "symbol": symbol,
                        "classification": "vendor_boundary",
                        "periods_stale": [period],
                        "target_trade_day": example.get("target_trade_day", ""),
                        "reason": "symbol_not_in_candidate_universe",
                    },
                )
        residual_summary = summarize_residuals(list(residuals_by_symbol.values()))
        qmt_cache_acceptance = self._build_qmt_cache_acceptance(
            periods=periods,
            candidate_symbols=candidate_symbols,
            imported_by_period=imported_by_period,
            residual_summary=residual_summary,
        )
        windows_qlib_acceptance = self._build_qlib_node_acceptance(
            node_name="windows_qlib",
            qlib_dir=local_qlib_dir,
            periods=periods,
            residual_summary=residual_summary,
            target_trade_day=trade_day["target_trading_day"],
            health_symbols=health_symbols,
        )
        emit_progress("sync_wsl:start", phase="sync_wsl", expected_next="sync_wsl:done")
        sync_result = sync_manifest_files(
            manifest,
            qlib_dir=wsl_qlib_dir,
            local_qlib_dir_windows=local_qlib_dir,
            wsl_distro_name=self._config.service.wsl_distro_name,
            progress_callback=lambda payload: emit_progress(
                str(dict(payload or {}).get("message") or "sync_wsl:copy"),
                phase="sync_wsl",
                copied_count=int(dict(payload or {}).get("copied_count", 0) or 0),
                missing_sources_count=int(dict(payload or {}).get("missing_sources_count", 0) or 0),
                total_count=int(dict(payload or {}).get("total_count", 0) or 0),
                expected_next=str(dict(payload or {}).get("expected_next") or "sync_wsl:done"),
            ),
        )
        emit_progress(
            "sync_wsl:done",
            phase="sync_wsl",
            increment=True,
            copied_count=int(sync_result.get("copied_count", 0) or 0),
            missing_sources_count=int(sync_result.get("missing_sources_count", 0) or 0),
            expected_next="acceptance:done",
        )
        wsl_qlib_acceptance = self._build_qlib_node_acceptance(
            node_name="wsl_qlib",
            qlib_dir=wsl_qlib_dir,
            periods=periods,
            residual_summary=residual_summary,
            target_trade_day=trade_day["target_trading_day"],
            health_symbols=health_symbols,
        )
        node_acceptance = {
            "qmt_cache": qmt_cache_acceptance,
            "windows_qlib": windows_qlib_acceptance,
            "wsl_qlib": wsl_qlib_acceptance,
        }
        acceptance_summary = dict(wsl_qlib_acceptance.get("acceptance_summary") or {})
        verdict = self._combine_node_verdicts(node_acceptance)
        if manifest["missing_required_files"] or int(sync_result.get("missing_sources_count", 0) or 0) > 0:
            verdict = "fail"
        manifest["acceptance_summary"] = acceptance_summary
        manifest["residual_summary"] = residual_summary
        manifest["wsl_sync_result"] = sync_result
        manifest["acceptance_verdict"] = verdict
        manifest["health_symbols"] = health_symbols
        manifest["node_acceptance"] = node_acceptance
        manifest_root = Path(self._config.service.download_root) / "jobs"
        manifest_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        manifest_path = manifest_root / f"bulk_sync_{trade_day['target_trading_day']}_{stamp}_manifest.json"
        acceptance_path = manifest_root / f"bulk_sync_{trade_day['target_trading_day']}_{stamp}_acceptance.json"
        quality_notes: list[str] = []
        if int(dict(residual_summary).get("count", 0) or 0) > 0 and int(dict(residual_summary).get("disallowed_count", 0) or 0) == 0:
            quality_notes.append("allowed_boundary_residuals")
        if int(sync_result.get("missing_sources_count", 0) or 0) > 0:
            quality_notes.append("missing_wsl_sync_sources")
        skipped_symbols_all = sorted(str(item) for item in set().union(*download_skipped_by_period.values()) if str(item).strip())
        download_recovery_summary = {
            "split_retry_count": int(download_stats.get("split_retry_count") or 0),
            "download_timeout_count": int(download_stats.get("download_timeout_count") or 0),
            "skipped_symbol_count": len(skipped_symbols_all),
            "slow_symbols_sample": list(download_stats.get("slow_symbols") or [])[:10],
            "current_chunk_size": int(download_stats.get("current_chunk_size") or 0),
        }
        manifest["download_recovery_summary"] = download_recovery_summary
        quality_summary = {
            "acceptance_path": str(acceptance_path),
            "job_target_date": trade_day["target_trading_day"],
            "node_verdicts": {name: str(dict(item or {}).get("verdict") or "") for name, item in node_acceptance.items()},
            "calendar_tails": dict(acceptance_summary.get("calendar_tails") or {}),
            "instrument_counts": dict(acceptance_summary.get("instrument_counts") or {}),
            "instrument_diff": dict(acceptance_summary.get("instrument_diff") or {}),
            "residual_summary": residual_summary,
            "changed_files_count": len(manifest["changed_files"]),
            "copied_count": int(sync_result.get("copied_count", 0) or 0),
            "missing_sources_count": int(sync_result.get("missing_sources_count", 0) or 0),
            "missing_required_files": list(manifest["missing_required_files"]),
            "download_recovery_summary": download_recovery_summary,
            "quality_notes": quality_notes,
        }
        _json_dump(manifest_path, manifest)
        _json_dump(
            acceptance_path,
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "verdict": verdict,
                "acceptance_summary": acceptance_summary,
                "residual_summary": residual_summary,
                "node_acceptance": node_acceptance,
                "quality_summary": quality_summary,
                "quality_notes": quality_notes,
                "job_target_date": trade_day["target_trading_day"],
            },
        )
        artifact_readiness = {
            "ready": verdict != "fail",
            "required_files": required_files,
            "missing_required_files": manifest["missing_required_files"],
            "changed_files_count": len(manifest["changed_files"]),
            "copied_count": int(sync_result.get("copied_count", 0) or 0),
            "imported_symbols_count": len(imported_union),
            "node_verdicts": {name: str(dict(item or {}).get("verdict") or "") for name, item in node_acceptance.items()},
        }
        emit_progress(
            "acceptance:done",
            phase="acceptance",
            increment=True,
            verdict=verdict,
            release_state="ready" if artifact_readiness["ready"] else "not_ready",
            missing_required_files=list(manifest["missing_required_files"]),
            expected_next="terminal",
        )
        return {
            "force_status": "failed" if verdict == "fail" else "completed",
            "completion_reason": "process_exit",
            "trade_day": trade_day,
            "plan": plan,
            "manifest": manifest,
            "manifest_path": str(manifest_path),
            "acceptance_summary": {
                "verdict": verdict,
                **acceptance_summary,
            },
            "acceptance_path": str(acceptance_path),
            "residual_summary": residual_summary,
            "artifact_readiness": artifact_readiness,
            **download_recovery_summary,
            "download_recovery_summary": download_recovery_summary,
            "node_acceptance": node_acceptance,
            "quality_summary": quality_summary,
            "quality_notes": quality_notes,
            "wsl_sync_result": sync_result,
            "bundle_evidence": bundle_evidence,
            "runtime_evidence": runtime_evidence,
            "port_evidence": {"configured_endpoint": configured_endpoint, "resolved_runtime_endpoint": resolved_runtime_endpoint},
        }

    def _cancel_download_job(self) -> None:
        self._backend.stop_download()

    def _subscription_path(self, subscription_id: str) -> Path:
        return self._subscriptions_root / f"{subscription_id}.json"

    def _persist_subscription(self, state: SubscriptionState) -> None:
        self._subscription_path(state.subscription_id).write_text(json.dumps(state.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_subscriptions(self) -> None:
        for path in sorted(self._subscriptions_root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            state = SubscriptionState(
                subscription_id=str(payload.get("subscription_id", path.stem) or path.stem),
                codes=tuple(str(item).strip() for item in payload.get("codes", []) if str(item).strip()),
                period=str(payload.get("period", "tick") or "tick"),
                created_at=str(payload.get("created_at", "") or self._now_fn()),
                start_time=str(payload.get("start_time", "") or ""),
                end_time=str(payload.get("end_time", "") or ""),
                count=int(payload.get("count", 0) or 0),
                dividend_type=str(payload.get("dividend_type", "none") or "none"),
                seqs={str(key): int(value) for key, value in dict(payload.get("seqs") or {}).items()},
                status=str(payload.get("status", "stopped") or "stopped"),
                event_count=int(payload.get("event_count", 0) or 0),
                last_event_at=str(payload.get("last_event_at", "") or ""),
                last_event=dict(payload.get("last_event") or {}),
                stop_reason=str(payload.get("stop_reason", "process_restart") or "process_restart"),
            )
            if state.status == "running":
                state.status = "stopped"
                state.stop_reason = state.stop_reason or "process_restart"
                self._persist_subscription(state)
            self._subscriptions[state.subscription_id] = state
