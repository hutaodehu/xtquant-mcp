"""Shared xttrader connection precheck and callback helpers."""

from __future__ import annotations

import os
from pathlib import Path
import time
from typing import Any


class _NoopXtTraderCallback:
    """Best-effort callback sink for xttrader lifecycle/events."""

    def __init__(self, event_sink: list[str] | None = None) -> None:
        self._event_sink = event_sink if event_sink is not None else []

    def _record(self, name: str) -> None:
        try:
            self._event_sink.append(str(name))
        except Exception:
            pass

    def __getattr__(self, name: str):
        if str(name).startswith("on_"):
            def _handler(*_args: Any, **_kwargs: Any) -> None:
                self._record(str(name))

            return _handler
        raise AttributeError(name)


def _build_callback(event_sink: list[str] | None = None) -> Any:
    try:
        from xtquant.xttrader import XtQuantTraderCallback  # type: ignore

        class _Callback(XtQuantTraderCallback):  # type: ignore[misc,valid-type]
            def __init__(self, sink: list[str] | None = None) -> None:
                super().__init__()
                self._sink = sink if sink is not None else []

            def _record(self, name: str) -> None:
                try:
                    self._sink.append(str(name))
                except Exception:
                    pass

            def __getattr__(self, name: str):
                if str(name).startswith("on_"):
                    def _handler(*_args: Any, **_kwargs: Any) -> None:
                        self._record(str(name))

                    return _handler
                raise AttributeError(name)

        return _Callback(event_sink)
    except Exception:
        return _NoopXtTraderCallback(event_sink)


def register_trader_callback(
    trader: Any,
    *,
    enable: bool,
    event_sink: list[str] | None = None,
) -> tuple[bool, str]:
    """Register a noop callback when available."""

    if not bool(enable):
        return False, "disabled"
    register_fn = getattr(trader, "register_callback", None)
    if not callable(register_fn):
        return False, "register_callback_unavailable"
    callback = _build_callback(event_sink)
    try:
        register_fn(callback)
        return True, "ok"
    except Exception as exc:
        return False, f"register_callback_failed:{exc}"


def run_user_data_precheck(
    user_data_path: str,
    *,
    require_up_queue_file: bool = True,
) -> dict[str, Any]:
    """Run filesystem-level readiness checks before xttrader connect."""

    root = Path(str(user_data_path or "").strip())
    issues: list[dict[str, str]] = []

    def _issue(code: str, message: str) -> None:
        issues.append({"code": str(code), "message": str(message)})

    result: dict[str, Any] = {
        "user_data_path": str(root),
        "path_exists": bool(root.exists()),
        "is_dir": bool(root.is_dir()) if root.exists() else False,
        "path_writable": False,
        "require_up_queue_file": bool(require_up_queue_file),
        "up_queue_xtquant_exists": False,
        "issues": issues,
        "ok": False,
    }

    if not str(root):
        _issue("path_invalid", "user_data_path is empty")
        return result
    if not root.exists():
        _issue("path_invalid", "user_data_path not exists")
        return result
    if not root.is_dir():
        _issue("path_invalid", "user_data_path is not directory")
        return result

    probe_path = root / f".ptv1_precheck_write_{os.getpid()}_{int(time.time() * 1000)}.tmp"
    try:
        probe_path.write_text("ok\n", encoding="utf-8")
        result["path_writable"] = True
    except Exception as exc:
        _issue("path_not_writable", str(exc))
    finally:
        try:
            if probe_path.exists():
                probe_path.unlink()
        except Exception:
            pass

    up_queue = root / "up_queue_xtquant"
    up_queue_exists = bool(up_queue.exists())
    result["up_queue_xtquant_exists"] = up_queue_exists
    if bool(require_up_queue_file) and (not up_queue_exists):
        _issue("up_queue_missing", "up_queue_xtquant not found under user_data_path")

    result["ok"] = len(issues) == 0
    return result


def run_layered_user_data_precheck(
    user_data_path: str,
    *,
    require_up_queue_file: bool = True,
) -> dict[str, Any]:
    """Return read-only and write-permission precheck layers in one payload."""

    read_only = run_user_data_precheck(
        user_data_path,
        require_up_queue_file=False,
    )
    write_permission = run_user_data_precheck(
        user_data_path,
        require_up_queue_file=bool(require_up_queue_file),
    )
    read_only_ok = bool(read_only.get("ok", False))
    write_permission_ok = bool(write_permission.get("ok", False))
    return {
        "read_only": {
            "ok": read_only_ok,
            "blocking": True,
            "reason": "" if read_only_ok else "qmt_read_precheck_failed",
            "report": read_only,
        },
        "write_permission": {
            "ok": write_permission_ok,
            "blocking": False,
            "reason": "" if write_permission_ok else "write_permission_precheck_failed",
            "report": write_permission,
            "require_up_queue_file": bool(require_up_queue_file),
        },
        "overall_read_only_ok": read_only_ok,
        "overall_write_permission_ok": write_permission_ok,
    }


def enforce_session_cooldown(
    session_last_attempt_ts: dict[int, float],
    *,
    session_id: int,
    cooldown_seconds: float,
) -> float:
    """Ensure same-session attempts are spaced by configured cooldown."""

    sid = int(session_id)
    cooldown = max(0.0, float(cooldown_seconds))
    now = time.time()
    slept = 0.0
    prev = session_last_attempt_ts.get(sid)
    if prev is not None and cooldown > 0.0:
        remain = float(cooldown - (now - float(prev)))
        if remain > 0.0:
            time.sleep(remain)
            slept = remain
    session_last_attempt_ts[sid] = time.time()
    return float(max(0.0, slept))
