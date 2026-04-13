from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock, Thread
from typing import Any, Callable


JobProgressCallback = Callable[[dict[str, Any]], bool]
DownloadRunner = Callable[["DownloadJobRequest", JobProgressCallback], dict[str, Any] | None]
CancelRunner = Callable[[], None]

RUNNING_JOB_STATUSES = {"pending", "running", "cancel_requested"}
FINAL_JOB_STATUSES = {"completed", "failed", "cancelled", "interrupted"}


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class DownloadJobRequest:
    codes: tuple[str, ...]
    period: str
    start_time: str = ""
    end_time: str = ""
    incrementally: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["codes"] = list(self.codes)
        return payload


@dataclass
class DownloadJobState:
    job_id: str
    request: DownloadJobRequest
    status: str
    created_at: str
    started_at: str = ""
    finished_at: str = ""
    progress_finished: int = 0
    progress_total: int = 0
    progress_message: str = ""
    cancel_requested: bool = False
    result: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    artifacts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    worker_name: str = ""
    progress_samples: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "request": self.request.as_dict(),
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "progress_finished": int(self.progress_finished),
            "progress_total": int(self.progress_total),
            "progress_message": self.progress_message,
            "cancel_requested": bool(self.cancel_requested),
            "result": dict(self.result or {}),
            "error": dict(self.error or {}) if self.error else None,
            "artifacts": list(self.artifacts or []),
            "warnings": list(self.warnings or []),
            "worker_name": self.worker_name,
            "progress_samples": [dict(item) for item in self.progress_samples or []],
        }


class DownloadJobManager:
    def __init__(
        self,
        jobs_root: str,
        *,
        run_download: DownloadRunner,
        cancel_download: CancelRunner | None = None,
        max_concurrent_jobs: int = 1,
        now_fn: Callable[[], str] = _utc_now_text,
        uuid_factory: Callable[[], str] | None = None,
    ) -> None:
        self._jobs_root = Path(str(jobs_root or "")).expanduser().resolve()
        self._jobs_root.mkdir(parents=True, exist_ok=True)
        self._run_download = run_download
        self._cancel_download = cancel_download
        self._max_concurrent_jobs = max(1, int(max_concurrent_jobs))
        self._now_fn = now_fn
        self._uuid_factory = uuid_factory or self._default_job_id
        self._lock = RLock()
        self._jobs: dict[str, DownloadJobState] = {}
        self._threads: dict[str, Thread] = {}
        self._load_existing_jobs()

    def submit(self, request: DownloadJobRequest) -> dict[str, Any]:
        with self._lock:
            if len(self._active_job_ids()) >= self._max_concurrent_jobs:
                raise RuntimeError("download_queue_full")
            job_id = self._uuid_factory()
            job = DownloadJobState(
                job_id=job_id,
                request=request,
                status="pending",
                created_at=self._now_fn(),
                worker_name=f"xtdata-download-{job_id[:8]}",
                artifacts=[self._job_path(job_id).as_posix()],
            )
            self._jobs[job_id] = job
            self._persist(job)
            thread = Thread(target=self._run_job, args=(job_id,), name=job.worker_name, daemon=True)
            self._threads[job_id] = thread
            thread.start()
            return job.as_dict()

    def status(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._jobs.get(str(job_id or "").strip())
            if state is None:
                raise KeyError(job_id)
            return state.as_dict()

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._jobs.get(str(job_id or "").strip())
            if state is None:
                raise KeyError(job_id)
            if state.status in FINAL_JOB_STATUSES:
                return state.as_dict()
            state.cancel_requested = True
            if state.status in {"pending", "running"}:
                state.status = "cancel_requested"
            state.progress_message = state.progress_message or "cancel_requested"
            self._persist(state)
        if callable(self._cancel_download):
            try:
                self._cancel_download()
            except Exception:
                pass
        return self.status(job_id)

    def list_active(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._jobs[job_id].as_dict() for job_id in self._active_job_ids()]

    def list_all(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = [job.as_dict() for job in self._jobs.values()]
        rows.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return rows

    def _active_job_ids(self) -> list[str]:
        return [job_id for job_id, state in self._jobs.items() if state.status in RUNNING_JOB_STATUSES]

    def _run_job(self, job_id: str) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                return
            state.status = "running" if not state.cancel_requested else "cancel_requested"
            state.started_at = self._now_fn()
            self._persist(state)

        def on_progress(progress: dict[str, Any]) -> bool:
            with self._lock:
                current = self._jobs.get(job_id)
                if current is None:
                    return True
                current.progress_finished = int(progress.get("finished", current.progress_finished) or 0)
                current.progress_total = int(progress.get("total", current.progress_total) or 0)
                current.progress_message = str(progress.get("message", current.progress_message) or current.progress_message)
                sample = {
                    "ts": self._now_fn(),
                    "finished": current.progress_finished,
                    "total": current.progress_total,
                    "message": current.progress_message,
                }
                current.progress_samples = (current.progress_samples + [sample])[-10:]
                self._persist(current)
                return bool(current.cancel_requested)

        try:
            result = self._run_download(state.request, on_progress)
        except Exception as exc:
            with self._lock:
                current = self._jobs.get(job_id)
                if current is None:
                    return
                current.finished_at = self._now_fn()
                current.status = "cancelled" if current.cancel_requested else "failed"
                current.error = {"code": "download_failed", "message": str(exc)}
                current.progress_message = current.progress_message or str(exc)
                self._persist(current)
        else:
            with self._lock:
                current = self._jobs.get(job_id)
                if current is None:
                    return
                current.finished_at = self._now_fn()
                current.status = "cancelled" if current.cancel_requested else "completed"
                current.result = dict(result or {})
                self._persist(current)
        finally:
            with self._lock:
                self._threads.pop(job_id, None)

    def _default_job_id(self) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        seq = len(self._jobs) + 1
        return f"job-{stamp}-{seq:03d}"

    def _job_path(self, job_id: str) -> Path:
        return self._jobs_root / f"{job_id}.json"

    def _persist(self, state: DownloadJobState) -> None:
        self._job_path(state.job_id).write_text(json.dumps(state.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_existing_jobs(self) -> None:
        for path in sorted(self._jobs_root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            request_payload = payload.get("request") if isinstance(payload, dict) else {}
            if not isinstance(request_payload, dict):
                request_payload = {}
            state = DownloadJobState(
                job_id=str(payload.get("job_id", path.stem) or path.stem),
                request=DownloadJobRequest(
                    codes=tuple(str(item).strip() for item in request_payload.get("codes", []) if str(item).strip()),
                    period=str(request_payload.get("period", "") or ""),
                    start_time=str(request_payload.get("start_time", "") or ""),
                    end_time=str(request_payload.get("end_time", "") or ""),
                    incrementally=request_payload.get("incrementally"),
                ),
                status=str(payload.get("status", "interrupted") or "interrupted"),
                created_at=str(payload.get("created_at", "") or self._now_fn()),
                started_at=str(payload.get("started_at", "") or ""),
                finished_at=str(payload.get("finished_at", "") or ""),
                progress_finished=int(payload.get("progress_finished", 0) or 0),
                progress_total=int(payload.get("progress_total", 0) or 0),
                progress_message=str(payload.get("progress_message", "") or ""),
                cancel_requested=bool(payload.get("cancel_requested", False)),
                result=dict(payload.get("result") or {}),
                error=dict(payload.get("error") or {}) if payload.get("error") else None,
                artifacts=[str(item) for item in payload.get("artifacts", []) if str(item).strip()],
                warnings=[str(item) for item in payload.get("warnings", []) if str(item).strip()],
                worker_name=str(payload.get("worker_name", "") or ""),
                progress_samples=[dict(item) for item in payload.get("progress_samples", []) if isinstance(item, dict)],
            )
            if state.status in RUNNING_JOB_STATUSES:
                state.status = "interrupted"
                state.finished_at = state.finished_at or self._now_fn()
                state.error = state.error or {"code": "download_interrupted", "message": "job was interrupted by process restart"}
                self._persist(state)
            self._jobs[state.job_id] = state
