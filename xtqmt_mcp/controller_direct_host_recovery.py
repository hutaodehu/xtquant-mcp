from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


_SESSION_RESIDUE_PATTERNS = (
    "down_queue_win_{session_id}",
    "lock_down_queue_win_{session_id}",
    "down_queue_win_{session_id}__mutex",
)
_LOG_GLOBS = (
    "XtMiniQmt_*.log",
    "XtMiniQmt_perform_*.log",
    "XtMiniQuote_*.log",
)


def _normalize_root(user_data_path: str | Path) -> Path:
    return Path(user_data_path).expanduser().resolve()


def _normalized_session_ids(session_ids: Iterable[int]) -> list[int]:
    seen: set[int] = set()
    normalized: list[int] = []
    for raw in session_ids:
        try:
            session_id = int(raw)
        except Exception:
            continue
        if session_id <= 0 or session_id in seen:
            continue
        seen.add(session_id)
        normalized.append(session_id)
    return normalized


def _residue_entry(path: Path, session_id: int) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path),
        "session_id": int(session_id),
        "size_bytes": int(stat.st_size),
        "last_write_time": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def list_session_residue(user_data_path: str | Path, session_ids: Iterable[int]) -> list[dict[str, Any]]:
    root = _normalize_root(user_data_path)
    entries: list[dict[str, Any]] = []
    for session_id in _normalized_session_ids(session_ids):
        for pattern in _SESSION_RESIDUE_PATTERNS:
            candidate = root / pattern.format(session_id=session_id)
            if candidate.is_file():
                entries.append(_residue_entry(candidate, session_id))
    entries.sort(key=lambda item: str(item["name"]))
    return entries


def _tail_lines(path: Path, limit: int) -> list[str]:
    if limit <= 0:
        return []
    lines: deque[str] = deque(maxlen=int(limit))
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            lines.append(line.rstrip("\r\n"))
    return list(lines)


def snapshot_host_recovery_state(
    user_data_path: str | Path,
    session_ids: Iterable[int],
    *,
    log_tail_lines: int = 120,
) -> dict[str, Any]:
    root = _normalize_root(user_data_path)
    log_dir = root / "log"
    logs: list[dict[str, Any]] = []
    if log_dir.is_dir():
        seen: set[Path] = set()
        candidates: list[Path] = []
        for pattern in _LOG_GLOBS:
            for path in log_dir.glob(pattern):
                resolved = path.resolve()
                if resolved in seen or not path.is_file():
                    continue
                seen.add(resolved)
                candidates.append(path)
        candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        for path in candidates:
            logs.append(
                {
                    "name": path.name,
                    "path": str(path.resolve()),
                    "last_write_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                    "tail": _tail_lines(path, int(log_tail_lines)),
                }
            )
    return {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "user_data_path": str(root),
        "session_ids": _normalized_session_ids(session_ids),
        "residue": list_session_residue(root, session_ids),
        "logs": logs,
    }


def cleanup_session_residue(user_data_path: str | Path, session_ids: Iterable[int]) -> dict[str, Any]:
    root = _normalize_root(user_data_path)
    deleted: list[dict[str, Any]] = []
    for entry in list_session_residue(root, session_ids):
        candidate = Path(str(entry["path"])).resolve()
        if candidate.parent != root:
            raise RuntimeError(f"refusing to delete path outside user_data root: {candidate}")
        candidate.unlink(missing_ok=True)
        deleted.append(
            {
                **entry,
                "deleted": True,
            }
        )
    return {
        "cleaned_at": datetime.now().isoformat(timespec="seconds"),
        "user_data_path": str(root),
        "session_ids": _normalized_session_ids(session_ids),
        "deleted": deleted,
        "deleted_count": len(deleted),
    }
