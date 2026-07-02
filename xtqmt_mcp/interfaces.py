"""Public interfaces for xtqmt_mcp components."""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Iterable, Optional, Protocol, Sequence

import pandas as pd

from .types import (
    AccountSnapshot,
    BrokerOrderAck,
    BrokerOrderIntent,
    RebalancePlanV2,
    FillEvent,
    MarketEvent,
    OrderState,
    RiskDecision,
    UnifiedSignalBatch,
    TargetBook,
    TradeState,
    VirtualOrder,
)


class SignalProvider(Protocol):
    """Provides rebalance target book."""

    def get_targets(self, asof: datetime) -> TargetBook:
        """Return target portfolio for as-of datetime."""


class MarketDataProvider(Protocol):
    """Provides local history and online realtime events."""

    def load_history(
        self,
        codes: Sequence[str],
        start_date: date,
        end_date: date,
        freq: str,
    ) -> Dict[str, pd.DataFrame]:
        """Load history from local cache."""

    def subscribe_today(
        self,
        codes: Sequence[str],
        trading_day: date,
        mode: str,
    ) -> Iterable[MarketEvent]:
        """Yield live events for today."""

    def latest_online_event(
        self,
        code: str,
        trading_day: date,
        mode: str,
    ) -> Optional[MarketEvent]:
        """Fetch latest online event for a code."""


class ExecutionModel(Protocol):
    """Matches virtual order with market event."""

    def match(self, order: VirtualOrder, event: MarketEvent) -> Optional[FillEvent]:
        """Return fill event if order is filled by event."""


class ShadowAccountAdapter(Protocol):
    """Optional read-only adapter for real account monitoring."""

    def get_positions(self) -> pd.DataFrame:
        """Return current live positions."""

    def get_orders(self) -> pd.DataFrame:
        """Return current orders."""

    def get_trades(self) -> pd.DataFrame:
        """Return current trades."""

    def get_asset(self) -> pd.DataFrame:
        """Return current asset snapshot."""


class BrokerOrderAdapter(Protocol):
    """Write-path adapter for broker order placement/cancel/query."""

    def place_order(self, intent: BrokerOrderIntent) -> BrokerOrderAck:
        """Submit one broker order and return acknowledgement."""

    def cancel_order(self, account_id: str, broker_order_id: str) -> BrokerOrderAck:
        """Cancel one broker order by broker-order-id."""

    def query_order(self, account_id: str, broker_order_id: str) -> OrderState | None:
        """Query broker order state by broker-order-id."""

    def query_open_orders(self, account_id: str) -> list[OrderState]:
        """Query current non-terminal broker orders for recovery/reconcile."""

    def query_trades(self, account_id: str, since_ts: datetime | None = None) -> list[TradeState]:
        """Query trade rows for post-submit reconciliation."""


class RiskEngine(Protocol):
    """Pre-trade risk gate interface for broker-order intents."""

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
        """Return allow/reject decision with normalized reason code."""


class UnifiedSignalProvider(Protocol):
    """Loads normalized multi-source signals for one rebalance point."""

    def load_batch(self, asof: datetime) -> UnifiedSignalBatch:
        """Return normalized signals batch for one as-of timestamp."""


class PlanResolver(Protocol):
    """Converts normalized signals to executable rebalance plan."""

    def resolve(self, batch: UnifiedSignalBatch) -> RebalancePlanV2:
        """Resolve one signal batch into one executable rebalance plan."""


class AccountEngine(Protocol):
    """Virtual account engine API."""

    def submit_orders(self, orders: Sequence[VirtualOrder]) -> None:
        """Submit virtual orders to pending queue."""

    def on_fill(self, fill: FillEvent) -> None:
        """Apply fill event to account state."""

    def snapshot(self, event_time: datetime, mark_prices: Dict[str, float]) -> AccountSnapshot:
        """Build account snapshot at event time."""
