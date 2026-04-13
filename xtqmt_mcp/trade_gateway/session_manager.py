from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass, field
from datetime import datetime
from queue import Queue
from threading import Event, RLock, Thread
from typing import Any, Callable

from xtqmt_mcp.session_resolution import session_resolution_payload

from .bootstrap import TradeOpsRuntimeContext, build_trade_ops_context
from .config import ACCOUNT_CONTRACT_SINGLE_PRIMARY, ACCOUNT_INPUT_MODE_SERVICE_CONTEXT, TradeOpsGatewayConfig


@dataclass
class _SessionTask:
    callback: Callable[[TradeOpsRuntimeContext], Any]
    future: Future


class SessionWarmError(RuntimeError):
    def __init__(self, message: str, *, payload: dict[str, Any]) -> None:
        super().__init__(message)
        self.payload = dict(payload or {})


def _trade_result_payload(result: Any) -> dict[str, Any]:
    payload = getattr(result, "payload", {})
    return dict(payload or {}) if isinstance(payload, dict) else {}


def _session_contract_meta() -> dict[str, Any]:
    return {
        "account_contract": ACCOUNT_CONTRACT_SINGLE_PRIMARY,
        "account_input_mode": ACCOUNT_INPUT_MODE_SERVICE_CONTEXT,
        "account_scope": "primary_session",
    }


def _context_session_resolution(context: TradeOpsRuntimeContext | None) -> dict[str, Any]:
    if context is None:
        return {}
    service = getattr(context, "service", None)
    payload = session_resolution_payload(getattr(service, "session_resolution", None))
    if payload:
        return payload
    return session_resolution_payload(getattr(context, "session_resolution", None))


def _context_base_session_resolution(context: TradeOpsRuntimeContext | None) -> dict[str, Any]:
    if context is None:
        return {}
    service = getattr(context, "service", None)
    payload = session_resolution_payload(getattr(service, "base_session_resolution", None))
    if payload:
        return payload
    return session_resolution_payload(getattr(context, "session_resolution", None))


def _context_effective_session_resolution(context: TradeOpsRuntimeContext | None) -> dict[str, Any]:
    if context is None:
        return {}
    service = getattr(context, "service", None)
    getter = getattr(service, "effective_session_resolution", None)
    if callable(getter):
        payload = session_resolution_payload(getter())
        if payload:
            return payload
    return _context_session_resolution(context)


def _context_runtime_session_override(context: TradeOpsRuntimeContext | None) -> dict[str, Any]:
    if context is None:
        return {}
    service = getattr(context, "service", None)
    getter = getattr(service, "runtime_session_override", None)
    if callable(getter):
        payload = getattr(getter, "__call__", None)
        try:
            override = getter()
        except Exception:
            override = {}
        return dict(override or {}) if isinstance(override, dict) else {}
    effective = _context_effective_session_resolution(context)
    override = effective.get("runtime_resolution_event")
    return dict(override or {}) if isinstance(override, dict) else {}


def _context_owner_session_id(context: TradeOpsRuntimeContext | None) -> int:
    if context is None:
        return 0
    service = getattr(context, "service", None)
    getter = getattr(service, "owner_managed_session_id", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:
            value = None
        try:
            session_id = int(value or 0)
        except Exception:
            session_id = 0
        if session_id > 0:
            return session_id
    try:
        return int(getattr(context, "resolved_session_id", 0) or 0)
    except Exception:
        return 0


def _align_trace_session_resolution(trace: list[dict[str, Any]], resolution: dict[str, Any]) -> None:
    if not resolution:
        return
    runtime_override = dict((resolution.get("runtime_resolution_event") or {}))
    for item in trace:
        if not isinstance(item, dict):
            continue
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        payload["session_resolution"] = dict(resolution)
        payload["effective_session_resolution"] = dict(resolution)
        if runtime_override:
            payload["runtime_session_override"] = dict(runtime_override)


def _run_session_health_check(context: TradeOpsRuntimeContext) -> dict[str, Any]:
    warm_orders_runner = getattr(context.service, "warm_health_orders_list", None) or context.service.orders_list
    checks = (
        ("account.show", context.service.account_show),
        ("positions.list", context.service.positions_list),
        ("orders.list", warm_orders_runner),
    )
    checked_at = datetime.now().isoformat(timespec="seconds")
    trace: list[dict[str, Any]] = []
    reason = ""
    for step, runner in checks:
        try:
            result = runner()
            payload = _trade_result_payload(result)
            ok = bool(getattr(result, "ok", False))
            item = {
                "step": step,
                "ok": ok,
                "payload": payload,
            }
            if not ok:
                item_reason = str(payload.get("error") or payload.get("code") or f"{step}_failed").strip() or f"{step}_failed"
                item["reason"] = item_reason
                message = str(payload.get("message") or "").strip()
                if message:
                    item["message"] = message
                if not reason:
                    reason = item_reason
            trace.append(item)
            if not ok:
                return {
                    "ready": False,
                    "reason": reason,
                    "checked_at": checked_at,
                    "trace": trace,
                }
        except Exception as exc:
            item_reason = f"{step}_exception"
            trace.append(
                {
                    "step": step,
                    "ok": False,
                    "payload": {},
                    "reason": item_reason,
                    "message": str(exc),
                }
            )
            if not reason:
                reason = item_reason
            return {
                "ready": False,
                "reason": reason,
                "checked_at": checked_at,
                "trace": trace,
            }
    owner_session_id = _context_owner_session_id(context)
    if owner_session_id > 0:
        align_fn = getattr(context.service, "realign_session_resolution", None)
        if callable(align_fn):
            aligned_resolution = dict(
                align_fn(
                    owner_session_id,
                    reason="owner_session_detected",
                    event_source="owner_managed_session",
                    owner_session_id=owner_session_id,
                )
                or {}
            )
            _align_trace_session_resolution(trace, aligned_resolution)
    probe_fn = getattr(context.service, "probe_connection", None)
    if callable(probe_fn):
        try:
            probe_result = probe_fn()
            probe_payload = _trade_result_payload(probe_result)
        except Exception:
            probe_payload = {}
        probe_resolution_confirmed = bool(probe_payload.get("same_plan_verdict", False)) and bool(
            probe_payload.get("probe_complete_verdict", False)
        )
        preferred_session_id = str(
            probe_payload.get("session_id")
            or session_resolution_payload(probe_payload.get("session_resolution") or {}).get("resolved_session_id")
            or ""
        ).strip()
        if probe_resolution_confirmed and preferred_session_id:
            align_fn = getattr(context.service, "realign_session_resolution", None)
            if callable(align_fn):
                try:
                    aligned_resolution = dict(
                        align_fn(
                            preferred_session_id,
                            reason="probe_resolution_confirmed",
                            event_source="probe.connection",
                            owner_session_id=owner_session_id,
                            observed_probe_session_id=str(probe_payload.get("observed_probe_session_id") or preferred_session_id),
                        )
                        or {}
                    )
                except Exception:
                    aligned_resolution = {}
                _align_trace_session_resolution(trace, aligned_resolution)
    return {
        "ready": not any(not bool(item.get("ok", False)) for item in trace),
        "reason": reason,
        "checked_at": checked_at,
        "trace": trace,
    }


class GatewaySessionWorker:
    def __init__(
        self,
        config: TradeOpsGatewayConfig,
        *,
        context_builder: Callable[[TradeOpsGatewayConfig, str], TradeOpsRuntimeContext] = build_trade_ops_context,
    ) -> None:
        self._config = config
        self._context_builder = context_builder
        self._tasks: Queue[_SessionTask | None] = Queue()
        self._ready = Event()
        self._thread = Thread(
            target=self._run,
            name=f"xtquant-session-{str(config.account_id or 'default').strip() or 'default'}",
            daemon=True,
        )
        self._startup_error: Exception | None = None
        self._startup_summary: dict[str, Any] = {}
        self._context: TradeOpsRuntimeContext | None = None
        self._closed = False

    @property
    def context(self) -> TradeOpsRuntimeContext | None:
        return self._context

    def is_alive(self) -> bool:
        return bool(self._ready.is_set() and self._thread.is_alive() and (not self._closed) and self._startup_error is None)

    def start(self) -> dict[str, Any]:
        self._thread.start()
        self._ready.wait()
        if self._startup_error is not None:
            raise self._startup_error
        if self._context is None:
            raise RuntimeError("session_warm_failed: worker_context_missing")
        return dict(self._startup_summary)

    def submit(self, callback: Callable[[TradeOpsRuntimeContext], Any]) -> Any:
        if self._closed:
            raise RuntimeError("session_closed")
        if not self._ready.is_set():
            raise RuntimeError("session_not_ready")
        if self._startup_error is not None:
            raise self._startup_error
        if not self._thread.is_alive():
            raise RuntimeError("session_closed")
        future: Future = Future()
        self._tasks.put(_SessionTask(callback=callback, future=future))
        return future.result()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._tasks.put(None)
        self._thread.join(timeout=5.0)

    def _run(self) -> None:
        context: TradeOpsRuntimeContext | None = None
        try:
            context = self._context_builder(self._config, "session.warm")
            self._context = context
            health = _run_session_health_check(context)
            self._startup_summary = {
                "account_id": str(context.resolved_account_id or self._config.account_id or "").strip(),
                "session_id": int(
                    _context_session_resolution(context).get("resolved_session_id")
                    or _context_owner_session_id(context)
                    or context.resolved_session_id
                ),
                "session_resolution": _context_session_resolution(context),
                "ready": bool(health["ready"]),
                "reason": str(health.get("reason") or ""),
                "last_check_at": str(health.get("checked_at") or ""),
                "wake_report": dict(getattr(context, "wake_report", {}) or {}),
                "warm_trace": list(health.get("trace") or []),
                "status_trace": list(health.get("trace") or []),
            }
            if not bool(health["ready"]):
                raise SessionWarmError(
                    f"session warm health check failed: {health.get('reason') or 'session_not_ready'}",
                    payload=self._startup_summary,
                )
        except Exception as exc:
            self._startup_error = exc
            if context is not None:
                context.close()
                self._context = None
        finally:
            self._ready.set()

        if self._startup_error is not None or context is None:
            return

        while True:
            item = self._tasks.get()
            if item is None:
                break
            try:
                result = item.callback(context)
            except Exception as exc:
                item.future.set_exception(exc)
            else:
                item.future.set_result(result)

        try:
            context.close()
        finally:
            self._context = None


@dataclass
class GatewaySessionState:
    account_id: str
    session_id: int
    worker: GatewaySessionWorker
    context: TradeOpsRuntimeContext
    warmed_at: datetime
    last_used_at: datetime
    wake_report: dict[str, Any] = field(default_factory=dict)
    warm_trace: list[dict[str, Any]] = field(default_factory=list)
    ready: bool = False
    last_error: str = ""
    last_check_at: str = ""
    status_trace: list[dict[str, Any]] = field(default_factory=list)
    owner_generation: int = 0
    owner_started_reason: str = ""

    def summary(self) -> dict[str, Any]:
        base_session_resolution = _context_base_session_resolution(self.context)
        effective_session_resolution = _context_effective_session_resolution(self.context)
        runtime_session_override = _context_runtime_session_override(self.context)
        return {
            "ready": bool(self.ready),
            "account_id": self.account_id,
            "owner_account_id": self.account_id,
            "session_id": self.session_id,
            "warmed_at": self.warmed_at.isoformat(timespec="seconds"),
            "last_used_at": self.last_used_at.isoformat(timespec="seconds"),
            "last_error": str(self.last_error or ""),
            "reason": str(self.last_error or ""),
            "last_check_at": str(self.last_check_at or ""),
            "wake_report": dict(self.wake_report or {}),
            "warm_trace": list(self.warm_trace or []),
            "status_trace": list(self.status_trace or []),
            "owner_generation": int(self.owner_generation),
            "owner_started_reason": str(self.owner_started_reason or ""),
            "session_resolution": base_session_resolution,
            "effective_session_resolution": effective_session_resolution,
            "runtime_session_override": runtime_session_override,
            **_session_contract_meta(),
        }


class GatewaySessionManager:
    def __init__(
        self,
        config: TradeOpsGatewayConfig,
        *,
        context_builder: Callable[[TradeOpsGatewayConfig, str], TradeOpsRuntimeContext] = build_trade_ops_context,
    ) -> None:
        self._config = config
        self._context_builder = context_builder
        self._lock = RLock()
        self._active_state: GatewaySessionState | None = None
        self._owner_generation = 0

    def _session_not_ready_payload(self, account_id: str, *, reason: str) -> dict[str, Any]:
        return {
            "ready": False,
            "account_id": account_id,
            "owner_account_id": "",
            "session_id": "",
            "warmed_at": "",
            "last_used_at": "",
            "last_error": "",
            "reason": reason,
            "last_check_at": "",
            "wake_report": {},
            "warm_trace": [],
            "status_trace": [],
            "owner_generation": 0,
            "owner_started_reason": "",
            "session_resolution": {},
            "effective_session_resolution": {},
            "runtime_session_override": {},
            **_session_contract_meta(),
        }

    def _owner_mismatch_payload(self, account_id: str, state: GatewaySessionState) -> dict[str, Any]:
        return {
            "ready": False,
            "account_id": account_id,
            "owner_account_id": state.account_id,
            "session_id": "",
            "warmed_at": "",
            "last_used_at": state.last_used_at.isoformat(timespec="seconds"),
            "last_error": "session_owner_mismatch",
            "reason": "session_owner_mismatch",
            "last_check_at": state.last_check_at,
            "wake_report": dict(state.wake_report or {}),
            "warm_trace": list(state.warm_trace or []),
            "status_trace": list(state.status_trace or []),
            "owner_generation": int(state.owner_generation),
            "owner_started_reason": str(state.owner_started_reason or ""),
            "session_resolution": _context_base_session_resolution(state.context),
            "effective_session_resolution": _context_effective_session_resolution(state.context),
            "runtime_session_override": _context_runtime_session_override(state.context),
            **_session_contract_meta(),
        }

    def _requested_account_id(self, account_id: str = "") -> str:
        return str(account_id or "").strip()

    def _close_active_state(self) -> None:
        state = self._active_state
        if state is None:
            return
        try:
            state.worker.close()
        finally:
            self._active_state = None

    def _apply_health(self, state: GatewaySessionState, health: dict[str, Any]) -> None:
        state.ready = bool(health.get("ready", False))
        try:
            resolved_session_id = int(_context_effective_session_resolution(state.context).get("resolved_session_id") or 0)
        except Exception:
            resolved_session_id = 0
        if resolved_session_id > 0:
            state.session_id = resolved_session_id
        else:
            owner_session_id = _context_owner_session_id(state.context)
            if owner_session_id > 0:
                state.session_id = owner_session_id
        state.last_error = "" if state.ready else str(health.get("reason") or "session_not_ready").strip()
        state.last_check_at = str(health.get("checked_at") or "")
        state.status_trace = list(health.get("trace") or [])

    def _refresh_state_health(self, state: GatewaySessionState) -> dict[str, Any]:
        try:
            health = state.worker.submit(lambda context: _run_session_health_check(context))
        except Exception as exc:
            health = {
                "ready": False,
                "reason": "session_health_check_exception",
                "checked_at": datetime.now().isoformat(timespec="seconds"),
                "trace": [
                    {
                        "step": "health.check",
                        "ok": False,
                        "payload": {},
                        "reason": "session_health_check_exception",
                        "message": str(exc),
                    }
                ],
            }
        self._apply_health(state, health)
        return health

    def warm(self, *, account_id: str = "", force: bool = False) -> GatewaySessionState:
        explicit_account_id = self._requested_account_id(account_id)
        resolved_account_id = explicit_account_id or str(self._config.account_id or "").strip()
        allow_auto_account = bool(self._config.auto_account and not resolved_account_id)
        if not resolved_account_id and not allow_auto_account:
            raise RuntimeError("session_warm_failed: account_id is required")
        with self._lock:
            rebuild_reason = "initial_warm"
            existing = self._active_state
            if existing is not None:
                same_owner_request = (not explicit_account_id) or existing.account_id == resolved_account_id
                if existing.worker.is_alive() and same_owner_request and (not bool(force)):
                    self._refresh_state_health(existing)
                    if existing.ready:
                        existing.last_used_at = datetime.now()
                        return existing
                    rebuild_reason = "owner_not_ready_rebuild"
                    self._close_active_state()
                elif existing.worker.is_alive() and explicit_account_id and existing.account_id != resolved_account_id and (not bool(force)):
                    raise RuntimeError(
                        f"session_owner_conflict: active_owner={existing.account_id}; use force=true to switch owner"
                    )
                else:
                    rebuild_reason = "force_rebuild" if bool(force) else "worker_not_alive_rebuild"
                    self._close_active_state()

            cfg = self._config
            if resolved_account_id != str(self._config.account_id or "").strip():
                from dataclasses import replace

                cfg = replace(self._config, account_id=resolved_account_id)

            try:
                worker = GatewaySessionWorker(cfg, context_builder=self._context_builder)
                startup = worker.start()
            except SessionWarmError:
                raise
            except Exception as exc:
                raise RuntimeError(f"session_warm_failed: {exc}") from exc

            context = worker.context
            if context is None:
                worker.close()
                raise RuntimeError("session_warm_failed: worker_context_missing")
            runtime_account_id = str(startup.get("account_id") or context.resolved_account_id or resolved_account_id).strip()
            if not runtime_account_id:
                worker.close()
                raise RuntimeError("session_warm_failed: account_id is required")
            if explicit_account_id and runtime_account_id != explicit_account_id:
                worker.close()
                raise RuntimeError(
                    f"session_warm_failed: resolved_account_mismatch requested={explicit_account_id} actual={runtime_account_id}"
                )
            now = datetime.now()
            self._owner_generation += 1
            state = GatewaySessionState(
                account_id=runtime_account_id,
                session_id=int(startup.get("session_id") or context.resolved_session_id),
                worker=worker,
                context=context,
                warmed_at=now,
                last_used_at=now,
                wake_report=dict(startup.get("wake_report") or getattr(context, "wake_report", {}) or {}),
                warm_trace=list(startup.get("warm_trace") or []),
                ready=bool(startup.get("ready", False)),
                last_error="" if bool(startup.get("ready", False)) else str(startup.get("reason") or "session_not_ready").strip(),
                last_check_at=str(startup.get("last_check_at") or ""),
                status_trace=list(startup.get("status_trace") or startup.get("warm_trace") or []),
                owner_generation=int(self._owner_generation),
                owner_started_reason=rebuild_reason,
            )
            self._active_state = state
            return state

    def status(self, *, account_id: str = "") -> dict[str, Any]:
        requested_account_id = self._requested_account_id(account_id)
        with self._lock:
            state = self._active_state
            if state is None:
                return self._session_not_ready_payload(requested_account_id, reason="session_not_ready")
            if requested_account_id and requested_account_id != state.account_id:
                return self._owner_mismatch_payload(requested_account_id, state)
            if not state.worker.is_alive():
                self._active_state = None
                return self._session_not_ready_payload(requested_account_id or state.account_id, reason="session_closed")
            if not state.ready:
                self._refresh_state_health(state)
            state.last_used_at = datetime.now()
            return state.summary()

    def close(self, *, account_id: str = "") -> dict[str, Any]:
        requested_account_id = self._requested_account_id(account_id)
        with self._lock:
            state = self._active_state
            if state is None:
                return {
                    "ok": True,
                    "account_id": requested_account_id,
                    "closed": False,
                    "message": "session not found",
                    "session_resolution": {},
                    **_session_contract_meta(),
                }
            if requested_account_id and requested_account_id != state.account_id:
                return {
                    "ok": True,
                    "account_id": requested_account_id,
                    "closed": False,
                    "message": "session owner mismatch",
                    "owner_account_id": state.account_id,
                    "owner_generation": int(state.owner_generation),
                    "session_resolution": _context_session_resolution(state.context),
                    **_session_contract_meta(),
                }
            self._close_active_state()
            return {
                "ok": True,
                "account_id": state.account_id,
                "closed": True,
                "message": "session closed",
                "owner_generation": int(state.owner_generation),
                "session_resolution": _context_session_resolution(state.context),
                **_session_contract_meta(),
            }

    def require(self, *, account_id: str = "", require_ready: bool = False) -> GatewaySessionState:
        requested_account_id = self._requested_account_id(account_id)
        with self._lock:
            state = self._active_state
            if state is None:
                raise RuntimeError("session_not_ready")
            if requested_account_id and requested_account_id != state.account_id:
                raise RuntimeError("session_owner_mismatch")
            if not state.worker.is_alive():
                self._active_state = None
                raise RuntimeError("session_closed")
            if bool(require_ready):
                self._refresh_state_health(state)
                if not state.ready:
                    raise RuntimeError(str(state.last_error or "session_not_ready"))
            state.last_used_at = datetime.now()
            return state

    def execute(
        self,
        *,
        account_id: str = "",
        runner: Callable[[TradeOpsRuntimeContext], Any],
        require_ready: bool = False,
    ) -> tuple[GatewaySessionState, Any]:
        requested_account_id = self._requested_account_id(account_id)
        with self._lock:
            state = self._active_state
            if state is None:
                raise RuntimeError("session_not_ready")
            if requested_account_id and requested_account_id != state.account_id:
                raise RuntimeError("session_owner_mismatch")
            if not state.worker.is_alive():
                self._active_state = None
                raise RuntimeError("session_closed")
            if bool(require_ready):
                self._refresh_state_health(state)
                if not state.ready:
                    raise RuntimeError(str(state.last_error or "session_not_ready"))
            state.last_used_at = datetime.now()
            result = state.worker.submit(runner)
            return state, result
