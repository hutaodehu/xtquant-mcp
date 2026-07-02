from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _normalize_session_id(raw: int) -> int:
    return int(max(100, int(raw)))


def _normalized_plan_items(values: Any) -> tuple[int, ...]:
    normalized: list[int] = []
    seen: set[int] = set()
    for raw in tuple(values or ()):
        try:
            sid = _normalize_session_id(int(raw))
        except Exception:
            continue
        if sid in seen:
            continue
        seen.add(sid)
        normalized.append(sid)
    return tuple(normalized)


def build_session_plan_version(values: Any) -> str:
    plan = _normalized_plan_items(values)
    if not plan:
        return "v1:empty"
    return "v1:" + ",".join(str(item) for item in plan)


def prioritize_session_candidates(primary_session_id: int, session_candidates: tuple[int, ...]) -> tuple[int, ...]:
    prioritized: list[int] = []
    seen: set[int] = set()

    def _append(raw: int) -> None:
        sid = _normalize_session_id(raw)
        if sid in seen:
            return
        seen.add(sid)
        prioritized.append(sid)

    _append(int(primary_session_id))
    for candidate in tuple(session_candidates or ()):
        _append(int(candidate))
    return tuple(prioritized)


def build_effective_session_plan(
    primary_session_id: int,
    session_candidates: tuple[int, ...],
    enable_derived_session_fallback: bool,
    max_session_attempts: int = 0,
) -> tuple[int, ...]:
    prioritized = prioritize_session_candidates(primary_session_id, session_candidates)
    plan: list[int] = list(prioritized)
    seen: set[int] = set(plan)

    if bool(enable_derived_session_fallback):
        for sid in prioritized:
            derived = _normalize_session_id(int(sid) + 1000)
            if derived in seen:
                continue
            seen.add(derived)
            plan.append(derived)

    limit = int(max_session_attempts)
    if limit > 0:
        return tuple(plan[:limit])
    return tuple(plan)


@dataclass(frozen=True)
class SessionResolution:
    configured_session_id: int
    resolved_base_session_id: int
    resolved_session_id: int
    configured_session_candidates: tuple[int, ...]
    effective_session_plan: tuple[int, ...]
    derived_session_fallback_enabled: bool
    max_session_attempts: int
    explicit_session_resolution_applied: bool
    session_plan_version: str = ""

    def as_payload(self) -> dict[str, Any]:
        configured_candidates = _normalized_plan_items(self.configured_session_candidates)
        effective_plan = _normalized_plan_items(self.effective_session_plan)
        session_plan_version = str(self.session_plan_version or "").strip() or build_session_plan_version(effective_plan)
        return {
            "configured_session_id": int(self.configured_session_id),
            "resolved_base_session_id": int(self.resolved_base_session_id),
            "resolved_session_id": int(self.resolved_session_id),
            "configured_session_candidates": [int(item) for item in configured_candidates],
            "effective_session_plan": [int(item) for item in effective_plan],
            "session_plan_version": session_plan_version,
            "derived_session_fallback_enabled": bool(self.derived_session_fallback_enabled),
            "max_session_attempts": int(self.max_session_attempts),
            "explicit_session_resolution_applied": bool(self.explicit_session_resolution_applied),
        }


def session_resolution_payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {}

    def _with_plan_version(payload: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(payload)
        enriched["session_plan_version"] = str(enriched.get("session_plan_version") or "").strip() or build_session_plan_version(
            enriched.get("effective_session_plan")
        )
        return enriched

    as_payload = getattr(value, "as_payload", None)
    if callable(as_payload):
        payload = as_payload()
        if isinstance(payload, dict):
            return _with_plan_version(payload)
        return {}
    if isinstance(value, dict):
        return _with_plan_version(value)
    return {}


def _optional_int(raw: Any) -> int:
    try:
        value = int(raw or 0)
    except Exception:
        return 0
    return value if value > 0 else 0


def build_runtime_session_resolution(
    value: Any,
    preferred_session_id: Any,
    *,
    reason: str = "",
    event_source: str = "runtime_realign",
    owner_session_id: Any = None,
    observed_probe_session_id: Any = None,
    attempted_broker_session_id: Any = None,
) -> dict[str, Any]:
    payload = session_resolution_payload(value)
    preferred = _optional_int(preferred_session_id)
    if not payload or preferred <= 0:
        return payload

    previous_resolved_session_id = _optional_int(payload.get("resolved_session_id"))
    seed_resolved_session_id = _optional_int(
        payload.get("seed_resolved_session_id")
        or payload.get("resolved_base_session_id")
        or previous_resolved_session_id
    )
    configured_candidates = list(_normalized_plan_items(payload.get("configured_session_candidates")))
    effective_plan = list(_normalized_plan_items(payload.get("effective_session_plan")))

    if preferred in configured_candidates:
        configured_candidates = [preferred] + [sid for sid in configured_candidates if sid != preferred]
    if preferred in effective_plan:
        effective_plan = [preferred] + [sid for sid in effective_plan if sid != preferred]
    elif effective_plan:
        effective_plan = [preferred] + effective_plan
    else:
        effective_plan = [preferred]

    observed_probe_token = str(observed_probe_session_id or "").strip()
    owner_session = _optional_int(owner_session_id)
    attempted_broker_session = _optional_int(attempted_broker_session_id)
    runtime_event = {
        "event_type": "runtime_session_resolution_realign",
        "event_source": str(event_source or "runtime_realign"),
        "reason": str(reason or "runtime_realign"),
        "previous_resolved_session_id": previous_resolved_session_id,
        "seed_resolved_session_id": seed_resolved_session_id,
        "resolved_session_id": preferred,
        "resolved_base_session_id": _optional_int(payload.get("resolved_base_session_id")),
        "session_plan_version": build_session_plan_version(effective_plan),
        "configured_session_candidates": [int(item) for item in configured_candidates],
        "effective_session_plan": [int(item) for item in effective_plan],
        "owner_session_id": owner_session,
        "observed_probe_session_id": observed_probe_token,
        "attempted_broker_session_id": attempted_broker_session,
    }

    enriched = dict(payload)
    enriched["resolved_session_id"] = preferred
    if configured_candidates:
        enriched["configured_session_candidates"] = [int(item) for item in configured_candidates]
    enriched["effective_session_plan"] = [int(item) for item in effective_plan]
    enriched["session_plan_version"] = runtime_event["session_plan_version"]
    enriched["seed_resolved_session_id"] = seed_resolved_session_id
    enriched["runtime_session_resolution_applied"] = True
    enriched["runtime_resolution_event"] = runtime_event
    if owner_session > 0:
        enriched["owner_session_id"] = owner_session
    if observed_probe_token:
        enriched["observed_probe_session_id"] = observed_probe_token
    if attempted_broker_session > 0:
        enriched["attempted_broker_session_id"] = attempted_broker_session
    return enriched
