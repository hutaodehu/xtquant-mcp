from __future__ import annotations

import argparse
import sys
from pathlib import Path

from harness_common import dump_json, find_repo_root, load_task_states


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect the latest artifacts for one task.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args()

    repo_root = find_repo_root(args.repo_root)
    for task in load_task_states(repo_root):
        if task.task_id != args.task_id:
            continue
        payload = {
            "task_id": task.task_id,
            "local_stage": task.local_stage,
            "controller_action": task.controller_action,
            "latest_change_pack": task.change_pack.path if task.change_pack else None,
            "latest_change_pack_stage": task.change_pack.fields.get("Stage") if task.change_pack else None,
            "latest_evidence_pack": task.latest_evidence.path if task.latest_evidence else None,
            "latest_evidence_conclusion": task.latest_evidence_conclusion,
            "latest_review_pack": task.latest_review.path if task.latest_review else None,
            "latest_review_decision": task.latest_review_decision,
            "latest_env_snapshot": task.latest_env_snapshot.path if task.latest_env_snapshot else None,
            "artifact_completeness": {
                "has_change_pack": task.change_pack is not None,
                "has_non_skeleton_change_pack": bool(task.change_pack and task.change_pack.fields.get("Stage") and task.change_pack.fields.get("Stage") != "skeleton"),
                "has_evidence_pack": task.latest_evidence is not None,
                "has_review_pack": task.latest_review is not None,
            },
        }
        print(dump_json(payload))
        return 0
    print(f"Unknown task: {args.task_id}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
