from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import socket
import subprocess
import time
from typing import Callable

from xtqmt_mcp.legacy_ports import (
    coerce_port,
    legacy_port_fields,
)

def port_ready(host: str = "127.0.0.1", port: int = 0, timeout_ms: int = 300) -> bool:
    resolved_port = coerce_port(port, 0)
    if resolved_port <= 0:
        return False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(max(0.1, float(timeout_ms) / 1000.0))
    try:
        sock.connect((host, resolved_port))
        return True
    except Exception:
        return False
    finally:
        try:
            sock.close()
        except Exception:
            pass


def ensure_miniqmt_awake(
    *,
    qmt_exe: str,
    wait_seconds: int,
    qmt_userdata: str = "",
    account_id: str = "",
    host: str = "127.0.0.1",
    port: int = 0,
) -> dict[str, object]:
    resolved_qmt_exe = str(qmt_exe or "").strip()
    resolved_port = coerce_port(port, 0)
    report = {
        "status": "",
        "ok": False,
        "qmt_exe": resolved_qmt_exe,
        "qmt_exe_exists": bool(Path(resolved_qmt_exe).exists()) if resolved_qmt_exe else False,
        "qmt_userdata": str(qmt_userdata or "").strip(),
        "account_id": str(account_id or "").strip(),
        "port_host": str(host or "127.0.0.1"),
        "port": resolved_port,
        "xtdata_port_ready_before": port_ready(host=host, port=resolved_port),
        "process_exists_before": False,
        "process_started": False,
        "process_id": None,
        "xtdata_port_ready_after": False,
        **legacy_port_fields(resolved_port),
    }
    if resolved_port <= 0:
        report["status"] = "xtdata_port_unconfigured"
        report["error"] = "xtdata_port_unconfigured"
    elif report["xtdata_port_ready_before"]:
        report["xtdata_port_ready_after"] = True
        report["status"] = "already_ready"
        report["ok"] = True
        return report

    try:
        proc = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq XtMiniQmt.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=10,
            check=False,
        )
    except Exception:
        proc = None
    if proc is not None:
        for row in csv.reader([line for line in str(proc.stdout or "").splitlines() if line.strip()]):
            if not row:
                continue
            if str(row[0] or "").strip().lower() != "xtminiqmt.exe":
                continue
            report["process_exists_before"] = True
            try:
                report["process_id"] = int(str(row[1] or "").replace(",", "").strip())
            except Exception:
                report["process_id"] = None
            break

    if not report["process_exists_before"]:
        if not report["qmt_exe_exists"]:
            report["status"] = "qmt_exe_missing_or_not_exists"
            report["error"] = "qmt_exe_missing_or_not_exists"
            return report
        try:
            started = subprocess.Popen([resolved_qmt_exe])
        except Exception as exc:
            report["status"] = "process_start_failed"
            report["error"] = str(exc)
            return report
        report["process_started"] = True
        report["process_id"] = int(started.pid)

    deadline = time.time() + max(1, int(wait_seconds))
    while resolved_port > 0 and time.time() < deadline:
        if port_ready(host=host, port=resolved_port):
            report["xtdata_port_ready_after"] = True
            report["status"] = "xtdata_port_ready"
            report["ok"] = True
            return report
        time.sleep(1.0)
    report["xtdata_port_ready_after"] = port_ready(host=host, port=resolved_port)
    if resolved_port <= 0:
        report["status"] = "xtdata_port_unconfigured"
    else:
        report["status"] = "xtdata_port_ready" if report["xtdata_port_ready_after"] else "xtdata_port_not_ready"
    report["ok"] = bool(report["xtdata_port_ready_after"])
    if not report["ok"]:
        report["error"] = str(report["status"])
    return report


@dataclass(frozen=True)
class ResolvedAccount:
    account_id: str
    session_id: int


class AutoAccountResolutionError(RuntimeError):
    """Raised when auto-account discovery exhausts all configured session candidates."""


def resolve_account_for_ops(
    *,
    qmt_userdata: str,
    account_id: str,
    auto_account: bool,
    session_id: int,
    session_candidates: tuple[int, ...],
    discover_stock_account_ids: Callable[..., list[str]],
    register_callback: bool = True,
    connect_cooldown_seconds: float = 3.2,
    enforce_connect_precheck: bool = True,
    require_up_queue_file: bool = True,
) -> ResolvedAccount:
    resolved_account_id = str(account_id or "").strip()
    resolved_session_id = int(session_id)
    if qmt_userdata and (not resolved_account_id) and bool(auto_account):
        candidate_failures: list[str] = []
        normalized_candidates = tuple(int(candidate) for candidate in tuple(session_candidates or ()))
        if not normalized_candidates:
            raise AutoAccountResolutionError("auto_account discovery failed: no session candidates configured")
        for candidate in normalized_candidates:
            try:
                discovered = discover_stock_account_ids(
                    user_data_path=qmt_userdata,
                    session_id=int(candidate),
                    allow_hk_connect=False,
                    register_callback=bool(register_callback),
                    connect_cooldown_seconds=float(connect_cooldown_seconds),
                    enforce_connect_precheck=bool(enforce_connect_precheck),
                    require_up_queue_file=bool(require_up_queue_file),
                )
            except Exception as exc:
                detail = str(exc).strip() or exc.__class__.__name__
                candidate_failures.append(f"session_id={int(candidate)} error={detail}")
                continue
            normalized_ids = [str(item).strip() for item in tuple(discovered or ()) if str(item).strip()]
            if normalized_ids:
                resolved_account_id = normalized_ids[0]
                resolved_session_id = int(candidate)
                break
            candidate_failures.append(f"session_id={int(candidate)} no_accounts_discovered")
        if (not resolved_account_id) and candidate_failures:
            raise AutoAccountResolutionError(
                "auto_account discovery failed across session candidates: " + "; ".join(candidate_failures)
            )
    return ResolvedAccount(account_id=resolved_account_id, session_id=resolved_session_id)
