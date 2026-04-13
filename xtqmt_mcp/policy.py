"""Data policy and runtime safety gates for xtqmt_mcp."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from .types import DataOrigin


class DataPolicyViolation(RuntimeError):
    """Raised when runtime data policy is violated."""


@dataclass(frozen=True)
class DataPolicy:
    """Policy enforcing online data for current trading day."""

    enforce_today_online: bool = True
    allow_today_pull: bool = True

    def validate(
        self,
        event_time: datetime,
        event_origin: DataOrigin,
        trading_day: date,
        context: Optional[str] = None,
    ) -> None:
        if not self.enforce_today_online:
            return
        if event_time.date() != trading_day:
            return
        if event_origin == DataOrigin.ONLINE_SUBSCRIBE:
            return
        if self.allow_today_pull and event_origin == DataOrigin.ONLINE_PULL:
            return
        suffix = f" ({context})" if context else ""
        raise DataPolicyViolation(
            "T0 market data must come from online subscribe or pull; "
            f"got {event_origin.value}{suffix}"
        )


