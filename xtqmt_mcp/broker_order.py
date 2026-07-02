"""Broker-order adapter implementations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .session_resolution import build_effective_session_plan
from .xtquant_env import ensure_xtquant_on_path
from .xttrader_precheck import enforce_session_cooldown, register_trader_callback, run_user_data_precheck
from .types import BrokerOrderAck, BrokerOrderIntent, OrderState, Side, TradeState, is_terminal_order_status


def _safe_get(obj: Any, *names: str) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj.get(name)
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def _normalize_status(order_status: Any) -> str:
    try:
        status = int(order_status)
    except Exception:
        return "submitted"
    # xtconstant ORDER_* mapping (common stock subset).
    if status in {48, 49, 50}:
        return "submitted"
    if status in {51, 52, 53, 54}:
        return "canceled"
    if status == 55:
        return "partial_filled"
    if status == 56:
        return "filled"
    if status == 57:
        return "rejected"
    if status == 255:
        return "failed"
    return "submitted"


def _normalize_broker_order_id(broker_order_id: str) -> int:
    raw = str(broker_order_id or "").strip()
    if not raw or (not raw.isdigit()):
        raise ValueError(f"invalid broker_order_id: {broker_order_id}")
    return int(raw)

@dataclass(frozen=True)
class XtTraderBrokerOrderConfig:
    """Config for live broker order adapter."""

    user_data_path: str
    account_id: str
    account_type: str = "STOCK"
    session_id: int = 100
    connect_retries: int = 3
    connect_retry_interval_seconds: float = 3.0
    strategy_name: str = "xtqmt_mcp"
    register_callback: bool = True
    connect_cooldown_seconds: float = 3.2
    enforce_connect_precheck: bool = True
    require_up_queue_file: bool = True
    session_candidates: tuple[int, ...] = ()
    enable_derived_session_fallback: bool = False
    max_session_attempts: int = 0


class DryRunBrokerOrderAdapter:
    """Safe adapter that simulates broker submit acknowledgements."""

    def __init__(self) -> None:
        self._orders: dict[str, OrderState] = {}
        self._next_broker_order_id = 10000001

    def place_order(self, intent: BrokerOrderIntent) -> BrokerOrderAck:
        ts = datetime.now()
        broker_order_id = str(int(self._next_broker_order_id))
        self._next_broker_order_id += 1
        state = OrderState(
            ts=ts,
            updated_at=ts,
            client_order_id=str(intent.client_order_id or ""),
            intent_id=str(intent.intent_id or ""),
            account_id=str(intent.account_id or ""),
            code=str(intent.code),
            side=intent.side,
            quantity=int(intent.quantity),
            status="submitted",
            broker_order_id=broker_order_id,
            message="dry-run submitted",
            price_hint=float(intent.price_hint) if intent.price_hint is not None else None,
            terminal=False,
            source_event_id=f"{ts.isoformat()}:{broker_order_id}:dry_run_submit",
        )
        self._orders[broker_order_id] = state
        return BrokerOrderAck(
            ts=ts,
            client_order_id=str(intent.client_order_id or ""),
            account_id=str(intent.account_id or ""),
            code=str(intent.code),
            side=intent.side,
            quantity=int(intent.quantity),
            ok=True,
            status="submitted",
            broker_order_id=broker_order_id,
            message="dry-run submitted",
            reject_code="",
            price_hint=float(intent.price_hint) if intent.price_hint is not None else None,
            price_mode=str(intent.price_mode or "fixed"),
            l1_bid1=float(intent.l1_bid1) if intent.l1_bid1 is not None else None,
            l1_ask1=float(intent.l1_ask1) if intent.l1_ask1 is not None else None,
            l1_last_price=float(intent.l1_last_price) if intent.l1_last_price is not None else None,
            l1_ts=str(intent.l1_ts or ""),
            l1_source=str(intent.l1_source or ""),
        )

    def cancel_order(self, account_id: str, broker_order_id: str) -> BrokerOrderAck:
        state = self._orders.get(str(broker_order_id or "").strip())
        side = state.side if state is not None else Side.BUY
        code = state.code if state is not None else ""
        quantity = state.quantity if state is not None else 0
        price_hint = state.price_hint if state is not None else None
        ts = datetime.now()
        if state is not None:
            self._orders[str(broker_order_id)] = OrderState(
                ts=state.ts,
                updated_at=ts,
                client_order_id=state.client_order_id,
                intent_id=state.intent_id,
                account_id=state.account_id,
                code=state.code,
                side=state.side,
                quantity=state.quantity,
                status="canceled",
                broker_order_id=state.broker_order_id,
                message="dry-run canceled",
                price_hint=state.price_hint,
                version=state.version,
                terminal=True,
                source_event_id=f"{ts.isoformat()}:{broker_order_id}:dry_run_cancel",
                retry_count=state.retry_count,
                last_error_code="",
            )
        return BrokerOrderAck(
            ts=ts,
            client_order_id=state.client_order_id if state is not None else "",
            account_id=str(account_id or ""),
            code=code,
            side=side,
            quantity=quantity,
            ok=True,
            status="canceled",
            broker_order_id=str(broker_order_id or ""),
            message="dry-run canceled",
            reject_code="",
            price_hint=price_hint,
        )

    def query_order(self, account_id: str, broker_order_id: str) -> OrderState | None:
        return self._orders.get(str(broker_order_id or "").strip())

    def query_open_orders(self, account_id: str) -> list[OrderState]:
        return [
            state
            for state in self._orders.values()
            if str(state.account_id or "") == str(account_id or "")
            and not bool(state.terminal)
        ]

    def query_trades(self, account_id: str, since_ts: datetime | None = None) -> list[TradeState]:
        return []


class XtTraderBrokerOrderAdapter:
    """Live broker adapter backed by `xtquant.xttrader` order APIs."""

    def __init__(self, cfg: XtTraderBrokerOrderConfig) -> None:
        self.cfg = cfg
        self._trader = None
        self._account = None
        self._connected = False
        self._active_session_id = int(cfg.session_id)

    def connect(self) -> None:
        if self._connected:
            return
        ensure_xtquant_on_path()
        from xtquant.xttrader import XtQuantTrader  # type: ignore
        from xtquant.xttype import StockAccount  # type: ignore

        path = str(Path(self.cfg.user_data_path))
        precheck = run_user_data_precheck(
            path,
            require_up_queue_file=bool(self.cfg.require_up_queue_file),
        ) if bool(self.cfg.enforce_connect_precheck) else {"ok": True, "issues": []}
        if not bool(precheck.get("ok", False)):
            raise RuntimeError(f"qmt_precheck_failed: {precheck}")

        account = StockAccount(str(self.cfg.account_id), str(self.cfg.account_type or "STOCK"))
        retries = max(1, int(self.cfg.connect_retries))
        retry_sleep = max(3.0, float(self.cfg.connect_retry_interval_seconds))
        cooldown = max(0.0, float(self.cfg.connect_cooldown_seconds))
        session_plan = list(build_effective_session_plan(
            int(self.cfg.session_id),
            tuple(self.cfg.session_candidates or ()),
            bool(self.cfg.enable_derived_session_fallback),
            max_session_attempts=int(self.cfg.max_session_attempts),
        ))
        conn_ok = -1
        attempts: list[dict[str, str]] = []
        callback_events: list[str] = []
        session_last_attempt_ts: dict[int, float] = {}
        for session_id in session_plan:
            for attempt in range(1, retries + 1):
                slept = enforce_session_cooldown(
                    session_last_attempt_ts,
                    session_id=int(session_id),
                    cooldown_seconds=float(cooldown),
                )
                trader = XtQuantTrader(path, int(session_id))
                callback_registered, callback_status = register_trader_callback(
                    trader,
                    enable=bool(self.cfg.register_callback),
                    event_sink=callback_events,
                )
                try:
                    trader.start()
                    conn_ok = int(trader.connect())
                    attempts.append(
                        {
                            "session_id": str(int(session_id)),
                            "phase": "connect",
                            "attempt": str(int(attempt)),
                            "code": str(int(conn_ok)),
                            "session_cooldown_slept_seconds": f"{float(slept):.3f}",
                            "callback_registered": str(bool(callback_registered)),
                            "callback_status": str(callback_status),
                        }
                    )
                    if conn_ok != 0:
                        if attempt < retries:
                            __import__("time").sleep(retry_sleep)
                        continue

                    sub_ok = int(trader.subscribe(account))
                    attempts.append(
                        {
                            "session_id": str(int(session_id)),
                            "phase": "subscribe",
                            "attempt": "1",
                            "code": str(int(sub_ok)),
                            "callback_registered": str(bool(callback_registered)),
                            "callback_status": str(callback_status),
                        }
                    )
                    if sub_ok != 0:
                        conn_ok = int(sub_ok)
                        if attempt < retries:
                            __import__("time").sleep(retry_sleep)
                        continue

                    self._trader = trader
                    self._account = account
                    self._active_session_id = int(session_id)
                    self._connected = True
                    return
                except Exception as exc:
                    attempts.append(
                        {
                            "session_id": str(int(session_id)),
                            "phase": "exception",
                            "attempt": str(int(attempt)),
                            "code": "",
                            "error": str(exc),
                        }
                    )
                    if attempt < retries:
                        __import__("time").sleep(retry_sleep)
                finally:
                    if not self._connected:
                        try:
                            trader.stop()
                        except Exception:
                            pass
        raise RuntimeError(
            f"xttrader connect failed: {conn_ok} after {retries} attempts "
            f"(session={int(self.cfg.session_id)}, session_plan={session_plan}, precheck={precheck}, attempts={attempts}, "
            f"callback_events_tail={callback_events[-10:]})"
        )

    def _ensure_connected(self) -> None:
        if not self._connected:
            self.connect()

    def close(self) -> None:
        if self._trader is None:
            return
        try:
            if self._account is not None:
                self._trader.unsubscribe(self._account)
        except Exception:
            pass
        try:
            self._trader.stop()
        except Exception:
            pass
        self._connected = False

    def _resolve_order_consts(self, side: Side) -> tuple[int, int]:
        from xtquant import xtconstant  # type: ignore

        order_type = int(xtconstant.STOCK_BUY if side == Side.BUY else xtconstant.STOCK_SELL)
        price_type = int(getattr(xtconstant, "FIX_PRICE", 11))
        return order_type, price_type

    def place_order(self, intent: BrokerOrderIntent) -> BrokerOrderAck:
        self._ensure_connected()
        order_type, price_type = self._resolve_order_consts(intent.side)
        price = float(intent.price_hint or 0.0)
        try:
            order_id = self._trader.order_stock(  # type: ignore[attr-defined]
                self._account,
                str(intent.code),
                int(order_type),
                int(intent.quantity),
                int(price_type),
                float(price),
                str(self.cfg.strategy_name),
                str(intent.client_order_id or intent.intent_id),
            )
            order_id_text = str(order_id or "")
            ok = bool(order_id_text and order_id_text != "-1")
            return BrokerOrderAck(
                ts=datetime.now(),
                client_order_id=str(intent.client_order_id or ""),
                account_id=str(intent.account_id or self.cfg.account_id),
                code=str(intent.code),
                side=intent.side,
                quantity=int(intent.quantity),
                ok=ok,
                status="submitted" if ok else "failed",
                broker_order_id=order_id_text if ok else "",
                message="submitted" if ok else "order_stock returned invalid order_id",
                reject_code="" if ok else "order_stock_failed",
                price_hint=float(intent.price_hint) if intent.price_hint is not None else None,
                price_mode=str(intent.price_mode or "fixed"),
                l1_bid1=float(intent.l1_bid1) if intent.l1_bid1 is not None else None,
                l1_ask1=float(intent.l1_ask1) if intent.l1_ask1 is not None else None,
                l1_last_price=float(intent.l1_last_price) if intent.l1_last_price is not None else None,
                l1_ts=str(intent.l1_ts or ""),
                l1_source=str(intent.l1_source or ""),
            )
        except Exception as exc:
            return BrokerOrderAck(
                ts=datetime.now(),
                client_order_id=str(intent.client_order_id or ""),
                account_id=str(intent.account_id or self.cfg.account_id),
                code=str(intent.code),
                side=intent.side,
                quantity=int(intent.quantity),
                ok=False,
                status="failed",
                broker_order_id="",
                message=str(exc),
                reject_code="submit_exception",
                price_hint=float(intent.price_hint) if intent.price_hint is not None else None,
                price_mode=str(intent.price_mode or "fixed"),
                l1_bid1=float(intent.l1_bid1) if intent.l1_bid1 is not None else None,
                l1_ask1=float(intent.l1_ask1) if intent.l1_ask1 is not None else None,
                l1_last_price=float(intent.l1_last_price) if intent.l1_last_price is not None else None,
                l1_ts=str(intent.l1_ts or ""),
                l1_source=str(intent.l1_source or ""),
            )

    def cancel_order(self, account_id: str, broker_order_id: str) -> BrokerOrderAck:
        self._ensure_connected()
        try:
            normalized_order_id = _normalize_broker_order_id(broker_order_id)
            cancel_code = int(self._trader.cancel_order_stock(self._account, normalized_order_id))  # type: ignore[attr-defined]
            ok = cancel_code == 0
            return BrokerOrderAck(
                ts=datetime.now(),
                client_order_id="",
                account_id=str(account_id or self.cfg.account_id),
                code="",
                side=Side.BUY,
                quantity=0,
                ok=ok,
                status="canceled" if ok else "failed",
                broker_order_id=str(broker_order_id or ""),
                message=f"cancel_result={cancel_code}",
                reject_code="" if ok else "cancel_failed",
                price_hint=None,
            )
        except Exception as exc:
            return BrokerOrderAck(
                ts=datetime.now(),
                client_order_id="",
                account_id=str(account_id or self.cfg.account_id),
                code="",
                side=Side.BUY,
                quantity=0,
                ok=False,
                status="failed",
                broker_order_id=str(broker_order_id or ""),
                message=str(exc),
                reject_code="cancel_exception",
                price_hint=None,
            )

    def query_order(self, account_id: str, broker_order_id: str) -> OrderState | None:
        self._ensure_connected()
        try:
            rows = self._trader.query_stock_orders(self._account, False) or []  # type: ignore[attr-defined]
        except Exception:
            return None
        target = None
        for row in rows:
            oid = str(_safe_get(row, "order_id", "orderId") or "")
            if oid == str(broker_order_id or ""):
                target = row
                break
        if target is None:
            return None

        code = str(_safe_get(target, "stock_code", "stockCode") or "")
        order_type = int(_safe_get(target, "order_type", "orderType") or 23)
        side = Side.BUY if order_type == 23 else Side.SELL
        quantity = int(float(_safe_get(target, "order_volume", "orderVolume") or 0))
        status = _normalize_status(_safe_get(target, "order_status", "orderStatus"))
        message = str(_safe_get(target, "status_msg", "statusMsg") or "")
        price_raw = _safe_get(target, "price")
        price_hint = float(price_raw) if price_raw is not None else None
        return OrderState(
            ts=datetime.now(),
            client_order_id="",
            intent_id="",
            account_id=str(account_id or self.cfg.account_id),
            code=code,
            side=side,
            quantity=quantity,
            status=status,
            broker_order_id=str(broker_order_id or ""),
            message=message,
            price_hint=price_hint,
            terminal=is_terminal_order_status(status),
        )

    def query_open_orders(self, account_id: str) -> list[OrderState]:
        self._ensure_connected()
        try:
            rows = self._trader.query_stock_orders(self._account, False) or []  # type: ignore[attr-defined]
        except Exception:
            return []
        out: list[OrderState] = []
        now = datetime.now()
        for row in rows:
            broker_order_id = str(_safe_get(row, "order_id", "orderId") or "")
            if not broker_order_id:
                continue
            order_type = int(_safe_get(row, "order_type", "orderType") or 23)
            side = Side.BUY if order_type == 23 else Side.SELL
            quantity = int(float(_safe_get(row, "order_volume", "orderVolume") or 0))
            status = _normalize_status(_safe_get(row, "order_status", "orderStatus"))
            if is_terminal_order_status(status):
                continue
            code = str(_safe_get(row, "stock_code", "stockCode") or "")
            message = str(_safe_get(row, "status_msg", "statusMsg") or "")
            price_raw = _safe_get(row, "price")
            price_hint = float(price_raw) if price_raw is not None else None
            out.append(
                OrderState(
                    ts=now,
                    client_order_id="",
                    intent_id="",
                    account_id=str(account_id or self.cfg.account_id),
                    code=code,
                    side=side,
                    quantity=quantity,
                    status=status,
                    broker_order_id=broker_order_id,
                    message=message,
                    price_hint=price_hint,
                    terminal=False,
                )
            )
        return out

    def query_trades(self, account_id: str, since_ts: datetime | None = None) -> list[TradeState]:
        self._ensure_connected()
        try:
            rows = self._trader.query_stock_trades(self._account) or []  # type: ignore[attr-defined]
        except Exception:
            return []
        out: list[TradeState] = []
        now = datetime.now()
        for row in rows:
            traded_id = str(_safe_get(row, "traded_id", "tradedId") or "")
            order_id = str(_safe_get(row, "order_id", "orderId") or "")
            code = str(_safe_get(row, "stock_code", "stockCode") or "")
            traded_volume = int(float(_safe_get(row, "traded_volume", "tradedVolume") or 0))
            traded_price_raw = _safe_get(row, "traded_price", "tradedPrice")
            traded_price = float(traded_price_raw) if traded_price_raw is not None else None
            order_type = int(_safe_get(row, "order_type", "orderType") or 23)
            side = Side.BUY if order_type == 23 else Side.SELL
            if traded_volume <= 0:
                continue
            out.append(
                TradeState(
                    ts=now,
                    account_id=str(account_id or self.cfg.account_id),
                    broker_order_id=order_id,
                    trade_id=traded_id,
                    code=code,
                    side=side,
                    quantity=traded_volume,
                    price=traded_price,
                )
            )
        if since_ts is None:
            return out
        return [row for row in out if row.ts >= since_ts]
