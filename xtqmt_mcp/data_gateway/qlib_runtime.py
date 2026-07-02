from __future__ import annotations

import html
import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from urllib.error import URLError
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd


DEFAULT_LOCAL_QLIB_DIR_WINDOWS = r"C:\xtquant-mcp-example\qlib_data\xtdata_export_local"
DEFAULT_QLIB_DIR_WSL = "/opt/xtquant-mcp-example/qlib_data/xtdata_export_local"
COMMON_INDICES = [
    "000001.SH",
    "000300.SH",
    "000905.SH",
    "000852.SH",
    "399001.SZ",
    "399006.SZ",
]
SECTOR_CANDIDATES = ("沪深A股", "全A股", "A股", "上证A股", "深证A股", "北证A股")
VALID_SUFFIX = (".SH", ".SZ", ".BJ")
FIELDS = ("open", "high", "low", "close", "volume", "amount", "factor")
FUTURE_CALENDAR_LOOKAHEAD_DAYS = 30
ALLOWED_RESIDUAL_CLASSES = {"upstream_no_bar", "vendor_boundary"}
DEFAULT_HTTP_TIMEOUT_SECONDS = 15
DEFAULT_USER_AGENT = "Mozilla/5.0 (xtqmtDataGateway official calendar verifier)"
OFFICIAL_A_SHARE_CALENDAR_URLS: dict[int, dict[str, str]] = {
    2026: {
        "sse": "https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml",
        "szse": "https://www.szse.cn/disclosure/notice/general/t20251222_618087.html",
    }
}


@dataclass(frozen=True)
class RoutePolicy:
    max_symbols_mcp: int = 1000
    max_trading_days_mcp: int = 5
    max_estimated_bars_mcp: int = 2_000_000


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reason: str
    symbols_count: int
    trading_days_count: int
    estimated_bars: int


DEFAULT_ROUTE_POLICY = RoutePolicy()


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _json_load(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload) if isinstance(payload, dict) else dict(default or {})


def to_ymd(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("日期不能为空")
    if len(text) >= 8 and text[:8].isdigit():
        return text[:8]
    dt = pd.Timestamp(text)
    if pd.isna(dt):
        raise ValueError(f"非法日期: {value}")
    return dt.strftime("%Y%m%d")


def normalize_code(code: str) -> str:
    text = str(code or "").strip().upper()
    if not text:
        return ""
    if "." in text:
        left, right = text.split(".", 1)
        if left.isdigit() and right in {"SH", "SZ", "BJ"}:
            return f"{left.zfill(6)}.{right}"
        return text
    if len(text) == 8 and text[:2] in {"SH", "SZ", "BJ"} and text[2:].isdigit():
        return f"{text[2:]}.{text[:2]}"
    return text


def normalize_calendar_days(raw_days: Sequence[object], *, period: str = "1d") -> list[str]:
    values: list[str] = []
    for item in raw_days:
        text = str(item or "").strip().replace("/", "-")
        if not text:
            continue
        dt = pd.to_datetime(text, errors="coerce")
        if pd.isna(dt):
            continue
        if period == "1m":
            values.append(dt.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            values.append(dt.strftime("%Y%m%d"))
    return sorted(set(values))


def _trade_days_from_closed_ranges(year: int, closed_ranges: list[dict[str, str]]) -> list[str]:
    closed_days: set[date] = set()
    for item in closed_ranges:
        start_date = date.fromisoformat(str(item.get("start") or ""))
        end_date = date.fromisoformat(str(item.get("end") or ""))
        cursor = start_date
        while cursor <= end_date:
            closed_days.add(cursor)
            cursor += timedelta(days=1)

    trade_days: list[str] = []
    cursor = date(year, 1, 1)
    year_end = date(year, 12, 31)
    while cursor <= year_end:
        if cursor.weekday() < 5 and cursor not in closed_days:
            trade_days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return trade_days


def _normalize_html_text(body: str) -> str:
    text = re.sub(r"<script[\\s\\S]*?</script>", "", body, flags=re.IGNORECASE)
    text = re.sub(r"<style[\\s\\S]*?</style>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\u3000", "").replace("\xa0", "")
    return re.sub(r"\s+", "", text)


def _parse_official_closed_ranges(body: str, *, year: int) -> list[dict[str, str]]:
    normalized = _normalize_html_text(body)
    pattern = re.compile(
        r"[（(][一二三四五六七八九十]+[)）]([^：:]{1,24})[：:](\d{1,2})月(\d{1,2})日(?:（[^）]*）)?至(\d{1,2})月(\d{1,2})日(?:（[^）]*）)?休市"
    )
    ranges: list[dict[str, str]] = []
    for match in pattern.finditer(normalized):
        name = str(match.group(1) or "").strip("，。；;:：")
        start = date(year, int(match.group(2)), int(match.group(3))).isoformat()
        end = date(year, int(match.group(4)), int(match.group(5))).isoformat()
        ranges.append({"name": name, "start": start, "end": end})
    return ranges


def _resolve_official_source_urls(year: int) -> dict[str, str]:
    return dict(OFFICIAL_A_SHARE_CALENDAR_URLS.get(int(year), {}))


def _fetch_official_trade_calendar_source(
    source: str,
    *,
    url: str,
    year: int,
    timeout_seconds: int = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    request = Request(url=url, headers={"User-Agent": DEFAULT_USER_AGENT}, method="GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
    except URLError as exc:
        return {
            "ok": False,
            "source": source,
            "url": url,
            "error": str(exc.reason),
            "trade_days": [],
            "closed_ranges": [],
            "content_hash": "",
        }
    except Exception as exc:  # pragma: no cover - network failure shape
        return {
            "ok": False,
            "source": source,
            "url": url,
            "error": f"{type(exc).__name__}: {exc}",
            "trade_days": [],
            "closed_ranges": [],
            "content_hash": "",
        }

    closed_ranges = _parse_official_closed_ranges(body, year=year)
    if not closed_ranges:
        return {
            "ok": False,
            "source": source,
            "url": url,
            "error": "closed_ranges_parse_failed",
            "trade_days": [],
            "closed_ranges": [],
            "content_hash": _compact_sha256(body),
        }
    return {
        "ok": True,
        "source": source,
        "url": url,
        "error": "",
        "trade_days": _trade_days_from_closed_ranges(year, closed_ranges),
        "closed_ranges": closed_ranges,
        "content_hash": _compact_sha256(body),
    }


def _fetch_official_trade_calendar_sources(
    year: int,
    *,
    timeout_seconds: int = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> dict[str, dict[str, Any]]:
    urls = _resolve_official_source_urls(year)
    if not urls:
        return {
            "sse": {
                "ok": False,
                "source": "sse",
                "url": "",
                "error": f"official_source_config_missing:{year}",
                "trade_days": [],
                "closed_ranges": [],
                "content_hash": "",
            },
            "szse": {
                "ok": False,
                "source": "szse",
                "url": "",
                "error": f"official_source_config_missing:{year}",
                "trade_days": [],
                "closed_ranges": [],
                "content_hash": "",
            },
        }
    return {
        source: _fetch_official_trade_calendar_source(source, url=url, year=year, timeout_seconds=timeout_seconds)
        for source, url in urls.items()
    }


def _compact_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def inspect_official_trade_day(target_date: str, *, timeout_seconds: int = DEFAULT_HTTP_TIMEOUT_SECONDS) -> dict[str, Any]:
    target_ymd = to_ymd(target_date)
    target_display = _display_trade_day(target_ymd)
    target_year = int(target_ymd[:4])
    official_sources = _fetch_official_trade_calendar_sources(target_year, timeout_seconds=timeout_seconds)
    source_status = {source: ("ok" if bool(payload.get("ok")) else "unreachable") for source, payload in official_sources.items()}
    source_urls = {source: str(payload.get("url") or "") for source, payload in official_sources.items()}
    source_hashes = {source: str(payload.get("content_hash") or "") for source, payload in official_sources.items()}
    source_errors = {source: str(payload.get("error") or "") for source, payload in official_sources.items() if str(payload.get("error") or "")}
    if any(status != "ok" for status in source_status.values()):
        return {
            "ok": False,
            "target_date": target_ymd,
            "is_trade_day": False,
            "official_conflict": False,
            "official_status_code": "official_calendar_unreachable",
            "official_summary": "官方在线双源不可达，无法确认目标日是否为交易日。",
            "source_status": source_status,
            "official_source_urls": source_urls,
            "official_source_hashes": source_hashes,
            "official_source_errors": source_errors,
            "official_trade_days_year": {},
        }

    sse_trade_days = list(official_sources.get("sse", {}).get("trade_days") or [])
    szse_trade_days = list(official_sources.get("szse", {}).get("trade_days") or [])
    if sse_trade_days != szse_trade_days:
        return {
            "ok": False,
            "target_date": target_ymd,
            "is_trade_day": False,
            "official_conflict": True,
            "official_status_code": "official_calendar_conflict",
            "official_summary": "上交所与深交所在线交易日历结论冲突。",
            "source_status": source_status,
            "official_source_urls": source_urls,
            "official_source_hashes": source_hashes,
            "official_source_errors": source_errors,
            "official_trade_days_year": {"sse": sse_trade_days, "szse": szse_trade_days},
        }

    official_trade_days = sse_trade_days
    return {
        "ok": True,
        "target_date": target_ymd,
        "is_trade_day": target_display in set(official_trade_days),
        "official_conflict": False,
        "official_status_code": "official_trade_day_confirmed" if target_display in set(official_trade_days) else "official_non_trade_day",
        "official_summary": "官方在线双源已确认目标日为交易日。" if target_display in set(official_trade_days) else "官方在线双源已确认目标日不是交易日。",
        "source_status": source_status,
        "official_source_urls": source_urls,
        "official_source_hashes": source_hashes,
        "official_source_errors": source_errors,
        "official_trade_days_year": {"sse": official_trade_days, "szse": official_trade_days},
    }


def parse_xt_time(value: object) -> pd.Timestamp:
    if value is None:
        return pd.NaT
    if isinstance(value, pd.Timestamp):
        return value
    text = str(value).strip()
    if not text:
        return pd.NaT
    if text.isdigit():
        if len(text) >= 14:
            return pd.to_datetime(text[:14], format="%Y%m%d%H%M%S", errors="coerce")
        if len(text) == 8:
            return pd.to_datetime(text, format="%Y%m%d", errors="coerce")
        if len(text) == 13:
            ts = pd.to_datetime(int(text), unit="ms", utc=True, errors="coerce")
            if pd.isna(ts):
                return pd.NaT
            return ts.tz_convert("Asia/Shanghai").tz_localize(None)
        if len(text) == 10:
            ts = pd.to_datetime(int(text), unit="s", utc=True, errors="coerce")
            if pd.isna(ts):
                return pd.NaT
            return ts.tz_convert("Asia/Shanghai").tz_localize(None)
    return pd.to_datetime(text, errors="coerce")


def resolve_core_indices_symbols() -> list[str]:
    return list(COMMON_INDICES)


def preview_symbols_scope(scope: str, *, limit: int = 20) -> list[str]:
    raw = str(scope or "").strip()
    if not raw or raw.lower() == "all_a":
        return []
    if raw.lower() == "core_indices":
        return resolve_core_indices_symbols()[:limit]
    path = Path(raw).expanduser()
    if path.exists() and path.is_file():
        values = [
            normalize_code(line.split("\t", 1)[0])
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        return [item for item in values if item][:limit]
    return [normalize_code(item) for item in raw.split(",") if normalize_code(item)][:limit]


def resolve_health_symbols_for_scope(
    scope: str,
    *,
    request_symbols: list[str] | None = None,
    limit: int = 20,
) -> list[str]:
    scope_key = str(scope or "").strip().lower()
    if scope_key in {"", "all_a"}:
        return resolve_core_indices_symbols()[: min(limit, len(COMMON_INDICES))]
    preview = [normalize_code(item) for item in list(request_symbols or []) if normalize_code(item)]
    merged = preview + [item for item in COMMON_INDICES if item not in preview]
    return merged[:limit]


def _candidate_calendar_roots(
    extra_roots: Sequence[str | Path],
    *,
    wsl_distro_name: str = "",
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in extra_roots:
        token = str(raw or "").strip()
        if not token:
            continue
        try:
            path, mapping = resolve_runtime_qlib_path(token, wsl_distro_name=wsl_distro_name)
        except Exception:
            path = host_path_to_local(token)
            mapping = {
                "requested_qlib_dir": token,
                "resolved_host_path": str(path),
                "path_mapping_source": "host_path_to_local",
                "wsl_distro_name": "",
            }
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        source_kind = "wsl" if str(mapping.get("path_mapping_source") or "").startswith("wsl_") or token.replace("\\", "/").startswith("/") else "windows"
        candidates.append(
            {
                "requested_root": token,
                "resolved_root": path,
                "source_kind": source_kind,
                "path_mapping_source": str(mapping.get("path_mapping_source") or ""),
                "wsl_distro_name": str(mapping.get("wsl_distro_name") or ""),
            }
        )
    return candidates


def _read_nonempty_lines(path: Path) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_local_calendar_index(
    start_ymd: str,
    end_ymd: str,
    calendar_roots: Sequence[str | Path],
    *,
    wsl_distro_name: str = "",
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for root_info in _candidate_calendar_roots(calendar_roots, wsl_distro_name=wsl_distro_name):
        qlib_dir = Path(root_info["resolved_root"])
        values: list[str] = []
        for name in ("day.txt", "day_future.txt"):
            path = qlib_dir / "calendars" / name
            days = normalize_calendar_days(_read_nonempty_lines(path))
            values.extend(day for day in days if start_ymd <= day <= end_ymd)
        entries.append(
            {
                **root_info,
                "confirmation_source": f"local_calendar_{root_info['source_kind']}",
                "days": sorted(set(values)),
            }
        )
    return entries


def _load_local_calendar_days(
    start_ymd: str,
    end_ymd: str,
    calendar_roots: Sequence[str | Path],
    *,
    wsl_distro_name: str = "",
) -> list[str]:
    values: list[str] = []
    for entry in _load_local_calendar_index(start_ymd, end_ymd, calendar_roots, wsl_distro_name=wsl_distro_name):
        values.extend(entry["days"])
    return sorted(set(values))


def _normalize_trade_day_values(raw_days: Sequence[object]) -> list[str]:
    values: list[str] = []
    for item in raw_days:
        text = str(item or "").strip()
        if not text:
            continue
        if text.isdigit():
            if len(text) == 8:
                values.append(text)
                continue
            if len(text) == 13:
                ts = pd.to_datetime(int(text), unit="ms", utc=True, errors="coerce")
                if not pd.isna(ts):
                    values.append(ts.tz_convert("Asia/Shanghai").strftime("%Y%m%d"))
                    continue
            if len(text) == 10:
                ts = pd.to_datetime(int(text), unit="s", utc=True, errors="coerce")
                if not pd.isna(ts):
                    values.append(ts.tz_convert("Asia/Shanghai").strftime("%Y%m%d"))
                    continue
        ts = pd.to_datetime(text, errors="coerce")
        if pd.isna(ts):
            continue
        values.append(ts.strftime("%Y%m%d"))
    return sorted(set(values))


def _ensure_holiday_data_ready(backend: Any) -> None:
    download = getattr(backend, "download_holiday_data", None)
    if callable(download):
        try:
            download()
        except Exception:
            pass


def _load_holiday_days(backend: Any) -> list[str]:
    getter = getattr(backend, "get_holidays", None)
    if not callable(getter):
        return []
    try:
        return normalize_calendar_days(getter() or [])
    except Exception:
        return []


def _business_days_from_holidays(start_ymd: str, end_ymd: str, holidays: Sequence[str]) -> list[str]:
    idx = pd.bdate_range(pd.Timestamp(start_ymd), pd.Timestamp(end_ymd))
    holiday_set = {str(item).strip() for item in holidays if str(item).strip()}
    return [day.strftime("%Y%m%d") for day in idx if day.strftime("%Y%m%d") not in holiday_set]


def _collect_backend_trade_days(backend: Any, start_ymd: str, end_ymd: str) -> list[str]:
    _ensure_holiday_data_ready(backend)
    days: list[str] = []
    holiday_days = _load_holiday_days(backend)
    if holiday_days:
        days.extend(_business_days_from_holidays(start_ymd, end_ymd, holiday_days))
    for market in ("SH", "SZ"):
        try:
            raw = backend.get_trading_dates(market, start_ymd, end_ymd, -1)
            days.extend(_normalize_trade_day_values(raw or []))
        except Exception:
            pass
        try:
            raw = backend.get_trading_calendar(market, start_ymd, end_ymd)
            days.extend(normalize_calendar_days(raw or []))
        except Exception:
            continue
    return sorted(set(days))


def get_trading_days(
    backend: Any,
    start_ymd: str,
    end_ymd: str,
    *,
    calendar_roots: Sequence[str | Path] = (),
    wsl_distro_name: str = "",
) -> list[str]:
    days = _collect_backend_trade_days(backend, start_ymd, end_ymd)
    days.extend(_load_local_calendar_days(start_ymd, end_ymd, calendar_roots, wsl_distro_name=wsl_distro_name))
    uniq = sorted(set(days))
    if uniq:
        return uniq
    idx = pd.bdate_range(pd.Timestamp(start_ymd), pd.Timestamp(end_ymd))
    return [day.strftime("%Y%m%d") for day in idx]


def inspect_trade_day(
    backend: Any,
    target_date: str,
    *,
    market: str = "SH",
    calendar_roots: Sequence[str | Path] = (),
    wsl_distro_name: str = "",
) -> dict[str, Any]:
    del market
    target_ymd = to_ymd(target_date)
    official = inspect_official_trade_day(target_ymd)
    backend_days = _collect_backend_trade_days(backend, "20100101", target_ymd)
    local_entries = _load_local_calendar_index("20100101", target_ymd, calendar_roots, wsl_distro_name=wsl_distro_name)
    local_days = sorted({day for entry in local_entries for day in entry["days"]})
    full_calendar = sorted(set(backend_days) | set(local_days))
    previous_trade_day = max((day for day in full_calendar if day < target_ymd), default="")
    backend_previous_trade_day = max((day for day in backend_days if day < target_ymd), default="")
    authoritative_entry = next((entry for entry in local_entries if entry["source_kind"] == "wsl"), local_entries[0] if local_entries else None)
    authoritative_hit = bool(authoritative_entry and target_ymd in set(authoritative_entry["days"]))
    windows_hit = any(entry["source_kind"] == "windows" and target_ymd in set(entry["days"]) for entry in local_entries)
    backend_hit = target_ymd in set(backend_days)
    non_authoritative_hits = [entry["confirmation_source"] for entry in local_entries if entry is not authoritative_entry and target_ymd in set(entry["days"])]
    warnings: list[str] = []
    runtime_observations = {
        "backend_hit": backend_hit,
        "authoritative_wsl_hit": authoritative_hit,
        "windows_hit": windows_hit,
        "non_authoritative_hits": list(non_authoritative_hits),
        "backend_previous_trade_day": backend_previous_trade_day,
    }
    runtime_consistency = "consistent"
    if bool(official.get("is_trade_day", False)):
        if not authoritative_hit:
            warnings.append("runtime_wsl_miss_target")
            runtime_consistency = "inconsistent"
        if not backend_hit:
            warnings.append("runtime_backend_miss_target")
            runtime_consistency = "inconsistent"
        if windows_hit and not authoritative_hit:
            warnings.append("runtime_windows_only_hit")
            runtime_consistency = "inconsistent"
    elif authoritative_hit or backend_hit or non_authoritative_hits:
        warnings.append("runtime_calendar_true_while_official_false")
        runtime_consistency = "inconsistent"
    if (not backend_hit) and backend_previous_trade_day:
        warnings.append("backend_previous_trade_day_mismatch")
    is_target_trade_day = bool(official.get("ok")) and bool(official.get("is_trade_day", False))
    return {
        "target_date": target_ymd,
        "target_trading_day": target_ymd if is_target_trade_day else "",
        "target_date_mapped": False,
        "is_target_trade_day": is_target_trade_day,
        "previous_trade_day": previous_trade_day,
        "confirmation_source": "official_online" if is_target_trade_day else "",
        "warnings": list(dict.fromkeys(warnings)),
        "official_status_code": str(official.get("official_status_code") or ""),
        "official_summary": str(official.get("official_summary") or ""),
        "official_conflict": bool(official.get("official_conflict", False)),
        "source_status": dict(official.get("source_status") or {}),
        "official_source_urls": dict(official.get("official_source_urls") or {}),
        "official_source_hashes": dict(official.get("official_source_hashes") or {}),
        "official_source_errors": dict(official.get("official_source_errors") or {}),
        "official_trade_days_year": dict(official.get("official_trade_days_year") or {}),
        "runtime_consistency": runtime_consistency,
        "runtime_observations": runtime_observations,
        "calendar_sources": [
            {
                "requested_root": str(entry["requested_root"]),
                "resolved_root": str(entry["resolved_root"]),
                "source_kind": str(entry["source_kind"]),
                "path_mapping_source": str(entry["path_mapping_source"]),
                "target_date_hit": target_ymd in set(entry["days"]),
            }
            for entry in local_entries
        ],
    }


def resolve_trade_day(
    backend: Any,
    target_date: str,
    *,
    market: str = "SH",
    calendar_roots: Sequence[str | Path] = (),
    wsl_distro_name: str = "",
) -> dict[str, Any]:
    payload = inspect_trade_day(
        backend,
        target_date,
        market=market,
        calendar_roots=calendar_roots,
        wsl_distro_name=wsl_distro_name,
    )
    if not bool(payload.get("is_target_trade_day", False)):
        official_status_code = str(payload.get("official_status_code") or "").strip()
        if official_status_code in {"official_calendar_unreachable", "official_calendar_conflict"}:
            raise ValueError(str(payload.get("official_summary") or official_status_code))
        raise ValueError(f"目标日期 {payload['target_date']} 未被确认是交易日")
    return payload

def _universe_cache_path(cache_root: Path, scope: str, asof_trade_day: str) -> Path:
    safe_scope = scope.replace("/", "_").replace("\\", "_").replace(":", "_")
    return cache_root / f"{safe_scope}_{asof_trade_day}.json"


def _resolve_all_a_symbols(
    backend: Any,
    asof_trade_day: str,
    *,
    cache_root: Path | None = None,
) -> list[str]:
    cache_path = _universe_cache_path(cache_root, "all_a", asof_trade_day) if cache_root else None
    if cache_path and cache_path.exists():
        cached = _json_load(cache_path).get("symbols", [])
        if isinstance(cached, list) and cached:
            return [normalize_code(item) for item in cached if normalize_code(item)]

    refresh = getattr(backend, "download_sector_data", None)
    if callable(refresh):
        try:
            refresh()
        except Exception:
            pass

    sectors: list[str] = []
    try:
        sectors = [str(item) for item in list(backend.get_sector_list() or [])]
    except Exception:
        sectors = []

    symbols: list[str] = []
    target_sector = next((name for name in SECTOR_CANDIDATES if name in sectors), None)
    if target_sector:
        try:
            symbols.extend(list(backend.get_stock_list_in_sector(target_sector) or []))
        except Exception:
            pass
    else:
        for sec_name in ("上证A股", "深证A股", "北证A股"):
            try:
                symbols.extend(list(backend.get_stock_list_in_sector(sec_name) or []))
            except Exception:
                continue

    normalized = sorted(
        set(
            [normalize_code(item) for item in symbols if normalize_code(item).endswith(VALID_SUFFIX)]
            + COMMON_INDICES
        )
    )
    if cache_path:
        _json_dump(
            cache_path,
            {
                "scope": "all_a",
                "asof_trade_day": asof_trade_day,
                "symbols": normalized,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
    return normalized


def resolve_universe(
    backend: Any,
    scope: str,
    asof_trade_day: str,
    *,
    cache_root: Path | None = None,
) -> dict[str, Any]:
    raw = str(scope or "").strip()
    raw_lower = raw.lower()
    if raw_lower in {"", "all_a"}:
        symbols = _resolve_all_a_symbols(backend, asof_trade_day, cache_root=cache_root)
    elif raw_lower == "core_indices":
        symbols = resolve_core_indices_symbols()
    else:
        path = Path(raw).expanduser()
        if path.exists() and path.is_file():
            symbols = [
                normalize_code(line.split("\t", 1)[0])
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            ]
        else:
            symbols = [normalize_code(item) for item in raw.split(",") if normalize_code(item)]
    symbols = sorted(set(item for item in symbols if item))
    return {
        "scope": raw or "all_a",
        "asof_trade_day": asof_trade_day,
        "symbols_total": len(symbols),
        "symbols": symbols,
    }


def pick_window_days(
    mode: str,
    trading_days: Sequence[str],
    target_trade_day: str,
    lookback_trading_days: int,
) -> list[str]:
    scoped = [day for day in trading_days if day <= target_trade_day]
    if not scoped:
        return []
    if mode == "full":
        return list(scoped)
    if mode == "tail":
        return [target_trade_day]
    return scoped[-max(1, int(lookback_trading_days or 1)) :]


def estimate_bars(symbols_count: int, trading_days_count: int, periods: Sequence[str]) -> int:
    total = 0
    for period in periods:
        if str(period) == "1m":
            total += symbols_count * trading_days_count * 240
        else:
            total += symbols_count * trading_days_count
    return total


def decide_route(
    symbols_count: int,
    trading_days_count: int,
    periods: Sequence[str],
    *,
    route_policy: RoutePolicy = DEFAULT_ROUTE_POLICY,
) -> RouteDecision:
    estimated = estimate_bars(symbols_count, trading_days_count, periods)
    if symbols_count > route_policy.max_symbols_mcp:
        return RouteDecision("bulk_sync", "symbols_threshold_exceeded", symbols_count, trading_days_count, estimated)
    if trading_days_count > route_policy.max_trading_days_mcp:
        return RouteDecision("bulk_sync", "trading_days_threshold_exceeded", symbols_count, trading_days_count, estimated)
    if estimated > route_policy.max_estimated_bars_mcp:
        return RouteDecision("bulk_sync", "estimated_bars_threshold_exceeded", symbols_count, trading_days_count, estimated)
    return RouteDecision("pull_bars", "within_mcp_threshold", symbols_count, trading_days_count, estimated)


def _metadata_key(period: str, symbol: str) -> str:
    return f"{period}:{normalize_code(symbol)}"


def build_integrity_plan(
    backend: Any,
    *,
    target_date: str,
    periods: Sequence[str],
    mode: str = "tail",
    lookback_trading_days: int = 20,
    symbols_scope: str = "all_a",
    metadata_path: Path | None = None,
    route_policy: RoutePolicy = DEFAULT_ROUTE_POLICY,
    plans_root: Path | None = None,
    cache_root: Path | None = None,
    calendar_roots: Sequence[str | Path] = (),
    wsl_distro_name: str = "",
) -> dict[str, Any]:
    trade_day_info = resolve_trade_day(backend, target_date, calendar_roots=calendar_roots, wsl_distro_name=wsl_distro_name)
    target_trade_day = trade_day_info["target_trading_day"]
    full_calendar = get_trading_days(
        backend,
        "20100101",
        target_trade_day,
        calendar_roots=calendar_roots,
        wsl_distro_name=wsl_distro_name,
    )
    expected_days = pick_window_days(mode, full_calendar, target_trade_day, lookback_trading_days)
    universe = resolve_universe(backend, symbols_scope, target_trade_day, cache_root=cache_root)
    symbols = universe["symbols"]

    metadata_file = Path(metadata_path) if metadata_path else Path()
    metadata = _json_load(metadata_file, default={"entries": {}}) if metadata_file else {"entries": {}}
    entries = dict(metadata.get("entries") or {})

    candidate_symbols: list[str] = []
    reasons_by_symbol: dict[str, list[str]] = {}
    for symbol in symbols:
        reasons: list[str] = []
        for period in periods:
            entry = dict(entries.get(_metadata_key(str(period), symbol)) or {})
            last_trade_day = str(entry.get("last_trade_day") or "")
            if not last_trade_day:
                reasons.append(f"{period}:no_metadata")
                continue
            if last_trade_day < target_trade_day:
                reasons.append(f"{period}:stale_to_{last_trade_day}")
        if reasons:
            candidate_symbols.append(symbol)
            reasons_by_symbol[symbol] = reasons
    if not candidate_symbols:
        candidate_symbols = list(symbols)

    trading_days_count = max(1, len(expected_days))
    route_decision = decide_route(len(candidate_symbols), trading_days_count, periods, route_policy=route_policy)
    plan = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_date": trade_day_info["target_date"],
        "target_trading_day": target_trade_day,
        "target_date_mapped": trade_day_info["target_date_mapped"],
        "mode": mode,
        "lookback_trading_days": int(lookback_trading_days or 20),
        "periods": [str(item) for item in periods],
        "symbols_scope": symbols_scope,
        "symbols_total": len(symbols),
        "candidate_symbols": candidate_symbols,
        "candidate_symbols_count": len(candidate_symbols),
        "expected_days": expected_days,
        "route_decision": asdict(route_decision),
        "reasons_by_symbol": reasons_by_symbol,
        "metadata_path": str(metadata_file) if metadata_file else "",
    }
    if plans_root:
        plan_path = Path(plans_root) / f"integrity_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        _json_dump(plan_path, plan)
        plan["plan_path"] = str(plan_path)
    return plan


def _frame_from_backend_item(item: object, symbol: str) -> pd.DataFrame:
    if item is None:
        return pd.DataFrame()
    if isinstance(item, pd.DataFrame):
        df = item.copy()
    else:
        df = pd.DataFrame(item)
    if df.empty:
        return df
    if "time" not in df.columns:
        if df.index.name == "time":
            df = df.reset_index()
        else:
            df = df.reset_index().rename(columns={"index": "time"})
    df["symbol"] = symbol
    return df


def _normalize_time_column(df: pd.DataFrame, period: str) -> pd.DataFrame:
    if df.empty:
        return df
    parsed = df["time"].map(parse_xt_time)
    df = df.loc[~parsed.isna()].copy()
    parsed = parsed.loc[~parsed.isna()]
    if period == "1d":
        df["time"] = parsed.dt.strftime("%Y-%m-%d")
    else:
        df["time"] = parsed.dt.strftime("%Y-%m-%d %H:%M:%S")
    return df


def _compute_factor(raw_df: pd.DataFrame, adj_df: pd.DataFrame) -> pd.Series:
    if raw_df.empty or adj_df.empty:
        return pd.Series(1.0, index=raw_df.index if not raw_df.empty else adj_df.index)
    merged = raw_df[["time", "close"]].merge(
        adj_df[["time", "close"]].rename(columns={"close": "adj_close"}),
        on="time",
        how="left",
    )
    factor = merged["adj_close"] / merged["close"]
    factor = factor.replace([pd.NA, float("inf"), float("-inf")], 1.0).fillna(1.0)
    return factor.astype(float)


def _rows_indicate_target_day_without_price_bar(df: pd.DataFrame, *, target_day: str) -> bool:
    if df.empty or not target_day:
        return False
    target_display = _display_trade_day(target_day)
    if not target_display:
        return False
    day_rows = df[df["time"].astype(str).str[:10] == target_display]
    if day_rows.empty:
        return False
    price_cols = [column for column in ("open", "high", "low", "close") if column in day_rows.columns]
    if not price_cols:
        return False
    if day_rows[price_cols].notna().to_numpy().any():
        return False
    volume_zero = True
    if "volume" in day_rows.columns:
        volume_zero = pd.to_numeric(day_rows["volume"], errors="coerce").fillna(0).eq(0).all()
    amount_zero = True
    if "amount" in day_rows.columns:
        amount_zero = pd.to_numeric(day_rows["amount"], errors="coerce").fillna(0).eq(0).all()
    return bool(volume_zero and amount_zero)


def pull_history_chunk(
    backend: Any,
    *,
    symbols: Sequence[str],
    period: str,
    start_time: str,
    end_time: str,
    cursor: int = 0,
    chunk_symbols: int = 100,
    adjusted_mode: str = "raw_with_factor",
    metadata_path: Path | None = None,
    chunks_root: Path | None = None,
) -> dict[str, Any]:
    normalized_symbols = [normalize_code(item) for item in symbols if normalize_code(item)]
    selected = normalized_symbols[cursor : cursor + max(1, int(chunk_symbols or 100))]
    if not selected:
        raise ValueError("当前 cursor 没有可拉取的标的")

    raw_payload = backend.get_market_data_ex(
        ["time", "open", "high", "low", "close", "volume", "amount"],
        list(selected),
        period,
        to_ymd(start_time),
        to_ymd(end_time),
        -1,
        "none",
        True,
    )
    adj_payload = {}
    if adjusted_mode == "raw_with_factor":
        adj_payload = backend.get_market_data_ex(
            ["time", "close"],
            list(selected),
            period,
            to_ymd(start_time),
            to_ymd(end_time),
            -1,
            "front",
            True,
        )

    frames: list[pd.DataFrame] = []
    metadata_updates: dict[str, dict[str, Any]] = {}
    imported_symbols: list[str] = []
    boundary_residuals: list[dict[str, Any]] = []
    target_trade_day = to_ymd(end_time)
    for symbol in selected:
        raw_item = (raw_payload or {}).get(symbol) if isinstance(raw_payload, dict) else None
        raw_df = _normalize_time_column(_frame_from_backend_item(raw_item, symbol), period)
        if raw_df.empty:
            continue
        if _rows_indicate_target_day_without_price_bar(raw_df, target_day=target_trade_day):
            boundary_residuals.append(
                {
                    "symbol": symbol,
                    "classification": "upstream_no_bar",
                    "periods_stale": [period],
                    "target_trade_day": _display_trade_day(target_trade_day),
                    "last_bar_time": raw_df["time"].iloc[-1],
                    "reason": "target_day_rows_without_price_bar",
                }
            )
        if adjusted_mode == "raw_with_factor":
            adj_item = (adj_payload or {}).get(symbol) if isinstance(adj_payload, dict) else None
            adj_df = _normalize_time_column(_frame_from_backend_item(adj_item, symbol), period)
            raw_df["factor"] = _compute_factor(raw_df, adj_df)
        else:
            raw_df["factor"] = 1.0
        frames.append(raw_df[["symbol", "time", "open", "high", "low", "close", "volume", "amount", "factor"]])
        imported_symbols.append(symbol)
        metadata_updates[_metadata_key(period, symbol)] = {
            "symbol": symbol,
            "period": period,
            "last_trade_day": raw_df["time"].iloc[-1][:10].replace("-", ""),
            "last_bar_time": raw_df["time"].iloc[-1],
            "rows": int(len(raw_df)),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

    chunk_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["symbol", "time", *FIELDS])
    chunk_root = Path(chunks_root) if chunks_root else Path.cwd() / "chunks"
    chunk_dir = chunk_root / datetime.now().strftime("%Y%m%d_%H%M%S")
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = chunk_dir / f"{period}_cursor_{cursor:05d}.parquet"
    chunk_df.to_parquet(chunk_path, index=False)

    if metadata_path and metadata_updates:
        current = _json_load(metadata_path, default={"entries": {}})
        entries = current.setdefault("entries", {})
        entries.update(metadata_updates)
        _json_dump(metadata_path, current)

    next_cursor = cursor + len(selected)
    if next_cursor >= len(normalized_symbols):
        next_cursor = None
    return {
        "period": period,
        "start_time": to_ymd(start_time),
        "end_time": to_ymd(end_time),
        "cursor": cursor,
        "next_cursor": next_cursor,
        "symbols_total": len(normalized_symbols),
        "chunk_symbols": selected,
        "chunk_symbols_count": len(selected),
        "rows": int(len(chunk_df)),
        "chunk_path": str(chunk_path),
        "metadata_path": str(metadata_path) if metadata_path else "",
        "imported_symbols": imported_symbols,
        "boundary_residuals": boundary_residuals,
    }


def qlib_symbol(code: str) -> str:
    text = normalize_code(code)
    if "." not in text:
        return text
    left, right = text.split(".", 1)
    return f"{right}{left}"


def _period_freq(period: str) -> str:
    return "1min" if str(period or "").strip() == "1m" else "day"


def _read_calendar(path: Path) -> list[str]:
    return _read_nonempty_lines(path)


def _write_calendar(path: Path, calendar: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = list(calendar)
    path.write_text("\n".join(values) + ("\n" if values else ""), encoding="utf-8")


def _feature_path(qlib_dir: Path, symbol: str, field: str, period: str) -> Path:
    freq = _period_freq(period)
    return qlib_dir / "features" / qlib_symbol(symbol).lower() / f"{field}.{freq}.bin"


def _read_feature(path: Path) -> tuple[int, np.ndarray]:
    if not path.exists():
        return 0, np.array([], dtype="<f4")
    raw = path.read_bytes()
    if len(raw) < 4:
        return 0, np.array([], dtype="<f4")
    start_idx = int(struct.unpack("<f", raw[:4])[0])
    arr = np.frombuffer(raw[4:], dtype="<f4").copy()
    return start_idx, arr


def _write_feature(path: Path, start_idx: int, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        fh.write(struct.pack("<f", float(start_idx)))
        fh.write(arr.astype("<f4").tobytes())


def _merge_feature(path: Path, global_calendar: list[str], values_by_time: dict[str, float]) -> bool:
    if not values_by_time:
        return False
    cal_map = {value: idx for idx, value in enumerate(global_calendar)}
    indices = sorted(cal_map[key] for key in values_by_time if key in cal_map)
    if not indices:
        return False

    new_start = indices[0]
    new_end = indices[-1]
    old_start, old_arr = _read_feature(path)
    if old_arr.size > 0:
        old_end = old_start + len(old_arr) - 1
        start_idx = min(old_start, new_start)
        end_idx = max(old_end, new_end)
        merged = np.full(end_idx - start_idx + 1, np.nan, dtype="<f4")
        merged[old_start - start_idx : old_start - start_idx + len(old_arr)] = old_arr
    else:
        start_idx = new_start
        end_idx = new_end
        merged = np.full(end_idx - start_idx + 1, np.nan, dtype="<f4")

    for time_key, value in values_by_time.items():
        idx = cal_map.get(time_key)
        if idx is None:
            continue
        merged[idx - start_idx] = np.float32(value)
    _write_feature(path, start_idx, merged)
    return True


def _load_instruments(path: Path) -> dict[str, tuple[str, str]]:
    records: dict[str, tuple[str, str]] = {}
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = [item for item in line.split("\t") if item]
        if len(parts) >= 3:
            records[parts[0]] = (parts[1], parts[2])
    return records


def _write_instruments(path: Path, records: dict[str, tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{symbol}\t{start}\t{end}" for symbol, (start, end) in sorted(records.items())]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def upsert_metadata(path: Path, updates: dict[str, dict[str, Any]]) -> None:
    payload = {"entries": {}}
    if path.exists():
        payload = _json_load(path, default={"entries": {}})
    entries = payload.setdefault("entries", {})
    entries.update(updates)
    _json_dump(path, payload)


def _build_future_day_calendar(
    backend: Any,
    *,
    last_trade_day: str,
    lookahead_days: int = FUTURE_CALENDAR_LOOKAHEAD_DAYS,
) -> list[str]:
    _ensure_holiday_data_ready(backend)
    start_ymd = pd.Timestamp(last_trade_day).strftime("%Y%m%d")
    end_ymd = (pd.Timestamp(last_trade_day) + pd.Timedelta(days=max(1, int(lookahead_days or 1)))).strftime("%Y%m%d")
    holidays = set(_load_holiday_days(backend))
    if holidays:
        inferred = _business_days_from_holidays(start_ymd, end_ymd, holidays)
        if inferred:
            return [f"{item[:4]}-{item[4:6]}-{item[6:8]}" for item in inferred]
    future_days: list[str] = []
    for market in ("SH", "SZ"):
        try:
            raw = backend.get_trading_calendar(market, start_ymd, end_ymd)
        except Exception:
            continue
        future_days.extend(
            [
                f"{item[:4]}-{item[4:6]}-{item[6:8]}"
                for item in normalize_calendar_days(raw or [])
            ]
        )
    return sorted(set(future_days))


def _replace_calendar_year_slice(existing_calendar: list[str], replacement_calendar: list[str], *, target_year: int) -> list[str]:
    year_prefix = f"{int(target_year):04d}-"
    preserved = [str(item).strip() for item in existing_calendar if str(item).strip() and not str(item).strip().startswith(year_prefix)]
    replacement = [str(item).strip() for item in replacement_calendar if str(item).strip()]
    return sorted(set(preserved + replacement))


def import_parquet_chunk(
    chunk_path: str | Path,
    qlib_dir: str | Path,
    period: str,
    *,
    backend: Any | None = None,
    future_day_calendar: list[str] | tuple[str, ...] | None = None,
    calendar_snapshot_year: int = 0,
) -> dict[str, Any]:
    chunk_file = Path(chunk_path)
    target_dir = Path(qlib_dir)
    df = pd.read_parquet(chunk_file)
    if df.empty:
        return {
            "chunk_path": str(chunk_file),
            "qlib_dir": str(target_dir),
            "period": period,
            "rows": 0,
            "symbols_processed": 0,
            "changed_files": [],
            "metadata_updates": {},
            "imported_symbols": [],
        }

    df = df.copy()
    df["symbol"] = df["symbol"].map(normalize_code)
    calendar_key = "day" if period == "1d" else "1min"
    df["time"] = df["time"].map(lambda value: str(value))
    calendar_path = target_dir / "calendars" / f"{calendar_key}.txt"
    existing_calendar = _read_calendar(calendar_path)
    merged_calendar = sorted(set(existing_calendar).union(df["time"].unique().tolist()))
    if merged_calendar != existing_calendar:
        _write_calendar(calendar_path, merged_calendar)

    changed_files: list[str] = [str(calendar_path.relative_to(target_dir)).replace("\\", "/")]
    instrument_path = target_dir / "instruments" / calendar_key / "all.txt"
    instruments = _load_instruments(instrument_path)
    metadata_updates: dict[str, dict[str, Any]] = {}
    imported_symbols: list[str] = []
    instrument_changed = False

    for symbol, symbol_df in df.groupby("symbol"):
        symbol_df = symbol_df.sort_values("time")
        q_symbol = qlib_symbol(symbol)
        symbol_written = False
        for field in FIELDS:
            if field not in symbol_df.columns:
                continue
            values: dict[str, float] = {}
            for _, row in symbol_df[["time", field]].dropna().iterrows():
                value = float(row[field])
                if math.isnan(value):
                    continue
                values[str(row["time"])] = value
            feature_path = _feature_path(target_dir, symbol, field, period)
            if _merge_feature(feature_path, merged_calendar, values):
                changed_files.append(str(feature_path.relative_to(target_dir)).replace("\\", "/"))
                symbol_written = True

        if not symbol_written:
            continue

        start = str(symbol_df["time"].iloc[0])
        end = str(symbol_df["time"].iloc[-1])
        old_start, old_end = instruments.get(q_symbol, (start, end))
        instruments[q_symbol] = (min(old_start, start), max(old_end, end))
        instrument_changed = True
        imported_symbols.append(symbol)
        metadata_updates[f"{period}:{symbol}"] = {
            "symbol": symbol,
            "period": period,
            "last_trade_day": end[:10].replace("-", ""),
            "last_bar_time": end,
            "rows": int(len(symbol_df)),
        }

    if instrument_changed:
        _write_instruments(instrument_path, instruments)
        changed_files.append(str(instrument_path.relative_to(target_dir)).replace("\\", "/"))

    if period == "1d" and merged_calendar:
        future_path = target_dir / "calendars" / "day_future.txt"
        future_calendar: list[str] = []
        normalized_future_calendar = [str(item).strip() for item in list(future_day_calendar or []) if str(item).strip()]
        if normalized_future_calendar:
            target_year = int(calendar_snapshot_year or 0)
            if target_year <= 0:
                target_year = int(str(normalized_future_calendar[0])[:4] or 0)
            future_calendar = _replace_calendar_year_slice(
                _read_calendar(future_path),
                normalized_future_calendar,
                target_year=target_year,
            )
        elif backend is not None:
            future_calendar = sorted(
                set(_build_future_day_calendar(backend, last_trade_day=merged_calendar[-1])).union(_read_calendar(future_path))
            )
        if future_calendar:
            _write_calendar(future_path, future_calendar)
            changed_files.append("calendars/day_future.txt")

    return {
        "chunk_path": str(chunk_file),
        "qlib_dir": str(target_dir),
        "period": period,
        "rows": int(len(df)),
        "symbols_processed": int(df["symbol"].nunique()),
        "changed_files": sorted(set(changed_files)),
        "metadata_updates": metadata_updates,
        "imported_symbols": sorted(set(imported_symbols)),
    }


def check_qlib_health(
    qlib_dir: str | Path,
    period: str,
    *,
    symbols: list[str] | None = None,
    wsl_distro_name: str = "",
) -> dict[str, Any]:
    target_dir, path_mapping = resolve_runtime_qlib_path(qlib_dir, wsl_distro_name=wsl_distro_name)
    freq = _period_freq(period)
    calendar_path = target_dir / "calendars" / f"{freq}.txt"
    instrument_path = target_dir / "instruments" / freq / "all.txt"
    checks: list[dict[str, Any]] = []

    checks.append({"name": "calendar_exists", "passed": calendar_path.exists(), "path": str(calendar_path)})
    checks.append({"name": "instrument_exists", "passed": instrument_path.exists(), "path": str(instrument_path)})

    for symbol in [normalize_code(item) for item in list(symbols or [])][:20]:
        for field in ("open", "close", "volume", "factor"):
            feature_path = _feature_path(target_dir, symbol, field, period)
            checks.append({"name": f"{symbol}:{field}", "passed": feature_path.exists(), "path": str(feature_path)})

    return {
        "qlib_dir": str(target_dir),
        **path_mapping,
        "period": period,
        "passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def _host_is_windows() -> bool:
    return os.name == "nt"


def windows_path_to_wsl(path: str) -> str:
    text = str(path or "").replace("\\", "/")
    if text.startswith("//wsl.localhost/") or text.startswith("//wsl$/"):
        parts = text.split("/")
        if len(parts) >= 5:
            return "/" + "/".join(parts[4:])
        return text
    if len(text) >= 3 and text[1:3] == ":/":
        drive = text[0].lower()
        return f"/mnt/{drive}{text[2:]}"
    return text


def host_path_to_local(path: str | Path) -> Path:
    token = str(path or "").strip()
    if _host_is_windows():
        return Path(token)
    return Path(windows_path_to_wsl(token)).expanduser()


def _extract_wsl_distro_name_from_unc(path: str | Path) -> str:
    text = str(path or "").strip().replace("\\", "/")
    if text.startswith("//wsl.localhost/") or text.startswith("//wsl$/"):
        parts = text.split("/")
        if len(parts) >= 4:
            return str(parts[3] or "").strip()
    return ""


def detect_wsl_distro_name(explicit: str = "", *, hints: Sequence[str | Path] | None = None) -> str:
    for candidate in (
        str(explicit or "").strip(),
        str(os.getenv("XTQMT_WSL_DISTRO_NAME", "") or "").strip(),
        str(os.getenv("WSL_DISTRO_NAME", "") or "").strip(),
    ):
        if candidate:
            return candidate
    for item in list(hints or []) + [os.getcwd(), __file__, *sys.argv]:
        distro_name = _extract_wsl_distro_name_from_unc(item)
        if distro_name:
            return distro_name
    return ""


def wsl_path_to_windows_unc(path: str | Path, *, wsl_distro_name: str) -> str:
    token = str(path or "").strip().replace("\\", "/")
    if not token.startswith("/"):
        return str(path or "").strip()
    relative = token.lstrip("/").replace("/", "\\")
    return f"\\\\wsl.localhost\\{wsl_distro_name}\\{relative}"


def resolve_runtime_qlib_path(
    qlib_dir: str | Path,
    *,
    wsl_distro_name: str = "",
) -> tuple[Path, dict[str, Any]]:
    token = str(qlib_dir or "").strip()
    if not token:
        raise ValueError("qlib_dir 不能为空")
    normalized = token.replace("\\", "/")
    mapping = {
        "requested_qlib_dir": token,
        "resolved_host_path": "",
        "path_mapping_source": "",
        "wsl_distro_name": "",
    }
    if _host_is_windows():
        if normalized.startswith("//wsl.localhost/") or normalized.startswith("//wsl$/"):
            resolved = Path(token)
            mapping["resolved_host_path"] = str(resolved)
            mapping["path_mapping_source"] = "wsl_unc_passthrough"
            mapping["wsl_distro_name"] = _extract_wsl_distro_name_from_unc(token)
            return resolved, mapping
        if normalized.startswith("/"):
            distro_name = detect_wsl_distro_name(wsl_distro_name)
            if not distro_name:
                raise ValueError(f"缺少 wsl_distro_name，无法在 Windows 主机解析 WSL 路径: {token}")
            resolved = Path(wsl_path_to_windows_unc(token, wsl_distro_name=distro_name))
            mapping["resolved_host_path"] = str(resolved)
            mapping["path_mapping_source"] = "wsl_unc"
            mapping["wsl_distro_name"] = distro_name
            return resolved, mapping
        resolved = Path(token)
        mapping["resolved_host_path"] = str(resolved)
        mapping["path_mapping_source"] = "windows_native"
        return resolved, mapping
    resolved = host_path_to_local(token)
    mapping["resolved_host_path"] = str(resolved)
    mapping["path_mapping_source"] = "host_path_to_local"
    mapping["wsl_distro_name"] = _extract_wsl_distro_name_from_unc(token)
    return resolved, mapping


def sync_manifest_files(
    manifest: dict[str, Any],
    *,
    qlib_dir: str | Path,
    local_qlib_dir_windows: str = DEFAULT_LOCAL_QLIB_DIR_WINDOWS,
    wsl_distro_name: str = "",
    progress_callback: Callable[[dict[str, Any]], object] | None = None,
    progress_interval: int = 500,
) -> dict[str, Any]:
    target_dir, path_mapping = resolve_runtime_qlib_path(qlib_dir, wsl_distro_name=wsl_distro_name)
    local_windows = str(manifest.get("local_qlib_dir_windows") or manifest.get("local_qlib_dir") or local_qlib_dir_windows)
    local_root = host_path_to_local(local_windows)
    copied: list[str] = []
    missing_sources: list[str] = []
    changed_paths = [str(item) for item in manifest.get("changed_files", []) if str(item).strip()]
    total_count = len(changed_paths)
    interval = max(1, int(progress_interval or 1))

    def emit_copy_progress() -> None:
        if progress_callback is None:
            return
        progress_callback(
            {
                "message": "sync_wsl:copy",
                "current_phase": "sync_wsl",
                "copied_count": len(copied),
                "missing_sources_count": len(missing_sources),
                "total_count": total_count,
                "expected_next": "sync_wsl:copy" if len(copied) + len(missing_sources) < total_count else "sync_wsl:done",
            }
        )

    for rel_path in changed_paths:
        src = local_root / rel_path
        dst = target_dir / rel_path
        if not src.exists():
            missing_sources.append(rel_path)
            if (len(copied) + len(missing_sources)) % interval == 0 or len(copied) + len(missing_sources) == total_count:
                emit_copy_progress()
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(str(dst))
        if (len(copied) + len(missing_sources)) % interval == 0 or len(copied) + len(missing_sources) == total_count:
            emit_copy_progress()

    return {
        "qlib_dir": str(target_dir),
        **path_mapping,
        "copied_count": len(copied),
        "copied_files": copied,
        "missing_sources": missing_sources,
        "missing_sources_count": len(missing_sources),
    }


def _display_trade_day(raw: str) -> str:
    token = str(raw or "").strip()
    if len(token) >= 10 and token[4] == "-" and token[7] == "-":
        return token[:10]
    if len(token) >= 8 and token[:8].isdigit():
        return f"{token[:4]}-{token[4:6]}-{token[6:8]}"
    return ""


def _compact_trade_day(raw: str) -> str:
    return _display_trade_day(raw).replace("-", "")


def _load_symbols_from_instrument_file(path: Path) -> list[str]:
    codes: list[str] = []
    for line in _read_nonempty_lines(path):
        parts = [item for item in line.split("\t") if item]
        if not parts:
            continue
        code = normalize_code(parts[0])
        if code:
            codes.append(code)
    return sorted(set(codes))


def _load_instrument_records(path: Path) -> dict[str, dict[str, str]]:
    records: dict[str, dict[str, str]] = {}
    for line in _read_nonempty_lines(path):
        parts = [item.strip() for item in line.split("\t") if item.strip()]
        if len(parts) < 3:
            continue
        raw_code = parts[0]
        code = normalize_code(raw_code)
        start = parts[1]
        end = parts[2]
        if not code:
            continue
        records[code] = {"raw_code": raw_code, "start": start, "end": end}
    return records


def _read_close_feature_tail(root: Path, *, raw_code: str, freq: str, calendar_entries: list[str]) -> dict[str, Any]:
    feature_path = root / "features" / qlib_symbol(raw_code).lower() / f"close.{freq}.bin"
    if not feature_path.exists() or not feature_path.is_file():
        return {"feature_exists": False, "feature_path": str(feature_path), "latest_bar_time": "", "latest_trade_day": ""}
    raw = feature_path.read_bytes()
    if len(raw) < 8 or not calendar_entries:
        return {"feature_exists": True, "feature_path": str(feature_path), "latest_bar_time": "", "latest_trade_day": ""}
    start_idx = int(struct.unpack("<f", raw[:4])[0])
    value_count = (len(raw) - 4) // 4
    for offset in range(value_count - 1, -1, -1):
        value = struct.unpack_from("<f", raw, 4 + offset * 4)[0]
        if math.isnan(value):
            continue
        calendar_idx = start_idx + offset
        if calendar_idx < 0 or calendar_idx >= len(calendar_entries):
            continue
        latest_bar_time = str(calendar_entries[calendar_idx]).strip()
        return {
            "feature_exists": True,
            "feature_path": str(feature_path),
            "latest_bar_time": latest_bar_time,
            "latest_trade_day": _display_trade_day(latest_bar_time),
        }
    return {"feature_exists": True, "feature_path": str(feature_path), "latest_bar_time": "", "latest_trade_day": ""}


def _assess_instrument_end_consistency(root: Path, periods: list[str], target_ymd: str) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for period in periods:
        freq = _period_freq(period)
        instrument_path = root / "instruments" / freq / "all.txt"
        calendar_entries = _read_nonempty_lines(root / "calendars" / f"{freq}.txt")
        records = _load_instrument_records(instrument_path)
        lagging: list[dict[str, str]] = []
        target_stale: list[dict[str, str]] = []
        checked = 0
        skipped_missing_feature = 0
        skipped_without_tail = 0
        for code, record in records.items():
            tail = _read_close_feature_tail(root, raw_code=record["raw_code"], freq=freq, calendar_entries=calendar_entries)
            if not tail["feature_exists"]:
                skipped_missing_feature += 1
                continue
            feature_day = _compact_trade_day(str(tail.get("latest_trade_day") or tail.get("latest_bar_time") or ""))
            if not feature_day:
                skipped_without_tail += 1
                continue
            checked += 1
            instrument_end_key = _compact_trade_day(record["end"])
            feature_tail = _display_trade_day(str(tail.get("latest_bar_time") or ""))
            if instrument_end_key and feature_day > instrument_end_key:
                lagging.append(
                    {
                        "symbol": code,
                        "raw_code": record["raw_code"],
                        "instrument_end": _display_trade_day(record["end"]),
                        "feature_tail": feature_tail,
                        "feature_tail_bar_time": str(tail.get("latest_bar_time") or ""),
                    }
                )
            if target_ymd and feature_day < target_ymd:
                target_stale.append(
                    {
                        "symbol": code,
                        "raw_code": record["raw_code"],
                        "feature_tail": feature_tail,
                        "feature_tail_bar_time": str(tail.get("latest_bar_time") or ""),
                        "target_trade_day": _display_trade_day(target_ymd),
                    }
                )
        summary[freq] = {
            "instrument_path": str(instrument_path),
            "calendar_path": str(root / "calendars" / f"{freq}.txt"),
            "records": len(records),
            "checked": checked,
            "lagging_count": len(lagging),
            "target_stale_count": len(target_stale),
            "skipped_missing_feature": skipped_missing_feature,
            "skipped_without_tail": skipped_without_tail,
            "examples": lagging[:20],
            "target_stale_examples": target_stale[:20],
        }
    return summary


def assess_qlib_acceptance(
    *,
    qlib_dir: str | Path,
    periods: list[str],
    target_trade_day: str,
    wsl_distro_name: str = "",
) -> dict[str, Any]:
    root, path_mapping = resolve_runtime_qlib_path(qlib_dir, wsl_distro_name=wsl_distro_name)
    root = root.expanduser().resolve()
    target_ymd = str(target_trade_day or "").strip().replace("-", "")
    target_day_display = _display_trade_day(target_ymd)
    blocking_issues: list[str] = []
    warnings: list[str] = []

    day_tail = _read_nonempty_lines(root / "calendars" / "day.txt")
    min_tail = _read_nonempty_lines(root / "calendars" / "1min.txt")
    future_tail = _read_nonempty_lines(root / "calendars" / "day_future.txt")
    day_tail_value = day_tail[-1] if day_tail else ""
    min_tail_value = min_tail[-1] if min_tail else ""
    future_tail_value = future_tail[-1] if future_tail else ""
    if "1d" in periods and target_day_display and day_tail_value != target_day_display:
        blocking_issues.append(f"day_calendar_tail_mismatch:{day_tail_value or '<missing>'}")
    if "1m" in periods and target_day_display:
        if not min_tail_value.startswith(target_day_display):
            blocking_issues.append(f"min_calendar_tail_mismatch:{min_tail_value or '<missing>'}")
        elif not min_tail_value.endswith("15:00:00"):
            blocking_issues.append(f"min_calendar_close_mismatch:{min_tail_value}")
    if "1d" in periods and target_day_display:
        if not future_tail_value:
            warnings.append("day_future_calendar_missing")
        elif future_tail_value <= target_day_display:
            warnings.append(f"day_future_calendar_stale:{future_tail_value}")

    instrument_counts = {
        "day": len(_read_nonempty_lines(root / "instruments" / "day" / "all.txt")),
        "1min": len(_read_nonempty_lines(root / "instruments" / "1min" / "all.txt")),
    }
    day_symbols = set(_load_symbols_from_instrument_file(root / "instruments" / "day" / "all.txt"))
    min_symbols = set(_load_symbols_from_instrument_file(root / "instruments" / "1min" / "all.txt"))
    day_only = sorted(day_symbols - min_symbols)
    min_only = sorted(min_symbols - day_symbols)
    if "1d" in periods and instrument_counts["day"] <= 0:
        blocking_issues.append("day_instruments_missing")
    if "1m" in periods and instrument_counts["1min"] <= 0:
        blocking_issues.append("min_instruments_missing")
    if "1d" in periods and "1m" in periods and (day_only or min_only):
        blocking_issues.append(f"day_vs_1min_instruments_mismatch:day_only={len(day_only)},min_only={len(min_only)}")
    instrument_end_consistency = _assess_instrument_end_consistency(root, periods, target_ymd)
    for freq, item in instrument_end_consistency.items():
        lagging_count = int(item.get("lagging_count") or 0)
        if lagging_count > 0:
            blocking_issues.append(f"instrument_end_lag:{freq}:count={lagging_count}")
        target_stale_count = int(item.get("target_stale_count") or 0)
        if target_stale_count > 0:
            blocking_issues.append(f"feature_tail_stale:{freq}:count={target_stale_count}")
    return {
        **path_mapping,
        "passed": not blocking_issues,
        "blocking_issues": blocking_issues,
        "warnings": warnings,
        "calendar_tails": {"day": day_tail_value, "1min": min_tail_value, "day_future": future_tail_value},
        "instrument_counts": instrument_counts,
        "instrument_diff": {
            "day_only": day_only[:20],
            "min_only": min_only[:20],
            "day_only_count": len(day_only),
            "min_only_count": len(min_only),
        },
        "instrument_end_consistency": instrument_end_consistency,
    }


def required_manifest_files(periods: Sequence[str]) -> list[str]:
    files: list[str] = []
    if "1d" in periods:
        files.extend(["calendars/day.txt", "calendars/day_future.txt", "instruments/day/all.txt"])
    if "1m" in periods:
        files.extend(["calendars/1min.txt", "instruments/1min/all.txt"])
    return sorted(set(files))


def scan_changed_files(root: Path, started_at: datetime) -> list[str]:
    changed: list[str] = []
    if not root.exists():
        return changed
    started_ts = started_at.timestamp() - 2
    for path in root.rglob("*"):
        if path.is_file() and path.stat().st_mtime >= started_ts:
            changed.append(str(path.relative_to(root)).replace("\\", "/"))
    return sorted(set(changed))


def classify_residuals(residuals: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    classified: list[dict[str, Any]] = []
    for item in residuals:
        payload = dict(item or {})
        classification = str(payload.get("classification") or "").strip()
        if not classification:
            periods_missing = [str(period) for period in payload.get("periods_missing", []) if str(period)]
            classification = "upstream_no_bar" if len(periods_missing) >= 2 else "vendor_boundary"
        payload["classification"] = classification
        payload["allowed_boundary"] = classification in ALLOWED_RESIDUAL_CLASSES
        classified.append(payload)
    return classified


def summarize_residuals(residuals: Sequence[dict[str, Any]]) -> dict[str, Any]:
    classified = classify_residuals(residuals)
    counts: dict[str, int] = {}
    allowed = 0
    disallowed = 0
    for item in classified:
        classification = str(item.get("classification") or "unclassified")
        counts[classification] = int(counts.get(classification, 0) or 0) + 1
        if item.get("allowed_boundary"):
            allowed += 1
        else:
            disallowed += 1
    return {
        "count": len(classified),
        "allowed_count": allowed,
        "disallowed_count": disallowed,
        "class_counts": counts,
        "items": classified,
    }


def apply_residuals_to_acceptance(
    acceptance_summary: dict[str, Any],
    residual_summary: dict[str, Any],
) -> dict[str, Any]:
    summary = dict(acceptance_summary or {})
    raw_blocking_issues = [str(item) for item in summary.get("blocking_issues", []) if str(item).strip()]
    residual_symbols_by_freq: dict[str, set[str]] = {}
    for item in dict(residual_summary or {}).get("items", []):
        payload = dict(item or {})
        if not payload.get("allowed_boundary"):
            continue
        symbol = normalize_code(str(payload.get("symbol") or ""))
        if not symbol:
            continue
        periods: list[str] = []
        periods.extend(str(period) for period in payload.get("periods_stale", []) if str(period).strip())
        periods.extend(str(period) for period in payload.get("periods_missing", []) if str(period).strip())
        for period in periods:
            residual_symbols_by_freq.setdefault(_period_freq(period), set()).add(symbol)

    instrument_end_consistency: dict[str, dict[str, Any]] = {}
    for freq, item in dict(summary.get("instrument_end_consistency") or {}).items():
        payload = dict(item or {})
        target_stale_examples = [dict(example) for example in payload.get("target_stale_examples", []) if isinstance(example, dict)]
        covered_symbols = residual_symbols_by_freq.get(freq, set())
        covered_examples = [
            example
            for example in target_stale_examples
            if normalize_code(str(example.get("symbol") or "")) in covered_symbols
        ]
        remaining_examples = [
            example
            for example in target_stale_examples
            if normalize_code(str(example.get("symbol") or "")) not in covered_symbols
        ]
        payload["target_stale_count"] = len(remaining_examples)
        payload["target_stale_examples"] = remaining_examples[:20]
        payload["residual_covered_count"] = len(covered_examples)
        payload["residual_covered_examples"] = covered_examples[:20]
        instrument_end_consistency[freq] = payload

    effective_blocking_issues: list[str] = []
    for issue in raw_blocking_issues:
        match = re.fullmatch(r"feature_tail_stale:(day|1min):count=\d+", issue)
        if not match:
            effective_blocking_issues.append(issue)
            continue
        freq = match.group(1)
        remaining_count = int(instrument_end_consistency.get(freq, {}).get("target_stale_count") or 0)
        if remaining_count > 0:
            effective_blocking_issues.append(f"feature_tail_stale:{freq}:count={remaining_count}")

    summary["raw_blocking_issues"] = raw_blocking_issues
    summary["instrument_end_consistency"] = instrument_end_consistency
    summary["blocking_issues"] = effective_blocking_issues
    summary["passed"] = not effective_blocking_issues
    return summary


def build_acceptance_verdict(
    acceptance_summary: dict[str, Any],
    residual_summary: dict[str, Any],
) -> str:
    if not bool(dict(acceptance_summary or {}).get("passed")):
        return "fail"
    if int(dict(residual_summary or {}).get("disallowed_count") or 0) > 0:
        return "fail"
    if int(dict(residual_summary or {}).get("allowed_count") or 0) > 0:
        return "pass_with_boundary_residuals"
    return "pass"


def find_listen_port_from_logs(log_root: str | Path) -> tuple[int | None, str]:
    root = Path(str(log_root or "")).expanduser()
    patterns = ("XtMiniQuote_*.log", "XtClient_datasource_*.log")
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(root.glob(pattern))
    candidates = [item for item in candidates if item.is_file()]
    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    port_pattern = re.compile(r"listen\s+port[^0-9]*(\d{4,6})", re.IGNORECASE)
    for candidate in candidates[:10]:
        lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines[-500:]):
            match = port_pattern.search(line)
            if match:
                return int(match.group(1)), str(candidate)
    return None, ""


__all__ = [
    "ALLOWED_RESIDUAL_CLASSES",
    "COMMON_INDICES",
    "DEFAULT_LOCAL_QLIB_DIR_WINDOWS",
    "DEFAULT_QLIB_DIR_WSL",
    "DEFAULT_ROUTE_POLICY",
    "FIELDS",
    "RouteDecision",
    "RoutePolicy",
    "apply_residuals_to_acceptance",
    "assess_qlib_acceptance",
    "build_acceptance_verdict",
    "build_integrity_plan",
    "check_qlib_health",
    "classify_residuals",
    "decide_route",
    "detect_wsl_distro_name",
    "find_listen_port_from_logs",
    "get_trading_days",
    "host_path_to_local",
    "import_parquet_chunk",
    "normalize_code",
    "parse_xt_time",
    "preview_symbols_scope",
    "pull_history_chunk",
    "required_manifest_files",
    "resolve_core_indices_symbols",
    "resolve_health_symbols_for_scope",
    "resolve_runtime_qlib_path",
    "resolve_trade_day",
    "resolve_universe",
    "scan_changed_files",
    "summarize_residuals",
    "sync_manifest_files",
    "to_ymd",
    "upsert_metadata",
]
