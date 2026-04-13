"""Risk gate engine for broker-order intents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from .types import BrokerOrderIntent, RejectReason, RiskDecision, Side


@dataclass(frozen=True)
class RiskConfig:
    """Risk configuration for pre-trade validation."""

    max_single_order_notional: float = 200000.0
    max_daily_notional: float = 2000000.0
    white_list: tuple[str, ...] = ()


class BasicRiskEngine:
    """Deterministic risk engine with explicit reject reasons."""

    def __init__(self, cfg: RiskConfig) -> None:
        self.cfg = cfg
        self.white_list = {str(code).upper().strip() for code in (cfg.white_list or ()) if str(code).strip()}

    def _decision(
        self,
        *,
        intent: BrokerOrderIntent,
        ok: bool,
        code: str,
        reason: str,
        notional: float,
    ) -> RiskDecision:
        return RiskDecision(
            ts=intent.ts,
            intent_id=intent.intent_id,
            client_order_id=str(intent.client_order_id or ""),
            ok=bool(ok),
            code=str(code),
            reason=str(reason),
            code_symbol=str(intent.code).upper(),
            side=intent.side,
            quantity=int(intent.quantity),
            price_hint=float(intent.price_hint) if intent.price_hint is not None else None,
            notional=float(notional),
        )

    def evaluate(
        self,
        intent: BrokerOrderIntent,
        *,
        cash_available: float,
        sellable_qty: int,
        cumulative_notional_today: float,
        is_market_open: bool,
        kill_switch_on: bool,
    ) -> RiskDecision:
        qty = int(intent.quantity)
        price = float(intent.price_hint or 0.0)
        notional = float(max(0.0, qty * price))
        symbol = str(intent.code).upper().strip()

        if kill_switch_on:
            return self._decision(
                intent=intent,
                ok=False,
                code=RejectReason.KILL_SWITCH.value,
                reason="kill switch is on",
                notional=notional,
            )

        if not is_market_open:
            return self._decision(
                intent=intent,
                ok=False,
                code=RejectReason.MARKET_CLOSED.value,
                reason="market session is closed",
                notional=notional,
            )

        if qty <= 0:
            return self._decision(
                intent=intent,
                ok=False,
                code=RejectReason.INVALID_QUANTITY.value,
                reason="quantity must be positive",
                notional=notional,
            )

        if price <= 0:
            return self._decision(
                intent=intent,
                ok=False,
                code=RejectReason.PRICE_NON_POSITIVE.value,
                reason="price hint is missing or non-positive",
                notional=notional,
            )

        if self.white_list and (symbol not in self.white_list):
            return self._decision(
                intent=intent,
                ok=False,
                code=RejectReason.NOT_WHITE_LISTED.value,
                reason="symbol not in white list",
                notional=notional,
            )

        if self.cfg.max_single_order_notional > 0 and notional > float(self.cfg.max_single_order_notional):
            return self._decision(
                intent=intent,
                ok=False,
                code=RejectReason.SINGLE_ORDER_NOTIONAL_LIMIT.value,
                reason="single-order notional exceeds limit",
                notional=notional,
            )

        if self.cfg.max_daily_notional > 0 and (float(cumulative_notional_today) + notional) > float(self.cfg.max_daily_notional):
            return self._decision(
                intent=intent,
                ok=False,
                code=RejectReason.DAILY_NOTIONAL_LIMIT.value,
                reason="daily notional exceeds limit",
                notional=notional,
            )

        if intent.side == Side.BUY and float(cash_available) < notional:
            return self._decision(
                intent=intent,
                ok=False,
                code=RejectReason.INSUFFICIENT_CASH.value,
                reason="cash available is insufficient",
                notional=notional,
            )

        if intent.side == Side.SELL and int(sellable_qty) < qty:
            return self._decision(
                intent=intent,
                ok=False,
                code=RejectReason.INSUFFICIENT_SELLABLE.value,
                reason="sellable quantity is insufficient",
                notional=notional,
            )

        return self._decision(
            intent=intent,
            ok=True,
            code="ok",
            reason="passed",
            notional=notional,
        )


def parse_white_list(raw: str) -> tuple[str, ...]:
    values: list[str] = []
    for chunk in str(raw or "").split(","):
        token = str(chunk).strip().upper()
        if not token:
            continue
        if token in values:
            continue
        values.append(token)
    return tuple(values)


def kill_switch_on(path: str) -> bool:
    from pathlib import Path

    candidate = str(path or "").strip()
    if not candidate:
        return False
    return Path(candidate).exists()

