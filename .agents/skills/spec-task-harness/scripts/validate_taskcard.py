from __future__ import annotations

import argparse
import sys
from pathlib import Path

from harness_common import (
    TASK_ID_PATTERN,
    dump_json,
    find_repo_root,
    parse_header_fields,
    taskcard_runtime_contract,
    taskcard_validation_failures,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate TaskCard headers for the harness contract.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--dump-json", action="store_true")
    args = parser.parse_args()

    repo_root = find_repo_root(args.repo_root)
    task_cards_dir = repo_root / "docs" / "task_cards"
    failures: list[str] = []
    selected_contract: dict[str, object] | None = None
    matched_task = False

    for path in sorted(task_cards_dir.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        fields = parse_header_fields(path)
        task_id = fields.get("Task ID", "").strip()
        if args.task_id and task_id != args.task_id:
            continue
        matched_task = True
        if not TASK_ID_PATTERN.match(task_id):
            failures.append(f"{path}: invalid or missing Task ID")
            continue
        for failure in taskcard_validation_failures(fields):
            failures.append(f"{task_id}: {failure}")
        if args.dump_json:
            selected_contract = taskcard_runtime_contract(fields)

    if args.task_id and not matched_task:
        failures.append(f"{args.task_id}: task card not found")
    if args.dump_json and not args.task_id:
        failures.append("--dump-json requires --task-id")

    if failures:
        print("TaskCard validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    if args.dump_json:
        print(dump_json(selected_contract or {}))
        return 0
    print("TaskCard validation ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
