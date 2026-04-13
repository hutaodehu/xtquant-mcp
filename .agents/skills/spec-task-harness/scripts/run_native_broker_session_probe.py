from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xtqmt_mcp.xtquant_env import ensure_xtquant_on_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded native broker/session probes for controller direct test.")
    parser.add_argument("--user-data-path", required=True)
    parser.add_argument("--sessions", default="")
    parser.add_argument("--account-id", default="")
    parser.add_argument("--report-json", default="")
    return parser.parse_args()


def iso_now() -> str:
    return datetime.now().astimezone().isoformat()


def safe_attr(obj: Any, *names: str) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj.get(name)
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def parse_sessions(raw: Any) -> list[int]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        source = list(raw)
    else:
        text = str(raw or "").strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None
            if isinstance(parsed, list):
                source = parsed
            else:
                source = text.split(",")
        else:
            source = text.split(",")
    out: list[int] = []
    seen: set[int] = set()
    for token in source:
        token_text = str(token or "").strip()
        if not token_text:
            continue
        session_id = int(max(100, int(token_text)))
        if session_id in seen:
            continue
        seen.add(session_id)
        out.append(session_id)
    return out


def make_stock_account(account_id: str) -> Any:
    from xtquant.xttype import StockAccount  # type: ignore

    try:
        return StockAccount(str(account_id))
    except TypeError:
        return StockAccount(str(account_id), "STOCK")


def choose_account_id(infos: list[Any], explicit_account_id: str) -> str:
    explicit = str(explicit_account_id or "").strip()
    if explicit:
        return explicit
    for info in infos:
        candidate = str(safe_attr(info, "account_id", "accountId", "account") or "").strip()
        if candidate:
            return candidate
    return ""


def query_orders(trader: Any, account: Any) -> list[Any]:
    try:
        return list(trader.query_stock_orders(account, False) or [])
    except TypeError:
        return list(trader.query_stock_orders(account) or [])


def run_one_probe(user_data_path: str, session_id: int, explicit_account_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "session_id": int(session_id),
        "observed_at": iso_now(),
        "ok": False,
        "steps": {},
        "selected_account_id": "",
    }
    trader = None
    account = None
    try:
        from xtquant.xttrader import XtQuantTrader  # type: ignore

        trader = XtQuantTrader(str(Path(user_data_path)), int(session_id))
        trader.start()
        connect_code = int(trader.connect())
        result["steps"]["connect"] = {"ok": connect_code == 0, "code": connect_code}
        if connect_code != 0:
            result["error"] = f"xttrader connect failed: {connect_code}"
            return result

        infos = list(trader.query_account_infos() or [])
        account_ids = [
            str(safe_attr(info, "account_id", "accountId", "account") or "").strip()
            for info in infos
            if str(safe_attr(info, "account_id", "accountId", "account") or "").strip()
        ]
        result["steps"]["query_account_infos"] = {
            "ok": True,
            "count": len(infos),
            "account_ids": account_ids,
        }

        selected_account_id = choose_account_id(infos, explicit_account_id)
        result["selected_account_id"] = selected_account_id
        if not selected_account_id:
            result["error"] = "no stock account id discovered from query_account_infos"
            return result

        account = make_stock_account(selected_account_id)
        subscribe_code = int(trader.subscribe(account))
        result["steps"]["subscribe"] = {"ok": subscribe_code == 0, "code": subscribe_code}
        if subscribe_code != 0:
            result["error"] = f"subscribe failed: {subscribe_code}"
            return result

        asset = trader.query_stock_asset(account)
        positions = list(trader.query_stock_positions(account) or [])
        orders = query_orders(trader, account)
        result["steps"]["query_stock_asset"] = {"ok": asset is not None}
        result["steps"]["query_stock_positions"] = {"ok": True, "count": len(positions)}
        result["steps"]["query_stock_orders"] = {"ok": True, "count": len(orders)}
        result["ok"] = asset is not None
        if asset is None:
            result["error"] = "query_stock_asset returned None"
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result
    finally:
        if account is not None and trader is not None:
            try:
                trader.unsubscribe(account)
            except Exception:
                pass
        if trader is not None:
            try:
                trader.stop()
            except Exception:
                pass


def main() -> int:
    args = parse_args()
    ensure_xtquant_on_path()

    payload: dict[str, Any] = {
        "started_at": iso_now(),
        "user_data_path": str(Path(args.user_data_path).expanduser()),
        "sessions": parse_sessions(args.sessions),
        "explicit_account_id": str(args.account_id or "").strip(),
        "results": [],
    }

    if not payload["sessions"]:
        payload["error"] = "no session ids were provided for native probe"
    else:
        for session_id in payload["sessions"]:
            payload["results"].append(
                run_one_probe(
                    user_data_path=payload["user_data_path"],
                    session_id=int(session_id),
                    explicit_account_id=payload["explicit_account_id"],
                )
            )

    payload["finished_at"] = iso_now()
    payload["overall_ok"] = bool(payload["results"]) and all(bool(item.get("ok")) for item in payload["results"])

    output = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.report_json:
        report_path = Path(args.report_json).expanduser()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if bool(payload["overall_ok"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
