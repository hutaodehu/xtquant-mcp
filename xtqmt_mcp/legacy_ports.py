from __future__ import annotations

from typing import Any


LEGACY_XTDATA_ARCHIVE_POLICY = "no_archived_xtdata_ports"


def coerce_port(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def is_legacy_archived_port(value: Any) -> bool:
    del value
    return False


def legacy_port_fields(value: Any = None) -> dict[str, Any]:
    del value
    return {
        "legacy_archived_ports": [],
        "legacy_archive_policy": LEGACY_XTDATA_ARCHIVE_POLICY,
        "legacy_port_detected": False,
    }


def annotate_legacy_port(payload: dict[str, Any], value: Any) -> dict[str, Any]:
    payload.update(legacy_port_fields(value))
    return payload
