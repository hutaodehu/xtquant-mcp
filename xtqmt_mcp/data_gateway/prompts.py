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
        text = "Prefer `bulk.sync_job.submit` for end-to-end qlib sync jobs. Query `gateway.health` first, resolve the trade day via `calendar.resolve_trade_day`, and plan the window with `integrity.plan` before submitting."
    elif name == "data-download-triage":
        text = "Inspect `xtdata://jobs/active`, `artifact.manifest`, and `qlib.acceptance.check` outputs before retrying. Use `qlib.health.check` and the residual verdict to separate boundary residuals from real failures."
    elif name == "xtdata-service-recover":
        text = "Recover in order: bundle validation, dynamic xtdata port resolution, `gateway.health`, then a small `calendar.resolve_trade_day` plus `integrity.plan` smoke. Subscription recovery stays in explicit rebuild mode and is not proof of durable reconnect. Do not treat the old `xtdata.*` tool names as a valid fallback path."
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
