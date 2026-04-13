from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Mapping


def yaml_load(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("PyYAML is required to load gateway config") from exc
    payload = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    return payload if isinstance(payload, dict) else {}


def load_yaml_payload(path: str | Path | None, *, required: bool) -> dict[str, Any]:
    if path in (None, ""):
        return {}
    resolved = Path(path)
    if resolved.exists():
        return yaml_load(resolved)
    if required:
        raise FileNotFoundError(f"gateway config not found: {resolved}")
    return {}


def section(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return dict(value) if isinstance(value, dict) else {}


def pick(payload: Mapping[str, Any], key: str, default: Any = None) -> Any:
    if key in payload:
        return payload.get(key)
    return default


def env_text(env: Mapping[str, str], key: str, *aliases: str) -> str:
    for candidate in (key,) + tuple(aliases):
        value = str(env.get(candidate, "") or "").strip()
        if value:
            return value
    return ""


def coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    token = str(value).strip().lower()
    if token in {"1", "true", "yes", "y", "on"}:
        return True
    if token in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)


def coerce_int(value: Any, default: int) -> int:
    if value in (None, ""):
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def coerce_float(value: Any, default: float) -> float:
    if value in (None, ""):
        return float(default)
    try:
        return float(value)
    except Exception:
        return float(default)


def coerce_date(value: Any, default: date) -> date:
    if value in (None, ""):
        return default
    try:
        return date.fromisoformat(str(value).strip())
    except Exception:
        return default


def coerce_str_tuple(value: Any, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    if value is None:
        return tuple(default)
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip()) or tuple(default)
    token = str(value).strip()
    if not token:
        return tuple(default)
    return tuple(part.strip() for part in token.split(",") if part.strip()) or tuple(default)


def coerce_int_tuple(value: Any, default: tuple[int, ...]) -> tuple[int, ...]:
    tokens = coerce_str_tuple(value, ())
    if not tokens:
        return tuple(default)
    out: list[int] = []
    for token in tokens:
        try:
            out.append(int(token))
        except Exception:
            continue
    return tuple(out) if out else tuple(default)


def normalize_http_path(value: str, default: str) -> str:
    token = str(value or "").strip() or default
    return token if token.startswith("/") else f"/{token}"
