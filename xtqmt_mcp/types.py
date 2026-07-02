"""Core types for xtqmt_mcp."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class DataOrigin(str, Enum):
    """Origin of market data."""

    LOCAL_CACHE = "local_cache"
    ONLINE_SUBSCRIBE = "online_subscribe"
    ONLINE_PULL = "online_pull"
    GET_FULL_TICK = "get_full_tick"
    WHOLE_QUOTE_CALLBACK = "whole_quote_callback"


class EventKind(str, Enum):
    """Kind of market event."""

    TICK = "tick"
    MINUTE = "1m"


class Side(str, Enum):
    """Order side."""

    BUY = "BUY"
    SELL = "SELL"


class SignalKind(str, Enum):
    """Normalized signal class used by unified signal ingestion."""

    SELECTOR = "selector"
    RISK_OVERRIDE = "risk_override"
    INTRADAY_T = "intraday_t"


class OrderStatus(str, Enum):
    """Runtime lifecycle status for broker-order flow."""

    PREPARED = "prepared"
    BLOCKED = "blocked"
    RISK_REJECTED = "risk_rejected"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    PARTIAL_FILLED = "partial_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    FAILED = "failed"


TERMINAL_ORDER_STATUSES: tuple[str, ...] = (
    OrderStatus.FILLED.value,
    OrderStatus.CANCELED.value,
    OrderStatus.REJECTED.value,
    OrderStatus.FAILED.value,
)


def is_terminal_order_status(status: str) -> bool:
    return str(status or "").strip().lower() in TERMINAL_ORDER_STATUSES


class RejectReason(str, Enum):
    """Normalized reject/restriction reason for risk and submit failures."""

    KILL_SWITCH = "kill_switch"
    MARKET_CLOSED = "market_closed"
    MISSING_PRICE = "missing_price"
    PRICE_NON_POSITIVE = "price_non_positive"
    INVALID_QUANTITY = "invalid_quantity"
    INSUFFICIENT_CASH = "insufficient_cash"
    INSUFFICIENT_SELLABLE = "insufficient_sellable"
    NOT_WHITE_LISTED = "not_white_listed"
    SINGLE_ORDER_NOTIONAL_LIMIT = "single_order_notional_limit"
    DAILY_NOTIONAL_LIMIT = "daily_notional_limit"
    ADAPTER_UNAVAILABLE = "adapter_unavailable"
    SUBMIT_EXCEPTION = "submit_exception"


@dataclass(frozen=True)
class MarketEvent:
    """Realtime market event consumed by matching engine."""

    code: str
    ts: datetime
    last_price: float
    source: DataOrigin
    kind: EventKind = EventKind.TICK
    bid1: Optional[float] = None
    bid2: Optional[float] = None
    bid3: Optional[float] = None
    bid4: Optional[float] = None
    bid5: Optional[float] = None
    ask1: Optional[float] = None
    ask2: Optional[float] = None
    ask3: Optional[float] = None
    ask4: Optional[float] = None
    ask5: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None
    prev_close: Optional[float] = None
    limit_up: Optional[float] = None
    limit_down: Optional[float] = None


@dataclass(frozen=True)
class L1Snapshot:
    """Top-of-book L1 snapshot for order pricing/audit."""

    code: str
    ts: datetime
    bid1: Optional[float]
    bid2: Optional[float]
    bid3: Optional[float]
    ask1: Optional[float]
    ask2: Optional[float]
    ask3: Optional[float]
    last_price: Optional[float]
    source: DataOrigin
    bid4: Optional[float] = None
    bid5: Optional[float] = None
    ask4: Optional[float] = None
    ask5: Optional[float] = None
    depth_available_levels: int = 1


@dataclass(frozen=True)
class TargetPosition:
    """Target portfolio item."""

    code: str
    target_weight: float


@dataclass(frozen=True)
class TargetBook:
    """Target portfolio for one rebalance point."""

    asof: datetime
    source: str
    positions: List[TargetPosition]


@dataclass(frozen=True)
class VirtualOrder:
    """Virtual order in paper account."""

    order_id: str
    code: str
    side: Side
    quantity: int
    created_at: datetime
    reason: str = "rebalance"


@dataclass(frozen=True)
class FillEvent:
    """Virtual fill event."""

    order_id: str
    code: str
    side: Side
    quantity: int
    price: float
    ts: datetime
    fee: float
    source: DataOrigin


@dataclass
class Position:
    """Position state in virtual account."""

    code: str
    quantity: int = 0
    sellable: int = 0
    avg_price: float = 0.0
    bought_today: int = 0


@dataclass(frozen=True)
class AccountSnapshot:
    """Point-in-time account snapshot."""

    ts: datetime
    cash: float
    market_value: float
    nav: float
    positions: int


@dataclass(frozen=True)
class RuntimeReport:
    """Runtime summary."""

    observe_only: bool
    warnings: List[str] = field(default_factory=list)
    policy_violations: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RealPositionSnapshot:
    """Real-account position snapshot row."""

    ts: datetime
    account_id: str
    code: str
    quantity: float
    sellable: Optional[float] = None
    avg_price: Optional[float] = None
    market_value: Optional[float] = None


@dataclass(frozen=True)
class RealOrderSnapshot:
    """Real-account order snapshot row."""

    ts: datetime
    account_id: str
    order_id: str
    code: Optional[str]
    order_type: Optional[str]
    order_volume: Optional[float]
    traded_volume: Optional[float]
    price: Optional[float]
    order_status: Optional[str]
    status_msg: Optional[str] = None


@dataclass(frozen=True)
class RealTradeSnapshot:
    """Real-account trade snapshot row."""

    ts: datetime
    account_id: str
    traded_id: str
    order_id: Optional[str]
    code: Optional[str]
    traded_volume: Optional[float]
    traded_price: Optional[float]
    traded_time: Optional[str] = None


@dataclass(frozen=True)
class RealAssetSnapshot:
    """Real-account asset snapshot row."""

    ts: datetime
    account_id: str
    cash: Optional[float]
    total_asset: Optional[float]
    market_value: Optional[float]


@dataclass(frozen=True)
class ChannelProbeItem:
    """Single channel-probe check item."""

    name: str
    ok: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: Optional[int] = None
    hint: Optional[str] = None
    details: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ChannelProbeReport:
    """Structured channel-probe report."""

    started_at: datetime
    finished_at: datetime
    items: List[ChannelProbeItem] = field(default_factory=list)
    overall_ok: bool = False
    discovered_account_id: str = ""
    selected_session_id: Optional[int] = None
    precheck: Dict[str, Any] = field(default_factory=dict)
    callback_events: List[str] = field(default_factory=list)
    failure_classification: str = ""
    connection_trace: List["ConnectionStageResult"] = field(default_factory=list)


@dataclass(frozen=True)
class ConnectionStageResult:
    """One stage result in connection orchestration."""

    name: str
    ok: bool
    code: str = ""
    message: str = ""
    latency_ms: Optional[int] = None
    retry_count: int = 0
    details: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectionTraceReport:
    """End-to-end trace for broker connection orchestration."""

    started_at: datetime
    finished_at: datetime
    stages: List[ConnectionStageResult] = field(default_factory=list)
    overall_ok: bool = False
    selected_session_id: Optional[int] = None
    selected_account_id: str = ""
    precheck: Dict[str, Any] = field(default_factory=dict)
    callback_events: List[str] = field(default_factory=list)
    failure_classification: str = ""


@dataclass(frozen=True)
class ShadowHealthSnapshot:
    """One polling-cycle health row for shadow snapshots."""

    ts: datetime
    poll_count: int
    rows_positions: int
    rows_orders: int
    rows_trades: int
    rows_asset: int
    is_stale: bool
    warning: Optional[str] = None


@dataclass(frozen=True)
class RiskDecision:
    """Risk decision for one order intent."""

    ts: datetime
    intent_id: str
    client_order_id: str
    ok: bool
    code: str
    reason: str
    code_symbol: str
    side: Side
    quantity: int
    price_hint: Optional[float]
    notional: float


@dataclass(frozen=True)
class BrokerOrderAck:
    """Submit/cancel acknowledgement from broker adapter."""

    ts: datetime
    client_order_id: str
    account_id: str
    code: str
    side: Side
    quantity: int
    ok: bool
    status: str
    broker_order_id: str = ""
    message: str = ""
    reject_code: str = ""
    price_hint: Optional[float] = None
    price_mode: str = "fixed"
    l1_bid1: Optional[float] = None
    l1_ask1: Optional[float] = None
    l1_last_price: Optional[float] = None
    l1_ts: Optional[str] = None
    l1_source: str = ""


@dataclass(frozen=True)
class OrderState:
    """Persistent order state row for timeline/recovery."""

    ts: datetime
    client_order_id: str
    intent_id: str
    account_id: str
    code: str
    side: Side
    quantity: int
    status: str
    broker_order_id: str = ""
    message: str = ""
    price_hint: Optional[float] = None
    version: int = 1
    updated_at: Optional[datetime] = None
    terminal: bool = False
    source_event_id: str = ""
    retry_count: int = 0
    last_error_code: str = ""


@dataclass(frozen=True)
class TradeState:
    """Normalized trade row from broker adapter queries."""

    ts: datetime
    account_id: str
    broker_order_id: str
    trade_id: str
    code: str
    side: Side
    quantity: int
    price: Optional[float] = None


@dataclass(frozen=True)
class BrokerOrderIntent:
    """Prepared broker-order intent in reserved live path."""

    ts: datetime
    intent_id: str
    sim_order_id: str
    account_id: str
    code: str
    side: Side
    quantity: int
    price_hint: Optional[float] = None
    dry_run: bool = True
    guard_token_present: bool = False
    status: str = OrderStatus.PREPARED.value
    client_order_id: str = ""
    risk_ok: bool = True
    risk_code: str = ""
    risk_reason: str = ""
    broker_order_id: str = ""
    submit_message: str = ""
    price_mode: str = "fixed"
    l1_bid1: Optional[float] = None
    l1_ask1: Optional[float] = None
    l1_last_price: Optional[float] = None
    l1_ts: Optional[str] = None
    l1_source: str = ""


@dataclass(frozen=True)
class UnifiedSignal:
    """One normalized signal row from selector/risk/intraday sources."""

    signal_id: str
    asof: datetime
    kind: SignalKind
    source: str
    code: str
    side: Optional[Side] = None
    target_weight: Optional[float] = None
    delta_qty: Optional[int] = None
    priority: int = 100
    ttl_seconds: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UnifiedSignalBatch:
    """Batch wrapper for one as-of snapshot of normalized signals."""

    asof: datetime
    batch_id: str
    source_root: str
    signals: tuple[UnifiedSignal, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConflictDecision:
    """One conflict/reject decision produced by signal resolver."""

    ts: datetime
    plan_id: str
    signal_id: str
    code: str
    action: str
    reason: str
    blocked: bool = False


@dataclass(frozen=True)
class OrderPlaceRequest:
    """Request payload for one CLI/manual broker order."""

    account_id: str
    code: str
    side: Side
    quantity: int
    guard_token: str = ""
    price_mode: str = "l1_protect"
    limit_price: Optional[float] = None
    client_order_key: str = ""
    intent_id: str = ""
    plan_id: str = ""
    signal_id: str = ""
    strategy_tag: str = ""
    signal_kind: str = ""


@dataclass(frozen=True)
class RebalancePlanV2:
    """Resolved signal-driven rebalance plan."""

    plan_id: str
    asof: datetime
    account_id: str
    source: str
    baseline: str
    orders: tuple[OrderPlaceRequest, ...]
    signals: tuple[UnifiedSignal, ...] = ()
    conflicts: tuple[ConflictDecision, ...] = ()


@dataclass(frozen=True)
class TradeCommandResult:
    """Normalized result payload for CLI trade operations."""

    ok: bool
    code: str
    message: str
    account_id: str = ""
    broker_order_id: str = ""
    client_order_id: str = ""
    client_order_key: str = ""
    intent_id: str = ""
    status: str = ""
    l1_snapshot: Optional[L1Snapshot] = None
