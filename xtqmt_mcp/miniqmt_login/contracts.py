from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


DEFAULT_QMT_EXE = r""
DEFAULT_QMT_USERDATA = r""
DEFAULT_CREDENTIAL_PREFIX = "xtqmt/miniqmt"


class MiniQmtLoginStatus(str, Enum):
    ALREADY_LOGGED_IN = "already_logged_in"
    REMEMBERED_LOGIN_SUCCESS = "remembered_login_success"
    UI_LOGIN_SUCCESS = "ui_login_success"
    CREDENTIAL_MISSING = "credential_missing"
    LOGIN_WINDOW_NOT_FOUND = "login_window_not_found"
    DESKTOP_NOT_INTERACTIVE = "desktop_not_interactive"
    EXTRA_AUTH_DETECTED = "extra_auth_detected"
    BAD_PASSWORD = "bad_password"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class MiniQmtLoginConfig:
    qmt_exe: str = ""
    account_id: str = ""
    credential_target: str = ""
    login_timeout_seconds: int = 45
    qmt_userdata: str = ""
    port_host: str = "127.0.0.1"
    port_num: int = 0
    startup_grace_seconds: int = 8


def _round_optional(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 3)


@dataclass(frozen=True)
class MiniQmtLoginTiming:
    total_seconds: float | None = None
    launch_or_attach_seconds: float | None = None
    startup_grace_wait_seconds: float = 0.0
    first_login_window_seconds: float | None = None
    credential_read_seconds: float | None = None
    submit_seconds: float | None = None
    first_main_window_seconds: float | None = None
    first_port_ready_seconds: float | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "total_seconds": _round_optional(self.total_seconds),
            "launch_or_attach_seconds": _round_optional(self.launch_or_attach_seconds),
            "startup_grace_wait_seconds": _round_optional(self.startup_grace_wait_seconds),
            "first_login_window_seconds": _round_optional(self.first_login_window_seconds),
            "credential_read_seconds": _round_optional(self.credential_read_seconds),
            "submit_seconds": _round_optional(self.submit_seconds),
            "first_main_window_seconds": _round_optional(self.first_main_window_seconds),
            "first_port_ready_seconds": _round_optional(self.first_port_ready_seconds),
        }


@dataclass(frozen=True)
class MiniQmtLoginRunProfile:
    observe_iterations: int = 0
    login_path: str = ""
    submit_attempted: bool = False
    saw_login_window: bool = False
    launch_started: bool = False
    already_running_before_launch: bool = False
    interactive_desktop: bool = True

    def as_payload(self) -> dict[str, Any]:
        return {
            "observe_iterations": int(self.observe_iterations),
            "login_path": self.login_path,
            "submit_attempted": bool(self.submit_attempted),
            "saw_login_window": bool(self.saw_login_window),
            "launch_started": bool(self.launch_started),
            "already_running_before_launch": bool(self.already_running_before_launch),
            "interactive_desktop": bool(self.interactive_desktop),
        }


@dataclass(frozen=True)
class MiniQmtLoginResult:
    ok: bool
    status: MiniQmtLoginStatus
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    process_id: int | None = None
    port_ready: bool = False

    def as_payload(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "status": self.status.value,
            "message": self.message,
            "evidence": dict(self.evidence),
            "process_id": self.process_id,
            "port_ready": bool(self.port_ready),
        }


@dataclass(frozen=True)
class CredentialReadResult:
    ok: bool
    target: str
    username: str = ""
    password: str = ""
    error: str = "credential_missing"

    def public_payload(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "target": self.target,
            "username": self.username,
            "error": self.error,
        }


@dataclass(frozen=True)
class CredentialWriteResult:
    ok: bool
    target: str
    username: str
    error: str = ""

    def public_payload(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "target": self.target,
            "username": self.username,
            "error": self.error,
        }
