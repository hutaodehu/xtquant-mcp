from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import os
from pathlib import Path
from typing import Any

from xtqmt_mcp import __version__
from xtqmt_mcp.config_utils import (
    coerce_bool,
    coerce_date,
    coerce_float,
    coerce_int,
    coerce_int_tuple,
    coerce_str_tuple,
    env_text,
    load_yaml_payload,
    normalize_http_path,
    pick,
    section,
)
from xtqmt_mcp.settings import (
    DEFAULT_BUNDLE_CONFIG,
    DEFAULT_RUNTIME_CONFIG,
    DEFAULT_RUNTIME_PATHS,
    QmtInstallConfig,
    RuntimeConfig,
    ServiceIdentity,
    ServiceRuntimePaths,
    TransportConfig,
    XtquantBundleConfig,
)


SERVER_NAME = "xtqmtTradeGateway"
DEFAULT_CONFIG_PATH = "configs/trade_gateway.local.yaml"
DEFAULT_TOOL_NAMES: tuple[str, ...] = (
    "miniqmt.ensure_logged_in",
    "session.warm",
    "session.status",
    "session.close",
    "probe.connection",
    "account.show",
    "positions.list",
    "orders.list",
    "fills.list",
    "snapshot.l1",
    "order.status",
    "order.cancel",
    "order.place",
)
DEFAULT_RESOURCE_URIS: tuple[str, ...] = (
    "trade://capability/current",
    "trade://session/current",
    "trade://account/current",
    "trade://orders/today",
    "trade://fills/today",
    "diag://probe/latest",
    "diag://login/latest",
    "diag://order_place/latest",
    "diag://order_cancel/latest",
    "diag://order_status/latest",
)
DEFAULT_PROMPT_NAMES: tuple[str, ...] = (
    "trade-preflight",
    "trade-recovery",
    "order-followup",
)
ACCOUNT_CONTRACT_SINGLE_PRIMARY = "single_account_primary"
ACCOUNT_INPUT_MODE_SERVICE_CONTEXT = "service_context_only"


@dataclass(frozen=True)
class TradeAuditConfig:
    enabled: bool = True
    call_log_root: str = str(Path(DEFAULT_RUNTIME_PATHS.artifact_root) / "trade_gateway")
    call_log_name: str = "trade_gateway_calls.jsonl"


@dataclass(frozen=True)
class TradeOpsGatewayConfig:
    account_id: str = ""
    auto_account: bool = False
    execution_mode: str = "live"
    trading_day: date = field(default_factory=date.today)
    event_mode: str = "tick"
    output_dir: str = str(Path(DEFAULT_RUNTIME_PATHS.artifact_root) / "trade_ops")
    state_dir: str = str(Path(DEFAULT_RUNTIME_PATHS.state_root) / "trade_ops")
    qmt_exe: str = ""
    qmt_userdata: str = ""
    xtdata_port: int = 0
    session_id: int = 100
    session_candidates: tuple[int, ...] = (100, 101, 111)
    register_callback: bool = True
    connect_cooldown_seconds: float = 3.2
    enforce_connect_precheck: bool = True
    require_up_queue_file: bool = True
    enable_derived_session_fallback: bool = False
    max_session_attempts: int = 12
    connect_retries: int = 3
    connect_retry_interval_seconds: float = 3.0
    wake_wait_seconds: int = 30
    session_warm_timeout_seconds: float = 30.0
    require_connect_stage: bool = True
    require_subscribe_stage: bool = True
    require_snapshot_stage: bool = True
    snapshot_requires_position: bool = False
    allow_non_online_t0: bool = False
    idle_timeout_seconds: float = 20.0
    enforce_trading_session: bool = True
    pretrade_connect_window: int = 5
    pretrade_connect_threshold: float = 0.9
    pretrade_connect_interval_seconds: float = 3.0
    price_mode: str = "l1_protect"
    risk_max_single_order_notional: float = 200000.0
    risk_max_daily_notional: float = 2000000.0
    risk_white_list: tuple[str, ...] = ()
    kill_switch_file: str = ""


@dataclass(frozen=True)
class TradeLoginConfig:
    account_id: str = ""
    qmt_exe: str = ""
    qmt_userdata: str = ""
    credential_target: str = ""
    login_timeout_seconds: int = 45
    startup_grace_seconds: int = 8
    port_host: str = "127.0.0.1"
    port_num: int = 0


@dataclass(frozen=True)
class TradeGatewayConfig:
    identity: ServiceIdentity
    runtime: RuntimeConfig = field(default_factory=lambda: DEFAULT_RUNTIME_CONFIG)
    runtime_paths: ServiceRuntimePaths = field(default_factory=lambda: DEFAULT_RUNTIME_PATHS)
    bundle: XtquantBundleConfig = field(default_factory=lambda: DEFAULT_BUNDLE_CONFIG)
    qmt: QmtInstallConfig = field(default_factory=QmtInstallConfig)
    transport: TransportConfig = field(default_factory=lambda: TransportConfig(bind_port=8765))
    audit: TradeAuditConfig = field(default_factory=TradeAuditConfig)
    trade_ops: TradeOpsGatewayConfig = field(default_factory=TradeOpsGatewayConfig)
    login: TradeLoginConfig = field(default_factory=TradeLoginConfig)
    enabled_tools: tuple[str, ...] = DEFAULT_TOOL_NAMES
    enabled_resources: tuple[str, ...] = DEFAULT_RESOURCE_URIS
    enabled_prompts: tuple[str, ...] = DEFAULT_PROMPT_NAMES
    config_path: str = DEFAULT_CONFIG_PATH


def _clamp_session_warm_timeout_seconds(wake_wait_seconds: int, timeout_seconds: float) -> float:
    wake_budget = float(max(1, int(wake_wait_seconds or 0)))
    configured_timeout = float(timeout_seconds or 0.0)
    if configured_timeout <= 0:
        return wake_budget
    return max(configured_timeout, wake_budget)


def load_trade_gateway_config(
    path: str | Path | None = None,
    *,
    env: dict[str, str] | None = None,
    today: date | None = None,
) -> TradeGatewayConfig:
    active_env = env or os.environ
    default_today = today or date.today()
    explicit_path = str(path or "").strip()
    env_path = env_text(active_env, "XTQMT_TRADE_CONFIG")
    resolved_path = explicit_path or env_path or DEFAULT_CONFIG_PATH
    payload = load_yaml_payload(resolved_path, required=bool(explicit_path or env_path))

    server_payload = section(payload, "server")
    runtime_payload = section(payload, "runtime")
    paths_payload = section(payload, "paths")
    bundle_payload = section(payload, "bundle")
    qmt_payload = section(payload, "qmt")
    transport_payload = section(payload, "transport")
    audit_payload = section(payload, "audit")
    trade_payload = section(payload, "trade")
    login_payload = section(payload, "login")

    runtime_cfg = RuntimeConfig(
        python_home=env_text(active_env, "XTQMT_PYTHON_HOME", "XTQMT_RUNTIME_PYTHON_HOME") or str(pick(runtime_payload, "python_home", DEFAULT_RUNTIME_CONFIG.python_home) or DEFAULT_RUNTIME_CONFIG.python_home),
        venv_path=env_text(active_env, "XTQMT_VENV_PATH", "XTQMT_RUNTIME_VENV_PATH") or str(pick(runtime_payload, "venv_path", DEFAULT_RUNTIME_CONFIG.venv_path) or DEFAULT_RUNTIME_CONFIG.venv_path),
    )
    paths_cfg = ServiceRuntimePaths(
        config_root=str(pick(paths_payload, "config_root", DEFAULT_RUNTIME_PATHS.config_root) or DEFAULT_RUNTIME_PATHS.config_root),
        logs_root=str(pick(paths_payload, "logs_root", DEFAULT_RUNTIME_PATHS.logs_root) or DEFAULT_RUNTIME_PATHS.logs_root),
        state_root=str(pick(paths_payload, "state_root", DEFAULT_RUNTIME_PATHS.state_root) or DEFAULT_RUNTIME_PATHS.state_root),
        artifact_root=str(pick(paths_payload, "artifact_root", DEFAULT_RUNTIME_PATHS.artifact_root) or DEFAULT_RUNTIME_PATHS.artifact_root),
    )
    bundle_cfg = XtquantBundleConfig(
        bundle_root=env_text(active_env, "XTQMT_BUNDLE_ROOT") or str(pick(bundle_payload, "bundle_root", DEFAULT_BUNDLE_CONFIG.bundle_root) or DEFAULT_BUNDLE_CONFIG.bundle_root),
        abi_tag=env_text(active_env, "XTQMT_ABI_TAG") or str(pick(bundle_payload, "abi_tag", DEFAULT_BUNDLE_CONFIG.abi_tag) or DEFAULT_BUNDLE_CONFIG.abi_tag),
        package_dir_name=str(pick(bundle_payload, "package_dir_name", DEFAULT_BUNDLE_CONFIG.package_dir_name) or DEFAULT_BUNDLE_CONFIG.package_dir_name),
        pth_filename=str(pick(bundle_payload, "pth_filename", DEFAULT_BUNDLE_CONFIG.pth_filename) or DEFAULT_BUNDLE_CONFIG.pth_filename),
    )
    qmt_cfg = QmtInstallConfig(
        account_id=env_text(active_env, "XTQMT_ACCOUNT_ID") or str(pick(qmt_payload, "account_id", "") or ""),
        qmt_exe=env_text(active_env, "XTQMT_QMT_EXE") or str(pick(qmt_payload, "qmt_exe", "") or ""),
        qmt_userdata=env_text(active_env, "XTQMT_QMT_USERDATA") or str(pick(qmt_payload, "qmt_userdata", "") or ""),
        credential_target=env_text(active_env, "XTQMT_CREDENTIAL_TARGET") or str(pick(qmt_payload, "credential_target", "") or ""),
        xtdata_host=str(pick(qmt_payload, "xtdata_host", "127.0.0.1") or "127.0.0.1"),
        xtdata_port=coerce_int(pick(qmt_payload, "xtdata_port"), 0),
    )
    transport_cfg = TransportConfig(
        bind_host=env_text(active_env, "XTQMT_TRADE_BIND_HOST") or str(pick(transport_payload, "bind_host", "127.0.0.1") or "127.0.0.1"),
        bind_port=coerce_int(env_text(active_env, "XTQMT_TRADE_BIND_PORT") or pick(transport_payload, "bind_port"), 8765),
        mcp_path=normalize_http_path(str(pick(transport_payload, "mcp_path", "/mcp") or "/mcp"), "/mcp"),
        health_path=normalize_http_path(str(pick(transport_payload, "health_path", "/healthz") or "/healthz"), "/healthz"),
        protocol_version_http=str(pick(transport_payload, "protocol_version_http", "2025-03-26") or "2025-03-26"),
        allow_origin_hosts=coerce_str_tuple(pick(transport_payload, "allow_origin_hosts"), ("127.0.0.1", "localhost", "::1")),
    )
    audit_root_default = str(Path(paths_cfg.artifact_root) / "trade_gateway")
    audit_cfg = TradeAuditConfig(
        enabled=coerce_bool(pick(audit_payload, "enabled"), True),
        call_log_root=str(pick(audit_payload, "call_log_root", audit_root_default) or audit_root_default),
        call_log_name=str(pick(audit_payload, "call_log_name", "trade_gateway_calls.jsonl") or "trade_gateway_calls.jsonl"),
    )
    wake_wait_seconds = coerce_int(pick(trade_payload, "wake_wait_seconds"), 30)
    session_warm_timeout_seconds = _clamp_session_warm_timeout_seconds(
        wake_wait_seconds,
        coerce_float(pick(trade_payload, "session_warm_timeout_seconds"), 30.0),
    )
    trade_cfg = TradeOpsGatewayConfig(
        account_id=str(pick(trade_payload, "account_id", qmt_cfg.account_id) or qmt_cfg.account_id),
        auto_account=coerce_bool(pick(trade_payload, "auto_account"), False),
        execution_mode=str(pick(trade_payload, "execution_mode", "live") or "live").strip().lower(),
        trading_day=coerce_date(pick(trade_payload, "trading_day"), default_today),
        event_mode=str(pick(trade_payload, "event_mode", "tick") or "tick"),
        output_dir=str(pick(trade_payload, "output_dir", Path(paths_cfg.artifact_root) / "trade_ops") or (Path(paths_cfg.artifact_root) / "trade_ops")),
        state_dir=str(pick(trade_payload, "state_dir", Path(paths_cfg.state_root) / "trade_ops") or (Path(paths_cfg.state_root) / "trade_ops")),
        qmt_exe=str(pick(trade_payload, "qmt_exe", qmt_cfg.qmt_exe) or qmt_cfg.qmt_exe),
        qmt_userdata=str(pick(trade_payload, "qmt_userdata", qmt_cfg.qmt_userdata) or qmt_cfg.qmt_userdata),
        xtdata_port=coerce_int(pick(trade_payload, "xtdata_port"), qmt_cfg.xtdata_port),
        session_id=coerce_int(pick(trade_payload, "session_id"), 100),
        session_candidates=coerce_int_tuple(pick(trade_payload, "session_candidates"), (100, 101, 111)),
        register_callback=coerce_bool(pick(trade_payload, "register_callback"), True),
        connect_cooldown_seconds=coerce_float(pick(trade_payload, "connect_cooldown_seconds"), 3.2),
        enforce_connect_precheck=coerce_bool(pick(trade_payload, "enforce_connect_precheck"), True),
        require_up_queue_file=coerce_bool(pick(trade_payload, "require_up_queue_file"), True),
        enable_derived_session_fallback=coerce_bool(pick(trade_payload, "enable_derived_session_fallback"), False),
        max_session_attempts=coerce_int(pick(trade_payload, "max_session_attempts"), 12),
        connect_retries=coerce_int(pick(trade_payload, "connect_retries"), 3),
        connect_retry_interval_seconds=coerce_float(pick(trade_payload, "connect_retry_interval_seconds"), 3.0),
        wake_wait_seconds=wake_wait_seconds,
        session_warm_timeout_seconds=session_warm_timeout_seconds,
        require_connect_stage=coerce_bool(pick(trade_payload, "require_connect_stage"), True),
        require_subscribe_stage=coerce_bool(pick(trade_payload, "require_subscribe_stage"), True),
        require_snapshot_stage=coerce_bool(pick(trade_payload, "require_snapshot_stage"), True),
        snapshot_requires_position=coerce_bool(pick(trade_payload, "snapshot_requires_position"), False),
        allow_non_online_t0=coerce_bool(pick(trade_payload, "allow_non_online_t0"), False),
        idle_timeout_seconds=coerce_float(pick(trade_payload, "idle_timeout_seconds"), 20.0),
        enforce_trading_session=coerce_bool(pick(trade_payload, "enforce_trading_session"), True),
        pretrade_connect_window=coerce_int(pick(trade_payload, "pretrade_connect_window"), 5),
        pretrade_connect_threshold=coerce_float(pick(trade_payload, "pretrade_connect_threshold"), 0.9),
        pretrade_connect_interval_seconds=coerce_float(pick(trade_payload, "pretrade_connect_interval_seconds"), 3.0),
        price_mode=str(pick(trade_payload, "price_mode", "l1_protect") or "l1_protect"),
        risk_max_single_order_notional=coerce_float(pick(trade_payload, "risk_max_single_order_notional"), 200000.0),
        risk_max_daily_notional=coerce_float(pick(trade_payload, "risk_max_daily_notional"), 2000000.0),
        risk_white_list=coerce_str_tuple(pick(trade_payload, "risk_white_list"), ()),
        kill_switch_file=str(pick(trade_payload, "kill_switch_file", "") or ""),
    )
    login_cfg = TradeLoginConfig(
        account_id=str(pick(login_payload, "account_id", qmt_cfg.account_id) or qmt_cfg.account_id),
        qmt_exe=str(pick(login_payload, "qmt_exe", qmt_cfg.qmt_exe) or qmt_cfg.qmt_exe),
        qmt_userdata=str(pick(login_payload, "qmt_userdata", qmt_cfg.qmt_userdata) or qmt_cfg.qmt_userdata),
        credential_target=str(pick(login_payload, "credential_target", qmt_cfg.credential_target) or qmt_cfg.credential_target),
        login_timeout_seconds=coerce_int(pick(login_payload, "login_timeout_seconds"), 45),
        startup_grace_seconds=coerce_int(pick(login_payload, "startup_grace_seconds"), 8),
        port_host=str(pick(login_payload, "port_host", qmt_cfg.xtdata_host) or qmt_cfg.xtdata_host),
        port_num=coerce_int(pick(login_payload, "port_num"), qmt_cfg.xtdata_port),
    )
    return TradeGatewayConfig(
        identity=ServiceIdentity(
            server_name=str(pick(server_payload, "server_name", SERVER_NAME) or SERVER_NAME),
            server_version=str(pick(server_payload, "server_version", __version__) or __version__),
            protocol_version=str(pick(server_payload, "protocol_version", "2025-03-26") or "2025-03-26"),
        ),
        runtime=runtime_cfg,
        runtime_paths=paths_cfg,
        bundle=bundle_cfg,
        qmt=qmt_cfg,
        transport=transport_cfg,
        audit=audit_cfg,
        trade_ops=trade_cfg,
        login=login_cfg,
        enabled_tools=coerce_str_tuple(pick(server_payload, "enabled_tools"), DEFAULT_TOOL_NAMES) or DEFAULT_TOOL_NAMES,
        enabled_resources=coerce_str_tuple(pick(server_payload, "enabled_resources"), DEFAULT_RESOURCE_URIS) or DEFAULT_RESOURCE_URIS,
        enabled_prompts=coerce_str_tuple(pick(server_payload, "enabled_prompts"), DEFAULT_PROMPT_NAMES) or DEFAULT_PROMPT_NAMES,
        config_path=str(Path(resolved_path)),
    )
