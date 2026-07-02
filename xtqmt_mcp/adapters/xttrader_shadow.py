"""Owner-managed shadow adapter for xtquant.xttrader live sessions."""

from __future__ import annotations

import time
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ..session_resolution import build_effective_session_plan
from ..xtquant_env import ensure_xtquant_on_path
from ..xttrader_precheck import enforce_session_cooldown, register_trader_callback, run_user_data_precheck
from ..types import BrokerOrderAck, BrokerOrderIntent, OrderState, Side, TradeState, is_terminal_order_status

def _safe_get(obj: Any, *names: str) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj.get(name)
        if hasattr(obj, name):
            return getattr(obj, name)
    return None

def _account_type_matches(account_type: Any, xtconstant: Any, allow_hk_connect: bool = False) -> bool:
    if account_type is None:
        return True

    str_token = str(account_type).strip().upper()
    if str_token in {"STOCK", "SECURITY", "SECURITY_ACCOUNT", "股票", "2"}:
        return True
    if allow_hk_connect and str_token in {"HUGANGTONG", "SHENGANGTONG"}:
        return True

    try:
        acc_int = int(account_type)
    except Exception:
        return False

    accepted_ints = set()
    for name in ["SECURITY_ACCOUNT"]:
        val = getattr(xtconstant, name, None) if xtconstant is not None else None
        if isinstance(val, int):
            accepted_ints.add(val)
    if allow_hk_connect:
        for name in ["HUGANGTONG_ACCOUNT", "SHENGANGTONG_ACCOUNT"]:
            val = getattr(xtconstant, name, None) if xtconstant is not None else None
            if isinstance(val, int):
                accepted_ints.add(val)

    if accepted_ints:
        return acc_int in accepted_ints
    return acc_int == 2


def _normalize_status(order_status: Any) -> str:
    try:
        status = int(order_status)
    except Exception:
        return "submitted"
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


def discover_stock_account_ids(
    user_data_path: str,
    session_id: int = 100,
    allow_hk_connect: bool = False,
    register_callback: bool = True,
    connect_cooldown_seconds: float = 3.2,
    enforce_connect_precheck: bool = True,
    require_up_queue_file: bool = True,
) -> list[str]:
    """Return stock account ids discoverable from broker xttrader session."""

    ensure_xtquant_on_path()
    from xtquant.xttrader import XtQuantTrader  # type: ignore

    try:
        from xtquant import xtconstant  # type: ignore
    except Exception:
        xtconstant = None

    path = str(Path(user_data_path))
    precheck = run_user_data_precheck(
        path,
        require_up_queue_file=bool(require_up_queue_file),
    ) if bool(enforce_connect_precheck) else {"ok": True, "issues": []}
    if not bool(precheck.get("ok", False)):
        raise RuntimeError(f"qmt_precheck_failed: {precheck}")

    trader = XtQuantTrader(path, int(session_id))
    callback_events: list[str] = []
    callback_registered, callback_status = register_trader_callback(
        trader,
        enable=bool(register_callback),
        event_sink=callback_events,
    )
    trader.start()
    try:
        _ = enforce_session_cooldown({}, session_id=int(session_id), cooldown_seconds=float(connect_cooldown_seconds))
        conn_ok = trader.connect()
        if conn_ok != 0:
            raise RuntimeError(
                f"xttrader connect failed: {conn_ok} "
                f"(callback_registered={callback_registered}, callback_status={callback_status})"
            )

        if not hasattr(trader, "query_account_infos"):
            raise RuntimeError("xttrader missing query_account_infos in current broker build")

        infos = trader.query_account_infos() or []
        matched: list[str] = []
        all_ids: list[str] = []
        for info in infos:
            account_id = str(_safe_get(info, "account_id", "accountId", "account") or "").strip()
            account_type = _safe_get(info, "account_type", "accountType", "broker_type", "type")
            if not account_id:
                continue
            all_ids.append(account_id)
            if _account_type_matches(account_type, xtconstant, allow_hk_connect=allow_hk_connect):
                matched.append(account_id)

        # Fallback to all account ids when account_type is unavailable or broker-side naming is inconsistent.
        source = matched if matched else all_ids
        deduped: list[str] = []
        seen: set[str] = set()
        for aid in source:
            if aid in seen:
                continue
            seen.add(aid)
            deduped.append(aid)
        return deduped
    finally:
        try:
            trader.stop()
        except Exception:
            pass


@dataclass
class XtTraderShadowConfig:
    """Config for read-only broker shadow adapter."""

    user_data_path: str
    account_id: str
    account_type: str = "STOCK"
    session_id: int = 100
    connect_retries: int = 3
    connect_retry_interval_seconds: float = 3.0
    session_candidates: tuple[int, ...] = (100, 101, 111)
    enable_derived_session_fallback: bool = False
    register_callback: bool = True
    connect_cooldown_seconds: float = 3.2
    enforce_connect_precheck: bool = True
    require_up_queue_file: bool = True
    max_session_attempts: int = 12


class XtTraderShadowAdapter:
    """Owner-managed live adapter for xttrader account snapshots and governed reuse."""

    def __init__(self, cfg: XtTraderShadowConfig) -> None:
        self.cfg = cfg
        self._trader = None
        self._account = None
        self._connected = False
        self._active_session_id: int | None = None

    def active_session_id(self) -> int | None:
        if self._active_session_id is None:
            return None
        return int(self._active_session_id)

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
            max_session_attempts=max(1, int(self.cfg.max_session_attempts)),
        ))

        last_connect_code = -1
        attempts: list[dict[str, str]] = []
        callback_events: list[str] = []
        session_last_attempt_ts: dict[int, float] = {}
        for sid in session_plan:
            for attempt in range(1, retries + 1):
                slept = enforce_session_cooldown(
                    session_last_attempt_ts,
                    session_id=int(sid),
                    cooldown_seconds=float(cooldown),
                )
                trader = XtQuantTrader(path, int(sid))
                callback_registered, callback_status = register_trader_callback(
                    trader,
                    enable=bool(self.cfg.register_callback),
                    event_sink=callback_events,
                )
                trader.start()
                keep_alive = False
                try:
                    code = int(trader.connect())
                    last_connect_code = int(code)
                    attempts.append(
                        {
                            "session_id": str(int(sid)),
                            "phase": "connect",
                            "attempt": str(int(attempt)),
                            "code": str(int(code)),
                            "session_cooldown_slept_seconds": f"{float(slept):.3f}",
                            "callback_registered": str(bool(callback_registered)),
                            "callback_status": str(callback_status),
                        }
                    )
                    if code != 0:
                        if attempt < retries:
                            time.sleep(retry_sleep)
                        continue

                    sub_ok = int(trader.subscribe(account))
                    attempts.append(
                        {
                            "session_id": str(int(sid)),
                            "phase": "subscribe",
                            "attempt": "1",
                            "code": str(int(sub_ok)),
                            "callback_registered": str(bool(callback_registered)),
                            "callback_status": str(callback_status),
                        }
                    )
                    if sub_ok != 0:
                        last_connect_code = int(sub_ok)
                        if attempt < retries:
                            time.sleep(retry_sleep)
                        continue

                    self._trader = trader
                    self._account = account
                    self._active_session_id = int(sid)
                    self._connected = True
                    keep_alive = True
                    return
                except Exception as exc:
                    attempts.append(
                        {
                            "session_id": str(int(sid)),
                            "phase": "exception",
                            "attempt": str(int(attempt)),
                            "code": "",
                            "error": str(exc),
                        }
                    )
                    if attempt < retries:
                        time.sleep(retry_sleep)
                finally:
                    if not keep_alive:
                        try:
                            trader.stop()
                        except Exception:
                            pass

        raise RuntimeError(
            f"xttrader connect failed: {int(last_connect_code)} after {int(retries)} attempts "
            f"(sessions={','.join(str(x) for x in session_plan)}, precheck={precheck}, "
            f"attempts={attempts}, callback_events_tail={callback_events[-10:]})"
        )

    def probe_connection(self) -> dict[str, str]:
        ensure_xtquant_on_path()
        from xtquant.xttrader import XtQuantTrader  # type: ignore

        user_data_path = str(Path(self.cfg.user_data_path))
        precheck = run_user_data_precheck(
            user_data_path,
            require_up_queue_file=bool(self.cfg.require_up_queue_file),
        ) if bool(self.cfg.enforce_connect_precheck) else {"ok": True, "issues": []}
        if not bool(precheck.get("ok", False)):
            return {
                "ok": "False",
                "connect_code": "-1",
                "session_id": str(int(self.cfg.session_id)),
                "base_session_id": str(int(self.cfg.session_id)),
                "attempts": "[]",
                "reason": "qmt_precheck_failed",
                "precheck": str(precheck),
            }

        session_attempts = list(build_effective_session_plan(
            int(self.cfg.session_id),
            tuple(self.cfg.session_candidates or ()),
            bool(self.cfg.enable_derived_session_fallback),
            max_session_attempts=max(1, int(self.cfg.max_session_attempts)),
        ))
        history: list[dict[str, str]] = []
        callback_events: list[str] = []
        session_last_attempt_ts: dict[int, float] = {}
        last_code = -1
        last_session_id = int(self.cfg.session_id)
        for sid in session_attempts:
            slept = enforce_session_cooldown(
                session_last_attempt_ts,
                session_id=int(sid),
                cooldown_seconds=float(self.cfg.connect_cooldown_seconds),
            )
            trader = XtQuantTrader(user_data_path, int(sid))
            callback_registered, callback_status = register_trader_callback(
                trader,
                enable=bool(self.cfg.register_callback),
                event_sink=callback_events,
            )
            trader.start()
            try:
                code = int(trader.connect())
                history.append(
                    {
                        "session_id": str(int(sid)),
                        "connect_code": str(code),
                        "session_cooldown_slept_seconds": f"{float(slept):.3f}",
                        "callback_registered": str(bool(callback_registered)),
                        "callback_status": str(callback_status),
                    }
                )
                last_code = int(code)
                last_session_id = int(sid)
                if code == 0:
                    return {
                        "ok": "True",
                        "connect_code": "0",
                        "session_id": str(int(sid)),
                        "base_session_id": str(int(self.cfg.session_id)),
                        "attempts": str(history),
                        "precheck": str(precheck),
                    }
            finally:
                try:
                    trader.stop()
                except Exception:
                    pass
        return {
            "ok": "False",
            "connect_code": str(int(last_code)),
            "session_id": str(int(last_session_id)),
            "base_session_id": str(int(self.cfg.session_id)),
            "attempts": str(history),
            "precheck": str(precheck),
            "callback_events_tail": str(callback_events[-10:]),
        }

    def probe_live_readiness(self, *, snapshot_requires_position: bool = False) -> dict[str, Any]:
        """Probe the current live shadow session without creating a new trader connection."""

        if (not self._connected) or self._trader is None or self._account is None:
            return {
                "available": False,
                "reused_session": False,
                "ok": False,
                "reason": "shadow_not_connected",
                "account_id": str(self.cfg.account_id),
                "session_id": str(int(self._active_session_id or self.cfg.session_id)),
                "source": "xttrader_shadow",
            }

        try:
            pos = self._trader.query_stock_positions(self._account) or []
            ast = self._trader.query_stock_asset(self._account)
            pos_rows = int(len(pos))
            ast_rows = int(1 if ast is not None else 0)
            ok = bool((ast_rows > 0) and ((pos_rows > 0) or (not bool(snapshot_requires_position))))
            return {
                "available": True,
                "reused_session": True,
                "ok": ok,
                "reason": "" if ok else "snapshot_not_ready",
                "account_id": str(self.cfg.account_id),
                "session_id": str(int(self._active_session_id or self.cfg.session_id)),
                "source": "xttrader_shadow",
                "positions_rows": pos_rows,
                "asset_rows": ast_rows,
                "snapshot_requires_position": bool(snapshot_requires_position),
                "warm_health_read_mode": "probe_only",
            }
        except Exception as exc:
            return {
                "available": True,
                "reused_session": True,
                "ok": False,
                "reason": "shadow_session_probe_failed",
                "message": str(exc),
                "account_id": str(self.cfg.account_id),
                "session_id": str(int(self._active_session_id or self.cfg.session_id)),
                "source": "xttrader_shadow",
            }

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
        self._active_session_id = None

    def _ensure_connected(self) -> None:
        if not self._connected:
            self.connect()

    def get_positions(self) -> pd.DataFrame:
        self._ensure_connected()
        data = self._trader.query_stock_positions(self._account)
        rows: list[dict[str, Any]] = []
        for p in data or []:
            rows.append(
                {
                    "account_id": str(self.cfg.account_id),
                    "stock_code": _safe_get(p, "stock_code", "stockCode"),
                    "quantity": _safe_get(p, "volume", "total_volume", "current_volume"),
                    "sellable": _safe_get(p, "can_use_volume", "can_use", "available_volume"),
                    "avg_price": _safe_get(p, "open_price", "avg_price", "cost_price"),
                    "market_value": _safe_get(p, "market_value"),
                }
            )
        return pd.DataFrame(rows)

    def get_orders(self) -> pd.DataFrame:
        self._ensure_connected()
        data = self._trader.query_stock_orders(self._account, False)
        rows: list[dict[str, Any]] = []
        for o in data or []:
            rows.append(
                {
                    "account_id": str(self.cfg.account_id),
                    "order_id": _safe_get(o, "order_id", "orderId"),
                    "stock_code": _safe_get(o, "stock_code", "stockCode"),
                    "order_type": _safe_get(o, "order_type", "orderType"),
                    "order_volume": _safe_get(o, "order_volume", "orderVolume"),
                    "traded_volume": _safe_get(o, "traded_volume", "tradedVolume"),
                    "price": _safe_get(o, "price"),
                    "order_status": _safe_get(o, "order_status", "orderStatus"),
                    "status_msg": _safe_get(o, "status_msg", "statusMsg"),
                }
            )
        return pd.DataFrame(rows)

    def get_trades(self) -> pd.DataFrame:
        self._ensure_connected()
        data = self._trader.query_stock_trades(self._account)
        rows: list[dict[str, Any]] = []
        for t in data or []:
            rows.append(
                {
                    "account_id": str(self.cfg.account_id),
                    "traded_id": _safe_get(t, "traded_id", "tradedId"),
                    "order_id": _safe_get(t, "order_id", "orderId"),
                    "stock_code": _safe_get(t, "stock_code", "stockCode"),
                    "traded_volume": _safe_get(t, "traded_volume", "tradedVolume"),
                    "traded_price": _safe_get(t, "traded_price", "tradedPrice"),
                    "traded_time": _safe_get(t, "traded_time", "tradedTime"),
                }
            )
        return pd.DataFrame(rows)

    def get_asset(self) -> pd.DataFrame:
        self._ensure_connected()
        asset = self._trader.query_stock_asset(self._account)
        if asset is None:
            return pd.DataFrame()
        return pd.DataFrame(
            [
                {
                    "account_id": str(self.cfg.account_id),
                    "cash": _safe_get(asset, "cash"),
                    "total_asset": _safe_get(asset, "total_asset", "totalAsset"),
                    "market_value": _safe_get(asset, "market_value", "marketValue"),
                }
            ]
        )

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
                "xtqmt_trade_gateway",
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
