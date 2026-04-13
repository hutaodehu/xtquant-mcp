from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.trade_gateway.config import load_trade_gateway_config
from xtqmt_mcp.trade_gateway.server import TradeGatewayServer


def _request(method: str, *, request_id: int, params: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": int(request_id),
        "method": str(method),
    }
    if params is not None:
        payload["params"] = dict(params)
    return payload


def _tool_call(name: str, arguments: dict[str, Any], *, request_id: int) -> dict[str, Any]:
    return _request(
        "tools/call",
        request_id=request_id,
        params={"name": str(name), "arguments": dict(arguments or {})},
    )


def _resource_read(uri: str, *, request_id: int) -> dict[str, Any]:
    return _request("resources/read", request_id=request_id, params={"uri": str(uri)})


def _structured_data(response: dict[str, Any]) -> Any:
    return (((response.get("result") or {}).get("structuredContent") or {}).get("data"))


def _resource_json(response: dict[str, Any]) -> Any:
    try:
        contents = ((response.get("result") or {}).get("contents") or [])
        if not contents:
            return None
        text = str((contents[0] or {}).get("text") or "")
        return json.loads(text) if text else None
    except Exception:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run non-prod trade flow-smoke lifecycle through TradeGatewayServer.dispatch().")
    parser.add_argument("--config", default="configs/trade_gateway.flow_smoke.yaml")
    parser.add_argument("--code", default="515880.SH")
    parser.add_argument("--side", default="BUY", choices=["BUY", "SELL"])
    parser.add_argument("--qty", type=int, default=100)
    parser.add_argument("--limit-price", type=float, default=1.23)
    parser.add_argument("--client-order-key", default="COID-FLOW-SMOKE-001")
    parser.add_argument("--intent-id", default="INT-FLOW-SMOKE-001")
    parser.add_argument("--output-json", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_trade_gateway_config(args.config)
    gateway = TradeGatewayServer(config)
    report: dict[str, Any] = {
        "config_path": str(Path(args.config)),
        "execution_mode": str(config.trade_ops.execution_mode or "live"),
    }

    request_id = 1

    def dispatch(payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal request_id
        response = gateway.dispatch(payload, session_id="flow-smoke-local")
        request_id += 1
        return dict(response or {})

    report["initialize"] = dispatch(_request("initialize", request_id=request_id))
    report["health"] = gateway.health_payload()
    report["session_warm"] = dispatch(_tool_call("session.warm", {}, request_id=request_id))
    report["session_status_before"] = dispatch(_tool_call("session.status", {}, request_id=request_id))
    report["order_place"] = dispatch(
        _tool_call(
            "order.place",
            {
                "code": str(args.code),
                "side": str(args.side),
                "qty": int(args.qty),
                "price_mode": "fixed",
                "limit_price": float(args.limit_price),
                "client_order_key": str(args.client_order_key),
                "intent_id": str(args.intent_id),
            },
            request_id=request_id,
        )
    )

    placed_data = _structured_data(report["order_place"]) or {}
    broker_order_id = str(placed_data.get("broker_order_id") or "")
    report["broker_order_id"] = broker_order_id

    if broker_order_id:
        report["order_status_before_cancel"] = dispatch(
            _tool_call("order.status", {"broker_order_id": broker_order_id}, request_id=request_id)
        )
    else:
        report["order_status_before_cancel"] = {"skipped": True, "reason": "missing_broker_order_id"}

    report["orders_list_before_cancel"] = dispatch(_tool_call("orders.list", {}, request_id=request_id))

    if broker_order_id:
        report["order_cancel"] = dispatch(
            _tool_call("order.cancel", {"broker_order_id": broker_order_id}, request_id=request_id)
        )
        report["order_status_after_cancel"] = dispatch(
            _tool_call("order.status", {"broker_order_id": broker_order_id}, request_id=request_id)
        )
        report["fills_list"] = dispatch(
            _tool_call("fills.list", {"broker_order_id": broker_order_id}, request_id=request_id)
        )
    else:
        report["order_cancel"] = {"skipped": True, "reason": "missing_broker_order_id"}
        report["order_status_after_cancel"] = {"skipped": True, "reason": "missing_broker_order_id"}
        report["fills_list"] = {"skipped": True, "reason": "missing_broker_order_id"}

    report["orders_list_after_cancel"] = dispatch(_tool_call("orders.list", {}, request_id=request_id))
    report["trade_session_resource"] = _resource_json(
        dispatch(_resource_read("trade://session/current", request_id=request_id))
    )

    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + "\n", encoding="utf-8")
    print(output)

    order_ok = bool(((_structured_data(report["order_place"]) or {}).get("ok")))
    cancel_ok = bool(((_structured_data(report["order_cancel"]) or {}).get("ok")))
    return 0 if (order_ok and cancel_ok and bool(broker_order_id)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
