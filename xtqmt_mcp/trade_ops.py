"""Trade-ops service for CLI manual operations in xtqmt_mcp."""

from __future__ import annotations

import ast
import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import socket
import time
from typing import Any, Iterable

from .order_state_store import SQLiteOrderStateStore
from .risk import BasicRiskEngine, RiskConfig, kill_switch_on
from .runtime_truth import is_prod_state_scope
from .session_resolution import build_runtime_session_resolution, build_session_plan_version, session_resolution_payload
from .xttrader_precheck import run_layered_user_data_precheck
from .types import (
    BrokerOrderAck,
    BrokerOrderIntent,
    DataOrigin,
    L1Snapshot,
    OrderPlaceRequest,
    OrderState,
    OrderStatus,
    Side,
    TradeCommandResult,
    is_terminal_order_status,
)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _is_decimal_identifier(value: Any) -> bool:
    token = str(value or "").strip()
    return bool(token) and token.isdigit()


def _safe_table_rows(table: Any) -> list[dict[str, Any]]:
    """Convert pandas-like tables to list[dict] without importing pandas."""

    if table is None:
        return []
    if isinstance(table, list):
        out: list[dict[str, Any]] = []
        for row in table:
            if isinstance(row, dict):
                out.append(dict(row))
        return out
    to_dict = getattr(table, "to_dict", None)
    if callable(to_dict):
        try:
            rows = to_dict(orient="records")
            if isinstance(rows, list):
                out_rows: list[dict[str, Any]] = []
                for row in rows:
                    if isinstance(row, dict):
                        out_rows.append(dict(row))
                return out_rows
        except Exception:
            return []
    return []


def _now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize_probe_field(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    token = value.strip()
    if not token:
        return token
    if token[0] not in "[{(":
        return token
    try:
        return ast.literal_eval(token)
    except Exception:
        return token


def _is_trading_session_time(ts: datetime) -> bool:
    hms = ts.strftime("%H:%M:%S")
    return ("09:30:00" <= hms <= "11:30:00") or ("13:00:00" <= hms <= "15:00:00")


def _trace_stage_pass(
    connection_trace: Iterable[dict[str, Any]],
    *,
    exact_name: str = "",
    prefix: str = "",
) -> bool:
    for item in connection_trace:
        if not isinstance(item, dict):
            continue
        stage_name = str(item.get("name", "") or "")
        if exact_name and stage_name != exact_name:
            continue
        if prefix and (not stage_name.startswith(prefix)):
            continue
        if bool(item.get("ok", False)):
            return True
    return False


def _adapter_connected_state(adapter: Any) -> bool | None:
    value = getattr(adapter, "_connected", None)
    if isinstance(value, bool):
        return value
    return None


def _is_xttrader_connect_failure(message: str) -> bool:
    return "xttrader connect failed" in str(message or "").casefold()


def _tcp_port_ready(host: str, port: int, timeout_ms: int = 500) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(max(0.1, float(timeout_ms) / 1000.0))
    try:
        sock.connect((host, int(port)))
        return True
    except Exception:
        return False
    finally:
        try:
            sock.close()
        except Exception:
            pass


@dataclass(frozen=True)
class TradeOpsConfig:
    """Runtime config for manual trade operations."""

    account_id: str
    trading_day: date
    event_mode: str = "tick"
    output_dir: str = "output"
    state_dir: str = "state"
    execution_mode: str = "live"
    enforce_guard_token: bool = True
    enforce_trading_session: bool = True
    risk_max_single_order_notional: float = 200000.0
    risk_max_daily_notional: float = 2000000.0
    risk_white_list: tuple[str, ...] = ()
    kill_switch_file: str = ""
    pretrade_connect_window: int = 5
    pretrade_connect_threshold: float = 0.9
    pretrade_connect_interval_seconds: float = 3.0
    price_mode: str = "l1_protect"
    qmt_exe: str = ""
    qmt_userdata: str = ""
    session_candidates: tuple[int, ...] = (100, 101, 111)
    connect_retries: int = 3
    connect_retry_interval_seconds: float = 3.0
    wake_wait_seconds: int = 30
    require_connect_stage: bool = True
    require_subscribe_stage: bool = True
    require_snapshot_stage: bool = True
    snapshot_requires_position: bool = False


@dataclass(frozen=True)
class TradeOpsResult:
    """Unified command result wrapper with payload."""

    command: str
    ok: bool
    payload: dict[str, Any]


class TradeOpsService:
    """Encapsulate CLI trade/query operations with strict governance gates."""

    def __init__(
        self,
        cfg: TradeOpsConfig,
        *,
        market_data_provider: Any,
        shadow_adapter: Any,
        broker_order_adapter: Any,
        broker_order_adapter_factory: Any | None = None,
        broker_order_adapter_requires_write_permission: bool = False,
        session_resolution: Any | None = None,
    ) -> None:
        self.cfg = cfg
        self.market_data = market_data_provider
        self.shadow = shadow_adapter
        self.broker = broker_order_adapter
        self._broker_order_adapter_factory = broker_order_adapter_factory
        self._broker_adapters: dict[bool, Any] = {}
        if broker_order_adapter is not None:
            self._broker_adapters[bool(broker_order_adapter_requires_write_permission)] = broker_order_adapter
        self._base_session_resolution = session_resolution_payload(session_resolution)
        self._runtime_session_resolution: dict[str, Any] = {}
        self.state_store = SQLiteOrderStateStore(cfg.state_dir)
        self.risk_engine = BasicRiskEngine(
            RiskConfig(
                max_single_order_notional=float(cfg.risk_max_single_order_notional),
                max_daily_notional=float(cfg.risk_max_daily_notional),
                white_list=tuple(cfg.risk_white_list or ()),
            )
        )
        self._daily_root = Path(cfg.output_dir) / cfg.trading_day.strftime("%Y%m%d")
        self._real_dir = self._daily_root / "real"
        self._audit_dir = self._daily_root / "audit"
        self._real_dir.mkdir(parents=True, exist_ok=True)
        self._audit_dir.mkdir(parents=True, exist_ok=True)
        self._cumulative_notional_today = 0.0

    def close(self) -> None:
        try:
            self.state_store.close()
        except Exception:
            pass
        closables: list[Any] = [self.shadow, self.broker]
        closables.extend(self._broker_adapters.values())
        seen: set[int] = set()
        for obj in closables:
            if obj is None:
                continue
            obj_id = id(obj)
            if obj_id in seen:
                continue
            seen.add(obj_id)
            close_fn = getattr(obj, "close", None)
            if callable(close_fn):
                try:
                    close_fn()
                except Exception:
                    continue

    @property
    def base_session_resolution(self) -> dict[str, Any]:
        return dict(self._base_session_resolution or {})

    @property
    def session_resolution(self) -> dict[str, Any]:
        return self.effective_session_resolution()

    @session_resolution.setter
    def session_resolution(self, value: Any) -> None:
        self._base_session_resolution = session_resolution_payload(value)
        self._runtime_session_resolution = {}

    def effective_session_resolution(self) -> dict[str, Any]:
        runtime_payload = dict(self._runtime_session_resolution or {})
        if runtime_payload:
            return runtime_payload
        return dict(self._base_session_resolution or {})

    def runtime_session_override(self) -> dict[str, Any]:
        effective = self.effective_session_resolution()
        override = effective.get("runtime_resolution_event")
        return dict(override or {}) if isinstance(override, dict) else {}

    def _execution_mode(self) -> str:
        return str(getattr(self.cfg, "execution_mode", "live") or "live").strip().lower()

    def _flow_smoke_mode(self) -> bool:
        return self._execution_mode() == "flow_smoke"

    def owner_managed_session_id(self) -> int | None:
        getter = getattr(self.shadow, "active_session_id", None)
        if callable(getter):
            try:
                value = getter()
            except Exception:
                value = None
        else:
            value = getattr(self.shadow, "_active_session_id", None)
        if value is None:
            return None
        try:
            session_id = int(value)
        except Exception:
            return None
        if session_id <= 0:
            return None
        return session_id

    def _broker_adapter_session_id(self, adapter: Any) -> str:
        getter = getattr(adapter, "active_session_id", None)
        if callable(getter):
            try:
                value = getter()
            except Exception:
                value = None
        else:
            value = getattr(adapter, "_active_session_id", None)
        token = str(value or "").strip()
        return token

    def _owner_managed_broker_fresh_verify(self) -> dict[str, Any] | None:
        adapter = None
        close_after = False
        if callable(self._broker_order_adapter_factory):
            try:
                adapter = self._broker_order_adapter_factory(False)
                close_after = True
            except Exception as exc:
                return {
                    "available": True,
                    "ok": False,
                    "error": str(exc),
                    "fresh_connect_attempted": False,
                    "connected_before": None,
                    "connected_after": None,
                    "session_id": "",
                    "rows_count": None,
                }
        else:
            adapter = self.broker
        query_fn = getattr(adapter, "query_open_orders", None)
        if not callable(query_fn):
            if close_after:
                close_fn = getattr(adapter, "close", None)
                if callable(close_fn):
                    try:
                        close_fn()
                    except Exception:
                        pass
            return None
        connected_before = _adapter_connected_state(adapter)
        try:
            rows = query_fn(self.cfg.account_id) or []
            connected_after = _adapter_connected_state(adapter)
            return {
                "available": True,
                "ok": True,
                "error": "",
                "fresh_connect_attempted": bool(connected_before is False),
                "connected_before": connected_before,
                "connected_after": connected_after,
                "session_id": self._broker_adapter_session_id(adapter),
                "rows_count": len(list(rows)),
            }
        except Exception as exc:
            return {
                "available": True,
                "ok": False,
                "error": str(exc),
                "fresh_connect_attempted": bool(connected_before is False),
                "connected_before": connected_before,
                "connected_after": _adapter_connected_state(adapter),
                "session_id": self._broker_adapter_session_id(adapter),
                "rows_count": None,
            }
        finally:
            if close_after:
                close_fn = getattr(adapter, "close", None)
                if callable(close_fn):
                    try:
                        close_fn()
                    except Exception:
                        pass

    def realign_session_resolution(
        self,
        preferred_session_id: Any,
        *,
        reason: str = "",
        event_source: str = "runtime_realign",
        owner_session_id: Any = None,
        observed_probe_session_id: Any = None,
        attempted_broker_session_id: Any = None,
    ) -> dict[str, Any]:
        payload = build_runtime_session_resolution(
            self.effective_session_resolution(),
            preferred_session_id,
            reason=reason,
            event_source=event_source,
            owner_session_id=owner_session_id,
            observed_probe_session_id=observed_probe_session_id,
            attempted_broker_session_id=attempted_broker_session_id,
        )
        if not payload:
            return self.effective_session_resolution()
        self._runtime_session_resolution = dict(payload)
        return self.effective_session_resolution()

    def _attach_session_resolution(self, payload: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(payload or {})
        effective_resolution = self.effective_session_resolution()
        if effective_resolution and "session_resolution" not in enriched:
            enriched["session_resolution"] = dict(effective_resolution)
        if effective_resolution and "effective_session_resolution" not in enriched:
            enriched["effective_session_resolution"] = dict(effective_resolution)
        base_resolution = self.base_session_resolution
        if base_resolution and "base_session_resolution" not in enriched:
            enriched["base_session_resolution"] = dict(base_resolution)
        runtime_override = self.runtime_session_override()
        if runtime_override and "runtime_session_override" not in enriched:
            enriched["runtime_session_override"] = dict(runtime_override)
        if "session_plan_version" not in enriched:
            enriched["session_plan_version"] = self._session_plan_version_text()
        if "execution_mode" not in enriched:
            enriched["execution_mode"] = self._execution_mode()
        return enriched

    def _result(self, command: str, *, ok: bool, payload: dict[str, Any]) -> TradeOpsResult:
        return TradeOpsResult(command=command, ok=bool(ok), payload=self._attach_session_resolution(payload))

    def _resolved_session_id_text(self) -> str:
        return str(self.session_resolution.get("resolved_session_id") or "").strip()

    def _resolved_base_session_id_text(self) -> str:
        return str(self.session_resolution.get("resolved_base_session_id") or "").strip()

    def _effective_session_plan_tokens(self) -> list[str]:
        plan = self.session_resolution.get("effective_session_plan") or []
        tokens: list[str] = []
        for item in plan:
            token = str(item or "").strip()
            if token:
                tokens.append(token)
        return tokens

    def _session_plan_version_text(self) -> str:
        version = str(self.session_resolution.get("session_plan_version") or "").strip()
        if version:
            return version
        return build_session_plan_version(self.session_resolution.get("effective_session_plan"))

    def _build_write_session_alignment(self, observed_session_id: Any) -> dict[str, Any]:
        observed_token = str(observed_session_id or "").strip()
        resolved_token = self._resolved_session_id_text()
        resolved_base_token = self._resolved_base_session_id_text()
        effective_plan_payload = list(self.session_resolution.get("effective_session_plan") or [])
        effective_plan_tokens = self._effective_session_plan_tokens()
        observed_in_plan = bool(observed_token) and observed_token in effective_plan_tokens
        same_session = bool(observed_token) and bool(resolved_token) and observed_token == resolved_token

        if not resolved_token:
            reason = "resolved_write_session_missing"
        elif not observed_token:
            reason = "probe_session_missing"
        elif same_session:
            reason = "same_session"
        elif observed_in_plan:
            reason = "probe_session_differs_from_resolved_write_session"
        else:
            reason = "probe_session_outside_effective_plan"

        return {
            "resolved_session_id": resolved_token,
            "resolved_base_session_id": resolved_base_token,
            "effective_session_plan": effective_plan_payload,
            "session_plan_version": self._session_plan_version_text(),
            "observed_probe_session_id": observed_token,
            "observed_probe_session_in_effective_plan": bool(observed_in_plan),
            "same_session_as_write_path": bool(same_session),
            "same_plan_verdict": bool(same_session),
            "same_plan_reason": str(reason),
        }

    def _decorate_order_submission_scope(
        self,
        result: TradeOpsResult,
        *,
        broker_submission_attempted: bool,
        local_gate_intercepted: bool,
        submission_scope: str,
        submission_stage: str,
    ) -> TradeOpsResult:
        result.payload["broker_submission_attempted"] = bool(broker_submission_attempted)
        result.payload["local_gate_intercepted"] = bool(local_gate_intercepted)
        result.payload["submission_scope"] = str(submission_scope)
        result.payload["submission_stage"] = str(submission_stage)
        return result

    def _cached_broker_adapter_matches_session_resolution(self, adapter: Any) -> bool:
        cfg = getattr(adapter, "cfg", None)
        if cfg is None:
            return True
        expected_session_id = self._resolved_session_id_text()
        if not expected_session_id:
            return True
        actual_session_id = str(getattr(cfg, "session_id", "") or "").strip()
        if not actual_session_id:
            return True
        return actual_session_id == expected_session_id

    def _drop_cached_broker_adapter(self, mode: bool, adapter: Any) -> None:
        self._broker_adapters.pop(bool(mode), None)
        if self.broker is adapter:
            self.broker = None
        close_fn = getattr(adapter, "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except Exception:
                pass

    def _ensure_broker_adapter(self, *, require_write_permission: bool) -> Any | None:
        mode = bool(require_write_permission)
        adapter = self._broker_adapters.get(mode)
        if adapter is not None:
            if callable(self._broker_order_adapter_factory) and (
                not self._cached_broker_adapter_matches_session_resolution(adapter)
            ):
                self._drop_cached_broker_adapter(mode, adapter)
            else:
                self.broker = adapter
                return adapter
        if self.broker is not None and self._broker_order_adapter_factory is None:
            self._broker_adapters[mode] = self.broker
            return self.broker
        if not callable(self._broker_order_adapter_factory):
            return None
        adapter = self._broker_order_adapter_factory(mode)
        self._broker_adapters[mode] = adapter
        self.broker = adapter
        return adapter

    def _append_csv(self, path: Path, fieldnames: list[str], row: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists()
        with path.open("a", encoding="utf-8", newline="") as fd:
            writer = csv.DictWriter(fd, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    def _kill_switch_configured(self) -> bool:
        return bool(str(self.cfg.kill_switch_file or "").strip())

    def _kill_switch_required_for_write(self) -> bool:
        return bool(is_prod_state_scope(self.cfg.state_dir))

    def _account_asset(self) -> dict[str, Any]:
        if self.shadow is None:
            virtual_cash = float(max(self.cfg.risk_max_daily_notional, self.cfg.risk_max_single_order_notional))
            return {
                "account_id": str(self.cfg.account_id),
                "cash": virtual_cash,
                "total_asset": virtual_cash,
                "market_value": 0.0,
            }
        rows = _safe_table_rows(self.shadow.get_asset())
        if not rows:
            return {}
        row = rows[0]
        return {
            "account_id": str(row.get("account_id") or self.cfg.account_id),
            "cash": _safe_float(row.get("cash")),
            "total_asset": _safe_float(row.get("total_asset")),
            "market_value": _safe_float(row.get("market_value")),
        }

    def _positions(self) -> list[dict[str, Any]]:
        if self.shadow is None:
            return []
        rows = _safe_table_rows(self.shadow.get_positions())
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "account_id": str(row.get("account_id") or self.cfg.account_id),
                    "code": str(row.get("stock_code") or row.get("code") or "").strip().upper(),
                    "quantity": _safe_int(row.get("quantity"), 0),
                    "sellable": _safe_int(row.get("sellable"), 0),
                    "avg_price": _safe_float(row.get("avg_price")),
                    "market_value": _safe_float(row.get("market_value")),
                }
            )
        return out

    def _run_connect_gate(self) -> dict[str, Any]:
        started_at = _now_text()
        started_monotonic = time.perf_counter()
        expected_write_session_id = self._resolved_session_id_text()
        expected_base_session_id = self._resolved_base_session_id_text()
        expected_effective_session_plan = list(self.session_resolution.get("effective_session_plan") or [])
        if self._flow_smoke_mode():
            return {
                "enabled": False,
                "pass": True,
                "attempts": 0,
                "ok_count": 0,
                "threshold": 0.0,
                "interval_seconds": 0.0,
                "samples": [],
                "reason": "flow_smoke_connect_gate_disabled",
                "gate_source": "probe.connection",
                "session_plan_version": self._session_plan_version_text(),
                "expected_write_session_id": expected_write_session_id,
                "expected_base_session_id": expected_base_session_id,
                "expected_effective_session_plan": expected_effective_session_plan,
                "session_alignment": {
                    "observed_session_ids": [],
                    "all_samples_in_effective_plan": False,
                    "same_session_as_write_path": False,
                    "same_plan_verdict": False,
                    "same_plan_reason": "flow_smoke_connect_gate_disabled",
                },
                "started_at": started_at,
                "finished_at": _now_text(),
                "duration_ms": round((time.perf_counter() - started_monotonic) * 1000.0, 2),
            }
        probe_result = self.probe_connection()
        probe_payload = dict(probe_result.payload or {})
        write_authority_snapshot = self._write_authority_snapshot_from_probe_payload(probe_payload)
        write_alignment = dict(probe_payload.get("write_session_alignment") or {})
        observed_probe_session_id = str(
            probe_payload.get("observed_probe_session_id") or write_alignment.get("observed_probe_session_id") or ""
        ).strip()
        observed_session_ids = [observed_probe_session_id] if observed_probe_session_id else []
        same_plan_reason = str(write_alignment.get("same_plan_reason") or probe_payload.get("reason") or "").strip()
        same_plan_verdict = bool(probe_payload.get("same_plan_verdict", False))
        same_session_as_write_path = bool(write_alignment.get("same_session_as_write_path", False))
        all_samples_in_effective_plan = bool(
            write_alignment.get("observed_probe_session_in_effective_plan", False) or same_session_as_write_path
        )
        connect_code = str(probe_payload.get("connect_code", "") or "").strip()
        samples = []
        if observed_probe_session_id or connect_code or probe_payload.get("reason"):
            samples.append(
                {
                    "attempt": 1,
                    "ts": str(probe_payload.get("ts") or _now_text()),
                    "ok": bool(probe_payload.get("fresh_connect_verified", False)),
                    "connect_code": connect_code,
                    "session_id": observed_probe_session_id,
                    "error": str(probe_payload.get("write_permission_block_reason") or probe_payload.get("reason") or ""),
                }
            )
        passed = bool(
            same_plan_verdict
            and bool(probe_payload.get("probe_complete_verdict", False))
            and bool(probe_payload.get("fresh_connect_verified", False))
            and bool(probe_payload.get("write_authority_ready", False))
        )
        reason = str(probe_payload.get("reason") or probe_payload.get("write_permission_block_reason") or "").strip()
        if passed:
            reason = "ok"
        return {
            "enabled": True,
            "pass": passed,
            "attempts": len(samples),
            "ok_count": 1 if passed else 0,
            "success_rate": 1.0 if passed else 0.0,
            "threshold": 1.0,
            "interval_seconds": 0.0,
            "samples": samples,
            "reason": str(reason),
            "gate_source": "probe.connection",
            "session_plan_version": str(probe_payload.get("session_plan_version") or self._session_plan_version_text()),
            "expected_write_session_id": expected_write_session_id,
            "expected_base_session_id": expected_base_session_id,
            "expected_effective_session_plan": expected_effective_session_plan,
            "write_authority_snapshot": write_authority_snapshot,
            "session_alignment": {
                "observed_session_ids": observed_session_ids,
                "all_samples_in_effective_plan": bool(all_samples_in_effective_plan),
                "same_session_as_write_path": bool(same_session_as_write_path),
                "same_plan_verdict": bool(same_plan_verdict),
                "same_plan_reason": str(same_plan_reason),
            },
            "started_at": started_at,
            "finished_at": _now_text(),
            "duration_ms": round((time.perf_counter() - started_monotonic) * 1000.0, 2),
        }

    def _write_authority_snapshot_from_probe_payload(self, probe_payload: dict[str, Any]) -> dict[str, Any]:
        write_alignment = dict(probe_payload.get("write_session_alignment") or {})
        return {
            "ready": bool(
                probe_payload.get("same_plan_verdict", False)
                and probe_payload.get("probe_complete_verdict", False)
                and probe_payload.get("fresh_connect_verified", False)
                and probe_payload.get("write_authority_ready", False)
            ),
            "blocking_reason": str(
                probe_payload.get("reason") or probe_payload.get("write_permission_block_reason") or ""
            ).strip(),
            "resolved_session_id": str(write_alignment.get("resolved_session_id") or probe_payload.get("session_id") or "").strip(),
            "observed_probe_session_id": str(
                probe_payload.get("observed_probe_session_id") or write_alignment.get("observed_probe_session_id") or ""
            ).strip(),
            "same_plan_verdict": bool(probe_payload.get("same_plan_verdict", False)),
            "probe_complete_verdict": bool(probe_payload.get("probe_complete_verdict", False)),
            "fresh_connect_verified": bool(probe_payload.get("fresh_connect_verified", False)),
            "write_authority_ready": bool(probe_payload.get("write_authority_ready", False)),
            "session_plan_version": str(probe_payload.get("session_plan_version") or self._session_plan_version_text()),
            "source": "probe.connection",
        }

    def _write_authority_snapshot(self) -> dict[str, Any]:
        if self._flow_smoke_mode():
            return {
                "ready": True,
                "blocking_reason": "",
                "resolved_session_id": self._resolved_session_id_text(),
                "observed_probe_session_id": self._resolved_session_id_text(),
                "same_plan_verdict": True,
                "probe_complete_verdict": True,
                "fresh_connect_verified": True,
                "write_authority_ready": True,
                "session_plan_version": self._session_plan_version_text(),
                "source": "flow_smoke",
            }
        probe_result = self.probe_connection()
        probe_payload = dict(probe_result.payload or {})
        return self._write_authority_snapshot_from_probe_payload(probe_payload)

    def _snapshot_l1(self, code: str) -> L1Snapshot | None:
        try:
            event = self.market_data.latest_online_event(str(code).upper(), self.cfg.trading_day, self.cfg.event_mode)
        except Exception:
            return None
        if event is None:
            return None
        return L1Snapshot(
            code=str(event.code).upper(),
            ts=event.ts,
            bid1=_safe_float(event.bid1),
            bid2=_safe_float(getattr(event, "bid2", None)),
            bid3=_safe_float(getattr(event, "bid3", None)),
            ask1=_safe_float(event.ask1),
            ask2=_safe_float(getattr(event, "ask2", None)),
            ask3=_safe_float(getattr(event, "ask3", None)),
            last_price=_safe_float(event.last_price),
            source=event.source if isinstance(event.source, DataOrigin) else DataOrigin.ONLINE_PULL,
            depth_available_levels=max(
                1,
                int(
                    sum(
                        1
                        for bid, ask in (
                            (_safe_float(event.bid1), _safe_float(event.ask1)),
                            (_safe_float(getattr(event, "bid2", None)), _safe_float(getattr(event, "ask2", None))),
                            (_safe_float(getattr(event, "bid3", None)), _safe_float(getattr(event, "ask3", None))),
                        )
                        if bid is not None or ask is not None
                    )
                ),
            ),
        )

    def _session_gate(self, l1_ts: datetime) -> dict[str, Any]:
        """Evaluate whether current request is in tradable session."""

        if self._flow_smoke_mode():
            return {
                "enabled": False,
                "pass": True,
                "reason": "flow_smoke_session_gate_disabled",
                "local_ts": _now_text(),
                "snapshot_ts": l1_ts.isoformat(),
                "trading_day": self.cfg.trading_day.isoformat(),
                "local_ok": True,
                "snapshot_ok": True,
                "trading_day_ok": True,
            }
        if self.shadow is None:
            return {
                "enabled": False,
                "pass": True,
                "reason": "skip_session_gate_no_shadow",
                "local_ts": _now_text(),
                "snapshot_ts": l1_ts.isoformat(),
                "trading_day": self.cfg.trading_day.isoformat(),
                "local_ok": True,
                "snapshot_ok": True,
                "trading_day_ok": True,
            }
        if not bool(self.cfg.enforce_trading_session):
            return {
                "enabled": False,
                "pass": True,
                "reason": "session_gate_disabled",
                "local_ts": _now_text(),
                "snapshot_ts": l1_ts.isoformat(),
                "trading_day": self.cfg.trading_day.isoformat(),
                "local_ok": True,
                "snapshot_ok": True,
                "trading_day_ok": True,
            }

        now_ts = datetime.now()
        local_ok = _is_trading_session_time(now_ts)
        snapshot_ok = _is_trading_session_time(l1_ts)
        trading_day_ok = bool(l1_ts.date() == self.cfg.trading_day)
        passed = bool(local_ok and snapshot_ok and trading_day_ok)
        reason = (
            "ok"
            if passed
            else (
                "snapshot_trading_day_mismatch"
                if not trading_day_ok
                else f"market_closed(local={local_ok},snapshot={snapshot_ok})"
            )
        )
        return {
            "enabled": True,
            "pass": passed,
            "reason": reason,
            "local_ts": now_ts.isoformat(timespec="seconds"),
            "snapshot_ts": l1_ts.isoformat(),
            "trading_day": self.cfg.trading_day.isoformat(),
            "local_ok": bool(local_ok),
            "snapshot_ok": bool(snapshot_ok),
            "trading_day_ok": bool(trading_day_ok),
        }

    def _risk_sellable_qty(self, code: str) -> int:
        for row in self._positions():
            if str(row.get("code") or "") == str(code).upper():
                return int(row.get("sellable", 0) or 0)
        return 0

    def _risk_cash_available(self) -> float:
        asset = self._account_asset()
        return float(asset.get("cash") or 0.0)

    def _to_result(self, command: str, result: TradeCommandResult) -> TradeOpsResult:
        l1_payload = None
        if result.l1_snapshot is not None:
            l1_payload = {
                "code": result.l1_snapshot.code,
                "ts": result.l1_snapshot.ts.isoformat(),
                "bid1": result.l1_snapshot.bid1,
                "bid2": result.l1_snapshot.bid2,
                "bid3": result.l1_snapshot.bid3,
                "ask1": result.l1_snapshot.ask1,
                "ask2": result.l1_snapshot.ask2,
                "ask3": result.l1_snapshot.ask3,
                "last_price": result.l1_snapshot.last_price,
                "source": result.l1_snapshot.source.value,
                "depth_available_levels": int(result.l1_snapshot.depth_available_levels),
            }
        payload = {
            "ok": bool(result.ok),
            "code": result.code,
            "message": result.message,
            "account_id": result.account_id,
            "broker_order_id": result.broker_order_id,
            "client_order_id": result.client_order_id,
            "client_order_key": result.client_order_key,
            "intent_id": result.intent_id,
            "status": result.status,
            "l1_snapshot": l1_payload,
        }
        return self._result(command, ok=bool(result.ok), payload=payload)

    def account_show(self) -> TradeOpsResult:
        asset = self._account_asset()
        ok = bool(asset)
        source = "sim_virtual" if self.shadow is None else "xttrader_shadow"
        payload = {
            "ts": _now_text(),
            "account_id": asset.get("account_id", self.cfg.account_id),
            "cash": asset.get("cash"),
            "total_asset": asset.get("total_asset"),
            "market_value": asset.get("market_value"),
            "source": source,
        }
        if not ok:
            payload["error"] = "account_asset_unavailable"
            payload["message"] = "xttrader account asset unavailable"
        return self._result("account.show", ok=ok, payload=payload)

    def positions_list(self) -> TradeOpsResult:
        rows = self._positions()
        return self._result(
            "positions.list",
            ok=True,
            payload={
                "ts": _now_text(),
                "account_id": self.cfg.account_id,
                "rows": rows,
                "count": len(rows),
            },
        )

    def _shadow_order_payload_rows(self) -> list[dict[str, Any]]:
        rows = _safe_table_rows(self.shadow.get_orders())
        payload_rows: list[dict[str, Any]] = []
        for row in rows:
            payload_rows.append(
                {
                    "account_id": str(row.get("account_id") or self.cfg.account_id),
                    "broker_order_id": str(row.get("order_id") or row.get("broker_order_id") or ""),
                    "code": str(row.get("stock_code") or row.get("code") or "").strip().upper(),
                    "side": row.get("order_type") or row.get("side"),
                    "quantity": _safe_int(row.get("order_volume") if row.get("order_volume") is not None else row.get("quantity"), 0),
                    "status": row.get("order_status") or row.get("status"),
                    "message": str(row.get("status_msg") or row.get("message") or ""),
                    "price_hint": _safe_float(row.get("price") if row.get("price") is not None else row.get("price_hint")),
                }
            )
        return payload_rows

    def _broker_order_payload_rows(self, rows: list[Any]) -> list[dict[str, Any]]:
        payload_rows: list[dict[str, Any]] = []
        for row in rows:
            payload_rows.append(
                {
                    "ts": row.ts.isoformat(),
                    "account_id": row.account_id,
                    "broker_order_id": row.broker_order_id,
                    "code": row.code,
                    "side": row.side.value,
                    "quantity": row.quantity,
                    "status": row.status,
                    "message": row.message,
                    "price_hint": row.price_hint,
                }
            )
        return payload_rows

    def _orders_broker_read_meta(
        self,
        *,
        ok: bool,
        error: str = "",
        connected_before: bool | None = None,
        connected_after: bool | None = None,
    ) -> dict[str, Any]:
        fresh_connect_attempted: bool | None = None
        fresh_connect_ok: bool | None = None
        if connected_before is not None:
            fresh_connect_attempted = not bool(connected_before)
            if bool(fresh_connect_attempted):
                if ok:
                    fresh_connect_ok = True if connected_after is True else None
                else:
                    fresh_connect_ok = False
        return {
            "source": "broker",
            "ok": bool(ok),
            "error": str(error or ""),
            "connected_before": connected_before,
            "connected_after": connected_after,
            "fresh_connect_attempted": fresh_connect_attempted,
            "fresh_connect_ok": fresh_connect_ok,
        }

    def _orders_truth_meta(
        self,
        *,
        truth_scope: str,
        broker_truth_confirmed: bool,
        shadow_fallback_used: bool,
        truth_reason: str,
    ) -> dict[str, Any]:
        return {
            "truth_scope": str(truth_scope),
            "broker_truth_confirmed": bool(broker_truth_confirmed),
            "shadow_fallback_used": bool(shadow_fallback_used),
            "truth_reason": str(truth_reason),
        }

    def _public_orders_shadow_fallback(
        self,
        *,
        fallback_reason: str,
        broker_error: str,
        broker_read: dict[str, Any],
    ) -> TradeOpsResult | None:
        if self.shadow is None:
            return None
        if fallback_reason == "broker_connect_failed":
            if not _is_xttrader_connect_failure(broker_error):
                return None
        elif fallback_reason != "broker_missing":
            return None
        probe_fn = getattr(self.shadow, "probe_live_readiness", None)
        if not callable(probe_fn):
            return None
        probe = probe_fn(snapshot_requires_position=False)
        if not isinstance(probe, dict):
            return None
        if (not bool(probe.get("available", False))) or (not bool(probe.get("reused_session", False))):
            return None
        payload_rows = self._shadow_order_payload_rows()
        return self._result(
            "orders.list",
            ok=True,
            payload={
                "ts": _now_text(),
                "account_id": self.cfg.account_id,
                "rows": payload_rows,
                "count": len(payload_rows),
                "source": "active_owner_shadow",
                "read_scope": "public_fallback",
                "degraded": True,
                "fallback_used": True,
                "fallback_reason": str(fallback_reason),
                "message": (
                    "broker adapter missing; returned orders from active owner-managed shadow session"
                    if fallback_reason == "broker_missing"
                    else "broker connect failed; returned orders from active owner-managed shadow session"
                ),
                **self._orders_truth_meta(
                    truth_scope="shadow_fallback",
                    broker_truth_confirmed=False,
                    shadow_fallback_used=True,
                    truth_reason=str(fallback_reason),
                ),
                "broker_read": dict(broker_read),
                "shadow_fallback": {
                    "used": True,
                    "source": "active_owner_shadow",
                    "probe_source": str(probe.get("source") or "xttrader_shadow"),
                    "reused_session": bool(probe.get("reused_session", False)),
                    "session_id": str(probe.get("session_id") or ""),
                    "account_id": str(probe.get("account_id") or self.cfg.account_id),
                    "reason": str(probe.get("reason") or ""),
                },
            },
        )

    def _orders_list_failure(
        self,
        *,
        code: str,
        message: str,
        broker_read: dict[str, Any],
        failure_classification: str,
        shadow_fallback_reason: str,
    ) -> TradeOpsResult:
        return self._result(
            "orders.list",
            ok=False,
            payload={
                "ts": _now_text(),
                "account_id": self.cfg.account_id,
                "rows": [],
                "count": 0,
                "source": "broker_unavailable",
                "read_scope": "public_broker",
                "degraded": False,
                "fallback_used": False,
                "shadow_fallback_reason": str(shadow_fallback_reason or ""),
                **self._orders_truth_meta(
                    truth_scope="broker_unavailable",
                    broker_truth_confirmed=False,
                    shadow_fallback_used=False,
                    truth_reason=str(code or "orders_list_broker_read_failed"),
                ),
                "broker_read": dict(broker_read),
                "failure_classification": str(failure_classification or ""),
                "error": str(code or "orders_list_broker_read_failed"),
                "code": str(code or "orders_list_broker_read_failed"),
                "message": str(message or code or "public orders.list unavailable"),
            },
        )

    def warm_health_orders_list(self) -> TradeOpsResult:
        if self.shadow is None:
            if self._flow_smoke_mode():
                return self._result(
                    "orders.list",
                    ok=True,
                    payload={
                        "ts": _now_text(),
                        "account_id": self.cfg.account_id,
                        "rows": [],
                        "count": 0,
                        "source": "flow_smoke",
                        "read_scope": "warm_health_flow_smoke",
                        **self._orders_truth_meta(
                            truth_scope="flow_smoke_local",
                            broker_truth_confirmed=False,
                            shadow_fallback_used=False,
                            truth_reason="flow_smoke_warm_health",
                        ),
                    },
                )
            return self._result(
                "orders.list",
                ok=False,
                payload={
                    "ts": _now_text(),
                    "account_id": self.cfg.account_id,
                    "error": "warm_health_orders_unavailable",
                    "code": "warm_health_orders_unavailable",
                    "message": "session warm requires shadow order visibility",
                },
            )
        payload_rows = self._shadow_order_payload_rows()
        return self._result(
            "orders.list",
            ok=True,
            payload={
                "ts": _now_text(),
                "account_id": self.cfg.account_id,
                "rows": payload_rows,
                "count": len(payload_rows),
                "source": "xttrader_shadow",
                "read_scope": "warm_health_only",
                **self._orders_truth_meta(
                    truth_scope="shadow_warm_health",
                    broker_truth_confirmed=False,
                    shadow_fallback_used=False,
                    truth_reason="warm_health_only",
                ),
            },
        )

    def _owner_managed_probe_report(self) -> dict[str, Any] | None:
        probe_fn = getattr(self.shadow, "probe_live_readiness", None)
        if not callable(probe_fn):
            return None
        probe = probe_fn(snapshot_requires_position=bool(self.cfg.snapshot_requires_position))
        if not isinstance(probe, dict):
            return None
        if not bool(probe.get("available", False)):
            return None

        layered_precheck = run_layered_user_data_precheck(
            str(self.cfg.qmt_userdata or ""),
            require_up_queue_file=True,
        )
        read_only_layer = dict(layered_precheck.get("read_only") or {})
        write_permission_layer = dict(layered_precheck.get("write_permission") or {})
        read_only_report = dict(read_only_layer.get("report") or {})
        write_permission_report = dict(write_permission_layer.get("report") or {})
        read_only_precheck_ok = bool(read_only_layer.get("ok", False))
        write_permission_precheck_ok = bool(write_permission_layer.get("ok", False))
        vendor_port_ready = bool(_tcp_port_ready("127.0.0.1", 58610, timeout_ms=300))
        owner_probe_ok = bool(probe.get("ok", False))
        owner_probe_reason = str(probe.get("reason") or "").strip()

        read_only_failure_classification = ""
        if not read_only_precheck_ok:
            read_only_failure_classification = "qmt_read_precheck_failed"
        elif not vendor_port_ready:
            read_only_failure_classification = "xtdata_port_not_ready"
        elif not owner_probe_ok:
            read_only_failure_classification = owner_probe_reason or "shadow_session_probe_failed"
        write_failure_classification = "" if write_permission_precheck_ok else "write_permission_precheck_failed"

        precheck = {
            "userdata_precheck": read_only_report,
            "userdata_precheck_read_only": read_only_report,
            "userdata_precheck_write_permission": write_permission_report,
            "xtdata_port_ready": bool(vendor_port_ready),
            "readiness_layers": {
                "read_only": {
                    "ok": not bool(read_only_failure_classification),
                    "blocking": True,
                    "reason": str(read_only_failure_classification or ""),
                    "source": "active_owner_shadow",
                    "reused_session": True,
                },
                "write_permission": {
                    "ok": bool(write_permission_precheck_ok),
                    "blocking": False,
                    "reason": str(write_failure_classification or ""),
                    "source": "userdata_precheck",
                },
            },
            "read_only_failure_classification": str(read_only_failure_classification or ""),
            "write_failure_classification": str(write_failure_classification or ""),
        }
        connection_trace = [
            {
                "name": "precheck_userdata_read_only",
                "ok": bool(read_only_precheck_ok),
                "code": "ok" if bool(read_only_precheck_ok) else "qmt_read_precheck_failed",
                "message": (
                    "read-only userdata precheck passed"
                    if bool(read_only_precheck_ok)
                    else f"read-only userdata precheck failed: {read_only_report}"
                ),
                "latency_ms": None,
                "retry_count": 0,
                "details": {},
            },
            {
                "name": "precheck_userdata_write_permission",
                "ok": bool(write_permission_precheck_ok),
                "code": "ok" if bool(write_permission_precheck_ok) else "write_permission_precheck_failed",
                "message": (
                    "write-permission userdata precheck passed"
                    if bool(write_permission_precheck_ok)
                    else f"write-permission userdata precheck failed: {write_permission_report}"
                ),
                "latency_ms": None,
                "retry_count": 0,
                "details": {},
            },
            {
                "name": "wait_xtdata_ready",
                "ok": bool(vendor_port_ready),
                "code": "ok" if bool(vendor_port_ready) else "xtdata_port_not_ready",
                "message": (
                    "xtdata ready on 127.0.0.1:58610"
                    if bool(vendor_port_ready)
                    else "xtdata not ready on 127.0.0.1:58610"
                ),
                "latency_ms": None,
                "retry_count": 0,
                "details": {"port": "58610"},
            },
            {
                "name": "query_shadow_session_smoke",
                "ok": bool(owner_probe_ok),
                "code": "ok" if bool(owner_probe_ok) else str(owner_probe_reason or "shadow_session_probe_failed"),
                "message": str(probe.get("message") or owner_probe_reason or "owner-managed shadow session probe"),
                "latency_ms": None,
                "retry_count": 0,
                "details": {
                    "account_id": str(probe.get("account_id") or self.cfg.account_id or ""),
                    "session_id": str(probe.get("session_id") or ""),
                    "source": str(probe.get("source") or "xttrader_shadow"),
                    "reused_session": str(bool(probe.get("reused_session", False))),
                    "positions_rows": str(probe.get("positions_rows", "")),
                    "asset_rows": str(probe.get("asset_rows", "")),
                },
            },
        ]
        owner_probe_session_id = str(probe.get("session_id") or "").strip()
        owner_session_id = owner_probe_session_id
        write_alignment = self._build_write_session_alignment(owner_probe_session_id)
        if bool(write_alignment.get("same_plan_verdict", False)) and bool(owner_probe_ok):
            connection_trace.extend(
                [
                    {
                        "name": "owner_session_connect_verified",
                        "ok": True,
                        "code": "ok",
                        "message": "owner-managed active session already connected on resolved write session",
                        "latency_ms": None,
                        "retry_count": 0,
                        "details": {
                            "session_id": owner_probe_session_id,
                            "source": str(probe.get("source") or "xttrader_shadow"),
                        },
                    },
                    {
                        "name": "owner_session_subscribe_verified",
                        "ok": True,
                        "code": "ok",
                        "message": "owner-managed active session already subscribed on resolved write session",
                        "latency_ms": None,
                        "retry_count": 0,
                        "details": {
                            "session_id": owner_probe_session_id,
                            "source": str(probe.get("source") or "xttrader_shadow"),
                        },
                    },
                ]
            )
        probe_mode = "owner_managed_session_reuse"
        selected_session_id = owner_probe_session_id
        fresh_connect_attempted = False
        broker_verify = None
        if (
            bool(owner_probe_ok)
            and bool(write_permission_precheck_ok)
            and (
                bool(write_alignment.get("same_plan_verdict", False))
                or bool(write_alignment.get("observed_probe_session_in_effective_plan", False))
            )
        ):
            broker_verify = self._owner_managed_broker_fresh_verify()
            if isinstance(broker_verify, dict) and bool(broker_verify.get("available", False)):
                fresh_connect_attempted = bool(broker_verify.get("fresh_connect_attempted", False))
                broker_session_id = str(broker_verify.get("session_id") or owner_probe_session_id).strip()
                if broker_session_id:
                    self.realign_session_resolution(
                        broker_session_id,
                        reason="broker_session_verified",
                        event_source="broker_fresh_verify",
                        owner_session_id=owner_session_id,
                        observed_probe_session_id=owner_probe_session_id,
                        attempted_broker_session_id=broker_session_id,
                    )
                    write_alignment = self._build_write_session_alignment(broker_session_id)
                selected_session_id = broker_session_id or owner_probe_session_id
                if bool(broker_verify.get("ok", False)):
                    connection_trace.extend(
                        [
                            {
                                "name": f"connect_session_{broker_session_id or owner_probe_session_id}",
                                "ok": True,
                                "code": "0",
                                "message": "broker adapter fresh connect verified",
                                "latency_ms": None,
                                "retry_count": 1,
                                "details": {
                                    "source": "broker_order",
                                    "connected_before": str(broker_verify.get("connected_before")),
                                    "connected_after": str(broker_verify.get("connected_after")),
                                    "rows_count": str(broker_verify.get("rows_count")),
                                },
                            },
                            {
                                "name": "subscribe_account",
                                "ok": True,
                                "code": "0",
                                "message": "broker adapter subscribe verified",
                                "latency_ms": None,
                                "retry_count": 1,
                                "details": {
                                    "account_id": str(self.cfg.account_id or ""),
                                    "session_id": broker_session_id or owner_probe_session_id,
                                    "source": "broker_order",
                                },
                            },
                        ]
                    )
                    probe_mode = "owner_managed_broker_fresh_verify"
                else:
                    connection_trace.append(
                        {
                            "name": f"connect_session_{broker_session_id or owner_probe_session_id or 'unknown'}",
                            "ok": False,
                            "code": "-1" if _is_xttrader_connect_failure(str(broker_verify.get('error') or "")) else "fresh_broker_verify_failed",
                            "message": str(broker_verify.get("error") or "broker adapter fresh verify failed"),
                            "latency_ms": None,
                            "retry_count": 1,
                            "details": {
                                "source": "broker_order",
                                "connected_before": str(broker_verify.get("connected_before")),
                                "connected_after": str(broker_verify.get("connected_after")),
                            },
                        }
                    )
                    probe_mode = "owner_managed_broker_fresh_verify_failed"
        return {
            "selected_session_id": str(selected_session_id or ""),
            "precheck": precheck,
            "connection_trace": connection_trace,
            "callback_events": [],
            "failure_classification": str(read_only_failure_classification or ""),
            "probe_mode": str(probe_mode),
            "session_reused": True,
            "fresh_connect_attempted": bool(fresh_connect_attempted),
            "read_only_probe_source": "active_owner_shadow",
            "write_permission_probe_source": "userdata_precheck",
        }

    def _build_probe_result(
        self,
        *,
        account_id: str,
        selected_session_id: Any,
        precheck: dict[str, Any],
        connection_trace: list[dict[str, Any]],
        callback_events: list[str],
        failure_classification: str,
        probe_mode: str,
        session_reused: bool,
        fresh_connect_attempted: bool,
        read_only_probe_source: str,
        write_permission_probe_source: str,
    ) -> TradeOpsResult:
        connect_stage = next(
            (
                item
                for item in reversed(connection_trace)
                if str(item.get("name", "")).startswith("connect_session_")
            ),
            {},
        )
        vendor_port_probe_ok = bool(precheck.get("xtdata_port_ready", False)) or _trace_stage_pass(
            connection_trace,
            exact_name="wait_xtdata_ready",
        )
        fresh_connect_pass = _trace_stage_pass(connection_trace, prefix="connect_session_") if bool(fresh_connect_attempted) else False
        subscribe_pass = _trace_stage_pass(connection_trace, exact_name="subscribe_account")
        owner_session_connect_verified = _trace_stage_pass(connection_trace, exact_name="owner_session_connect_verified")
        owner_session_subscribe_verified = _trace_stage_pass(connection_trace, exact_name="owner_session_subscribe_verified")
        shadow_snapshot_ok = (
            _trace_stage_pass(connection_trace, exact_name="query_snapshot_smoke")
            or _trace_stage_pass(connection_trace, exact_name="query_shadow_session_smoke")
        )
        market_data_pass = bool(vendor_port_probe_ok)
        readiness_layers = dict(precheck.get("readiness_layers") or {})
        read_only_layer = dict(readiness_layers.get("read_only") or {})
        write_permission_layer = dict(readiness_layers.get("write_permission") or {})
        read_only_failure_classification = str(
            precheck.get("read_only_failure_classification") or failure_classification or ""
        )
        write_failure_classification = str(precheck.get("write_failure_classification") or "")

        if not read_only_layer:
            read_only_layer = {
                "ok": not bool(read_only_failure_classification),
                "blocking": True,
                "reason": read_only_failure_classification,
            }
        read_only_ready = bool(read_only_layer.get("ok", False))
        if not read_only_failure_classification:
            read_only_failure_classification = str(read_only_layer.get("reason") or "")

        if not write_permission_layer:
            write_report = dict(precheck.get("userdata_precheck_write_permission") or {})
            write_ok = bool(write_report.get("ok", True)) if write_report else True
            write_permission_layer = {
                "ok": write_ok,
                "blocking": False,
                "reason": "" if write_ok else "write_permission_precheck_failed",
            }
        write_permission_precheck_ok = bool(write_permission_layer.get("ok", False))
        if not write_failure_classification:
            write_failure_classification = str(write_permission_layer.get("reason") or "")

        observed_probe_session_id = str(selected_session_id or "").strip()
        write_session_alignment = self._build_write_session_alignment(observed_probe_session_id)
        same_plan_verdict = bool(write_session_alignment.get("same_plan_verdict", False))
        fresh_connect_verified = bool(
            fresh_connect_attempted and same_plan_verdict and fresh_connect_pass and subscribe_pass
        )
        probe_complete_verdict = bool(
            read_only_ready
            and market_data_pass
            and shadow_snapshot_ok
            and (
                (fresh_connect_attempted and fresh_connect_pass and subscribe_pass)
                or (session_reused and owner_session_connect_verified and owner_session_subscribe_verified)
            )
        )
        connection_evidence_source = "fresh_connect" if bool(fresh_connect_attempted) else "reused_owner_session"
        if not write_permission_precheck_ok:
            write_authority_reason = str(write_failure_classification or "write_permission_precheck_failed")
        elif not same_plan_verdict:
            write_authority_reason = str(write_session_alignment.get("same_plan_reason") or "write_session_mismatch")
        elif bool(fresh_connect_attempted) and bool(fresh_connect_pass) and bool(subscribe_pass):
            write_authority_reason = "ok"
        elif not bool(fresh_connect_attempted):
            if bool(session_reused) and owner_session_connect_verified and owner_session_subscribe_verified:
                write_authority_reason = "reuse_only_not_sufficient"
            else:
                write_authority_reason = "write_session_not_verified"
        elif not bool(fresh_connect_pass):
            write_authority_reason = "write_connect_failed"
        elif not bool(subscribe_pass):
            write_authority_reason = "write_subscribe_failed"
        elif bool(session_reused) and owner_session_connect_verified and owner_session_subscribe_verified:
            write_authority_reason = "write_session_not_verified"
        else:
            write_authority_reason = "ok"
        write_permission_ready = write_authority_reason == "ok"

        readiness_layers = {
            "read_only": read_only_layer,
            "write_permission": write_permission_layer,
        }
        overall_trade_ready = bool(read_only_ready and write_permission_ready)
        ok = bool(read_only_ready)
        if not ok:
            reason = str(read_only_failure_classification or "probe_failed")
        elif not write_permission_ready:
            reason = str(write_authority_reason)
        else:
            reason = "ok"
        top_level_session_id = str(write_session_alignment.get("resolved_session_id") or observed_probe_session_id)
        payload = {
            "ts": _now_text(),
            "account_id": account_id,
            "ok": ok,
            "connect_code": str(connect_stage.get("code", "") or ""),
            "session_id": top_level_session_id,
            "observed_probe_session_id": observed_probe_session_id,
            "reason": str(reason),
            "precheck": dict(precheck or {}),
            "connection_trace": connection_trace,
            "failure_classification": str(read_only_failure_classification or ""),
            "write_failure_classification": str(write_failure_classification or ""),
            "vendor_port_probe_ok": bool(vendor_port_probe_ok),
            "connect_pass": bool(fresh_connect_pass),
            "subscribe_pass": bool(subscribe_pass),
            "shadow_snapshot_ok": bool(shadow_snapshot_ok),
            "market_data_pass": bool(market_data_pass),
            "overall_trade_ready": bool(overall_trade_ready),
            "read_only_ready": bool(read_only_ready),
            "same_plan_verdict": bool(same_plan_verdict),
            "probe_complete_verdict": bool(probe_complete_verdict),
            "write_permission_ready": bool(write_permission_ready),
            "write_authority_ready": bool(write_permission_ready),
            "write_permission_precheck_ok": bool(write_permission_precheck_ok),
            "write_permission_blocked": bool((not write_permission_ready) and read_only_ready),
            "write_permission_block_reason": str("" if write_permission_ready else write_authority_reason),
            "readiness_layers": readiness_layers,
            "market_data_ok": bool(market_data_pass),
            "snapshot_ok": bool(shadow_snapshot_ok),
            "probe_mode": str(probe_mode),
            "session_reused": bool(session_reused),
            "fresh_connect_attempted": bool(fresh_connect_attempted),
            "fresh_connect_verified": bool(fresh_connect_verified),
            "connection_evidence_source": str(connection_evidence_source),
            "fresh_connect_pass": bool(fresh_connect_pass),
            "read_only_probe_source": str(read_only_probe_source),
            "write_permission_probe_source": str(write_permission_probe_source),
            "write_session_alignment": write_session_alignment,
            "read_only_probe": {
                "source": str(read_only_probe_source),
                "session_reused": bool(session_reused),
                "fresh_connect_attempted": bool(fresh_connect_attempted),
                "fresh_connect_verified": bool(fresh_connect_verified),
                "connection_evidence_source": str(connection_evidence_source),
                "session_id": observed_probe_session_id,
                "connect_code": str(connect_stage.get("code", "") or ""),
            },
            "write_permission_probe": {
                "source": str(write_permission_probe_source),
                "session_reused": False,
                "precheck_ok": bool(write_permission_precheck_ok),
                "implies_write_permission": bool(write_permission_ready),
            },
            "probe_scope_note": (
                "probe.connection 的 ok/read_only_ready 仅表示 read-only probe 成功；"
                "顶层 session_id 对齐 write-path resolved session，实际观测到的 probe session 见 observed_probe_session_id/read_only_probe.session_id；"
                "write_permission_precheck_ok 仅表示本地预检通过，write_permission_ready 只有在 same-plan 成立且当前 packet 完成 fresh connect/subscribe verify 后才为真"
            ),
            "callback_events_tail": list(callback_events or [])[-10:],
        }
        if not ok:
            payload["error"] = str(reason)
            payload["code"] = str(reason)
        return self._result("probe.connection", ok=ok, payload=payload)

    def probe_connection(self) -> TradeOpsResult:
        qmt_userdata = str(self.cfg.qmt_userdata or "").strip()
        account_id = str(self.cfg.account_id or "").strip()
        if (not qmt_userdata) or (not account_id):
            return self._result(
                "probe.connection",
                ok=False,
                payload={
                    "ts": _now_text(),
                    "account_id": account_id,
                    "error": "probe_connection_unavailable",
                    "message": "probe.connection requires server-side qmt_userdata and primary account context",
                },
            )
        owner_managed_report = self._owner_managed_probe_report()
        if owner_managed_report is not None:
            return self._build_probe_result(
                account_id=account_id,
                selected_session_id=owner_managed_report.get("selected_session_id", ""),
                precheck=dict(owner_managed_report.get("precheck") or {}),
                connection_trace=list(owner_managed_report.get("connection_trace") or []),
                callback_events=list(owner_managed_report.get("callback_events") or []),
                failure_classification=str(owner_managed_report.get("failure_classification") or ""),
                probe_mode=str(owner_managed_report.get("probe_mode") or "owner_managed_session_reuse"),
                session_reused=bool(owner_managed_report.get("session_reused", False)),
                fresh_connect_attempted=bool(owner_managed_report.get("fresh_connect_attempted", False)),
                read_only_probe_source=str(owner_managed_report.get("read_only_probe_source") or "active_owner_shadow"),
                write_permission_probe_source=str(owner_managed_report.get("write_permission_probe_source") or "userdata_precheck"),
            )
        try:
            from .channel_probe import ChannelProbeConfig, run_channel_probe

            report = run_channel_probe(
                ChannelProbeConfig(
                    user_data_path=qmt_userdata,
                    account_id=account_id,
                    auto_account=False,
                    connect_retries=max(1, int(self.cfg.connect_retries)),
                    connect_retry_interval_seconds=max(3.0, float(self.cfg.connect_retry_interval_seconds)),
                    session_candidates=tuple(self.cfg.session_candidates or (100, 101, 111)),
                    qmt_exe=str(self.cfg.qmt_exe or ""),
                    wake_wait_seconds=max(1, int(self.cfg.wake_wait_seconds)),
                    require_connect_stage=bool(self.cfg.require_connect_stage),
                    require_subscribe_stage=bool(self.cfg.require_subscribe_stage),
                    require_snapshot_stage=bool(self.cfg.require_snapshot_stage),
                    snapshot_requires_position=bool(self.cfg.snapshot_requires_position),
                )
            )
        except Exception as exc:
            return self._result(
                "probe.connection",
                ok=False,
                payload={
                    "ts": _now_text(),
                    "account_id": account_id,
                    "error": "probe_connection_failed",
                    "message": str(exc),
                },
            )

        connection_trace = [
            {
                "name": item.name,
                "ok": bool(item.ok),
                "code": str(item.code or ""),
                "message": str(item.message or ""),
                "latency_ms": item.latency_ms,
                "retry_count": int(item.retry_count),
                "details": dict(item.details or {}),
            }
            for item in list(report.connection_trace or [])
        ]
        return self._build_probe_result(
            account_id=account_id,
            selected_session_id=report.selected_session_id,
            precheck=dict(report.precheck or {}),
            connection_trace=connection_trace,
            callback_events=list(report.callback_events or []),
            failure_classification=str(report.failure_classification or ""),
            probe_mode="fresh_connect_orchestrator",
            session_reused=False,
            fresh_connect_attempted=True,
            read_only_probe_source="connection_orchestrator",
            write_permission_probe_source="userdata_precheck",
        )


    def orders_list(self) -> TradeOpsResult:
        connected_before: bool | None = None
        try:
            broker = self._ensure_broker_adapter(require_write_permission=False)
        except Exception as exc:
            broker_error = str(exc)
            broker_read = self._orders_broker_read_meta(ok=False, error=broker_error)
            fallback = self._public_orders_shadow_fallback(
                fallback_reason="broker_connect_failed",
                broker_error=broker_error,
                broker_read=broker_read,
            )
            if fallback is not None:
                return fallback
            if _is_xttrader_connect_failure(broker_error):
                return self._orders_list_failure(
                    code="connect_failed",
                    message=broker_error,
                    broker_read=broker_read,
                    failure_classification="fail_env",
                    shadow_fallback_reason="shadow_not_reusable",
                )
            return self._orders_list_failure(
                code="orders_list_broker_read_failed",
                message=broker_error,
                broker_read=broker_read,
                failure_classification="fail_design",
                shadow_fallback_reason="shadow_not_reusable",
            )
        if broker is None:
            broker_read = self._orders_broker_read_meta(ok=False, error="broker_adapter_missing")
            fallback = self._public_orders_shadow_fallback(
                fallback_reason="broker_missing",
                broker_error="broker_adapter_missing",
                broker_read=broker_read,
            )
            if fallback is not None:
                return fallback
            return self._orders_list_failure(
                code="orders_list_broker_missing",
                message=(
                    "public orders.list requires a broker adapter or an active owner-managed shadow fallback; "
                    "broker adapter is missing"
                ),
                broker_read=broker_read,
                failure_classification="fail_design",
                shadow_fallback_reason="shadow_unavailable",
            )
        connected_before = _adapter_connected_state(broker)
        try:
            rows = broker.query_open_orders(self.cfg.account_id) or []
        except Exception as exc:
            broker_error = str(exc)
            broker_read = self._orders_broker_read_meta(
                ok=False,
                error=broker_error,
                connected_before=connected_before,
                connected_after=_adapter_connected_state(broker),
            )
            fallback = self._public_orders_shadow_fallback(
                fallback_reason="broker_connect_failed",
                broker_error=broker_error,
                broker_read=broker_read,
            )
            if fallback is not None:
                return fallback
            if _is_xttrader_connect_failure(broker_error):
                return self._orders_list_failure(
                    code="connect_failed",
                    message=broker_error,
                    broker_read=broker_read,
                    failure_classification="fail_env",
                    shadow_fallback_reason="shadow_not_reusable",
                )
            return self._orders_list_failure(
                code="orders_list_broker_read_failed",
                message=broker_error,
                broker_read=broker_read,
                failure_classification="fail_design",
                shadow_fallback_reason="shadow_not_reusable",
            )
        payload_rows = self._broker_order_payload_rows(rows)
        if self._flow_smoke_mode():
            return self._result(
                "orders.list",
                ok=True,
                payload={
                    "ts": _now_text(),
                    "account_id": self.cfg.account_id,
                    "rows": payload_rows,
                    "count": len(payload_rows),
                    "source": "flow_smoke",
                    "read_scope": "non_prod_flow_smoke",
                    "degraded": False,
                    "fallback_used": False,
                    **self._orders_truth_meta(
                        truth_scope="flow_smoke_local",
                        broker_truth_confirmed=False,
                        shadow_fallback_used=False,
                        truth_reason="flow_smoke_broker_adapter",
                    ),
                    "broker_read": self._orders_broker_read_meta(
                        ok=True,
                        connected_before=connected_before,
                        connected_after=_adapter_connected_state(broker),
                    ),
                },
            )
        return self._result(
            "orders.list",
            ok=True,
            payload={
                "ts": _now_text(),
                "account_id": self.cfg.account_id,
                "rows": payload_rows,
                "count": len(payload_rows),
                "source": "broker",
                "read_scope": "public_broker",
                "degraded": False,
                "fallback_used": False,
                **self._orders_truth_meta(
                    truth_scope="broker_truth",
                    broker_truth_confirmed=True,
                    shadow_fallback_used=False,
                    truth_reason="broker_read_ok",
                ),
                "broker_read": self._orders_broker_read_meta(
                    ok=True,
                    connected_before=connected_before,
                    connected_after=_adapter_connected_state(broker),
                ),
            },
        )

    def order_status(self, broker_order_id: str) -> TradeOpsResult:
        broker_order_id_text = str(broker_order_id or "").strip()
        if not _is_decimal_identifier(broker_order_id_text):
            return self._result(
                "order.status",
                ok=False,
                payload={
                    "ts": _now_text(),
                    "account_id": self.cfg.account_id,
                    "broker_order_id": broker_order_id_text,
                    "error": "invalid_broker_order_id",
                },
            )
        broker = self._ensure_broker_adapter(require_write_permission=False)
        if broker is None:
            return self._result(
                "order.status",
                ok=False,
                payload={
                    "ts": _now_text(),
                    "account_id": self.cfg.account_id,
                    "broker_order_id": broker_order_id_text,
                    "error": "broker_adapter_missing",
                },
            )
        state = broker.query_order(self.cfg.account_id, broker_order_id_text)
        if state is None:
            return self._result(
                "order.status",
                ok=False,
                payload={
                    "ts": _now_text(),
                    "account_id": self.cfg.account_id,
                    "broker_order_id": broker_order_id_text,
                    "error": "order_not_found",
                },
            )
        return self._result(
            "order.status",
            ok=True,
            payload={
                "ts": state.ts.isoformat(),
                "account_id": state.account_id,
                "broker_order_id": state.broker_order_id,
                "code": state.code,
                "side": state.side.value,
                "quantity": state.quantity,
                "status": state.status,
                "terminal": bool(state.terminal),
                "message": state.message,
                "price_hint": state.price_hint,
            },
        )

    def order_cancel(self, broker_order_id: str) -> TradeOpsResult:
        broker_order_id_text = str(broker_order_id or "").strip()

        def _with_persistence(result: TradeOpsResult, errors: list[str] | None = None) -> TradeOpsResult:
            return self._attach_persistence_meta(result, errors)

        def _with_submission_scope(
            result: TradeOpsResult,
            *,
            broker_submission_attempted: bool,
            local_gate_intercepted: bool,
            submission_scope: str,
            submission_stage: str,
            errors: list[str] | None = None,
        ) -> TradeOpsResult:
            self._decorate_order_submission_scope(
                result,
                broker_submission_attempted=broker_submission_attempted,
                local_gate_intercepted=local_gate_intercepted,
                submission_scope=submission_scope,
                submission_stage=submission_stage,
            )
            return _with_persistence(result, errors)

        if not _is_decimal_identifier(broker_order_id_text):
            return _with_submission_scope(
                TradeOpsResult(
                    command="order.cancel",
                    ok=False,
                    payload={
                        "ts": _now_text(),
                        "account_id": self.cfg.account_id,
                        "broker_order_id": broker_order_id_text,
                        "error": "invalid_broker_order_id",
                    },
                ),
                broker_submission_attempted=False,
                local_gate_intercepted=False,
                submission_scope="local_validation",
                submission_stage="request_validation",
            )
        connect_gate = self._run_connect_gate()
        write_authority_snapshot = dict(connect_gate.get("write_authority_snapshot") or self._write_authority_snapshot())
        if not bool(connect_gate.get("pass", False)):
            result = self._result(
                "order.cancel",
                ok=False,
                payload={
                    "ts": _now_text(),
                    "account_id": self.cfg.account_id,
                    "broker_order_id": broker_order_id_text,
                    "ok": False,
                    "code": "connect_gate_failed",
                    "status": OrderStatus.RISK_REJECTED.value,
                    "message": str(connect_gate.get("reason") or "pretrade connect gate failed"),
                    "reject_code": "connect_gate_failed",
                    "connect_gate": connect_gate,
                    "write_authority_snapshot": write_authority_snapshot,
                },
            )
            return _with_submission_scope(
                result,
                broker_submission_attempted=False,
                local_gate_intercepted=True,
                submission_scope="local_gate",
                submission_stage="connect_gate",
            )
        broker = self._ensure_broker_adapter(require_write_permission=True)
        if broker is None:
            result = self._result(
                "order.cancel",
                ok=False,
                payload={
                    "ts": _now_text(),
                    "account_id": self.cfg.account_id,
                    "broker_order_id": broker_order_id_text,
                    "error": "broker_adapter_missing",
                    "connect_gate": connect_gate,
                    "write_authority_snapshot": write_authority_snapshot,
                },
            )
            return _with_submission_scope(
                result,
                broker_submission_attempted=False,
                local_gate_intercepted=False,
                submission_scope="local_broker_bootstrap",
                submission_stage="broker_adapter",
            )
        current_state = broker.query_order(self.cfg.account_id, broker_order_id_text)
        if current_state is None:
            result = self._result(
                "order.cancel",
                ok=False,
                payload={
                    "ts": _now_text(),
                    "account_id": self.cfg.account_id,
                    "broker_order_id": broker_order_id_text,
                    "error": "order_not_found",
                    "connect_gate": connect_gate,
                    "write_authority_snapshot": write_authority_snapshot,
                },
            )
            return _with_submission_scope(
                result,
                broker_submission_attempted=False,
                local_gate_intercepted=False,
                submission_scope="local_validation",
                submission_stage="query_order",
            )
        if bool(current_state.terminal):
            result = self._result(
                "order.cancel",
                ok=False,
                payload={
                    "ts": _now_text(),
                    "account_id": current_state.account_id,
                    "broker_order_id": current_state.broker_order_id,
                    "ok": False,
                    "code": "order_not_cancelable",
                    "status": current_state.status,
                    "message": f"order already terminal: {current_state.status}",
                    "reject_code": "order_not_cancelable",
                    "connect_gate": connect_gate,
                    "write_authority_snapshot": write_authority_snapshot,
                },
            )
            return _with_submission_scope(
                result,
                broker_submission_attempted=False,
                local_gate_intercepted=False,
                submission_scope="local_validation",
                submission_stage="terminal_check",
            )
        ack = broker.cancel_order(self.cfg.account_id, broker_order_id_text)
        _, persistence_errors = self._persist_order_state(
            OrderState(
                ts=ack.ts,
                updated_at=ack.ts,
                client_order_id=str(ack.client_order_id or ""),
                intent_id="",
                account_id=str(ack.account_id or self.cfg.account_id),
                code=str(ack.code or ""),
                side=ack.side,
                quantity=int(ack.quantity),
                status=str(ack.status or "failed"),
                broker_order_id=str(ack.broker_order_id or ""),
                message=str(ack.message or ""),
                price_hint=ack.price_hint,
                terminal=is_terminal_order_status(str(ack.status or "")),
                source_event_id=f"{ack.ts.isoformat()}:cancel",
                last_error_code=str(ack.reject_code or ""),
            )
        )
        result = self._result(
            "order.cancel",
            ok=bool(ack.ok),
            payload={
                "ts": ack.ts.isoformat(),
                "account_id": ack.account_id,
                "broker_order_id": ack.broker_order_id,
                "ok": ack.ok,
                "code": "ok" if ack.ok else str(ack.reject_code or "cancel_failed"),
                "status": ack.status,
                "message": ack.message,
                "reject_code": ack.reject_code,
                "connect_gate": connect_gate,
                "write_authority_snapshot": write_authority_snapshot,
            },
        )
        return _with_submission_scope(
            result,
            broker_submission_attempted=True,
            local_gate_intercepted=False,
            submission_scope="broker_cancel",
            submission_stage="broker_cancel_order",
            errors=persistence_errors,
        )

    def snapshot_l1(self, code: str) -> TradeOpsResult:
        l1 = self._snapshot_l1(code)
        if l1 is None:
            return self._result(
                "snapshot.l1",
                ok=False,
                payload={"ts": _now_text(), "code": str(code).upper(), "error": "l1_snapshot_unavailable"},
            )
        return self._result(
            "snapshot.l1",
            ok=True,
            payload={
                "ts": l1.ts.isoformat(),
                "code": l1.code,
                "bid1": l1.bid1,
                "bid2": l1.bid2,
                "bid3": l1.bid3,
                "ask1": l1.ask1,
                "ask2": l1.ask2,
                "ask3": l1.ask3,
                "last_price": l1.last_price,
                "source": l1.source.value,
                "depth_available_levels": int(l1.depth_available_levels),
            },
        )

    def _price_from_l1(self, snapshot: L1Snapshot, side: Side) -> float | None:
        if side == Side.BUY:
            return _safe_float(snapshot.ask1)
        return _safe_float(snapshot.bid1)

    def _flow_smoke_snapshot(self, code: str, limit_price: float | None) -> L1Snapshot | None:
        if (not self._flow_smoke_mode()) or limit_price is None or float(limit_price) <= 0:
            return None
        price = float(limit_price)
        return L1Snapshot(
            code=str(code).upper(),
            ts=datetime.now(),
            bid1=price,
            bid2=price,
            bid3=price,
            ask1=price,
            ask2=price,
            ask3=price,
            last_price=price,
            source=DataOrigin.LOCAL_CACHE,
            depth_available_levels=1,
        )

    def _risk_decision_row(
        self,
        *,
        ts: datetime,
        intent_id: str,
        client_order_id: str,
        ok: bool,
        code: str,
        reason: str,
        symbol: str,
        side: Side,
        quantity: int,
        price_hint: float | None,
        l1: L1Snapshot | None,
    ) -> dict[str, Any]:
        return {
            "ts": ts.isoformat(),
            "intent_id": intent_id,
            "client_order_id": client_order_id,
            "ok": bool(ok),
            "code": str(code),
            "reason": str(reason),
            "code_symbol": str(symbol).upper(),
            "side": side.value,
            "quantity": int(quantity),
            "price_hint": price_hint,
            "notional": float(max(0.0, (price_hint or 0.0) * int(quantity))),
            "l1_available": bool(l1 is not None),
            "l1_validation_code": "ok" if l1 is not None else "l1_snapshot_unavailable",
        }

    def _log_submit_ack(
        self,
        ack: BrokerOrderAck,
        *,
        intent_id: str = "",
        plan_id: str = "",
        signal_id: str = "",
        strategy_tag: str = "",
        signal_kind: str = "",
        requested_price_mode: str = "",
        requested_limit_price: float | None = None,
        effective_price_hint: float | None = None,
    ) -> None:
        path = self._real_dir / "orders_submit_log.csv"
        extended = [
            "ts",
            "intent_id",
            "plan_id",
            "signal_id",
            "strategy_tag",
            "signal_kind",
            "client_order_id",
            "account_id",
            "code",
            "side",
            "quantity",
            "ok",
            "status",
            "broker_order_id",
            "message",
            "reject_code",
            "requested_price_mode",
            "requested_limit_price",
            "effective_price_hint",
            "price_hint",
            "price_mode",
            "l1_bid1",
            "l1_ask1",
            "l1_last_price",
            "l1_ts",
            "l1_source",
        ]
        legacy = [
            "ts",
            "intent_id",
            "client_order_id",
            "account_id",
            "code",
            "side",
            "quantity",
            "ok",
            "status",
            "broker_order_id",
            "message",
            "reject_code",
            "requested_price_mode",
            "requested_limit_price",
            "effective_price_hint",
            "price_hint",
            "price_mode",
            "l1_bid1",
            "l1_ask1",
            "l1_last_price",
            "l1_ts",
            "l1_source",
        ]
        fieldnames = list(extended)
        if path.exists():
            try:
                header = path.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
            except Exception:
                header = ""
            if ("plan_id" not in header) and ("signal_id" not in header):
                fieldnames = list(legacy)

        self._append_csv(
            path,
            fieldnames,
            {
                "ts": ack.ts.isoformat(),
                "intent_id": str(intent_id or ""),
                "plan_id": str(plan_id or ""),
                "signal_id": str(signal_id or ""),
                "strategy_tag": str(strategy_tag or ""),
                "signal_kind": str(signal_kind or ""),
                "client_order_id": ack.client_order_id,
                "account_id": ack.account_id,
                "code": ack.code,
                "side": ack.side.value,
                "quantity": ack.quantity,
                "ok": ack.ok,
                "status": ack.status,
                "broker_order_id": ack.broker_order_id,
                "message": ack.message,
                "reject_code": ack.reject_code,
                "requested_price_mode": str(requested_price_mode or ""),
                "requested_limit_price": requested_limit_price,
                "effective_price_hint": effective_price_hint,
                "price_hint": ack.price_hint,
                "price_mode": ack.price_mode,
                "l1_bid1": ack.l1_bid1,
                "l1_ask1": ack.l1_ask1,
                "l1_last_price": ack.l1_last_price,
                "l1_ts": ack.l1_ts,
                "l1_source": ack.l1_source,
            },
        )

    def _log_order_state(self, state: OrderState) -> None:
        self._append_csv(
            self._real_dir / "orders_state_timeline.csv",
            [
                "ts",
                "updated_at",
                "client_order_id",
                "intent_id",
                "account_id",
                "code",
                "side",
                "quantity",
                "status",
                "broker_order_id",
                "message",
                "price_hint",
                "version",
                "terminal",
                "source_event_id",
                "retry_count",
                "last_error_code",
            ],
            {
                "ts": state.ts.isoformat(),
                "updated_at": (state.updated_at or state.ts).isoformat(),
                "client_order_id": state.client_order_id,
                "intent_id": state.intent_id,
                "account_id": state.account_id,
                "code": state.code,
                "side": state.side.value,
                "quantity": state.quantity,
                "status": state.status,
                "broker_order_id": state.broker_order_id,
                "message": state.message,
                "price_hint": state.price_hint,
                "version": state.version,
                "terminal": state.terminal,
                "source_event_id": state.source_event_id,
                "retry_count": state.retry_count,
                "last_error_code": state.last_error_code,
            },
        )

    def _capture_local_write(self, label: str, writer: Any, errors: list[str]) -> Any:
        try:
            return writer()
        except Exception as exc:
            errors.append(f"{label}: {exc}")
            return None

    def _persist_order_state(self, state: OrderState) -> tuple[OrderState | None, list[str]]:
        errors: list[str] = []
        stored_state = self._capture_local_write(
            "order_state_timeline.sqlite3",
            lambda: self.state_store.append(state, source_event_id=str(state.source_event_id or "")),
            errors,
        )
        if stored_state is not None:
            self._capture_local_write("orders_state_timeline.csv", lambda: self._log_order_state(stored_state), errors)
        return stored_state, errors

    def _attach_persistence_meta(self, result: TradeOpsResult, errors: list[str] | None = None) -> TradeOpsResult:
        payload = dict(result.payload or {})
        local_errors = [str(item) for item in (errors or []) if str(item).strip()]
        payload["persist_ok"] = not bool(local_errors)
        payload["reconcile_required"] = bool(local_errors)
        payload["persistence_error"] = "; ".join(local_errors)
        return self._result(result.command, ok=bool(result.ok), payload=payload)

    def place_order(self, req: OrderPlaceRequest) -> TradeOpsResult:
        ts = datetime.now()
        code = str(req.code or "").upper().strip()
        quantity = max(0, int(req.quantity))
        side = req.side
        requested_price_mode = str(req.price_mode or self.cfg.price_mode or "l1_protect").strip().lower()
        requested_limit_price = _safe_float(getattr(req, "limit_price", None))
        plan_id = str(getattr(req, "plan_id", "") or "").strip()
        signal_id = str(getattr(req, "signal_id", "") or "").strip()
        strategy_tag = str(getattr(req, "strategy_tag", "") or "").strip()
        signal_kind = str(getattr(req, "signal_kind", "") or "").strip()
        intent_id = str(getattr(req, "intent_id", "") or "").strip() or f"INT-CLI-{ts.strftime('%Y%m%d%H%M%S')}"
        client_order_key = (
            str(getattr(req, "client_order_key", "") or "").strip()
            or f"COID-CLI-{ts.strftime('%Y%m%d')}-{code.replace('.', '')}-{side.value}-1"
        )
        client_order_id = client_order_key

        def _with_persistence(result: TradeOpsResult, errors: list[str] | None = None) -> TradeOpsResult:
            return self._attach_persistence_meta(result, errors)

        def _with_submission_scope(
            result: TradeOpsResult,
            *,
            broker_submission_attempted: bool,
            local_gate_intercepted: bool,
            submission_scope: str,
            submission_stage: str,
            errors: list[str] | None = None,
        ) -> TradeOpsResult:
            self._decorate_order_submission_scope(
                result,
                broker_submission_attempted=broker_submission_attempted,
                local_gate_intercepted=local_gate_intercepted,
                submission_scope=submission_scope,
                submission_stage=submission_stage,
            )
            return _with_persistence(result, errors)

        if quantity <= 0:
            result = self._to_result(
                "order.place",
                TradeCommandResult(
                    ok=False,
                    code="invalid_quantity",
                    message="quantity must be positive",
                    account_id=self.cfg.account_id,
                    client_order_id=client_order_id,
                    client_order_key=client_order_key,
                    intent_id=intent_id,
                    status=OrderStatus.RISK_REJECTED.value,
                ),
            )
            return _with_submission_scope(
                result,
                broker_submission_attempted=False,
                local_gate_intercepted=False,
                submission_scope="local_validation",
                submission_stage="request_validation",
            )

        if self.cfg.enforce_guard_token and (not str(req.guard_token or "").strip()):
            result = self._to_result(
                "order.place",
                TradeCommandResult(
                    ok=False,
                    code="guard_token_missing",
                    message="broker-order-guard-token is required",
                    account_id=self.cfg.account_id,
                    client_order_id=client_order_id,
                    client_order_key=client_order_key,
                    intent_id=intent_id,
                    status=OrderStatus.RISK_REJECTED.value,
                ),
            )
            return _with_submission_scope(
                result,
                broker_submission_attempted=False,
                local_gate_intercepted=False,
                submission_scope="local_validation",
                submission_stage="guard_token",
            )

        if requested_price_mode not in {"l1_protect", "fixed"}:
            result = self._to_result(
                "order.place",
                TradeCommandResult(
                    ok=False,
                    code="invalid_price_mode",
                    message="price_mode must be one of: l1_protect,fixed",
                    account_id=self.cfg.account_id,
                    client_order_id=client_order_id,
                    client_order_key=client_order_key,
                    intent_id=intent_id,
                    status=OrderStatus.RISK_REJECTED.value,
                ),
            )
            result.payload["requested_price_mode"] = requested_price_mode
            result.payload["requested_limit_price"] = requested_limit_price
            return _with_submission_scope(
                result,
                broker_submission_attempted=False,
                local_gate_intercepted=False,
                submission_scope="local_validation",
                submission_stage="request_validation",
            )

        if requested_limit_price is not None and requested_price_mode != "fixed":
            result = self._to_result(
                "order.place",
                TradeCommandResult(
                    ok=False,
                    code="limit_price_requires_fixed_mode",
                    message="limit_price requires price_mode=fixed",
                    account_id=self.cfg.account_id,
                    client_order_id=client_order_id,
                    client_order_key=client_order_key,
                    intent_id=intent_id,
                    status=OrderStatus.RISK_REJECTED.value,
                ),
            )
            result.payload["requested_price_mode"] = requested_price_mode
            result.payload["requested_limit_price"] = requested_limit_price
            return _with_submission_scope(
                result,
                broker_submission_attempted=False,
                local_gate_intercepted=False,
                submission_scope="local_validation",
                submission_stage="request_validation",
            )

        if requested_price_mode == "fixed":
            if getattr(req, "limit_price", None) is None:
                result = self._to_result(
                    "order.place",
                    TradeCommandResult(
                        ok=False,
                        code="limit_price_required",
                        message="limit_price is required when price_mode=fixed",
                        account_id=self.cfg.account_id,
                        client_order_id=client_order_id,
                        client_order_key=client_order_key,
                        intent_id=intent_id,
                        status=OrderStatus.RISK_REJECTED.value,
                    ),
                )
                result.payload["requested_price_mode"] = requested_price_mode
                result.payload["requested_limit_price"] = requested_limit_price
                return _with_submission_scope(
                    result,
                    broker_submission_attempted=False,
                    local_gate_intercepted=False,
                    submission_scope="local_validation",
                    submission_stage="request_validation",
                )
            if requested_limit_price is None or requested_limit_price <= 0:
                result = self._to_result(
                    "order.place",
                    TradeCommandResult(
                        ok=False,
                        code="limit_price_non_positive",
                        message="limit_price must be positive",
                        account_id=self.cfg.account_id,
                        client_order_id=client_order_id,
                        client_order_key=client_order_key,
                        intent_id=intent_id,
                        status=OrderStatus.RISK_REJECTED.value,
                    ),
                )
                result.payload["requested_price_mode"] = requested_price_mode
                result.payload["requested_limit_price"] = requested_limit_price
                return _with_submission_scope(
                    result,
                    broker_submission_attempted=False,
                    local_gate_intercepted=False,
                    submission_scope="local_validation",
                    submission_stage="request_validation",
                )

        if self._kill_switch_required_for_write() and (not self._kill_switch_configured()):
            result = self._to_result(
                "order.place",
                TradeCommandResult(
                    ok=False,
                    code="kill_switch_unconfigured",
                    message="prod write path requires non-empty kill_switch_file",
                    account_id=self.cfg.account_id,
                    client_order_id=client_order_id,
                    client_order_key=client_order_key,
                    intent_id=intent_id,
                    status=OrderStatus.RISK_REJECTED.value,
                ),
            )
            result.payload["kill_switch_configured"] = False
            result.payload["kill_switch_file"] = str(self.cfg.kill_switch_file or "")
            return _with_submission_scope(
                result,
                broker_submission_attempted=False,
                local_gate_intercepted=True,
                submission_scope="local_risk",
                submission_stage="kill_switch_configuration",
            )

        connect_gate = self._run_connect_gate()
        write_authority_snapshot = dict(connect_gate.get("write_authority_snapshot") or self._write_authority_snapshot())
        if not bool(connect_gate.get("pass", False)):
            result = self._to_result(
                "order.place",
                TradeCommandResult(
                    ok=False,
                    code="connect_gate_failed",
                    message="pretrade connect gate failed",
                    account_id=self.cfg.account_id,
                    client_order_id=client_order_id,
                    client_order_key=client_order_key,
                    intent_id=intent_id,
                    status=OrderStatus.RISK_REJECTED.value,
                ),
            )
            result.payload["connect_gate"] = connect_gate
            result.payload["write_authority_snapshot"] = write_authority_snapshot
            result.payload["requested_price_mode"] = requested_price_mode
            result.payload["requested_limit_price"] = requested_limit_price
            return _with_submission_scope(
                result,
                broker_submission_attempted=False,
                local_gate_intercepted=True,
                submission_scope="local_gate",
                submission_stage="connect_gate",
            )

        l1 = self._flow_smoke_snapshot(code, requested_limit_price)
        if l1 is None:
            l1 = self._snapshot_l1(code)
        if l1 is None:
            result = self._to_result(
                "order.place",
                TradeCommandResult(
                    ok=False,
                    code="l1_snapshot_unavailable",
                    message="cannot fetch L1 snapshot for symbol",
                    account_id=self.cfg.account_id,
                    client_order_id=client_order_id,
                    client_order_key=client_order_key,
                    intent_id=intent_id,
                    status=OrderStatus.RISK_REJECTED.value,
                ),
            )
            result.payload["connect_gate"] = connect_gate
            result.payload["requested_price_mode"] = requested_price_mode
            result.payload["requested_limit_price"] = requested_limit_price
            return _with_submission_scope(
                result,
                broker_submission_attempted=False,
                local_gate_intercepted=False,
                submission_scope="local_market_data",
                submission_stage="snapshot_l1",
            )

        if requested_price_mode == "fixed":
            price_hint = requested_limit_price
        else:
            price_hint = self._price_from_l1(l1, side)
        session_gate = self._session_gate(l1.ts)
        if price_hint is None or float(price_hint) <= 0:
            if requested_price_mode == "fixed":
                validation_code = "limit_price_non_positive"
            else:
                validation_code = "ask1_missing_or_non_positive" if side == Side.BUY else "bid1_missing_or_non_positive"
            decision_row = self._risk_decision_row(
                ts=ts,
                intent_id=intent_id,
                client_order_id=client_order_id,
                ok=False,
                code="l1_price_missing",
                reason=validation_code,
                symbol=code,
                side=side,
                quantity=quantity,
                price_hint=price_hint,
                l1=l1,
            )
            decision_row["l1_validation_code"] = validation_code
            self._append_csv(
                self._audit_dir / "risk_decisions.csv",
                list(decision_row.keys()),
                decision_row,
            )
            result = self._to_result(
                "order.place",
                TradeCommandResult(
                    ok=False,
                    code="l1_price_missing",
                    message=validation_code,
                    account_id=self.cfg.account_id,
                    client_order_id=client_order_id,
                    client_order_key=client_order_key,
                    intent_id=intent_id,
                    status=OrderStatus.RISK_REJECTED.value,
                    l1_snapshot=l1,
                ),
            )
            result.payload["connect_gate"] = connect_gate
            result.payload["write_authority_snapshot"] = write_authority_snapshot
            result.payload["session_gate"] = session_gate
            result.payload["requested_price_mode"] = requested_price_mode
            result.payload["requested_limit_price"] = requested_limit_price
            return _with_submission_scope(
                result,
                broker_submission_attempted=False,
                local_gate_intercepted=False,
                submission_scope="local_market_data",
                submission_stage="price_validation",
            )

        intent = BrokerOrderIntent(
            ts=ts,
            intent_id=intent_id,
            sim_order_id=f"CLI-{intent_id}",
            account_id=str(req.account_id or self.cfg.account_id),
            code=code,
            side=side,
            quantity=quantity,
            price_hint=float(price_hint),
            dry_run=self._flow_smoke_mode(),
            guard_token_present=True,
            status=OrderStatus.PREPARED.value,
            client_order_id=client_order_id,
            risk_ok=True,
            risk_code="",
            risk_reason="",
            broker_order_id="",
            submit_message="",
            price_mode=requested_price_mode,
            l1_bid1=l1.bid1,
            l1_ask1=l1.ask1,
            l1_last_price=l1.last_price,
            l1_ts=l1.ts.isoformat(),
            l1_source=l1.source.value,
        )
        decision = self.risk_engine.evaluate(
            intent,
            cash_available=self._risk_cash_available(),
            sellable_qty=self._risk_sellable_qty(code),
            cumulative_notional_today=float(self._cumulative_notional_today),
            is_market_open=bool(session_gate.get("pass", False)),
            kill_switch_on=kill_switch_on(self.cfg.kill_switch_file),
        )
        decision_row = self._risk_decision_row(
            ts=decision.ts,
            intent_id=decision.intent_id,
            client_order_id=decision.client_order_id,
            ok=decision.ok,
            code=decision.code,
            reason=decision.reason,
            symbol=decision.code_symbol,
            side=decision.side,
            quantity=decision.quantity,
            price_hint=decision.price_hint,
            l1=l1,
        )
        self._append_csv(
            self._audit_dir / "risk_decisions.csv",
            list(decision_row.keys()),
            decision_row,
        )

        if not decision.ok:
            state, persistence_errors = self._persist_order_state(
                OrderState(
                    ts=ts,
                    updated_at=ts,
                    client_order_id=client_order_id,
                    intent_id=intent_id,
                    account_id=self.cfg.account_id,
                    code=code,
                    side=side,
                    quantity=quantity,
                    status=OrderStatus.RISK_REJECTED.value,
                    broker_order_id="",
                    message=str(decision.reason),
                    price_hint=float(price_hint),
                    terminal=True,
                    source_event_id=f"{ts.isoformat()}:{intent_id}:risk",
                    last_error_code=str(decision.code),
                )
            )
            reject_ack = BrokerOrderAck(
                ts=ts,
                client_order_id=client_order_id,
                account_id=self.cfg.account_id,
                code=code,
                side=side,
                quantity=quantity,
                ok=False,
                status=OrderStatus.RISK_REJECTED.value,
                broker_order_id="",
                message=str(decision.reason),
                reject_code=str(decision.code),
                price_hint=float(price_hint),
                price_mode=requested_price_mode,
                l1_bid1=l1.bid1,
                l1_ask1=l1.ask1,
                l1_last_price=l1.last_price,
                l1_ts=l1.ts.isoformat(),
                l1_source=l1.source.value,
            )
            self._capture_local_write(
                "orders_submit_log.csv",
                lambda: self._log_submit_ack(
                    reject_ack,
                    intent_id=intent_id,
                    plan_id=plan_id,
                    signal_id=signal_id,
                    strategy_tag=strategy_tag,
                    signal_kind=signal_kind,
                    requested_price_mode=requested_price_mode,
                    requested_limit_price=requested_limit_price,
                    effective_price_hint=float(price_hint),
                ),
                persistence_errors,
            )
            result = self._to_result(
                "order.place",
                TradeCommandResult(
                    ok=False,
                    code=str(decision.code),
                    message=str(decision.reason),
                    account_id=self.cfg.account_id,
                    broker_order_id="",
                    client_order_id=client_order_id,
                    client_order_key=client_order_key,
                    intent_id=intent_id,
                    status=OrderStatus.RISK_REJECTED.value,
                    l1_snapshot=l1,
                ),
            )
            result.payload["connect_gate"] = connect_gate
            result.payload["write_authority_snapshot"] = write_authority_snapshot
            result.payload["session_gate"] = session_gate
            result.payload["requested_price_mode"] = requested_price_mode
            result.payload["requested_limit_price"] = requested_limit_price
            return _with_submission_scope(
                result,
                broker_submission_attempted=False,
                local_gate_intercepted=False,
                submission_scope="local_risk",
                submission_stage="risk_engine",
                errors=persistence_errors,
            )

        broker = self._ensure_broker_adapter(require_write_permission=True)
        if broker is None:
            result = self._to_result(
                "order.place",
                TradeCommandResult(
                    ok=False,
                    code="broker_adapter_missing",
                    message="broker adapter is not available for governed write",
                    account_id=self.cfg.account_id,
                    broker_order_id="",
                    client_order_id=client_order_id,
                    client_order_key=client_order_key,
                    intent_id=intent_id,
                    status=OrderStatus.FAILED.value,
                    l1_snapshot=l1,
                ),
            )
            result.payload["connect_gate"] = connect_gate
            result.payload["write_authority_snapshot"] = write_authority_snapshot
            result.payload["session_gate"] = session_gate
            result.payload["requested_price_mode"] = requested_price_mode
            result.payload["requested_limit_price"] = requested_limit_price
            return _with_submission_scope(
                result,
                broker_submission_attempted=False,
                local_gate_intercepted=False,
                submission_scope="local_broker_bootstrap",
                submission_stage="broker_adapter",
            )
        ack = broker.place_order(intent)
        persistence_errors: list[str] = []
        self._capture_local_write(
            "orders_submit_log.csv",
            lambda: self._log_submit_ack(
                ack,
                intent_id=intent_id,
                plan_id=plan_id,
                signal_id=signal_id,
                strategy_tag=strategy_tag,
                signal_kind=signal_kind,
                requested_price_mode=requested_price_mode,
                requested_limit_price=requested_limit_price,
                effective_price_hint=float(price_hint),
            ),
            persistence_errors,
        )
        if ack.ok:
            self._cumulative_notional_today += float(max(0.0, float(price_hint) * quantity))
        _, state_errors = self._persist_order_state(
            OrderState(
                ts=ack.ts,
                updated_at=ack.ts,
                client_order_id=client_order_id,
                intent_id=intent_id,
                account_id=ack.account_id,
                code=code,
                side=side,
                quantity=quantity,
                status=str(ack.status or (OrderStatus.SUBMITTED.value if ack.ok else OrderStatus.FAILED.value)),
                broker_order_id=str(ack.broker_order_id or ""),
                message=str(ack.message or ""),
                price_hint=float(price_hint),
                terminal=is_terminal_order_status(str(ack.status or "")),
                source_event_id=f"{ack.ts.isoformat()}:{intent_id}:submit",
                last_error_code=str(ack.reject_code or ""),
            )
        )
        persistence_errors.extend(state_errors)
        result = self._to_result(
            "order.place",
            TradeCommandResult(
                ok=bool(ack.ok),
                code="ok" if ack.ok else str(ack.reject_code or "submit_failed"),
                message=str(ack.message or ""),
                account_id=ack.account_id,
                broker_order_id=ack.broker_order_id,
                client_order_id=client_order_id,
                client_order_key=client_order_key,
                intent_id=intent_id,
                status=ack.status,
                l1_snapshot=l1,
            ),
        )
        result.payload["connect_gate"] = connect_gate
        result.payload["write_authority_snapshot"] = write_authority_snapshot
        result.payload["session_gate"] = session_gate
        result.payload["price_hint"] = float(price_hint)
        result.payload["price_mode"] = requested_price_mode
        result.payload["requested_price_mode"] = requested_price_mode
        result.payload["requested_limit_price"] = requested_limit_price
        result.payload["effective_price_hint"] = float(price_hint)
        result.payload["plan_id"] = plan_id
        result.payload["signal_id"] = signal_id
        result.payload["strategy_tag"] = strategy_tag
        result.payload["signal_kind"] = signal_kind
        return _with_submission_scope(
            result,
            broker_submission_attempted=not self._flow_smoke_mode(),
            local_gate_intercepted=False,
            submission_scope="flow_smoke" if self._flow_smoke_mode() else "broker_submit",
            submission_stage="dry_run_place_order" if self._flow_smoke_mode() else "broker_place_order",
            errors=persistence_errors,
        )

