from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .config import DEFAULT_RESOURCE_URIS, DataGatewayConfig
from xtqmt_mcp.runtime_truth import is_prod_state_scope, resource_truth_metadata, state_scope_label


def data_resource_definitions(config: DataGatewayConfig) -> list[dict[str, Any]]:
    descriptions = {
        "xtdata://service/status": "Latest xtdata layered readiness and runtime endpoint snapshot.",
        "xtdata://jobs/active": "Current active download jobs.",
        "xtdata://catalog/instruments": "Latest cached instrument catalog slice.",
        "xtdata://leases/active": "Experimental subscription lease and rebuild-hint view with runtime endpoint correlation. Not proof of durable reconnect.",
    }
    out: list[dict[str, Any]] = []
    for uri in config.enabled_resources or DEFAULT_RESOURCE_URIS:
        out.append({"uri": uri, "name": uri.split("://", 1)[-1], "description": descriptions.get(uri, uri), "mimeType": "application/json"})
    return out


def _resource_cache_path(config: DataGatewayConfig, uri: str) -> Path:
    safe_name = uri.replace("://", "_").replace("/", "_")
    return Path(config.runtime_paths.state_root) / "data_resources" / f"{safe_name}.json"


def _blocked_fake_payload(config: DataGatewayConfig, payload: Any) -> dict[str, Any] | None:
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


def _with_truth_metadata(
    config: DataGatewayConfig,
    payload: Any,
    *,
    authority: str,
    resource_path: str = "",
    server_ts: str = "",
    trace_id: str = "",
) -> Any:
    if not isinstance(payload, dict):
        return payload
    enriched = dict(payload)
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


def cache_data_resource(
    config: DataGatewayConfig,
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


def read_data_resource(
    config: DataGatewayConfig,
    uri: str,
    *,
    dynamic_provider: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if dynamic_provider is not None:
        payload = _with_truth_metadata(
            config,
            dict(dynamic_provider() or {}),
            authority="live_runtime_truth",
        )
        blocked = _blocked_fake_payload(config, payload)
        if blocked is not None:
            return {"uri": uri, "payload": blocked}
        return {"uri": uri, "payload": payload}
    path = _resource_cache_path(config, uri)
    if not path.exists():
        return {
            "uri": uri,
            "payload": {
                "available": False,
                "reason": "resource_not_cached",
                "state_scope": state_scope_label(config.runtime_paths.state_root),
                "freshness_status": "cached_state_missing",
                "resource_authority": "unavailable",
            },
        }
    payload = _with_truth_metadata(
        config,
        json.loads(path.read_text(encoding="utf-8")),
        authority="cached_last_known_state",
        resource_path=str(path),
    )
    blocked = _blocked_fake_payload(config, payload)
    if blocked is not None:
        return {"uri": uri, "payload": blocked}
    return {"uri": uri, "payload": payload}
