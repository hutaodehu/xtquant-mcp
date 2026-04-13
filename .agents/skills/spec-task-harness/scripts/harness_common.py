from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


FIELD_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9 /_-]*):\s*(.*)$")
TIMESTAMP_PATTERNS = [
    re.compile(r"(?<!\d)(\d{8})[-_](\d{6})(?!\d)"),
    re.compile(r"(?<!\d)(\d{14})(?!\d)"),
    re.compile(r"(?<!\d)(\d{12})(?!\d)"),
]
TASK_ID_PATTERN = re.compile(r"^[A-Z]+-\d+$")
REVIEW_DECISION_PATTERN = re.compile(
    r"(?mi)^\s*-\s*Decision:\s*(?P<tick>`?)(?P<decision>pass|needs_fix|blocked)(?P=tick)\s*$"
)
REVIEW_TARGET_STATUS_PATTERNS = [
    re.compile(r"(?mi)^\s*-\s*(?:Target Status|Suggested Status):\s*`([^`]+)`"),
    re.compile(r"(?mi)建议(?:任务)?(?:状态)?(?:保持|回到)\s*`([^`]+)`"),
    re.compile(r"(?ms)^##\s*建议回退状态\s*$.*?^\s*-\s*([A-Za-z][A-Za-z ]+?)(?:[（(].*)?$"),
]

TASKCARD_REQUIRED_FIELDS = [
    "Task ID",
    "Title",
    "Type",
    "Priority",
    "Owner Role",
    "Current Role",
    "Status",
    "Blocking Reason",
    "Repo Spec Link",
    "Acceptance Gate",
    "Change Package Link",
    "Evidence Pack Link",
    "Review Pack Link",
    "Env Snapshot Link",
    "Verifier",
    "Merge Owner",
    "Review Result",
    "Depends On",
    "Lane",
    "Risk Class",
    "Write Scope",
    "Automation Policy",
    "Execution Class",
]

CONTROLLER_TEST_POLICY_VALUES = {
    "none",
    "delegated_test_required",
    "controller_direct_required",
}

CONTROLLER_DIRECT_TEST_REQUIRED_FIELDS = [
    "Execution Packet Side",
    "Execution Packet Symbol",
    "Execution Packet Qty",
    "Execution Packet Price Mode",
    "Execution Packet Cancel Timeout",
]


@dataclass
class ArtifactFile:
    path: str
    mtime: float
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class TaskState:
    task_id: str
    title: str
    task_type: str
    priority: str
    lane: str
    risk_class: str
    automation_policy: str
    execution_class: str
    controller_test_policy: str
    write_scope: list[str]
    depends_on: list[str]
    task_card_path: str
    task_card_fields: dict[str, str]
    change_pack: ArtifactFile | None
    latest_evidence: ArtifactFile | None
    latest_review: ArtifactFile | None
    latest_env_snapshot: ArtifactFile | None
    local_stage: str
    latest_evidence_conclusion: str | None
    latest_review_decision: str | None
    suggested_status: str
    controller_action: str
    blocking_reason_hint: str | None
    next_validation_task: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "docs" / "task_cards").is_dir() and (candidate / "docs" / "change_packages").is_dir():
            return candidate
    raise FileNotFoundError("Could not locate repo root with docs/task_cards and docs/change_packages")


def parse_header_fields(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            break
        if line.startswith("# "):
            if fields:
                break
            continue
        match = FIELD_PATTERN.match(line)
        if match:
            fields[match.group(1).strip()] = match.group(2).strip()
    return fields


def normalize_status_value(raw: str) -> str:
    value = raw.strip().strip("`").strip()
    if "->" in value:
        value = value.split("->", 1)[0].strip()
    if "（" in value:
        value = value.split("（", 1)[0].strip()
    if "(" in value:
        value = value.split("(", 1)[0].strip()
    return " ".join(value.split())


def augment_artifact_fields(path: Path, fields: dict[str, str]) -> dict[str, str]:
    if path.parent.name != "reviews":
        return fields

    text = path.read_text(encoding="utf-8")
    decision_match = REVIEW_DECISION_PATTERN.search(text)
    if decision_match:
        fields["Decision"] = decision_match.group("decision").strip().lower()

    for pattern in REVIEW_TARGET_STATUS_PATTERNS:
        match = pattern.search(text)
        if match:
            fields["Target Status"] = normalize_status_value(match.group(1))
            break
    return fields


def parse_task_ids(raw: str) -> list[str]:
    if not raw or raw == "-":
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_scopes(raw: str) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def normalize_controller_test_policy(raw: str) -> str:
    value = (raw or "").strip().lower()
    return value or "none"


def controller_direct_test_eligible(fields: dict[str, str]) -> bool:
    return (
        normalize_controller_test_policy(fields.get("Controller Test Policy", "")) == "controller_direct_required"
        and fields.get("Automation Policy", "").strip().lower() == "manual_gate"
        and fields.get("Execution Class", "").strip().lower() == "test_only"
        and fields.get("Risk Class", "").strip().lower() == "high"
    )


def parse_positive_int(raw: str) -> int | None:
    try:
        value = int((raw or "").strip())
    except ValueError:
        return None
    return value if value > 0 else None


def taskcard_validation_failures(fields: dict[str, str]) -> list[str]:
    failures: list[str] = []
    for field in TASKCARD_REQUIRED_FIELDS:
        if field not in fields:
            failures.append(f"missing field '{field}'")

    policy = normalize_controller_test_policy(fields.get("Controller Test Policy", ""))
    if policy not in CONTROLLER_TEST_POLICY_VALUES:
        failures.append(
            "invalid Controller Test Policy; expected one of none, delegated_test_required, controller_direct_required"
        )

    if policy != "controller_direct_required":
        return failures

    if fields.get("Owner Role", "").strip().lower() != "test":
        failures.append("Controller Test Policy controller_direct_required requires Owner Role: test")
    if fields.get("Automation Policy", "").strip().lower() != "manual_gate":
        failures.append("Controller Test Policy controller_direct_required requires Automation Policy: manual_gate")
    if fields.get("Execution Class", "").strip().lower() != "test_only":
        failures.append("Controller Test Policy controller_direct_required requires Execution Class: test_only")
    if fields.get("Risk Class", "").strip().lower() != "high":
        failures.append("Controller Test Policy controller_direct_required requires Risk Class: high")

    side = fields.get("Execution Packet Side", "").strip().upper()
    if side not in {"BUY", "SELL"}:
        failures.append("Execution Packet Side must be BUY or SELL for controller_direct_required tasks")

    qty = parse_positive_int(fields.get("Execution Packet Qty", ""))
    if qty is None:
        failures.append("Execution Packet Qty must be a positive integer for controller_direct_required tasks")

    for field in CONTROLLER_DIRECT_TEST_REQUIRED_FIELDS:
        if not fields.get(field, "").strip():
            failures.append(f"missing or empty field '{field}' for controller_direct_required task")

    return failures


def taskcard_runtime_contract(fields: dict[str, str]) -> dict[str, Any]:
    policy = normalize_controller_test_policy(fields.get("Controller Test Policy", ""))
    packet = None
    if policy == "controller_direct_required":
        packet = {
            "side": fields.get("Execution Packet Side", "").strip().upper(),
            "symbol": fields.get("Execution Packet Symbol", "").strip(),
            "qty": parse_positive_int(fields.get("Execution Packet Qty", "")),
            "price_mode": fields.get("Execution Packet Price Mode", "").strip(),
            "cancel_timeout": fields.get("Execution Packet Cancel Timeout", "").strip(),
        }
    return {
        "task_id": fields.get("Task ID", "").strip(),
        "title": fields.get("Title", "").strip(),
        "acceptance_gate": fields.get("Acceptance Gate", "").strip(),
        "repo_spec_link": fields.get("Repo Spec Link", "").strip(),
        "change_package_link": fields.get("Change Package Link", "").strip(),
        "evidence_pack_link": fields.get("Evidence Pack Link", "").strip(),
        "review_pack_link": fields.get("Review Pack Link", "").strip(),
        "env_snapshot_link": fields.get("Env Snapshot Link", "").strip(),
        "owner_role": fields.get("Owner Role", "").strip(),
        "current_role": fields.get("Current Role", "").strip(),
        "status": fields.get("Status", "").strip(),
        "blocking_reason": fields.get("Blocking Reason", "").strip(),
        "lane": fields.get("Lane", "").strip(),
        "risk_class": fields.get("Risk Class", "").strip(),
        "automation_policy": fields.get("Automation Policy", "").strip(),
        "execution_class": fields.get("Execution Class", "").strip(),
        "controller_test_policy": policy,
        "trade_config_path": fields.get("Trade Config Path", "").strip(),
        "data_config_path": fields.get("Data Config Path", "").strip(),
        "trade_health_url": fields.get("Trade Health URL", "").strip(),
        "data_health_url": fields.get("Data Health URL", "").strip(),
        "packet": packet,
    }


def is_skeleton_stage(stage: str | None) -> bool:
    return (stage or "").strip().lower() in {"", "skeleton", "reserved-pre-dev"}


def normalized_filename_timestamp(path: Path) -> int | None:
    candidates: list[int] = []
    name = path.name
    for pattern in TIMESTAMP_PATTERNS:
        for match in pattern.finditer(name):
            if len(match.groups()) == 2:
                candidates.append(int(f"{match.group(1)}{match.group(2)}"))
                continue
            raw = match.group(1)
            if len(raw) == 12:
                candidates.append(int(f"{raw}00"))
                continue
            candidates.append(int(raw))
    if candidates:
        return max(candidates)
    return None


def filename_timestamp_value(path: Path) -> int:
    normalized = normalized_filename_timestamp(path)
    if normalized is not None:
        return normalized
    return int(path.stat().st_mtime)


def latest_artifact_for_task(directory: Path, task_id: str) -> ArtifactFile | None:
    if not directory.exists():
        return None
    matches: list[ArtifactFile] = []
    for path in directory.glob("*.md"):
        if path.name.upper() == "README.MD":
            continue
        fields = augment_artifact_fields(path, parse_header_fields(path))
        if fields.get("Task ID", "").strip() == task_id:
            matches.append(ArtifactFile(path=str(path), mtime=path.stat().st_mtime, fields=fields))
    if not matches:
        return None
    matches.sort(key=lambda item: (filename_timestamp_value(Path(item.path)), item.mtime), reverse=True)
    return matches[0]


def infer_local_stage(task_id: str, change_pack: ArtifactFile | None, evidence: ArtifactFile | None, review: ArtifactFile | None) -> str:
    if task_id == "PREP-001":
        return "migration_exempt"
    if review:
        decision = (review.fields.get("Decision") or "").strip().lower()
        if decision == "pass":
            return "reviewed_pass_local"
        if decision == "needs_fix":
            return "reviewed_needs_fix_local"
        if decision == "blocked":
            return "reviewed_blocked_local"
    if evidence:
        return "tested_local"
    if change_pack and not is_skeleton_stage(change_pack.fields.get("Stage")):
        return "implemented_local"
    return "todo_local"


def infer_suggested_status(local_stage: str, review: ArtifactFile | None) -> str:
    target_status = (review.fields.get("Target Status") or "").strip() if review else ""
    if local_stage == "migration_exempt":
        return "Migration Exempt"
    if local_stage == "todo_local":
        return "Ready"
    if local_stage == "implemented_local":
        return "In Self-Test"
    if local_stage == "tested_local":
        return "In Independent Test"
    if local_stage == "reviewed_needs_fix_local":
        return target_status or "In Dev"
    if local_stage == "reviewed_blocked_local":
        return target_status or "Blocked"
    if local_stage == "reviewed_pass_local":
        return target_status or "In Review"
    return "Ready"


def infer_controller_action(task_fields: dict[str, str], local_stage: str, review: ArtifactFile | None) -> tuple[str, str | None, str | None]:
    lane = task_fields.get("Lane", "").strip().lower()
    task_type = task_fields.get("Type", "").strip().lower()
    task_id = task_fields.get("Task ID", "").strip()
    review_text = Path(review.path).read_text(encoding="utf-8") if review else ""
    if local_stage == "migration_exempt":
        return "controller_archive_exempt", "migration_exempt", None
    if local_stage == "reviewed_pass_local":
        return "controller_closeout", None, None
    if local_stage == "reviewed_needs_fix_local":
        return "return_to_dev", "design_blocked", None
    if local_stage == "reviewed_blocked_local":
        if ("G2" in review_text or "live `G2`" in review_text or "G2 live" in review_text) and lane == "data":
            return "prepare_validation", "validation_pending", "VAL-001"
        if ("G3" in review_text or "live `G3`" in review_text or "G3 live" in review_text) and lane == "trade":
            return "prepare_validation", "validation_pending", "VAL-002"
        return "controller_review_required", "blocked", None
    if local_stage == "tested_local":
        return "review_needed", None, None
    if local_stage == "implemented_local":
        return "independent_test_needed", None, None
    if controller_direct_test_eligible(task_fields):
        return "manual_gate_pending", "manual_gate", task_id
    if task_type == "investigation":
        return "manual_gate_pending", "manual_gate", task_id
    if task_fields.get("Automation Policy", "").strip().lower() == "manual_gate":
        return "manual_gate_pending", "manual_gate", None
    return "dispatchable", None, None


def load_task_states(repo_root: Path) -> list[TaskState]:
    task_cards_dir = repo_root / "docs" / "task_cards"
    change_dir = repo_root / "docs" / "change_packages"
    evidence_dir = repo_root / "docs" / "evidence_packs"
    review_dir = repo_root / "docs" / "reviews"
    env_dir = repo_root / "docs" / "env_snapshots"
    task_states: list[TaskState] = []
    for path in sorted(task_cards_dir.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        fields = parse_header_fields(path)
        task_id = fields.get("Task ID", "").strip()
        if not TASK_ID_PATTERN.match(task_id):
            continue
        change_pack = latest_artifact_for_task(change_dir, task_id)
        evidence = latest_artifact_for_task(evidence_dir, task_id)
        review = latest_artifact_for_task(review_dir, task_id)
        env_snapshot = latest_artifact_for_task(env_dir, task_id)
        local_stage = infer_local_stage(task_id, change_pack, evidence, review)
        controller_action, blocking_hint, validation_task = infer_controller_action(fields, local_stage, review)
        task_states.append(
            TaskState(
                task_id=task_id,
                title=fields.get("Title", ""),
                task_type=fields.get("Type", ""),
                priority=fields.get("Priority", ""),
                lane=fields.get("Lane", ""),
                risk_class=fields.get("Risk Class", ""),
                automation_policy=fields.get("Automation Policy", ""),
                execution_class=fields.get("Execution Class", ""),
                controller_test_policy=normalize_controller_test_policy(fields.get("Controller Test Policy", "")),
                write_scope=parse_scopes(fields.get("Write Scope", "")),
                depends_on=parse_task_ids(fields.get("Depends On", "")),
                task_card_path=str(path),
                task_card_fields=fields,
                change_pack=change_pack,
                latest_evidence=evidence,
                latest_review=review,
                latest_env_snapshot=env_snapshot,
                local_stage=local_stage,
                latest_evidence_conclusion=(evidence.fields.get("Conclusion") if evidence else None),
                latest_review_decision=(review.fields.get("Decision") if review else None),
                suggested_status=infer_suggested_status(local_stage, review),
                controller_action=controller_action,
                blocking_reason_hint=blocking_hint,
                next_validation_task=validation_task,
            )
        )
    return task_states


def normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")


def load_board_export(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("tasks", raw) if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        raise ValueError("Board export must be a list or an object with a 'tasks' list")
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = {normalize_key(key): value for key, value in row.items()}
        task_id = normalized.get("task_id") or normalized.get("id")
        if task_id:
            out[str(task_id)] = normalized
    return out


def compute_reconcile_state(task: TaskState, board_row: dict[str, Any] | None) -> str:
    if task.local_stage == "migration_exempt":
        return "migration_exempt"
    if board_row is None:
        return "missing_board"
    board_status = str(board_row.get("status", "")).strip()
    board_review = str(board_row.get("review_result", "")).strip().lower()
    local_review = (task.latest_review_decision or "").strip().lower()
    if not board_status:
        return "artifact_incomplete"
    if task.local_stage == "todo_local" and board_status in {"Ready", "Backlog"}:
        return "aligned"
    if task.local_stage == "implemented_local" and board_status in {"In Dev", "In Self-Test"}:
        return "aligned"
    if task.local_stage == "tested_local" and board_status in {"In Independent Test", "In Review"}:
        return "aligned"
    if task.local_stage == "reviewed_pass_local" and board_review == "pass":
        return "aligned"
    if task.local_stage == "reviewed_needs_fix_local" and board_review == "needs_fix":
        return "aligned"
    if task.local_stage == "reviewed_blocked_local" and board_review == "blocked":
        return "aligned"
    if task.local_stage in {"implemented_local", "tested_local", "reviewed_pass_local", "reviewed_needs_fix_local", "reviewed_blocked_local"} and board_status in {"Ready", "Backlog"}:
        return "board_stale"
    if task.local_stage == "todo_local" and board_status not in {"Ready", "Backlog"}:
        return "artifact_incomplete"
    if local_review and board_review and local_review != board_review:
        return "conflict_needs_controller"
    return "conflict_needs_controller"


def build_snapshot(repo_root: Path, board: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    tasks = load_task_states(repo_root)
    board = board or {}
    snapshot: list[dict[str, Any]] = []
    for task in tasks:
        row = board.get(task.task_id)
        item = task.to_dict()
        item["board"] = row
        item["reconcile_state"] = compute_reconcile_state(task, row)
        snapshot.append(item)
    return snapshot


def priority_sort_key(priority: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(priority.upper(), 99)


def risk_sort_key(risk: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(risk.lower(), 99)


def dependencies_satisfied(task: dict[str, Any], task_by_id: dict[str, dict[str, Any]]) -> bool:
    deps = task.get("depends_on", [])
    if not deps:
        return True
    task_type = str(task.get("task_type", "")).lower()
    for dep_id in deps:
        dep = task_by_id.get(dep_id)
        if dep is None:
            return False
        dep_stage = dep.get("local_stage")
        dep_review = (dep.get("latest_review_decision") or "").lower()
        if task_type == "investigation":
            if dep_stage in {"reviewed_pass_local", "reviewed_blocked_local"}:
                continue
            if dep_stage == "tested_local" and dep_review != "needs_fix":
                continue
            return False
        if dep_stage not in {"reviewed_pass_local", "migration_exempt"}:
            return False
    return True


def write_scopes_overlap(left: list[str], right: list[str]) -> bool:
    if not left or not right:
        return False
    return bool(set(left) & set(right))


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
