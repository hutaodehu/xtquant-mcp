from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import importlib
import json
from pathlib import Path
import sys
from threading import RLock
from typing import Any, Callable, Protocol

from xtqmt_mcp.bundle import ensure_bundle_package_on_sys_path, validate_xtquant_bundle, xtquant_import_spec
from xtqmt_mcp.runtime_support import port_ready

from .config import DataGatewayConfig
from .jobs import DownloadJobManager, DownloadJobRequest


DEFAULT_INSTRUMENT_SECTORS: tuple[str, ...] = ("沪深A股", "上证A股", "深证A股", "北证A股")
SUBSCRIPTION_LEASE_GRACE_SECONDS = 15
SUBSCRIPTION_LEASE_STALE_SECONDS = 60
SUBSCRIPTION_RECONNECT_STRATEGY = "explicit_rebuild_required"


class XtDataBackend(Protocol):
    def get_sector_list(self) -> list[str]: ...
    def get_stock_list_in_sector(self, sector_name: str, real_timetag: int = -1) -> list[str]: ...
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
    return {
        "host": _safe_str(host) or "127.0.0.1",
        "port": int(port or 58610),
        "source": str(source or "configured"),
        "port_ready": None if port_ready_state is None else bool(port_ready_state),
    }


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
            host = _safe_str(self._config.qmt.xtdata_host) or "127.0.0.1"
            port = int(self._config.qmt.xtdata_port or 58610)
            if not port_ready(host=host, port=port):
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

    def get_stock_list_in_sector(self, sector_name: str, real_timetag: int = -1) -> list[str]:
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

    def get_stock_list_in_sector(self, sector_name: str, real_timetag: int = -1) -> list[str]:
        module = self._module(True)
        return list(module.get_stock_list_in_sector(sector_name) or [])

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
        host = _safe_str(self._config.qmt.xtdata_host) or "127.0.0.1"
        port = int(self._config.qmt.xtdata_port or 58610)
        port_state = port_ready(host=host, port=port) if probe_connect else None
        configured_endpoint = _to_endpoint(host, port, source="configured", port_ready_state=None)
        resolved_runtime_endpoint = _to_endpoint(
            host,
            port,
            source="connectivity_probe" if probe_connect else "configured",
            port_ready_state=port_state,
        )
        resolved_runtime_endpoint["matches_configured"] = (
            resolved_runtime_endpoint["host"] == configured_endpoint["host"]
            and int(resolved_runtime_endpoint["port"]) == int(configured_endpoint["port"])
        )
        connectivity_ready = bool(port_state) if port_state is not None else True
        return configured_endpoint, resolved_runtime_endpoint, connectivity_ready

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
        probe_basic_query = bool(arguments.get("probe_basic_query", True))
        probe_metadata = bool(arguments.get("probe_metadata", True))
        probe_import = bool(arguments.get("probe_import", False))

        bundle_state = validate_xtquant_bundle(self._config.bundle)
        import_spec = xtquant_import_spec(self._config.bundle)
        import_spec_found = bool(import_spec)
        configured_endpoint, resolved_runtime_endpoint, connectivity_ready = self._resolve_runtime_endpoint(probe_connect=probe_connect)
        host = str(configured_endpoint["host"])
        port = int(configured_endpoint["port"])

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

        jobs_payload = {"active": self._jobs.list_active(), "recent": self._jobs.list_all()[:5]}
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
            reason = "xtdata_port_not_ready"
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
            "xtdata_port": {"host": host, "port": port, "ready": bool(connectivity_ready)},
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
        if reason == "xtdata_port_not_ready":
            return DataToolResult(ok=False, payload=payload, code="xtdata_port_not_ready", message=f"xtdata port not ready: {host}:{port}", category="connectivity", retryable=True)
        return DataToolResult(ok=False, payload=payload, code="xtdata_basic_query_failed", message=basic_query_error or "xtdata basic query failed", category="connectivity", retryable=True)

    def status_summary(self) -> DataToolResult:
        return self.status()

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

    def _run_download_job(self, request: DownloadJobRequest, progress_cb: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        result = self._backend.download_history_data2(list(request.codes), request.period, request.start_time, request.end_time, progress_cb, request.incrementally)
        return {"codes": list(request.codes), "period": request.period, "start_time": request.start_time, "end_time": request.end_time, "incrementally": request.incrementally, "result": _normalize_mapping(dict(result or {}))}

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
