"""Order-state persistence for broker-order flow and recovery."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from threading import get_ident
from typing import Dict, List

from .types import OrderState, Side, is_terminal_order_status


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _to_iso(ts: datetime | None) -> str:
    value = ts or datetime.now()
    return value.isoformat()


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    token = str(value).strip().lower()
    if token in {"1", "true", "yes"}:
        return True
    if token in {"0", "false", "no"}:
        return False
    return bool(default)


def _normalize_state(state: OrderState, *, version: int | None = None, source_event_id: str = "") -> OrderState:
    normalized_version = max(1, int(version if version is not None else state.version))
    updated_at = state.updated_at or state.ts
    status = str(state.status or "").strip().lower()
    terminal = bool(state.terminal or is_terminal_order_status(status))
    return OrderState(
        ts=state.ts,
        client_order_id=str(state.client_order_id or ""),
        intent_id=str(state.intent_id or ""),
        account_id=str(state.account_id or ""),
        code=str(state.code or ""),
        side=state.side,
        quantity=int(state.quantity),
        status=status,
        broker_order_id=str(state.broker_order_id or ""),
        message=str(state.message or ""),
        price_hint=state.price_hint,
        version=normalized_version,
        updated_at=updated_at,
        terminal=terminal,
        source_event_id=str(state.source_event_id or source_event_id or ""),
        retry_count=max(0, int(state.retry_count)),
        last_error_code=str(state.last_error_code or ""),
    )


class JsonOrderStateStore:
    """Legacy JSON-based persistent store for order timeline states."""

    def __init__(self, state_dir: str) -> None:
        self.root = Path(state_dir)
        _ensure_dir(self.root)
        self.path = self.root / "order_state_timeline.json"

    def _load_payload(self) -> Dict:
        if not self.path.exists():
            return {"orders": []}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("orders"), list):
                return payload
        except Exception:
            pass
        return {"orders": []}

    def append(self, state: OrderState) -> None:
        payload = self._load_payload()
        orders = list(payload.get("orders") or [])
        normalized = _normalize_state(state)
        record = asdict(normalized)
        record["ts"] = normalized.ts.isoformat()
        record["updated_at"] = _to_iso(normalized.updated_at)
        record["side"] = normalized.side.value
        orders.append(record)
        payload["orders"] = orders
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_all(self) -> List[OrderState]:
        payload = self._load_payload()
        out: List[OrderState] = []
        for rec in list(payload.get("orders") or []):
            if not isinstance(rec, dict):
                continue
            try:
                state = OrderState(
                    ts=datetime.fromisoformat(str(rec.get("ts"))),
                    client_order_id=str(rec.get("client_order_id") or ""),
                    intent_id=str(rec.get("intent_id") or ""),
                    account_id=str(rec.get("account_id") or ""),
                    code=str(rec.get("code") or ""),
                    side=Side(str(rec.get("side") or "BUY")),
                    quantity=int(rec.get("quantity") or 0),
                    status=str(rec.get("status") or ""),
                    broker_order_id=str(rec.get("broker_order_id") or ""),
                    message=str(rec.get("message") or ""),
                    price_hint=float(rec.get("price_hint")) if rec.get("price_hint") is not None else None,
                    version=_as_int(rec.get("version"), 1),
                    updated_at=(
                        datetime.fromisoformat(str(rec.get("updated_at")))
                        if rec.get("updated_at")
                        else None
                    ),
                    terminal=_as_bool(rec.get("terminal"), False),
                    source_event_id=str(rec.get("source_event_id") or ""),
                    retry_count=_as_int(rec.get("retry_count"), 0),
                    last_error_code=str(rec.get("last_error_code") or ""),
                )
                out.append(_normalize_state(state))
            except Exception:
                continue
        return out

    def latest_by_client_order_id(self) -> Dict[str, OrderState]:
        states = self.load_all()
        latest: Dict[str, OrderState] = {}
        for state in states:
            key = str(state.client_order_id or "").strip()
            if not key:
                continue
            latest[key] = state
        return latest


class SQLiteOrderStateStore:
    """SQLite-based persistent store for order timeline states."""

    def __init__(self, state_dir: str) -> None:
        self.root = Path(state_dir)
        _ensure_dir(self.root)
        self.path = self.root / "order_state_timeline.sqlite3"
        self._owner_thread_id = int(get_ident())
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._init_schema()

    def _assert_owner_thread(self) -> None:
        current_thread_id = int(get_ident())
        if current_thread_id != self._owner_thread_id:
            raise RuntimeError(
                "SQLiteOrderStateStore must be used on its owner thread "
                f"(owner={self._owner_thread_id}, current={current_thread_id})"
            )

    def _init_schema(self) -> None:
        self._assert_owner_thread()
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS order_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                client_order_id TEXT NOT NULL,
                intent_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                code TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                status TEXT NOT NULL,
                broker_order_id TEXT NOT NULL,
                message TEXT NOT NULL,
                price_hint REAL,
                version INTEGER NOT NULL,
                terminal INTEGER NOT NULL,
                source_event_id TEXT NOT NULL,
                retry_count INTEGER NOT NULL,
                last_error_code TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_order_states_client_order_id
            ON order_states(client_order_id, id)
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_order_states_broker_order_id
            ON order_states(broker_order_id, id)
            """
        )
        self._conn.commit()

    def _row_to_state(self, row: sqlite3.Row | tuple) -> OrderState:
        if isinstance(row, sqlite3.Row):
            rec = dict(row)
        else:
            rec = {
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
        return _normalize_state(
            OrderState(
                ts=datetime.fromisoformat(str(rec.get("ts"))),
                updated_at=datetime.fromisoformat(str(rec.get("updated_at"))),
                client_order_id=str(rec.get("client_order_id") or ""),
                intent_id=str(rec.get("intent_id") or ""),
                account_id=str(rec.get("account_id") or ""),
                code=str(rec.get("code") or ""),
                side=Side(str(rec.get("side") or "BUY")),
                quantity=_as_int(rec.get("quantity"), 0),
                status=str(rec.get("status") or ""),
                broker_order_id=str(rec.get("broker_order_id") or ""),
                message=str(rec.get("message") or ""),
                price_hint=_as_float(rec.get("price_hint")),
                version=_as_int(rec.get("version"), 1),
                terminal=_as_bool(rec.get("terminal"), False),
                source_event_id=str(rec.get("source_event_id") or ""),
                retry_count=_as_int(rec.get("retry_count"), 0),
                last_error_code=str(rec.get("last_error_code") or ""),
            )
        )

    def append(self, state: OrderState, *, source_event_id: str = "") -> OrderState:
        self._assert_owner_thread()
        latest = self.get_latest(str(state.client_order_id or ""))
        version = int(latest.version + 1) if latest is not None else 1
        normalized = _normalize_state(state, version=version, source_event_id=source_event_id)
        self._conn.execute(
            """
            INSERT INTO order_states (
                ts, updated_at, client_order_id, intent_id, account_id, code, side, quantity, status,
                broker_order_id, message, price_hint, version, terminal, source_event_id, retry_count, last_error_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized.ts.isoformat(),
                _to_iso(normalized.updated_at),
                normalized.client_order_id,
                normalized.intent_id,
                normalized.account_id,
                normalized.code,
                normalized.side.value,
                int(normalized.quantity),
                normalized.status,
                normalized.broker_order_id,
                normalized.message,
                normalized.price_hint,
                int(normalized.version),
                int(1 if normalized.terminal else 0),
                normalized.source_event_id,
                int(normalized.retry_count),
                normalized.last_error_code,
            ),
        )
        self._conn.commit()
        return normalized

    def load_all(self) -> List[OrderState]:
        self._assert_owner_thread()
        cur = self._conn.execute(
            """
            SELECT ts, updated_at, client_order_id, intent_id, account_id, code, side, quantity, status,
                   broker_order_id, message, price_hint, version, terminal, source_event_id, retry_count, last_error_code
            FROM order_states
            ORDER BY id ASC
            """
        )
        return [self._row_to_state(row) for row in cur.fetchall()]

    def get_latest(self, client_order_id: str) -> OrderState | None:
        self._assert_owner_thread()
        key = str(client_order_id or "").strip()
        if not key:
            return None
        cur = self._conn.execute(
            """
            SELECT ts, updated_at, client_order_id, intent_id, account_id, code, side, quantity, status,
                   broker_order_id, message, price_hint, version, terminal, source_event_id, retry_count, last_error_code
            FROM order_states
            WHERE client_order_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (key,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_state(row)

    def latest_by_client_order_id(self) -> Dict[str, OrderState]:
        self._assert_owner_thread()
        out: Dict[str, OrderState] = {}
        for state in self.load_all():
            key = str(state.client_order_id or "").strip()
            if not key:
                continue
            out[key] = state
        return out

    def migrate_from_json(self) -> int:
        self._assert_owner_thread()
        legacy = JsonOrderStateStore(str(self.root))
        if not legacy.path.exists():
            return 0
        existing_count = int(
            self._conn.execute("SELECT COUNT(1) FROM order_states").fetchone()[0]  # type: ignore[index]
        )
        if existing_count > 0:
            return 0
        migrated = 0
        for state in legacy.load_all():
            self.append(state, source_event_id="legacy_json_migration")
            migrated += 1
        return migrated

    def close(self) -> None:
        self._assert_owner_thread()
        try:
            self._conn.close()
        except Exception:
            pass
