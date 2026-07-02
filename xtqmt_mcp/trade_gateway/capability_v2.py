from __future__ import annotations

from dataclasses import replace

from xtqmt_mcp.trade_ops import TradeOpsResult, TradeOpsService
from xtqmt_mcp.types import OrderPlaceRequest


GOVERNED_ORDER_PLACE_GATE_SEQUENCE: tuple[str, ...] = (
    "login",
    "session",
    "connectivity",
    "write_permission",
    "risk",
    "kill_switch",
    "audit_persistence",
)

_SERVER_GUARD_TOKEN = "mcp_server_governed_write_path"


def _governed_request(req: OrderPlaceRequest) -> OrderPlaceRequest:
    if str(req.guard_token or "").strip():
        return req
    return replace(req, guard_token=_SERVER_GUARD_TOKEN)


def place_order_capability(service: TradeOpsService, req: OrderPlaceRequest) -> TradeOpsResult:
    """Compatibility adapter that routes MCP `order.place` into the governed service path."""

    result = service.place_order(_governed_request(req))
    payload = dict(result.payload or {})
    payload["governed_write_path"] = True
    payload["write_path"] = "governed_service_order_place"
    payload["gate_sequence"] = list(GOVERNED_ORDER_PLACE_GATE_SEQUENCE)
    return TradeOpsResult(command=result.command, ok=bool(result.ok), payload=payload)
