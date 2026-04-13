"""Cross-day history query service with broker-first/local-fallback policy."""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable


def _safe_get(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row.get(key)
    return None


def _safe_date(raw: Any) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    text = str(raw).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except Exception:
        return None


def _safe_dt(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _parse_day_dir(name: str) -> date | None:
    token = str(name or "").strip()
    if len(token) != 8 or (not token.isdigit()):
        return None
    try:
        return datetime.strptime(token, "%Y%m%d").date()
    except Exception:
        return None


def _table_rows(table: Any) -> list[dict[str, Any]]:
    if table is None:
        return []
    if isinstance(table, list):
        return [dict(item) for item in table if isinstance(item, dict)]
    to_dict = getattr(table, "to_dict", None)
    if callable(to_dict):
        try:
            rows = to_dict(orient="records")
            if isinstance(rows, list):
                return [dict(item) for item in rows if isinstance(item, dict)]
        except Exception:
            return []
    return []


@dataclass(frozen=True)
class HistoryQueryConfig:
    account_id: str
    start_date: date
    end_date: date
    output_roots: tuple[str, ...] = ("output", "output_e2e", "output_live_smoke", "output_trade_ops")
    state_roots: tuple[str, ...] = ("state", "state_e2e", "state_live_smoke", "state_trade_ops")
    prefer_broker: bool = True
    fallback_local: bool = True


class HistoryService:
    """Query cross-day order/trade/position history with broker-first policy."""

    def __init__(self, cfg: HistoryQueryConfig, *, shadow_adapter: Any = None) -> None:
        self.cfg = cfg
        self.shadow = shadow_adapter

    def query_orders_history(self) -> dict[str, Any]:
        return self._query(
            entity="orders",
            broker_loader=self._load_broker_orders,
            local_loader=self._load_local_orders,
            dedupe=self._dedupe_orders,
        )

    def query_trades_history(self) -> dict[str, Any]:
        return self._query(
            entity="trades",
            broker_loader=self._load_broker_trades,
            local_loader=self._load_local_trades,
            dedupe=self._dedupe_trades,
        )

    def query_positions_history(self) -> dict[str, Any]:
        return self._query(
            entity="positions",
            broker_loader=self._load_broker_positions,
            local_loader=self._load_local_positions,
            dedupe=self._dedupe_positions,
        )

    def _query(
        self,
        *,
        entity: str,
        broker_loader: Callable[[], list[dict[str, Any]]],
        local_loader: Callable[[], list[dict[str, Any]]],
        dedupe: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    ) -> dict[str, Any]:
        today = datetime.now().date()
        broker_attempted = bool(self.cfg.prefer_broker)
        notes: list[str] = []
        broker_rows: list[dict[str, Any]] = []
        if broker_attempted:
            try:
                broker_rows = broker_loader()
            except Exception as exc:
                broker_rows = []
                notes.append(f"broker_read_failed:{exc}")
        broker_rows = [row for row in broker_rows if self._in_range(row, fallback_date=today)]

        load_local = bool(self.cfg.fallback_local and (not broker_rows or (self.cfg.start_date != self.cfg.end_date)))
        local_rows: list[dict[str, Any]] = []
        if load_local:
            try:
                local_rows = local_loader()
            except Exception as exc:
                local_rows = []
                notes.append(f"local_read_failed:{exc}")

        merged = dedupe(local_rows + broker_rows)
        merged.sort(key=lambda row: str(row.get("_record_ts", row.get("_record_date", ""))))

        if broker_rows and local_rows:
            source = "hybrid"
        elif broker_rows:
            source = "broker"
        elif local_rows or load_local:
            source = "local"
        else:
            source = "broker" if broker_attempted else "local"
        return {
            "ok": True,
            "entity": entity,
            "start_date": self.cfg.start_date.isoformat(),
            "end_date": self.cfg.end_date.isoformat(),
            "source": source,
            "rows": merged,
            "meta": {
                "broker_attempted": broker_attempted,
                "broker_row_count": len(broker_rows),
                "local_row_count": len(local_rows),
                "fallback_used": bool(load_local),
                "notes": notes,
            },
        }

    def _in_range(self, row: dict[str, Any], *, fallback_date: date) -> bool:
        d = self._record_date(row, fallback_date=fallback_date)
        return bool(self.cfg.start_date <= d <= self.cfg.end_date)

    def _record_date(self, row: dict[str, Any], *, fallback_date: date) -> date:
        for key in ("_record_ts", "ts", "updated_at", "traded_time", "l1_ts", "date", "trading_day", "_record_date"):
            parsed = _safe_date(row.get(key))
            if parsed is not None:
                return parsed
        return fallback_date

    def _enrich_row(
        self,
        row: dict[str, Any],
        *,
        fallback_date: date,
        source_file: str = "",
    ) -> dict[str, Any]:
        out = dict(row)
        d = self._record_date(out, fallback_date=fallback_date)
        ts = None
        for key in ("_record_ts", "ts", "updated_at", "traded_time", "l1_ts"):
            ts = _safe_dt(out.get(key))
            if ts is not None:
                break
        out["_record_date"] = d.isoformat()
        out["_record_ts"] = (ts.isoformat() if ts is not None else f"{d.isoformat()}T00:00:00")
        if source_file:
            out["_source_file"] = source_file
        return out

    def _account_match(self, row: dict[str, Any]) -> bool:
        expected = str(self.cfg.account_id or "").strip()
        if not expected:
            return True
        actual = str(_safe_get(row, "account_id", "accountId") or "").strip()
        return (not actual) or (actual == expected)

    def _load_broker_orders(self) -> list[dict[str, Any]]:
        if self.shadow is None:
            return []
        rows = _table_rows(self.shadow.get_orders())
        out: list[dict[str, Any]] = []
        today = datetime.now().date()
        for row in rows:
            if not self._account_match(row):
                continue
            out.append(self._enrich_row(row, fallback_date=today, source_file="broker:get_orders"))
        return out

    def _load_broker_trades(self) -> list[dict[str, Any]]:
        if self.shadow is None:
            return []
        rows = _table_rows(self.shadow.get_trades())
        out: list[dict[str, Any]] = []
        today = datetime.now().date()
        for row in rows:
            if not self._account_match(row):
                continue
            out.append(self._enrich_row(row, fallback_date=today, source_file="broker:get_trades"))
        return out

    def _load_broker_positions(self) -> list[dict[str, Any]]:
        if self.shadow is None:
            return []
        rows = _table_rows(self.shadow.get_positions())
        out: list[dict[str, Any]] = []
        today = datetime.now().date()
        for row in rows:
            if not self._account_match(row):
                continue
            out.append(self._enrich_row(row, fallback_date=today, source_file="broker:get_positions"))
        return out

    def _iter_output_days(self) -> list[tuple[date, Path]]:
        out: list[tuple[date, Path]] = []
        for root_token in self.cfg.output_roots:
            root = Path(str(root_token or "").strip())
            if (not root) or (not root.exists()) or (not root.is_dir()):
                continue
            for child in root.iterdir():
                if not child.is_dir():
                    continue
                day = _parse_day_dir(child.name)
                if day is None:
                    continue
                if self.cfg.start_date <= day <= self.cfg.end_date:
                    out.append((day, child))
        return out

    def _read_csv(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8", newline="") as fd:
                reader = csv.DictReader(fd)
                for row in reader:
                    if isinstance(row, dict):
                        rows.append({str(k): v for k, v in row.items()})
        except Exception:
            return []
        return rows

    def _load_local_orders(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        rels = (
            "real/orders_real.csv",
            "real/orders_submit_log.csv",
            "real/orders_state_timeline.csv",
            "real/order_intents_real.csv",
            "real/signal_execution_log.csv",
        )
        for day, day_dir in self._iter_output_days():
            for rel in rels:
                path = day_dir / rel
                for row in self._read_csv(path):
                    if not self._account_match(row):
                        continue
                    out.append(self._enrich_row(row, fallback_date=day, source_file=str(path)))
        out.extend(self._load_state_order_history())
        return [row for row in out if self._in_range(row, fallback_date=self.cfg.start_date)]

    def _load_local_trades(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for day, day_dir in self._iter_output_days():
            path = day_dir / "real/trades_real.csv"
            for row in self._read_csv(path):
                if not self._account_match(row):
                    continue
                out.append(self._enrich_row(row, fallback_date=day, source_file=str(path)))
        return [row for row in out if self._in_range(row, fallback_date=self.cfg.start_date)]

    def _load_local_positions(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for day, day_dir in self._iter_output_days():
            path = day_dir / "real/positions_real.csv"
            for row in self._read_csv(path):
                if not self._account_match(row):
                    continue
                out.append(self._enrich_row(row, fallback_date=day, source_file=str(path)))
        return [row for row in out if self._in_range(row, fallback_date=self.cfg.start_date)]

    def _load_state_order_history(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for root_token in self.cfg.state_roots:
            root = Path(str(root_token or "").strip())
            db_path = root / "order_state_timeline.sqlite3"
            if not db_path.exists():
                continue
            try:
                conn = sqlite3.connect(str(db_path))
                cur = conn.execute(
                    """
                    SELECT ts, updated_at, client_order_id, intent_id, account_id, code, side, quantity,
                           status, broker_order_id, message, price_hint, version, terminal, source_event_id,
                           retry_count, last_error_code
                    FROM order_states
                    """
                )
                rows = cur.fetchall()
            except Exception:
                rows = []
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
            for row in rows:
                item = {
                    "ts": row[0],
                    "updated_at": row[1],
                    "client_order_id": row[2],
                    "intent_id": row[3],
                    "account_id": row[4],
                    "code": row[5],
                    "side": row[6],
                    "quantity": row[7],
                    "status": row[8],
                    "broker_order_id": row[9],
                    "message": row[10],
                    "price_hint": row[11],
                    "version": row[12],
                    "terminal": row[13],
                    "source_event_id": row[14],
                    "retry_count": row[15],
                    "last_error_code": row[16],
                }
                if not self._account_match(item):
                    continue
                item = self._enrich_row(item, fallback_date=self.cfg.start_date, source_file=str(db_path))
                if self._in_range(item, fallback_date=self.cfg.start_date):
                    out.append(item)
        return out

    def _dedupe_orders(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        keep: dict[str, dict[str, Any]] = {}
        for row in rows:
            oid = str(_safe_get(row, "broker_order_id", "order_id", "orderId") or "").strip()
            cid = str(_safe_get(row, "client_order_id", "clientOrderId") or "").strip()
            code = str(_safe_get(row, "code", "stock_code", "stockCode") or "").strip()
            status = str(_safe_get(row, "status", "order_status", "orderStatus") or "").strip()
            qty = str(_safe_get(row, "quantity", "order_volume", "orderVolume") or "").strip()
            side = str(_safe_get(row, "side", "order_type", "orderType") or "").strip()
            ts = str(row.get("_record_ts", ""))
            key = oid or f"{cid}|{code}|{status}|{qty}|{side}|{ts}"
            old = keep.get(key)
            if old is None or str(old.get("_record_ts", "")) <= ts:
                keep[key] = row
        return list(keep.values())

    def _dedupe_trades(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        keep: dict[str, dict[str, Any]] = {}
        for row in rows:
            tid = str(_safe_get(row, "trade_id", "traded_id", "tradedId") or "").strip()
            oid = str(_safe_get(row, "broker_order_id", "order_id", "orderId") or "").strip()
            code = str(_safe_get(row, "code", "stock_code", "stockCode") or "").strip()
            qty = str(_safe_get(row, "quantity", "traded_volume", "tradedVolume") or "").strip()
            tts = str(_safe_get(row, "traded_time", "ts") or "").strip()
            ts = str(row.get("_record_ts", ""))
            key = tid or f"{oid}|{code}|{qty}|{tts}|{ts}"
            old = keep.get(key)
            if old is None or str(old.get("_record_ts", "")) <= ts:
                keep[key] = row
        return list(keep.values())

    def _dedupe_positions(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        keep: dict[str, dict[str, Any]] = {}
        for row in rows:
            d = str(row.get("_record_date", ""))
            code = str(_safe_get(row, "code", "stock_code", "stockCode") or "").strip()
            acc = str(_safe_get(row, "account_id", "accountId") or self.cfg.account_id or "").strip()
            ts = str(row.get("_record_ts", ""))
            key = f"{d}|{acc}|{code}"
            old = keep.get(key)
            if old is None or str(old.get("_record_ts", "")) <= ts:
                keep[key] = row
        return list(keep.values())
