"""MiniQMT launch and login module."""

from .contracts import MiniQmtLoginConfig, MiniQmtLoginResult, MiniQmtLoginRunProfile, MiniQmtLoginStatus, MiniQmtLoginTiming
from .credential_store import build_credential_target, read_credential, write_credential
from .service import ensure_miniqmt_logged_in, resolve_login_config

__all__ = [
    "MiniQmtLoginConfig",
    "MiniQmtLoginResult",
    "MiniQmtLoginRunProfile",
    "MiniQmtLoginStatus",
    "MiniQmtLoginTiming",
    "build_credential_target",
    "ensure_miniqmt_logged_in",
    "read_credential",
    "resolve_login_config",
    "write_credential",
]
