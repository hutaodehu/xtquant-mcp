from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xtqmt_mcp.controller_direct_host_recovery import (
    cleanup_session_residue,
    snapshot_host_recovery_state,
)


def _parse_sessions(raw: str) -> list[int]:
    values: list[int] = []
    seen: set[int] = set()
    for token in str(raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        session_id = int(token)
        if session_id <= 0 or session_id in seen:
            continue
        seen.add(session_id)
        values.append(session_id)
    return values


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect or clean controller-direct host recovery residue.")
    parser.add_argument("mode", choices=("inspect", "cleanup"))
    parser.add_argument("--user-data-path", required=True)
    parser.add_argument("--sessions", default="")
    parser.add_argument("--log-tail-lines", type=int, default=120)
    return parser


def _ensure_utf8_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    _ensure_utf8_stdout()
    sessions = _parse_sessions(args.sessions)
    if args.mode == "inspect":
        payload = snapshot_host_recovery_state(
            args.user_data_path,
            sessions,
            log_tail_lines=max(0, int(args.log_tail_lines)),
        )
    else:
        payload = cleanup_session_residue(args.user_data_path, sessions)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
