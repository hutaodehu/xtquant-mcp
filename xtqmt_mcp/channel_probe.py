"""Channel probe for broker-version xttrader read path."""

from __future__ import annotations

import importlib
import time
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from typing import Callable, Optional

from .connection_orchestrator import ConnectionOrchestratorConfig, run_connection_orchestrator
from .types import ChannelProbeItem, ChannelProbeReport
from .xtquant_env import ensure_xtquant_on_path


def _hint_for_exception(exc: Exception) -> tuple[str, str]:
    message = str(exc)
    low = message.lower()
    if "connect failed: -1" in low:
        return (
            "xttrader_connect_failed",
            "Check broker terminal login status, API permission, and session conflicts.",
        )
    if "module" in low and "xtquant" in low:
        return (
            "xtquant_import_failed",
            "Check QMT_SITE_PACKAGES/QMT_ROOT/QMT_EXE path settings.",
        )
    if "query_account_infos" in low:
        return (
            "query_account_infos_unavailable",
            "Current broker build may not support query_account_infos; use explicit account_id.",
        )
    return ("unknown", "Check MiniQMT status, account login, and local path settings.")


def _timed_check(name: str, fn: Callable[[], tuple[bool, dict[str, str]]]) -> ChannelProbeItem:
    begin = time.perf_counter()
    try:
        ok, details = fn()
        latency_ms = int((time.perf_counter() - begin) * 1000)
        return ChannelProbeItem(name=name, ok=ok, latency_ms=latency_ms, details=details)
    except Exception as exc:
        latency_ms = int((time.perf_counter() - begin) * 1000)
        code, hint = _hint_for_exception(exc)
        return ChannelProbeItem(
            name=name,
            ok=False,
            error_code=code,
            error_message=str(exc),
            latency_ms=latency_ms,
            hint=hint,
        )


@dataclass(frozen=True)
class ChannelProbeConfig:
    user_data_path: str
    account_id: str = ""
    auto_account: bool = False
    connect_retries: int = 3
    connect_retry_interval_seconds: float = 3.0
    session_candidates: tuple[int, ...] = (100, 101, 111)
    qmt_exe: str = ""
    wake_wait_seconds: int = 30
    require_connect_stage: bool = True
    require_subscribe_stage: bool = True
    require_snapshot_stage: bool = True
    snapshot_requires_position: bool = False


def _import_xt_modules() -> tuple[bool, dict[str, str]]:
    ensure_xtquant_on_path()
    xtquant_mod = importlib.import_module("xtquant")
    xttrader_mod = importlib.import_module("xtquant.xttrader")
    xttype_mod = importlib.import_module("xtquant.xttype")
    return True, {
        "xtquant": str(getattr(xtquant_mod, "__file__", "")),
        "xttrader": str(getattr(xttrader_mod, "__file__", "")),
        "xttype": str(getattr(xttype_mod, "__file__", "")),
    }


def _connect_once(user_data_path: str, session_id: int) -> tuple[bool, dict[str, str]]:
    ensure_xtquant_on_path()
    from xtquant.xttrader import XtQuantTrader  # type: ignore

    trader = XtQuantTrader(str(Path(user_data_path)), int(session_id))
    trader.start()
    try:
        code = int(trader.connect())
        if code != 0:
            raise RuntimeError(f"xttrader connect failed: {code} (session={session_id})")
        return True, {"session_id": str(session_id), "connect_code": str(code)}
    finally:
        try:
            trader.stop()
        except Exception:
            pass


def _discover_account(
    user_data_path: str,
    session_id: int,
    auto_account: bool,
    explicit_id: str,
) -> tuple[bool, dict[str, str], str]:
    account_id = (explicit_id or "").strip()
    if account_id:
        return True, {"mode": "explicit", "account_id": account_id}, account_id
    if not auto_account:
        return True, {"mode": "disabled", "account_id": ""}, ""

    from .adapters.xttrader_shadow import discover_stock_account_ids

    ids = discover_stock_account_ids(user_data_path=user_data_path, session_id=session_id)
    selected = ids[0] if ids else ""
    return bool(selected), {"mode": "auto", "candidates": ",".join(ids), "selected": selected}, selected


def run_channel_probe(cfg: ChannelProbeConfig) -> ChannelProbeReport:
    started_at = datetime.now()
    items: list[ChannelProbeItem] = []

    items.append(_timed_check("import_xt_modules", _import_xt_modules))

    qmt_exe = str(cfg.qmt_exe or os.environ.get("QMT_EXE", "")).strip()
    explicit_account = str(cfg.account_id or "").strip()
    if explicit_account:
        trace = run_connection_orchestrator(
            ConnectionOrchestratorConfig(
                qmt_exe=qmt_exe,
                qmt_userdata=cfg.user_data_path,
                account_id=explicit_account,
                session_plan=tuple(cfg.session_candidates),
                connect_retries=max(1, int(cfg.connect_retries)),
                connect_retry_interval_seconds=max(3.0, float(cfg.connect_retry_interval_seconds)),
                wake_wait_seconds=max(1, int(cfg.wake_wait_seconds)),
                require_connect_stage=bool(cfg.require_connect_stage),
                require_subscribe_stage=bool(cfg.require_subscribe_stage),
                require_snapshot_stage=bool(cfg.require_snapshot_stage),
                snapshot_requires_position=bool(cfg.snapshot_requires_position),
            )
        )
        for st in trace.stages:
            items.append(
                ChannelProbeItem(
                    name=st.name,
                    ok=bool(st.ok),
                    error_code=None if st.ok else (st.code or "stage_failed"),
                    error_message=None if st.ok else (st.message or "stage failed"),
                    latency_ms=st.latency_ms,
                    details=st.details,
                )
            )
        finished_at = datetime.now()
        selected_session = trace.selected_session_id
        return ChannelProbeReport(
            started_at=started_at,
            finished_at=finished_at,
            items=items,
            overall_ok=bool(trace.overall_ok),
            discovered_account_id=explicit_account if trace.overall_ok else "",
            selected_session_id=selected_session,
            precheck=trace.precheck,
            callback_events=trace.callback_events,
            failure_classification=trace.failure_classification,
            connection_trace=list(trace.stages),
        )

    selected_session: Optional[int] = None
    best_connect_item: Optional[ChannelProbeItem] = None
    retries = max(1, int(cfg.connect_retries))

    for session_id in cfg.session_candidates:
        for attempt in range(1, retries + 1):
            item = _timed_check(
                f"connect_session_{session_id}_attempt_{attempt}",
                lambda sid=session_id: _connect_once(cfg.user_data_path, sid),
            )
            items.append(item)
            best_connect_item = item
            if item.ok:
                selected_session = session_id
                break
            if attempt < retries:
                time.sleep(max(3.0, float(cfg.connect_retry_interval_seconds)))
        if selected_session is not None:
            break

    selected_account_id = ""
    if selected_session is not None:
        begin = time.perf_counter()
        try:
            ok, details, resolved = _discover_account(
                user_data_path=cfg.user_data_path,
                session_id=selected_session,
                auto_account=cfg.auto_account,
                explicit_id=cfg.account_id,
            )
            latency_ms = int((time.perf_counter() - begin) * 1000)
            items.append(
                ChannelProbeItem(
                    name="discover_account",
                    ok=ok,
                    latency_ms=latency_ms,
                    details=details,
                )
            )
            if ok:
                selected_account_id = resolved
        except Exception as exc:
            latency_ms = int((time.perf_counter() - begin) * 1000)
            code, hint = _hint_for_exception(exc)
            items.append(
                ChannelProbeItem(
                    name="discover_account",
                    ok=False,
                    error_code=code,
                    error_message=str(exc),
                    latency_ms=latency_ms,
                    hint=hint,
                )
            )
    else:
        code = best_connect_item.error_code if best_connect_item is not None else "xttrader_connect_failed"
        msg = best_connect_item.error_message if best_connect_item is not None else "no session connected"
        hint = best_connect_item.hint if best_connect_item is not None else "Check trading-terminal login and API permission."
        items.append(
            ChannelProbeItem(
                name="discover_account",
                ok=False,
                error_code=code,
                error_message=msg,
                hint=hint,
            )
        )

    finished_at = datetime.now()
    overall_ok = all(it.ok for it in items)
    return ChannelProbeReport(
        started_at=started_at,
        finished_at=finished_at,
        items=items,
        overall_ok=overall_ok,
        discovered_account_id=selected_account_id,
        selected_session_id=selected_session,
        precheck={},
        callback_events=[],
        failure_classification=("" if overall_ok else "connect_or_discovery_failed"),
        connection_trace=[],
    )
