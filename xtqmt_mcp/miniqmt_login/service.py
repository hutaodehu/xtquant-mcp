from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path
import time
from typing import Protocol

from .contracts import (
    DEFAULT_QMT_EXE,
    DEFAULT_QMT_USERDATA,
    MiniQmtLoginConfig,
    MiniQmtLoginResult,
    MiniQmtLoginRunProfile,
    MiniQmtLoginStatus,
    MiniQmtLoginTiming,
)
from .credential_store import build_credential_target, read_credential
from .desktop_harness import DesktopObservation, WindowsDesktopHarness


SUCCESS_STATUSES = {
    MiniQmtLoginStatus.ALREADY_LOGGED_IN,
    MiniQmtLoginStatus.REMEMBERED_LOGIN_SUCCESS,
    MiniQmtLoginStatus.UI_LOGIN_SUCCESS,
}
RETRYABLE_ACTION_CODES = {"login_window_not_found", "password_field_missing"}
TERMINAL_ACTION_CODES = {"password_fill_failed", "submit_failed"}


class CredentialReader(Protocol):
    def __call__(self, target: str):
        ...


class ReadinessProbe(Protocol):
    def __call__(self, config: MiniQmtLoginConfig) -> dict[str, object]:
        ...


@dataclass
class _RunMetrics:
    started_at: float
    observe_iterations: int = 0
    launch_or_attach_seconds: float | None = None
    startup_grace_wait_seconds: float = 0.0
    first_login_window_seconds: float | None = None
    credential_read_seconds: float | None = None
    submit_seconds: float | None = None
    first_main_window_seconds: float | None = None
    first_port_ready_seconds: float | None = None
    login_path: str = ""
    submit_attempted: bool = False
    saw_login_window: bool = False
    launch_started: bool = False
    already_running_before_launch: bool = False
    interactive_desktop: bool = True

    def record_observation(self, observation: DesktopObservation, observed_at: float) -> None:
        self.observe_iterations += 1
        elapsed = max(0.0, observed_at - self.started_at)
        if observation.login_window_found:
            self.saw_login_window = True
            if self.first_login_window_seconds is None:
                self.first_login_window_seconds = elapsed
        if observation.main_window_found and self.first_main_window_seconds is None:
            self.first_main_window_seconds = elapsed
        if observation.port_ready and self.first_port_ready_seconds is None:
            self.first_port_ready_seconds = elapsed

    def build_timing(self, finished_at: float) -> MiniQmtLoginTiming:
        return MiniQmtLoginTiming(
            total_seconds=max(0.0, finished_at - self.started_at),
            launch_or_attach_seconds=self.launch_or_attach_seconds,
            startup_grace_wait_seconds=self.startup_grace_wait_seconds,
            first_login_window_seconds=self.first_login_window_seconds,
            credential_read_seconds=self.credential_read_seconds,
            submit_seconds=self.submit_seconds,
            first_main_window_seconds=self.first_main_window_seconds,
            first_port_ready_seconds=self.first_port_ready_seconds,
        )

    def build_run_profile(self) -> MiniQmtLoginRunProfile:
        return MiniQmtLoginRunProfile(
            observe_iterations=self.observe_iterations,
            login_path=self.login_path,
            submit_attempted=self.submit_attempted,
            saw_login_window=self.saw_login_window,
            launch_started=self.launch_started,
            already_running_before_launch=self.already_running_before_launch,
            interactive_desktop=self.interactive_desktop,
        )


def _safe_str(value: object) -> str:
    return str(value or "").strip()


def _resolve_path(explicit_value: str, env_name: str, default_value: str) -> str:
    explicit_path = _safe_str(explicit_value)
    if explicit_path:
        return explicit_path
    env_value = _safe_str(os.environ.get(env_name, ""))
    if env_value:
        return env_value
    return default_value


def resolve_login_config(config: MiniQmtLoginConfig) -> MiniQmtLoginConfig:
    return replace(
        config,
        qmt_exe=_resolve_path(config.qmt_exe, "QMT_EXE", DEFAULT_QMT_EXE),
        qmt_userdata=_resolve_path(config.qmt_userdata, "QMT_USERDATA", DEFAULT_QMT_USERDATA),
        credential_target=build_credential_target(config.account_id, config.credential_target),
        login_timeout_seconds=max(1, int(config.login_timeout_seconds)),
        startup_grace_seconds=max(0, int(config.startup_grace_seconds)),
    )


def _observation_payload(observation: DesktopObservation) -> dict[str, object]:
    payload = observation.as_payload()
    payload.pop("screenshot_path", None)
    return payload


def _finalize_evidence(evidence: dict[str, object], metrics: _RunMetrics) -> dict[str, object]:
    payload = dict(evidence)
    payload["timing"] = metrics.build_timing(time.monotonic()).as_payload()
    payload["run_profile"] = metrics.build_run_profile().as_payload()
    return payload


def _resolve_process_id(observation: DesktopObservation, harness: WindowsDesktopHarness) -> int | None:
    if observation.process_id is not None:
        return int(observation.process_id)
    list_process_ids = getattr(harness, "list_process_ids", None)
    if not callable(list_process_ids):
        return None
    try:
        process_ids = list_process_ids()
    except Exception:
        return None
    if not process_ids:
        return None
    try:
        return int(process_ids[0])
    except Exception:
        return None


def _build_result(
    status: MiniQmtLoginStatus,
    message: str,
    evidence: dict[str, object],
    metrics: _RunMetrics,
    *,
    process_id: int | None = None,
    port_ready: bool = False,
) -> MiniQmtLoginResult:
    if status in SUCCESS_STATUSES:
        metrics.login_path = status.value
    return MiniQmtLoginResult(
        ok=status in SUCCESS_STATUSES,
        status=status,
        message=message,
        evidence=_finalize_evidence(evidence, metrics),
        process_id=process_id,
        port_ready=port_ready,
    )


def _summarize_channel_probe(config: MiniQmtLoginConfig) -> dict[str, object]:
    account_id = _safe_str(config.account_id)
    qmt_userdata = _safe_str(config.qmt_userdata)
    qmt_exe = _safe_str(config.qmt_exe)
    if (not account_id) or (not qmt_userdata):
        return {
            "ok": False,
            "reason": "probe_unavailable_missing_account_or_userdata",
            "account_id": account_id,
            "qmt_userdata": qmt_userdata,
        }
    try:
        from xtqmt_mcp.channel_probe import ChannelProbeConfig, run_channel_probe
    except Exception as exc:
        return {
            "ok": False,
            "reason": "probe_import_failed",
            "account_id": account_id,
            "message": str(exc),
        }

    try:
        report = run_channel_probe(
            ChannelProbeConfig(
                user_data_path=qmt_userdata,
                account_id=account_id,
                auto_account=False,
                qmt_exe=qmt_exe,
                connect_retries=2,
                connect_retry_interval_seconds=3.0,
                session_candidates=(100, 101, 111),
                wake_wait_seconds=15,
                require_connect_stage=True,
                require_subscribe_stage=True,
                require_snapshot_stage=False,
                snapshot_requires_position=False,
            )
        )
    except Exception as exc:
        return {
            "ok": False,
            "reason": "probe_exception",
            "account_id": account_id,
            "message": str(exc),
        }

    connection_trace = list(report.connection_trace or [])
    connect_stage = next(
        (
            item
            for item in reversed(connection_trace)
            if str(getattr(item, "name", "")).startswith("connect_session_")
        ),
        None,
    )
    vendor_port_probe_ok = bool(report.precheck.get("xtdata_port_ready", False)) or any(
        str(getattr(item, "name", "")) == "wait_xtdata_ready" and bool(getattr(item, "ok", False))
        for item in connection_trace
    )
    connect_pass = any(
        str(getattr(item, "name", "")).startswith("connect_session_") and bool(getattr(item, "ok", False))
        for item in connection_trace
    )
    subscribe_pass = any(
        str(getattr(item, "name", "")) == "subscribe_account" and bool(getattr(item, "ok", False))
        for item in connection_trace
    )
    shadow_snapshot_ok = any(
        str(getattr(item, "name", "")) == "query_snapshot_smoke" and bool(getattr(item, "ok", False))
        for item in connection_trace
    )
    overall_trade_ready = bool(report.overall_ok)
    return {
        "ok": bool(overall_trade_ready),
        "reason": str(report.failure_classification or ("ok" if overall_trade_ready else "probe_failed")),
        "account_id": account_id,
        "selected_session_id": report.selected_session_id,
        "precheck": dict(report.precheck or {}),
        "connect_code": str(getattr(connect_stage, "code", "") or ""),
        "vendor_port_probe_ok": bool(vendor_port_probe_ok),
        "connect_pass": bool(connect_pass),
        "subscribe_pass": bool(subscribe_pass),
        "shadow_snapshot_ok": bool(shadow_snapshot_ok),
        "market_data_pass": bool(vendor_port_probe_ok),
        "overall_trade_ready": bool(overall_trade_ready),
        "market_data_ok": bool(vendor_port_probe_ok),
        "snapshot_ok": bool(shadow_snapshot_ok),
        "probe_scope_note": "probe.connection 仅覆盖 vendor 行情探针与 trader shadow snapshot，不等价于 snapshot.l1",
    }


def _status_for_port_ready_success(metrics: _RunMetrics, *, submit_attempted: bool) -> MiniQmtLoginStatus:
    if submit_attempted:
        return MiniQmtLoginStatus.UI_LOGIN_SUCCESS
    if metrics.launch_started:
        return MiniQmtLoginStatus.REMEMBERED_LOGIN_SUCCESS
    return MiniQmtLoginStatus.ALREADY_LOGGED_IN


def _message_for_status(status: MiniQmtLoginStatus) -> str:
    if status == MiniQmtLoginStatus.UI_LOGIN_SUCCESS:
        return "MiniQMT login verified via port-ready probe after UI submit"
    if status == MiniQmtLoginStatus.REMEMBERED_LOGIN_SUCCESS:
        return "MiniQMT auto login verified via port-ready probe"
    return "MiniQMT already logged in via port-ready probe"


def _maybe_accept_port_ready_without_window(
    *,
    resolved: MiniQmtLoginConfig,
    observation: DesktopObservation,
    evidence: dict[str, object],
    metrics: _RunMetrics,
    readiness_probe: ReadinessProbe,
    phase: str,
    process_id: int | None,
    submit_attempted: bool,
) -> MiniQmtLoginResult | None:
    if (not observation.port_ready) or observation.login_window_found or observation.extra_auth_detected or observation.bad_password_detected:
        return None
    probe_payload = dict(readiness_probe(resolved) or {})
    probe_payload["phase"] = phase
    evidence["readiness_probe"] = probe_payload
    if not bool(probe_payload.get("ok", False)):
        return None
    status = _status_for_port_ready_success(metrics, submit_attempted=submit_attempted)
    return _build_result(
        status,
        _message_for_status(status),
        evidence,
        metrics,
        process_id=process_id,
        port_ready=observation.port_ready,
    )


def ensure_miniqmt_logged_in(
    config: MiniQmtLoginConfig,
    *,
    harness: WindowsDesktopHarness | None = None,
    credential_reader: CredentialReader = read_credential,
    readiness_probe: ReadinessProbe = _summarize_channel_probe,
) -> MiniQmtLoginResult:
    resolved = resolve_login_config(config)
    if not Path(resolved.qmt_exe).exists():
        raise ValueError(f"qmt_exe not found: {resolved.qmt_exe}")
    login_harness = harness or WindowsDesktopHarness()
    metrics = _RunMetrics(started_at=time.monotonic())
    evidence: dict[str, object] = {
        "qmt_exe": resolved.qmt_exe,
        "qmt_userdata": resolved.qmt_userdata,
        "account_id": resolved.account_id,
        "credential_target": resolved.credential_target,
        "port_host": resolved.port_host,
        "port_num": resolved.port_num,
    }
    if not login_harness.is_interactive_desktop():
        metrics.interactive_desktop = False
        return _build_result(
            MiniQmtLoginStatus.DESKTOP_NOT_INTERACTIVE,
            "interactive desktop required",
            evidence,
            metrics,
        )

    initial_observation = login_harness.observe(port_host=resolved.port_host, port_num=resolved.port_num)
    metrics.record_observation(initial_observation, time.monotonic())
    evidence["initial_observation"] = _observation_payload(initial_observation)
    initial_process_id = _resolve_process_id(initial_observation, login_harness)
    if initial_process_id is not None:
        metrics.already_running_before_launch = True
    initial_port_ready_result = _maybe_accept_port_ready_without_window(
        resolved=resolved,
        observation=initial_observation,
        evidence=evidence,
        metrics=metrics,
        readiness_probe=readiness_probe,
        phase="initial_observation",
        process_id=initial_process_id,
        submit_attempted=False,
    )
    if initial_port_ready_result is not None:
        return initial_port_ready_result

    launch_started_at = time.monotonic()
    launch = login_harness.launch_or_attach(resolved.qmt_exe)
    metrics.launch_or_attach_seconds = max(0.0, time.monotonic() - launch_started_at)
    metrics.launch_started = bool(launch.started)
    metrics.already_running_before_launch = bool(launch.already_running)
    evidence["launch"] = launch.as_payload()
    if not launch.ok:
        return _build_result(
            MiniQmtLoginStatus.TIMEOUT,
            launch.message,
            evidence,
            metrics,
            process_id=launch.process_id,
            port_ready=initial_observation.port_ready,
        )

    deadline = time.monotonic() + resolved.login_timeout_seconds
    startup_grace_deadline = time.monotonic() + resolved.startup_grace_seconds
    process_id = launch.process_id or initial_observation.process_id
    credential = None
    submit_attempted = False

    while time.monotonic() <= deadline:
        observation = login_harness.observe(
            process_id=process_id,
            port_host=resolved.port_host,
            port_num=resolved.port_num,
        )
        metrics.record_observation(observation, time.monotonic())
        evidence["last_observation"] = _observation_payload(observation)
        process_id = observation.process_id or process_id

        if observation.extra_auth_detected:
            return _build_result(
                MiniQmtLoginStatus.EXTRA_AUTH_DETECTED,
                "extra authentication detected",
                evidence,
                metrics,
                process_id=process_id,
                port_ready=observation.port_ready,
            )
        if observation.bad_password_detected:
            return _build_result(
                MiniQmtLoginStatus.BAD_PASSWORD,
                "password rejected by MiniQMT",
                evidence,
                metrics,
                process_id=process_id,
                port_ready=observation.port_ready,
            )
        port_ready_result = _maybe_accept_port_ready_without_window(
            resolved=resolved,
            observation=observation,
            evidence=evidence,
            metrics=metrics,
            readiness_probe=readiness_probe,
            phase="polling_observation",
            process_id=process_id,
            submit_attempted=submit_attempted,
        )
        if port_ready_result is not None:
            return port_ready_result

        if observation.login_window_found and not submit_attempted:
            now = time.monotonic()
            remaining_grace_seconds = startup_grace_deadline - now
            if remaining_grace_seconds > 0:
                sleep_seconds = min(0.5, remaining_grace_seconds)
                metrics.startup_grace_wait_seconds += sleep_seconds
                time.sleep(sleep_seconds)
                continue

            if credential is None:
                credential_started_at = time.monotonic()
                credential = credential_reader(resolved.credential_target)
                metrics.credential_read_seconds = max(0.0, time.monotonic() - credential_started_at)
                evidence["credential_lookup"] = credential.public_payload()
                if not credential.ok:
                    return _build_result(
                        MiniQmtLoginStatus.CREDENTIAL_MISSING,
                        f"credential lookup failed: {credential.error}",
                        evidence,
                        metrics,
                        process_id=process_id,
                        port_ready=observation.port_ready,
                    )

            if observation.password_edit_index is None:
                time.sleep(0.5)
                continue

            submit_started_at = time.monotonic()
            action = login_harness.submit_saved_password(observation, credential.password)
            metrics.submit_seconds = max(0.0, time.monotonic() - submit_started_at)
            evidence["submit_action"] = action.as_payload()

            if action.ok:
                submit_attempted = True
                metrics.submit_attempted = True
            elif action.code in RETRYABLE_ACTION_CODES:
                time.sleep(0.5)
            elif action.code in TERMINAL_ACTION_CODES:
                return _build_result(
                    MiniQmtLoginStatus.TIMEOUT,
                    action.message,
                    evidence,
                    metrics,
                    process_id=process_id,
                    port_ready=observation.port_ready,
                )
        time.sleep(0.5)

    final_observation = login_harness.observe(
        process_id=process_id,
        port_host=resolved.port_host,
        port_num=resolved.port_num,
    )
    metrics.record_observation(final_observation, time.monotonic())
    evidence["final_observation"] = _observation_payload(final_observation)
    if final_observation.extra_auth_detected:
        return _build_result(
            MiniQmtLoginStatus.EXTRA_AUTH_DETECTED,
            "extra authentication detected",
            evidence,
            metrics,
            process_id=process_id,
            port_ready=final_observation.port_ready,
        )
    if final_observation.bad_password_detected:
        return _build_result(
            MiniQmtLoginStatus.BAD_PASSWORD,
            "password rejected by MiniQMT",
            evidence,
            metrics,
            process_id=process_id,
            port_ready=final_observation.port_ready,
        )
    final_port_ready_result = _maybe_accept_port_ready_without_window(
        resolved=resolved,
        observation=final_observation,
        evidence=evidence,
        metrics=metrics,
        readiness_probe=readiness_probe,
        phase="final_observation",
        process_id=process_id,
        submit_attempted=submit_attempted,
    )
    if final_port_ready_result is not None:
        return final_port_ready_result
    if metrics.saw_login_window or final_observation.login_window_found:
        return _build_result(
            MiniQmtLoginStatus.TIMEOUT,
            "MiniQMT login timed out",
            evidence,
            metrics,
            process_id=process_id,
            port_ready=final_observation.port_ready,
        )
    return _build_result(
        MiniQmtLoginStatus.LOGIN_WINDOW_NOT_FOUND,
        "MiniQMT login window not found",
        evidence,
        metrics,
        process_id=process_id,
        port_ready=final_observation.port_ready,
    )

