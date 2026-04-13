from __future__ import annotations

import argparse
import sys
from pathlib import Path

from harness_common import (
    build_snapshot,
    dependencies_satisfied,
    dump_json,
    find_repo_root,
    load_board_export,
    priority_sort_key,
    risk_sort_key,
    write_scopes_overlap,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Select the next safe controller action.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--board-json", type=Path, default=None)
    args = parser.parse_args()

    repo_root = find_repo_root(args.repo_root)
    board = load_board_export(args.board_json) if args.board_json else {}
    snapshot = build_snapshot(repo_root, board)
    task_by_id = {item["task_id"]: item for item in snapshot}

    if args.board_json:
        stale = [item["task_id"] for item in snapshot if item["reconcile_state"] in {"board_stale", "artifact_incomplete", "conflict_needs_controller"}]
        if stale:
            print(
                dump_json(
                    {
                        "mode": "board_reconcile",
                        "controller_action": "sync_runledger_first",
                        "reason": "reconcile_mismatch",
                        "tasks": stale,
                    }
                )
            )
            return 0

    closeout = [item["task_id"] for item in snapshot if item["controller_action"] == "controller_closeout"]
    validation_preparation: list[dict[str, str]] = []
    for item in snapshot:
        if item["controller_action"] == "prepare_validation" and item["next_validation_task"]:
            validation_preparation.append({"blocked_task": item["task_id"], "next_validation_task": item["next_validation_task"]})

    dispatchable = []
    for item in snapshot:
        if item["controller_action"] != "dispatchable":
            continue
        if item["automation_policy"].lower() != "auto_safe":
            continue
        if item["risk_class"].lower() == "high":
            continue
        if not dependencies_satisfied(item, task_by_id):
            continue
        if args.board_json:
            board_row = item.get("board") or {}
            if board_row.get("status") != "Ready":
                continue
        dispatchable.append(item)

    dispatchable.sort(key=lambda item: (priority_sort_key(item["priority"]), risk_sort_key(item["risk_class"]), item["task_id"]))

    selected = []
    used_scopes: list[list[str]] = []
    for item in dispatchable:
        if len(selected) >= 2:
            break
        if any(write_scopes_overlap(item["write_scope"], scope) for scope in used_scopes):
            continue
        selected.append(item["task_id"])
        used_scopes.append(item["write_scope"])

    payload = {
        "mode": "board_reconcile" if args.board_json else "repo_only_recovery",
        "controller_action": "dispatchable" if selected and args.board_json else "manual_resume_required",
        "closeout_candidates": closeout,
        "validation_preparation": validation_preparation,
        "dispatchable_candidates": [item["task_id"] for item in dispatchable],
        "selected_tasks": selected,
    }
    print(dump_json(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
