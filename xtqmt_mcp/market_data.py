"""Market data provider using xtquant.xtdata with policy-safe behavior."""

from __future__ import annotations

import os
import queue
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from .policy import DataPolicy
from .types import DataOrigin, EventKind, MarketEvent
from .xtquant_env import ensure_xtquant_on_path


def _configure_xtdata_dir(xtdata) -> None:
    data_dir = os.environ.get("QMT_DATA_DIR") or os.environ.get("XTDATA_DIR")
    if data_dir:
        try:
            xtdata.data_dir = data_dir
        except Exception:
            pass


def _require_xtdata():
    try:
        from xtquant import xtdata  # type: ignore

        _configure_xtdata_dir(xtdata)
        return xtdata
    except Exception:
        pass
    ensure_xtquant_on_path()
    sys.modules.pop("xtquant", None)
    sys.modules.pop("xtquant.xtdata", None)
    from xtquant import xtdata  # type: ignore

    _configure_xtdata_dir(xtdata)
    return xtdata


def _to_timestamp(raw) -> datetime:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, (np.datetime64, pd.Timestamp)):
        return pd.Timestamp(raw).to_pydatetime()
    if isinstance(raw, str):
        dt = pd.to_datetime(raw, errors="coerce")
        if pd.isna(dt):
            return datetime.now()
        return pd.Timestamp(dt).to_pydatetime()
    if isinstance(raw, (int, np.integer, float, np.floating)):
        val = int(float(raw))
        digits = len(str(abs(val)))
        if digits in {17, 14, 8}:
            if digits == 17:
                dt = pd.to_datetime(str(val), format="%Y%m%d%H%M%S%f", errors="coerce")
            elif digits == 14:
                dt = pd.to_datetime(str(val), format="%Y%m%d%H%M%S", errors="coerce")
            else:
                dt = pd.to_datetime(str(val), format="%Y%m%d", errors="coerce")
            if not pd.isna(dt):
                return pd.Timestamp(dt).to_pydatetime()
        if val > 1e12:
            dt = pd.to_datetime(val, unit="ms", utc=True).tz_convert("Asia/Shanghai").tz_localize(None)
            return pd.Timestamp(dt).to_pydatetime()
        if val > 1e9:
            dt = pd.to_datetime(val, unit="s", utc=True).tz_convert("Asia/Shanghai").tz_localize(None)
            return pd.Timestamp(dt).to_pydatetime()
    return datetime.now()


def _price_levels(raw) -> list[Optional[float]]:
    if raw is None:
        return []
    if isinstance(raw, np.ndarray):
        values = raw.tolist()
    elif isinstance(raw, (list, tuple)):
        values = list(raw)
    else:
        return []
    out: list[Optional[float]] = []
    for item in values:
        try:
            out.append(float(item))
        except Exception:
            out.append(None)
    return out


def _extract_price_level(item: dict, prefix: str, level: int) -> Optional[float]:
    direct = item.get(f"{prefix}Price{level}")
    if direct is not None:
        try:
            return float(direct)
        except Exception:
            return None
    values = _price_levels(item.get(f"{prefix}Price"))
    idx = max(0, int(level) - 1)
    if idx < len(values):
        return values[idx]
    return None


def _extract_tick_payload(payload) -> tuple[
    Optional[float],
    Optional[datetime],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
]:
    if payload is None:
        return None, None, None, None, None, None, None, None, None, None, None, None, None
    if isinstance(payload, np.ndarray):
        if payload.size == 0:
            return None, None, None, None, None, None, None, None, None, None, None, None, None
        last = payload[-1]
        if payload.dtype.names:
            fields = set(payload.dtype.names or [])
            last_price = float(last["lastPrice"]) if "lastPrice" in fields else None
            time_val = _to_timestamp(last["time"]) if "time" in fields else None
            bid_levels = _price_levels(last["bidPrice"]) if "bidPrice" in fields else []
            ask_levels = _price_levels(last["askPrice"]) if "askPrice" in fields else []
            bid1 = bid_levels[0] if len(bid_levels) > 0 else None
            bid2 = bid_levels[1] if len(bid_levels) > 1 else None
            bid3 = bid_levels[2] if len(bid_levels) > 2 else None
            bid4 = bid_levels[3] if len(bid_levels) > 3 else None
            bid5 = bid_levels[4] if len(bid_levels) > 4 else None
            ask1 = ask_levels[0] if len(ask_levels) > 0 else None
            ask2 = ask_levels[1] if len(ask_levels) > 1 else None
            ask3 = ask_levels[2] if len(ask_levels) > 2 else None
            ask4 = ask_levels[3] if len(ask_levels) > 3 else None
            ask5 = ask_levels[4] if len(ask_levels) > 4 else None
            prev_close = float(last["lastClose"]) if "lastClose" in fields else None
            return last_price, time_val, bid1, bid2, bid3, bid4, bid5, ask1, ask2, ask3, ask4, ask5, prev_close
    if isinstance(payload, (list, tuple)) and payload:
        item = payload[-1]
        if isinstance(item, dict):
            lp = item.get("lastPrice")
            tm = item.get("time")
            if tm is None:
                tm = item.get("timetag")
            bid1 = _extract_price_level(item, "bid", 1)
            bid2 = _extract_price_level(item, "bid", 2)
            bid3 = _extract_price_level(item, "bid", 3)
            bid4 = _extract_price_level(item, "bid", 4)
            bid5 = _extract_price_level(item, "bid", 5)
            ask1 = _extract_price_level(item, "ask", 1)
            ask2 = _extract_price_level(item, "ask", 2)
            ask3 = _extract_price_level(item, "ask", 3)
            ask4 = _extract_price_level(item, "ask", 4)
            ask5 = _extract_price_level(item, "ask", 5)
            return (
                float(lp) if lp is not None else None,
                _to_timestamp(tm) if tm is not None else None,
                bid1,
                bid2,
                bid3,
                bid4,
                bid5,
                ask1,
                ask2,
                ask3,
                ask4,
                ask5,
                float(item.get("lastClose")) if item.get("lastClose") is not None else None,
            )
    if isinstance(payload, dict):
        lp = payload.get("lastPrice")
        tm = payload.get("time")
        if tm is None:
            tm = payload.get("timetag")
        bid1 = _extract_price_level(payload, "bid", 1)
        bid2 = _extract_price_level(payload, "bid", 2)
        bid3 = _extract_price_level(payload, "bid", 3)
        bid4 = _extract_price_level(payload, "bid", 4)
        bid5 = _extract_price_level(payload, "bid", 5)
        ask1 = _extract_price_level(payload, "ask", 1)
        ask2 = _extract_price_level(payload, "ask", 2)
        ask3 = _extract_price_level(payload, "ask", 3)
        ask4 = _extract_price_level(payload, "ask", 4)
        ask5 = _extract_price_level(payload, "ask", 5)
        return (
            float(lp) if lp is not None else None,
            _to_timestamp(tm) if tm is not None else None,
            bid1,
            bid2,
            bid3,
            bid4,
            bid5,
            ask1,
            ask2,
            ask3,
            ask4,
            ask5,
            float(payload.get("lastClose")) if payload.get("lastClose") is not None else None,
        )
    return None, None, None, None, None, None, None, None, None, None, None, None, None


def _tick_payload_available(payload) -> bool:
    if payload is None:
        return False
    if isinstance(payload, np.ndarray):
        return bool(payload.size)
    try:
        return len(payload) > 0  # type: ignore[arg-type]
    except Exception:
        return True


def _query_tick_payload(xtdata, code: str, date_str: str):
    data = xtdata.get_market_data(
        field_list=["lastPrice", "lastClose", "open", "time", "bidPrice", "askPrice"],
        stock_list=[code],
        period="tick",
        start_time=date_str,
        end_time=date_str,
        count=-1,
        dividend_type="none",
        fill_data=False,
    )
    return data.get(code) if isinstance(data, dict) else None


def _subscribe_tick_stream(xtdata, code: str) -> int | None:
    subscribe_attempts = []
    subscribe_quote2 = getattr(xtdata, "subscribe_quote2", None)
    if callable(subscribe_quote2):
        subscribe_attempts.extend(
            [
                lambda: subscribe_quote2(
                    stock_code=code,
                    period="tick",
                    start_time="",
                    end_time="",
                    count=0,
                    dividend_type="none",
                    callback=None,
                ),
                lambda: subscribe_quote2(code, "tick", "", "", 0, "none", None),
                lambda: subscribe_quote2(code, "tick", "", "", 0, None, None),
            ]
        )

    subscribe_quote = getattr(xtdata, "subscribe_quote", None)
    if callable(subscribe_quote):
        subscribe_attempts.extend(
            [
                lambda: subscribe_quote(
                    stock_code=code,
                    period="tick",
                    start_time="",
                    end_time="",
                    count=0,
                    callback=None,
                ),
                lambda: subscribe_quote(code, "tick", "", "", 0, None),
            ]
        )

    for subscribe_once in subscribe_attempts:
        try:
            seq = int(subscribe_once())
        except TypeError:
            continue
        except Exception:
            continue
        if seq > 0:
            return seq
    return None


def _unsubscribe_tick_stream(xtdata, seq: int | None) -> None:
    if seq is None or seq <= 0:
        return
    unsubscribe_quote = getattr(xtdata, "unsubscribe_quote", None)
    if not callable(unsubscribe_quote):
        return
    try:
        unsubscribe_quote(int(seq))
    except Exception:
        pass


class XtQuantMarketDataProvider:
    """Market data provider with strict T0 online policy."""

    def __init__(self, policy: DataPolicy, idle_timeout_seconds: float = 30.0) -> None:
        self.policy = policy
        self.idle_timeout_seconds = max(float(idle_timeout_seconds), 1.0)

    def load_history(
        self,
        codes: Sequence[str],
        start_date: date,
        end_date: date,
        freq: str,
    ) -> Dict[str, pd.DataFrame]:
        xtdata = _require_xtdata()
        period = "1d" if freq.lower() in {"1d", "day", "daily"} else "1m"
        data = xtdata.get_market_data_ex(
            field_list=["open", "high", "low", "close", "volume", "amount"],
            stock_list=list(codes),
            period=period,
            start_time=pd.Timestamp(start_date).strftime("%Y%m%d"),
            end_time=pd.Timestamp(end_date).strftime("%Y%m%d"),
            count=-1,
            dividend_type="none",
            fill_data=False,
        )
        out: Dict[str, pd.DataFrame] = {}
        for code in codes:
            df = data.get(code) if data else None
            if df is None or df.empty:
                continue
            cpy = df.copy()
            cpy.index = pd.to_datetime(cpy.index.astype(str), errors="coerce")
            cpy = cpy[cpy.index.notna()].sort_index()
            out[code] = cpy
        return out

    def latest_online_event(
        self,
        code: str,
        trading_day: date,
        mode: str,
    ) -> Optional[MarketEvent]:
        xtdata = _require_xtdata()
        period = "tick" if mode in {"tick", "hybrid_tick"} else "1m"
        date_str = pd.Timestamp(trading_day).strftime("%Y%m%d")
        if period == "tick":
            try:
                full_tick = xtdata.get_full_tick([code])
                full_tick_payload = full_tick.get(code) if isinstance(full_tick, dict) else None
            except Exception:
                full_tick_payload = None
            if _tick_payload_available(full_tick_payload):
                (
                    last_price,
                    ts,
                    bid1,
                    bid2,
                    bid3,
                    bid4,
                    bid5,
                    ask1,
                    ask2,
                    ask3,
                    ask4,
                    ask5,
                    prev_close,
                ) = _extract_tick_payload(full_tick_payload)
                if last_price is not None and ts is not None:
                    self.policy.validate(ts, DataOrigin.GET_FULL_TICK, trading_day, context=f"latest_online_event:{code}")
                    return MarketEvent(
                        code=code,
                        ts=ts,
                        last_price=float(last_price),
                        source=DataOrigin.GET_FULL_TICK,
                        kind=EventKind.TICK,
                        bid1=bid1,
                        bid2=bid2,
                        bid3=bid3,
                        bid4=bid4,
                        bid5=bid5,
                        ask1=ask1,
                        ask2=ask2,
                        ask3=ask3,
                        ask4=ask4,
                        ask5=ask5,
                        prev_close=prev_close,
                    )
            subscribe_seq = _subscribe_tick_stream(xtdata, code)
            payload = None
            event_source = DataOrigin.ONLINE_PULL
            try:
                for attempt in range(3):
                    payload = _query_tick_payload(xtdata, code, date_str)
                    if _tick_payload_available(payload):
                        if subscribe_seq is not None:
                            event_source = DataOrigin.ONLINE_SUBSCRIBE
                        break
                    if attempt < 2:
                        time.sleep(0.2)
            except Exception:
                payload = None
            finally:
                _unsubscribe_tick_stream(xtdata, subscribe_seq)

            if not _tick_payload_available(payload):
                try:
                    full_tick = xtdata.get_full_tick([code])
                    full_tick_payload = full_tick.get(code) if isinstance(full_tick, dict) else None
                    if _tick_payload_available(full_tick_payload):
                        payload = full_tick_payload
                        event_source = DataOrigin.GET_FULL_TICK
                except Exception:
                    pass
            (
                last_price,
                ts,
                bid1,
                bid2,
                bid3,
                bid4,
                bid5,
                ask1,
                ask2,
                ask3,
                ask4,
                ask5,
                prev_close,
            ) = _extract_tick_payload(payload)
            if last_price is None or ts is None:
                return None
            self.policy.validate(ts, event_source, trading_day, context=f"latest_online_event:{code}")
            return MarketEvent(
                code=code,
                ts=ts,
                last_price=float(last_price),
                source=event_source,
                kind=EventKind.TICK,
                bid1=bid1,
                bid2=bid2,
                bid3=bid3,
                bid4=bid4,
                bid5=bid5,
                ask1=ask1,
                ask2=ask2,
                ask3=ask3,
                ask4=ask4,
                ask5=ask5,
                prev_close=prev_close,
            )
        data = xtdata.get_market_data_ex(
            field_list=["close", "open"],
            stock_list=[code],
            period="1m",
            start_time=date_str,
            end_time=date_str,
            count=-1,
            dividend_type="none",
            fill_data=False,
        )
        df = data.get(code) if data else None
        if df is None or df.empty:
            return None
        cpy = df.copy()
        cpy.index = pd.to_datetime(cpy.index.astype(str), errors="coerce")
        cpy = cpy[cpy.index.notna()].sort_index()
        if cpy.empty:
            return None
        ts = pd.Timestamp(cpy.index[-1]).to_pydatetime()
        px = float(pd.to_numeric(cpy.iloc[-1].get("close"), errors="coerce"))
        self.policy.validate(ts, DataOrigin.ONLINE_PULL, trading_day, context=f"latest_online_event:{code}")
        return MarketEvent(
            code=code,
            ts=ts,
            last_price=px,
            source=DataOrigin.ONLINE_PULL,
            kind=EventKind.MINUTE,
        )

    def subscribe_today(
        self,
        codes: Sequence[str],
        trading_day: date,
        mode: str,
    ) -> Iterable[MarketEvent]:
        xtdata = _require_xtdata()
        date_str = pd.Timestamp(trading_day).strftime("%Y%m%d")
        event_queue: queue.Queue[MarketEvent] = queue.Queue()
        seqs: List[int] = []
        period = "tick" if mode in {"tick", "hybrid_tick"} else "1m"

        def on_data(datas):
            if not isinstance(datas, dict):
                return
            for code, payload in datas.items():
                if code not in codes:
                    continue
                if period == "tick":
                    (
                        last_price,
                        ts,
                        bid1,
                        bid2,
                        bid3,
                        bid4,
                        bid5,
                        ask1,
                        ask2,
                        ask3,
                        ask4,
                        ask5,
                        prev_close,
                    ) = _extract_tick_payload(payload)
                    if last_price is None or ts is None:
                        continue
                    try:
                        self.policy.validate(ts, DataOrigin.ONLINE_SUBSCRIBE, trading_day, context=f"subscribe:{code}")
                    except Exception:
                        continue
                    event_queue.put(
                        MarketEvent(
                            code=code,
                            ts=ts,
                            last_price=float(last_price),
                            source=DataOrigin.ONLINE_SUBSCRIBE,
                            kind=EventKind.TICK,
                            bid1=bid1,
                            bid2=bid2,
                            bid3=bid3,
                            bid4=bid4,
                            bid5=bid5,
                            ask1=ask1,
                            ask2=ask2,
                            ask3=ask3,
                            ask4=ask4,
                            ask5=ask5,
                            prev_close=prev_close,
                        )
                    )
                    continue
                df = payload if isinstance(payload, pd.DataFrame) else None
                if df is None or df.empty:
                    continue
                cpy = df.copy()
                cpy.index = pd.to_datetime(cpy.index.astype(str), errors="coerce")
                cpy = cpy[cpy.index.notna()].sort_index()
                if cpy.empty:
                    continue
                ts = pd.Timestamp(cpy.index[-1]).to_pydatetime()
                close_val = pd.to_numeric(cpy.iloc[-1].get("close"), errors="coerce")
                if pd.isna(close_val):
                    continue
                try:
                    self.policy.validate(ts, DataOrigin.ONLINE_SUBSCRIBE, trading_day, context=f"subscribe:{code}")
                except Exception:
                    continue
                event_queue.put(
                    MarketEvent(
                        code=code,
                        ts=ts,
                        last_price=float(close_val),
                        source=DataOrigin.ONLINE_SUBSCRIBE,
                        kind=EventKind.MINUTE,
                    )
                )

        for code in codes:
            try:
                if hasattr(xtdata, "subscribe_quote2"):
                    seq = xtdata.subscribe_quote2(
                        stock_code=code,
                        period=period,
                        start_time=date_str,
                        end_time=date_str,
                        count=0,
                        dividend_type="none",
                        callback=on_data,
                    )
                else:
                    seq = xtdata.subscribe_quote(
                        stock_code=code,
                        period=period,
                        start_time=date_str,
                        end_time=date_str,
                        count=0,
                        callback=on_data,
                    )
            except Exception:
                seq = -1
            if seq and seq > 0:
                seqs.append(seq)

        idle_since = time.monotonic()
        try:
            while True:
                try:
                    event = event_queue.get(timeout=1.0)
                except queue.Empty:
                    if (time.monotonic() - idle_since) >= self.idle_timeout_seconds:
                        break
                    continue
                idle_since = time.monotonic()
                yield event
        finally:
            for seq in seqs:
                try:
                    xtdata.unsubscribe_quote(seq)
                except Exception:
                    continue
