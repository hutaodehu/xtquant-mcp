from __future__ import annotations

import argparse
import sys
from pathlib import Path

from harness_common import find_repo_root, load_task_states


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a bounded controller dispatch for one task.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--target-role", default=None)
    args = parser.parse_args()

    repo_root = find_repo_root(args.repo_root)
    tasks = {task.task_id: task for task in load_task_states(repo_root)}
    task = tasks.get(args.task_id)
    if task is None:
        print(f"Unknown task: {args.task_id}", file=sys.stderr)
        return 1

    target_role = args.target_role or task.task_card_fields.get("Current Role", "")
    change_link = task.change_pack.path if task.change_pack else task.task_card_fields.get("Change Package Link", "")
    evidence_link = task.latest_evidence.path if task.latest_evidence else task.task_card_fields.get("Evidence Pack Link", "")

    scope_in = []
    scope_out = []
    current_section = None
    for line in Path(task.task_card_path).read_text(encoding="utf-8").splitlines():
        if line.strip() == "## Scope In":
            current_section = "in"
            continue
        if line.strip() == "## Scope Out":
            current_section = "out"
            continue
        if line.startswith("## "):
            current_section = None
        if current_section == "in" and line.strip().startswith(("1.", "2.", "3.", "4.", "5.")):
            scope_in.append(line.strip())
        if current_section == "out" and line.strip().startswith(("1.", "2.", "3.", "4.", "5.")):
            scope_out.append(line.strip())

    print("# 主控派单")
    print()
    print(f"Task ID: {task.task_id}")
    print(f"Target Role: {target_role}")
    print(f"Spec Link: {task.task_card_path}")
    print(f"Change Package Link: {change_link}")
    print(f"Evidence Pack Link: {evidence_link or 'N/A'}")
    print()
    print("## In Scope")
    print()
    for item in scope_in or ["1. Follow the TaskCard Scope In section exactly."]:
        print(item)
    print()
    print("## Out of Scope")
    print()
    for item in scope_out or ["1. Do not expand beyond the TaskCard Scope Out section."]:
        print(item)
    print()
    print("## Expected Outputs")
    print()
    print("1. Updated ChangePack or superseding execution artifact for this task.")
    print("2. Modified file list or no-code evidence summary.")
    print("3. Explicit self-check or test result for the current role.")
    print("4. Known risks and recommended next board status.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
