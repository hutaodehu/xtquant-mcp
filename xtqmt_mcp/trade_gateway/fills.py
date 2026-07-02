from __future__ import annotations

from datetime import date
from threading import Thread
from typing import Any

from xtqmt_mcp.history_service import HistoryQueryConfig, HistoryService
from xtqmt_mcp.trade_ops import TradeOpsResult


def _safe_get(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row.get(key)
    return None


def _dedupe_trades(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keep: dict[str, dict[str, Any]] = {}
    for row in rows:
        trade_id = str(_safe_get(row, "trade_id", "traded_id", "tradedId") or "").strip()
        broker_order_id = str(_safe_get(row, "broker_order_id", "order_id", "orderId") or "").strip()
        code = str(_safe_get(row, "code", "stock_code", "stockCode") or "").strip()
        quantity = str(_safe_get(row, "quantity", "traded_volume", "tradedVolume") or "").strip()
        traded_time = str(_safe_get(row, "traded_time", "ts") or "").strip()
        ts = str(row.get("_record_ts", "") or "").strip()
        key = trade_id or f"{broker_order_id}|{code}|{quantity}|{traded_time}|{ts}"
        old = keep.get(key)
        if old is None or str(old.get("_record_ts", "")) <= ts:
            keep[key] = row
    return list(keep.values())


def _build_order_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for row in rows:
        broker_order_id = str(_safe_get(row, "broker_order_id", "order_id", "orderId") or "").strip()
        client_order_key = str(_safe_get(row, "client_order_key", "client_order_id", "clientOrderId") or "").strip()
        intent_id = str(_safe_get(row, "intent_id") or "").strip()
        payload = {
            "broker_order_id": broker_order_id,
            "client_order_key": client_order_key,
            "intent_id": intent_id,
        }
        for key in (broker_order_id, client_order_key, intent_id):
            if key:
                index[key] = payload
    return index


def _normalize_source(row: dict[str, Any]) -> str:
    explicit_source = str(row.get("_trade_source", "") or "").strip()
    if explicit_source:
        return explicit_source
    source_file = str(row.get("_source_file", "") or "")
    if source_file.startswith("broker:"):
        return "broker"
    return "local"


def _fallback_trades_from_broker_orders(rows: list[dict[str, Any]], *, account_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        broker_order_id = str(_safe_get(row, "broker_order_id", "order_id", "orderId") or "").strip()
        code = str(_safe_get(row, "code", "stock_code", "stockCode") or "").strip()
        traded_volume = _safe_get(row, "traded_volume", "tradedVolume", "quantity")
        traded_price = _safe_get(row, "traded_price", "tradedPrice", "price")
        try:
            traded_qty = int(float(traded_volume or 0))
            traded_px = float(traded_price or 0)
        except (TypeError, ValueError):
            continue
        if not broker_order_id or not code or traded_qty <= 0 or traded_px <= 0:
            continue
        out.append(
            {
                "_source_file": "broker:orders_traded_volume",
                "_trade_source": "broker_order_traded_volume",
                "_record_ts": str(_safe_get(row, "_record_ts", "ts", "updated_at", "traded_time") or ""),
                "ts": str(_safe_get(row, "ts", "updated_at", "_record_ts") or ""),
                "traded_time": str(_safe_get(row, "traded_time", "ts", "updated_at", "_record_ts") or ""),
                "account_id": str(_safe_get(row, "account_id", "accountId") or account_id),
                "trade_id": f"broker_order_traded_volume:{broker_order_id}",
                "broker_order_id": broker_order_id,
                "client_order_key": str(_safe_get(row, "client_order_key", "client_order_id", "clientOrderId") or ""),
                "intent_id": str(_safe_get(row, "intent_id") or ""),
                "code": code,
                "stock_code": code,
                "side": _safe_get(row, "side", "order_type", "orderType"),
                "order_type": _safe_get(row, "order_type", "orderType"),
                "traded_volume": traded_qty,
                "quantity": traded_qty,
                "traded_price": traded_px,
                "price": traded_px,
            }
        )
    return out


def _query_with_timeout(
    callback,
    *,
    entity: str,
    start_date: date,
    end_date: date,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    box: dict[str, Any] = {}
    error_box: dict[str, Exception] = {}

    def _run() -> None:
        try:
            box["value"] = callback()
        except Exception as exc:  # pragma: no cover - defensive wrapper
            error_box["exc"] = exc

    worker = Thread(target=_run, name=f"fills-{entity}-query", daemon=True)
    worker.start()
    worker.join(max(0.1, float(timeout_seconds)))
    if worker.is_alive():
        return {
            "ok": True,
            "entity": entity,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "source": "broker",
            "rows": [],
            "meta": {
                "broker_attempted": True,
                "broker_row_count": 0,
                "local_row_count": 0,
                "fallback_used": False,
                "notes": [f"broker_read_timeout:{timeout_seconds:g}s"],
            },
        }
    if "exc" in error_box:
        return {
            "ok": True,
            "entity": entity,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "source": "broker",
            "rows": [],
            "meta": {
                "broker_attempted": True,
                "broker_row_count": 0,
                "local_row_count": 0,
                "fallback_used": False,
                "notes": [f"broker_read_failed:{error_box['exc']}"],
            },
        }
    return dict(box.get("value") or {})


def list_fills(
    service: Any,
    *,
    trading_day: date,
    broker_order_id: str = "",
    client_order_key: str = "",
    intent_id: str = "",
) -> TradeOpsResult:
    account_id = str(getattr(getattr(service, "cfg", None), "account_id", "") or "").strip()
    history_cfg_broker = HistoryQueryConfig(
        account_id=account_id,
        start_date=trading_day,
        end_date=trading_day,
        output_roots=(str(service.cfg.output_dir),),
        state_roots=(str(service.cfg.state_dir),),
        prefer_broker=True,
        fallback_local=True,
    )
    history_cfg_local = HistoryQueryConfig(
        account_id=account_id,
        start_date=trading_day,
        end_date=trading_day,
        output_roots=(str(service.cfg.output_dir),),
        state_roots=(str(service.cfg.state_dir),),
        prefer_broker=False,
        fallback_local=True,
    )

    broker_history = HistoryService(history_cfg_broker, shadow_adapter=getattr(service, "shadow", None))
    local_history = HistoryService(history_cfg_local, shadow_adapter=getattr(service, "shadow", None))

    broker_trade_payload = _query_with_timeout(
        broker_history.query_trades_history,
        entity="trades",
        start_date=trading_day,
        end_date=trading_day,
    )
    broker_order_payload = _query_with_timeout(
        broker_history.query_orders_history,
        entity="orders",
        start_date=trading_day,
        end_date=trading_day,
    )
    local_trade_payload = local_history.query_trades_history()
    local_order_payload = local_history.query_orders_history()

    normalized_filters = {
        "broker_order_id": str(broker_order_id or "").strip(),
        "client_order_key": str(client_order_key or "").strip(),
        "intent_id": str(intent_id or "").strip(),
    }
    broker_order_rows = list(broker_order_payload.get("rows", []))
    broker_trade_rows = list(broker_trade_payload.get("rows", []))
    local_trade_rows = list(local_trade_payload.get("rows", []))
    order_index = _build_order_index(broker_order_rows + list(local_order_payload.get("rows", [])))
    fallback_trade_rows: list[dict[str, Any]] = []
    if not broker_trade_rows:
        fallback_trade_rows = _fallback_trades_from_broker_orders(broker_order_rows, account_id=account_id)
    merged_rows = _dedupe_trades(broker_trade_rows + fallback_trade_rows + local_trade_rows)

    rows: list[dict[str, Any]] = []
    for row in merged_rows:
        normalized_broker_order_id = str(_safe_get(row, "broker_order_id", "order_id", "orderId") or "").strip()
        mapped = (
            order_index.get(normalized_broker_order_id)
            or order_index.get(str(_safe_get(row, "intent_id") or "").strip())
            or order_index.get(str(_safe_get(row, "client_order_key", "client_order_id", "clientOrderId") or "").strip())
            or {}
        )
        normalized = {
            "ts": str(_safe_get(row, "ts", "_record_ts") or ""),
            "traded_time": str(_safe_get(row, "traded_time", "ts", "_record_ts") or ""),
            "account_id": str(_safe_get(row, "account_id", "accountId") or account_id),
            "trade_id": str(_safe_get(row, "trade_id", "traded_id", "tradedId") or ""),
            "broker_order_id": normalized_broker_order_id,
            "client_order_key": str(mapped.get("client_order_key") or _safe_get(row, "client_order_key", "client_order_id", "clientOrderId") or ""),
            "intent_id": str(mapped.get("intent_id") or _safe_get(row, "intent_id") or ""),
            "code": str(_safe_get(row, "code", "stock_code", "stockCode") or ""),
            "side": str(_safe_get(row, "side", "order_type", "orderType") or ""),
            "traded_volume": _safe_get(row, "traded_volume", "quantity", "tradedVolume"),
            "traded_price": _safe_get(row, "traded_price", "price", "tradedPrice"),
            "source": _normalize_source(row),
            "source_file": str(row.get("_source_file", "") or ""),
        }
        if normalized_filters["broker_order_id"] and normalized["broker_order_id"] != normalized_filters["broker_order_id"]:
            continue
        if normalized_filters["client_order_key"] and normalized["client_order_key"] != normalized_filters["client_order_key"]:
            continue
        if normalized_filters["intent_id"] and normalized["intent_id"] != normalized_filters["intent_id"]:
            continue
        rows.append(normalized)

    source_kinds = {row["source"] for row in rows}
    if not source_kinds:
        source = "none"
    elif len(source_kinds) == 1:
        source = next(iter(source_kinds))
    else:
        source = "hybrid"

    return TradeOpsResult(
        command="fills.list",
        ok=True,
        payload={
            "account_id": account_id,
            "trading_day": trading_day.isoformat(),
            "broker_order_id": normalized_filters["broker_order_id"],
            "client_order_key": normalized_filters["client_order_key"],
            "intent_id": normalized_filters["intent_id"],
            "row_count": len(rows),
            "source": source,
            "broker_attempted": bool((broker_trade_payload.get("meta") or {}).get("broker_attempted") or (broker_order_payload.get("meta") or {}).get("broker_attempted")),
            "broker_row_count": int((broker_trade_payload.get("meta") or {}).get("broker_row_count") or 0),
            "local_row_count": int((local_trade_payload.get("meta") or {}).get("local_row_count") or len(local_trade_rows)),
            "fallback_used": bool(fallback_trade_rows),
            "meta": {
                "broker_trade_meta": dict(broker_trade_payload.get("meta") or {}),
                "broker_order_meta": dict(broker_order_payload.get("meta") or {}),
                "local_trade_meta": dict(local_trade_payload.get("meta") or {}),
                "broker_order_traded_volume_fallback_count": len(fallback_trade_rows),
            },
            "rows": rows,
        },
    )
