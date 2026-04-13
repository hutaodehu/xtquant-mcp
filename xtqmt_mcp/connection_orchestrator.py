"""Connection orchestration for broker xttrader shadow read path."""

from __future__ import annotations

import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .types import ConnectionStageResult, ConnectionTraceReport
from .xtquant_env import ensure_xtquant_on_path
from .xttrader_precheck import run_layered_user_data_precheck


def _now() -> datetime:
    return datetime.now()


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
class ConnectionOrchestratorConfig:
    qmt_exe: str
    qmt_userdata: str
    account_id: str
    session_plan: tuple[int, ...] = (100, 101, 111)
    connect_retries: int = 3
    connect_retry_interval_seconds: float = 3.0
    wake_wait_seconds: int = 30
    port_host: str = "127.0.0.1"
    port_num: int = 58610
    require_connect_stage: bool = True
    require_subscribe_stage: bool = True
    require_snapshot_stage: bool = True
    snapshot_requires_position: bool = False


class _TraderCallback:
    def __init__(self) -> None:
        self.events: list[str] = []

    def on_connected(self) -> None:
        self.events.append("on_connected")

    def on_disconnected(self) -> None:
        self.events.append("on_disconnected")

    def on_account_status(self, status) -> None:
        account_id = getattr(status, "account_id", "")
        status_value = getattr(status, "status", "")
        self.events.append(f"on_account_status:{account_id}:{status_value}")


def run_connection_orchestrator(cfg: ConnectionOrchestratorConfig) -> ConnectionTraceReport:
    started_at = _now()
    stages: list[ConnectionStageResult] = []
    precheck: dict[str, object] = {
        "qmt_exe_exists": bool(Path(cfg.qmt_exe).exists()) if cfg.qmt_exe else False,
        "qmt_userdata_exists": bool(Path(cfg.qmt_userdata).exists()) if cfg.qmt_userdata else False,
        "process_exists": False,
        "xtdata_port_ready": False,
        "process_check_shell": "pwsh",
    }
    layered_precheck = run_layered_user_data_precheck(
        str(cfg.qmt_userdata or ""),
        require_up_queue_file=True,
    )
    read_only_layer = dict(layered_precheck.get("read_only") or {})
    write_permission_layer = dict(layered_precheck.get("write_permission") or {})
    userdata_precheck_read_only = dict(read_only_layer.get("report") or {})
    userdata_precheck_write_permission = dict(write_permission_layer.get("report") or {})
    read_only_precheck_ok = bool(read_only_layer.get("ok", False))
    write_permission_precheck_ok = bool(write_permission_layer.get("ok", False))
    precheck["userdata_precheck"] = userdata_precheck_read_only
    precheck["userdata_precheck_read_only"] = userdata_precheck_read_only
    precheck["userdata_precheck_write_permission"] = userdata_precheck_write_permission
    precheck["readiness_layers"] = {
        "read_only": {
            "ok": read_only_precheck_ok,
            "blocking": True,
            "reason": "" if read_only_precheck_ok else "qmt_read_precheck_failed",
        },
        "write_permission": {
            "ok": write_permission_precheck_ok,
            "blocking": False,
            "reason": "" if write_permission_precheck_ok else "write_permission_precheck_failed",
        },
    }
    selected_session: Optional[int] = None
    callback_events: list[str] = []
    failure_classification = ""

    stages.append(
        ConnectionStageResult(
            name="precheck_userdata_read_only",
            ok=bool(read_only_precheck_ok),
            code="ok" if bool(read_only_precheck_ok) else "qmt_read_precheck_failed",
            message=(
                "read-only userdata precheck passed"
                if bool(read_only_precheck_ok)
                else f"read-only userdata precheck failed: {userdata_precheck_read_only}"
            ),
        )
    )
    stages.append(
        ConnectionStageResult(
            name="precheck_userdata_write_permission",
            ok=bool(write_permission_precheck_ok),
            code="ok" if bool(write_permission_precheck_ok) else "write_permission_precheck_failed",
            message=(
                "write-permission userdata precheck passed"
                if bool(write_permission_precheck_ok)
                else f"write-permission userdata precheck failed: {userdata_precheck_write_permission}"
            ),
        )
    )

    if not bool(read_only_precheck_ok):
        finished_at = _now()
        precheck["read_only_failure_classification"] = "qmt_read_precheck_failed"
        precheck["write_failure_classification"] = "" if write_permission_precheck_ok else "write_permission_precheck_failed"
        return ConnectionTraceReport(
            started_at=started_at,
            finished_at=finished_at,
            overall_ok=False,
            stages=stages,
            selected_session_id=None,
            precheck=precheck,
            callback_events=callback_events,
            failure_classification="qmt_read_precheck_failed",
        )

    t0 = time.perf_counter()
    process_exists = False
    try:
        out = subprocess.check_output(
            [
                "pwsh",
                "-Command",
                "@(Get-Process -Name XtMiniQmt -ErrorAction SilentlyContinue).Count",
            ],
            text=True,
            timeout=8,
        )
        process_exists = int((out or "0").strip() or "0") > 0
    except Exception:
        process_exists = False
    precheck["process_exists"] = process_exists
    stages.append(
        ConnectionStageResult(
            name="precheck_process",
            ok=process_exists,
            code="ok" if process_exists else "process_missing",
            message="XtMiniQmt running" if process_exists else "XtMiniQmt process not found",
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
    )

    if (not process_exists) and cfg.qmt_exe and Path(cfg.qmt_exe).exists():
        t_start = time.perf_counter()
        try:
            subprocess.Popen([cfg.qmt_exe])
            ok = True
            msg = "XtMiniQmt started by orchestrator"
            code = "started"
        except Exception as exc:
            ok = False
            msg = f"failed to start XtMiniQmt: {exc}"
            code = "start_failed"
        stages.append(
            ConnectionStageResult(
                name="wake_qmt_process",
                ok=ok,
                code=code,
                message=msg,
                latency_ms=int((time.perf_counter() - t_start) * 1000),
            )
        )

    t_wait = time.perf_counter()
    port_ready = False
    deadline = time.time() + max(1, int(cfg.wake_wait_seconds))
    while time.time() < deadline:
        port_ready = _tcp_port_ready(cfg.port_host, int(cfg.port_num), timeout_ms=300)
        if port_ready:
            break
        time.sleep(1.0)
    precheck["xtdata_port_ready"] = port_ready
    stages.append(
        ConnectionStageResult(
            name="wait_xtdata_ready",
            ok=port_ready,
            code="ok" if port_ready else "xtdata_port_not_ready",
            message=(
                f"xtdata ready on {cfg.port_host}:{cfg.port_num}"
                if port_ready
                else f"xtdata not ready on {cfg.port_host}:{cfg.port_num}"
            ),
            latency_ms=int((time.perf_counter() - t_wait) * 1000),
        )
    )

    ensure_xtquant_on_path()
    from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback  # type: ignore
    from xtquant.xttype import StockAccount  # type: ignore

    class CallbackImpl(XtQuantTraderCallback, _TraderCallback):
        def __init__(self) -> None:
            XtQuantTraderCallback.__init__(self)
            _TraderCallback.__init__(self)

    for session_id in cfg.session_plan:
        cb = CallbackImpl()
        trader = XtQuantTrader(str(Path(cfg.qmt_userdata)), int(session_id), cb)
        trader.start()
        connect_code = -999
        t_conn = time.perf_counter()
        try:
            retries = max(1, int(cfg.connect_retries))
            retry_sleep = max(3.0, float(cfg.connect_retry_interval_seconds))
            for attempt in range(1, retries + 1):
                connect_code = int(trader.connect())
                if connect_code == 0:
                    break
                if attempt < retries:
                    time.sleep(retry_sleep)
            connect_ok = connect_code == 0
            stages.append(
                ConnectionStageResult(
                    name=f"connect_session_{session_id}",
                    ok=connect_ok,
                    code=str(connect_code),
                    message="connect success" if connect_ok else f"connect failed: {connect_code}",
                    retry_count=retries,
                    latency_ms=int((time.perf_counter() - t_conn) * 1000),
                    details={"session_id": str(session_id)},
                )
            )
            if not connect_ok:
                callback_events.extend(cb.events)
                continue

            selected_session = int(session_id)
            account = StockAccount(str(cfg.account_id))
            t_sub = time.perf_counter()
            sub_code = int(trader.subscribe(account))
            sub_ok = sub_code == 0
            stages.append(
                ConnectionStageResult(
                    name="subscribe_account",
                    ok=sub_ok,
                    code=str(sub_code),
                    message="subscribe success" if sub_ok else f"subscribe failed: {sub_code}",
                    latency_ms=int((time.perf_counter() - t_sub) * 1000),
                    details={"account_id": str(cfg.account_id), "session_id": str(session_id)},
                )
            )
            if (not sub_ok) and cfg.require_subscribe_stage:
                callback_events.extend(cb.events)
                continue

            t_snap = time.perf_counter()
            snapshot_ok = True
            snapshot_msg = "snapshot ok"
            snapshot_details: dict[str, str] = {}
            try:
                pos = trader.query_stock_positions(account) or []
                ast = trader.query_stock_asset(account)
                pos_rows = int(len(pos))
                ast_rows = int(1 if ast is not None else 0)
                # Empty positions are valid for cash-only/flat accounts. The strict mode can
                # still enforce a non-empty position snapshot when explicitly required.
                snapshot_ok = bool((ast_rows > 0) and ((pos_rows > 0) or (not cfg.snapshot_requires_position)))
                snapshot_msg = f"positions={pos_rows}, asset_rows={ast_rows}"
                snapshot_details = {
                    "positions_rows": str(pos_rows),
                    "asset_rows": str(ast_rows),
                    "snapshot_requires_position": str(bool(cfg.snapshot_requires_position)),
                }
            except Exception as exc:
                snapshot_ok = False
                snapshot_msg = f"snapshot failed: {exc}"
            stages.append(
                ConnectionStageResult(
                    name="query_snapshot_smoke",
                    ok=snapshot_ok,
                    code="ok" if snapshot_ok else "snapshot_empty_or_failed",
                    message=snapshot_msg,
                    latency_ms=int((time.perf_counter() - t_snap) * 1000),
                    details=snapshot_details,
                )
            )
            callback_events.extend(cb.events)
            if snapshot_ok or (not cfg.require_snapshot_stage):
                try:
                    trader.unsubscribe(account)
                except Exception:
                    pass
                try:
                    trader.stop()
                except Exception:
                    pass
                break
        finally:
            try:
                trader.stop()
            except Exception:
                pass

    connect_stage_ok = any(st.name.startswith("connect_session_") and st.ok for st in stages)
    subscribe_stage_ok = any(st.name == "subscribe_account" and st.ok for st in stages)
    snapshot_stage_ok = any(st.name == "query_snapshot_smoke" and st.ok for st in stages)

    if not connect_stage_ok:
        failure_classification = "connect_failed"
    elif cfg.require_subscribe_stage and not subscribe_stage_ok:
        failure_classification = "subscribe_failed"
    elif cfg.require_snapshot_stage and not snapshot_stage_ok:
        failure_classification = "snapshot_not_ready"
    else:
        failure_classification = ""
    write_failure_classification = "" if write_permission_precheck_ok else "write_permission_precheck_failed"
    precheck["read_only_failure_classification"] = str(failure_classification or "")
    precheck["write_failure_classification"] = write_failure_classification
    readiness_layers = dict(precheck.get("readiness_layers") or {})
    read_only_entry = dict(readiness_layers.get("read_only") or {})
    write_permission_entry = dict(readiness_layers.get("write_permission") or {})
    if read_only_entry:
        read_only_entry["reason"] = str(failure_classification or "")
        read_only_entry["ok"] = bool(not failure_classification)
        readiness_layers["read_only"] = read_only_entry
    if write_permission_entry:
        write_permission_entry["reason"] = str(write_failure_classification or "")
        write_permission_entry["ok"] = bool(write_permission_precheck_ok)
        readiness_layers["write_permission"] = write_permission_entry
    precheck["readiness_layers"] = readiness_layers

    overall_ok = bool(
        (connect_stage_ok or (not cfg.require_connect_stage))
        and (subscribe_stage_ok or (not cfg.require_subscribe_stage))
        and (snapshot_stage_ok or (not cfg.require_snapshot_stage))
    )

    return ConnectionTraceReport(
        started_at=started_at,
        finished_at=_now(),
        stages=stages,
        overall_ok=overall_ok,
        selected_session_id=selected_session,
        selected_account_id=str(cfg.account_id or ""),
        precheck=precheck,
        callback_events=callback_events,
        failure_classification=failure_classification,
    )
