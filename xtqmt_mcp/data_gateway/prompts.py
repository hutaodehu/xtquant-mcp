from __future__ import annotations

from typing import Any

from .config import DEFAULT_PROMPT_NAMES, DataGatewayConfig


def data_prompt_definitions(config: DataGatewayConfig) -> list[dict[str, Any]]:
    descriptions = {
        "data-backfill-plan": "Prompt for planning one historical backfill job.",
        "data-download-triage": "Prompt for debugging a failed download job.",
        "xtdata-service-recover": "Prompt for restoring xtdata service readiness.",
    }
    out: list[dict[str, Any]] = []
    for name in config.enabled_prompts or DEFAULT_PROMPT_NAMES:
        out.append({"name": name, "description": descriptions.get(name, name), "arguments": []})
    return out


def get_data_prompt(config: DataGatewayConfig, name: str) -> dict[str, Any]:
    if name == "data-backfill-plan":
        text = "Prefer `xtdata.download.submit` for long-running downloads. Query `xtdata.status` first, keep jobs small and date-bounded, and do not infer durable stream readiness from experimental subscription leases."
    elif name == "data-download-triage":
        text = "Inspect `xtdata://jobs/active` and the job artifact path before retrying. Treat subscription capability as experimental, read `xtdata://leases/active`, and use `needs_rebuild` plus `rebuild_reason` instead of assuming reconnect is already stable."
    elif name == "xtdata-service-recover":
        text = "Recover in order: bundle validation, MiniQMT/xtdata port readiness, then a small `xtdata.history.get_bars` smoke query. If subscription leases are stale or stopped, inspect callback and connection liveness in `xtdata://leases/active`, then do an explicit rebuild. Do not treat `subscription_id` as proof of durable reconnect or persistent delivery."
    else:
        raise KeyError(name)
    return {
        "description": name,
        "messages": [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": text,
                },
            }
        ],
    }
