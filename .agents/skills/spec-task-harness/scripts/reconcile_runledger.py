from __future__ import annotations

import argparse
import sys
from pathlib import Path

from harness_common import build_snapshot, dump_json, find_repo_root, load_board_export


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile repo artifacts against an optional board export.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--board-json", type=Path, default=None)
    parser.add_argument("--task-id", default=None)
    args = parser.parse_args()

    repo_root = find_repo_root(args.repo_root)
    board = load_board_export(args.board_json) if args.board_json else {}
    snapshot = build_snapshot(repo_root, board)
    if args.task_id:
        snapshot = [item for item in snapshot if item["task_id"] == args.task_id]
    output = {
        "repo_root": str(repo_root),
        "mode": "board_reconcile" if args.board_json else "repo_only_recovery",
        "task_count": len(snapshot),
        "tasks": snapshot,
    }
    print(dump_json(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
