from __future__ import annotations

from typing import Any

from .config import DEFAULT_PROMPT_NAMES, TradeGatewayConfig


def trade_prompt_definitions(config: TradeGatewayConfig) -> list[dict[str, Any]]:
    descriptions = {
        "trade-preflight": "Checklist for login, warmup and connection diagnostics before write actions.",
        "trade-recovery": "Prompt for recovering from login/session/probe failures.",
        "order-followup": "Prompt for reconciling one broker order after submission.",
    }
    out: list[dict[str, Any]] = []
    for name in config.enabled_prompts or DEFAULT_PROMPT_NAMES:
        out.append({"name": name, "description": descriptions.get(name, name), "arguments": []})
    return out


def get_trade_prompt(config: TradeGatewayConfig, name: str) -> dict[str, Any]:
    if name == "trade-preflight":
        text = (
            "Run the trade preflight in order: `miniqmt.ensure_logged_in`, `session.warm`, "
            "`session.status`, `probe.connection`, `snapshot.l1`. "
            "`probe.connection` reports layered readiness: read-only capability and write-permission capability are separated. "
            "All trade tools use the server-side primary account context; do not plan per-call account switching. "
            "`order.place` is a governed server-side write path with login/session/connectivity/write-permission/risk/kill-switch/audit gates. "
            "Do not place orders when write-permission readiness is red."
        )
    elif name == "trade-recovery":
        text = (
            "Classify the failure by layer: login/UI, QMT userdata, xtdata port, trader connect, snapshot. "
            "Prefer `diag://login/latest` and `diag://probe/latest` before retrying."
        )
    elif name == "order-followup":
        text = (
            "After `order.place`, follow with `order.status`, `orders.list`, and `fills.list`. "
            "Use the returned `broker_order_id`, `client_order_key`, and `intent_id` to reconcile within the same primary account context."
        )
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
