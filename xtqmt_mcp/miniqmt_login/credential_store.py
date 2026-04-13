from __future__ import annotations

import importlib
from typing import Any

from .contracts import CredentialReadResult, CredentialWriteResult, DEFAULT_CREDENTIAL_PREFIX


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def build_credential_target(account_id: str = "", target: str = "") -> str:
    explicit_target = _safe_str(target)
    if explicit_target:
        return explicit_target
    account = _safe_str(account_id) or "default"
    return f"{DEFAULT_CREDENTIAL_PREFIX}/{account}"


def read_credential(target: str) -> CredentialReadResult:
    normalized_target = _safe_str(target)
    try:
        win32cred = importlib.import_module("win32cred")
    except Exception as exc:
        return CredentialReadResult(
            ok=False,
            target=normalized_target,
            error=f"win32cred_unavailable:{exc}",
        )
    try:
        credential = win32cred.CredRead(normalized_target, win32cred.CRED_TYPE_GENERIC)
    except Exception:
        return CredentialReadResult(ok=False, target=normalized_target)
    secret = credential.get("CredentialBlob", b"")
    if isinstance(secret, bytes):
        password = secret.decode("utf-16-le", errors="ignore") if b"\x00" in secret else secret.decode(errors="ignore")
    else:
        password = str(secret or "")
    return CredentialReadResult(
        ok=True,
        target=normalized_target,
        username=_safe_str(credential.get("UserName", "")),
        password=password,
        error="",
    )


def write_credential(*, target: str, username: str, password: str) -> CredentialWriteResult:
    normalized_target = _safe_str(target)
    normalized_username = _safe_str(username)
    try:
        win32cred = importlib.import_module("win32cred")
    except Exception as exc:
        return CredentialWriteResult(
            ok=False,
            target=normalized_target,
            username=normalized_username,
            error=f"win32cred_unavailable:{exc}",
        )
    try:
        win32cred.CredWrite(
            {
                "Type": win32cred.CRED_TYPE_GENERIC,
                "TargetName": normalized_target,
                "UserName": normalized_username,
                "CredentialBlob": str(password or ""),
                "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
            },
            0,
        )
    except Exception as exc:
        return CredentialWriteResult(
            ok=False,
            target=normalized_target,
            username=normalized_username,
            error=str(exc),
        )
    return CredentialWriteResult(ok=True, target=normalized_target, username=normalized_username)

