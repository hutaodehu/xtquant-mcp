from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .config import (
    ACCOUNT_CONTRACT_SINGLE_PRIMARY,
    ACCOUNT_INPUT_MODE_SERVICE_CONTEXT,
    DEFAULT_RESOURCE_URIS,
    TradeGatewayConfig,
)
from xtqmt_mcp.runtime_truth import is_prod_state_scope, resource_truth_metadata, state_scope_label


def trade_resource_definitions(config: TradeGatewayConfig) -> list[dict[str, Any]]:
    descriptions = {
        "trade://capability/current": "Current trade gateway capability contract for agent-first read/write integration.",
        "trade://session/current": "Current single-account primary session summary.",
        "trade://account/current": "Latest cached primary-account snapshot from trade gateway.",
        "trade://orders/today": "Latest cached order list for the primary account from trade gateway.",
        "trade://fills/today": "Latest cached fills list for the primary account from trade gateway.",
        "diag://probe/latest": "Latest connection probe result with layered readiness (read-only vs write-permission).",
        "diag://login/latest": "Latest MiniQMT login result.",
        "diag://order_place/latest": "Latest governed order.place result.",
        "diag://order_cancel/latest": "Latest governed order.cancel result.",
        "diag://order_status/latest": "Latest order.status result.",
    }
    out: list[dict[str, Any]] = []
    for uri in config.enabled_resources or DEFAULT_RESOURCE_URIS:
        out.append({"uri": uri, "name": uri.split("://", 1)[-1], "description": descriptions.get(uri, uri), "mimeType": "application/json"})
    return out


def _resource_cache_path(config: TradeGatewayConfig, uri: str) -> Path:
    safe_name = uri.replace("://", "_").replace("/", "_")
    return Path(config.runtime_paths.state_root) / "trade_resources" / f"{safe_name}.json"


def _blocked_fake_payload(config: TradeGatewayConfig, payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    marker = str(payload.get("source", "") or "").strip().lower()
    if marker != "fake":
        return None
    if not is_prod_state_scope(config.runtime_paths.state_root):
        return None
    blocked = {"available": False, "reason": "fake_payload_blocked", "source": "fake"}
    blocked.update(
        resource_truth_metadata(
            state_root=config.runtime_paths.state_root,
            authority="cached_last_known_state",
        )
    )
    return blocked


def _resource_account_scope(uri: str) -> str:
    if uri == "trade://capability/current":
        return "service_contract"
    if uri == "trade://session/current":
        return "primary_session"
    if uri in {"trade://account/current", "trade://orders/today", "trade://fills/today"}:
        return "primary_account"
    return "service_context"


def _with_account_contract(uri: str, payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    enriched = dict(payload)
    enriched.setdefault("account_contract", ACCOUNT_CONTRACT_SINGLE_PRIMARY)
    enriched.setdefault("account_input_mode", ACCOUNT_INPUT_MODE_SERVICE_CONTEXT)
    enriched.setdefault("account_scope", _resource_account_scope(uri))
    return enriched


def _with_truth_metadata(
    config: TradeGatewayConfig,
    uri: str,
    payload: Any,
    *,
    authority: str,
    resource_path: str = "",
    server_ts: str = "",
    trace_id: str = "",
) -> Any:
    enriched = _with_account_contract(uri, payload)
    if not isinstance(enriched, dict):
        return enriched
    enriched.update(
        resource_truth_metadata(
            state_root=config.runtime_paths.state_root,
            authority=authority,
            resource_path=resource_path,
            server_ts=server_ts,
            trace_id=trace_id,
        )
    )
    return enriched


def cache_trade_resource(
    config: TradeGatewayConfig,
    uri: str,
    payload: dict[str, Any],
    *,
    server_ts: str = "",
    trace_id: str = "",
) -> Path:
    path = _resource_cache_path(config, uri)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _with_truth_metadata(
                config,
                uri,
                payload,
                authority="cached_last_known_state",
                resource_path=str(path),
                server_ts=server_ts,
                trace_id=trace_id,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def read_trade_resource(
    config: TradeGatewayConfig,
    uri: str,
    *,
    session_summary_provider: Callable[[], dict[str, Any]] | None = None,
    capability_summary_provider: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if uri == "trade://capability/current" and capability_summary_provider is not None:
        payload = _with_truth_metadata(
            config,
            uri,
            capability_summary_provider(),
            authority="service_runtime_contract",
        )
        blocked = _blocked_fake_payload(config, payload)
        if blocked is not None:
            return {"uri": uri, "payload": blocked}
        return {"uri": uri, "payload": payload}
    if uri == "trade://session/current" and session_summary_provider is not None:
        payload = _with_truth_metadata(
            config,
            uri,
            session_summary_provider(),
            authority="live_runtime_truth",
        )
        blocked = _blocked_fake_payload(config, payload)
        if blocked is not None:
            return {"uri": uri, "payload": blocked}
        return {"uri": uri, "payload": payload}
    path = _resource_cache_path(config, uri)
    if not path.exists():
        missing_payload = {
            "available": False,
            "reason": "resource_not_cached",
            "state_scope": state_scope_label(config.runtime_paths.state_root),
            "freshness_status": "cached_state_missing",
            "resource_authority": "unavailable",
        }
        missing_payload.update(
            resource_truth_metadata(
                state_root=config.runtime_paths.state_root,
                authority="unavailable",
            )
        )
        missing_payload["freshness_status"] = "cached_state_missing"
        return {"uri": uri, "payload": missing_payload}
    cached_payload = json.loads(path.read_text(encoding="utf-8"))
    payload = _with_truth_metadata(
        config,
        uri,
        cached_payload,
        authority="cached_last_known_state",
        resource_path=str(path),
        server_ts=str((cached_payload or {}).get("resource_server_ts") or ""),
        trace_id=str((cached_payload or {}).get("resource_trace_id") or ""),
    )
    blocked = _blocked_fake_payload(config, payload)
    if blocked is not None:
        return {"uri": uri, "payload": blocked}
    return {"uri": uri, "payload": payload}
