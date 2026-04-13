from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any

from xtqmt_mcp import __version__
from xtqmt_mcp.config_utils import (
    coerce_bool,
    coerce_int,
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


SERVER_NAME = "xtqmtDataGateway"
DEFAULT_CONFIG_PATH = "configs/data_gateway.local.yaml"
DEFAULT_TOOL_NAMES: tuple[str, ...] = (
    "xtdata.status",
    "xtdata.instruments.search",
    "xtdata.calendar.query",
    "xtdata.snapshot.batch",
    "xtdata.history.get_bars",
    "xtdata.history.get_ticks",
    "xtdata.download.submit",
    "xtdata.download.status",
    "xtdata.download.cancel",
    "xtdata.subscribe.start",
    "xtdata.subscribe.stop",
)
DEFAULT_RESOURCE_URIS: tuple[str, ...] = (
    "xtdata://service/status",
    "xtdata://jobs/active",
    "xtdata://catalog/instruments",
    "xtdata://leases/active",
)
DEFAULT_PROMPT_NAMES: tuple[str, ...] = (
    "data-backfill-plan",
    "data-download-triage",
    "xtdata-service-recover",
)


@dataclass(frozen=True)
class DataAuditConfig:
    enabled: bool = True
    call_log_root: str = str(Path(DEFAULT_RUNTIME_PATHS.artifact_root) / "data_gateway")
    call_log_name: str = "data_gateway_calls.jsonl"


@dataclass(frozen=True)
class DataGatewayRuntimeConfig:
    jobs_root: str = str(Path(DEFAULT_RUNTIME_PATHS.state_root) / "data_jobs")
    subscriptions_root: str = str(Path(DEFAULT_RUNTIME_PATHS.state_root) / "subscriptions")
    download_root: str = str(Path(DEFAULT_RUNTIME_PATHS.artifact_root) / "data_downloads")
    max_concurrent_jobs: int = 1
    max_query_symbols: int = 200


@dataclass(frozen=True)
class DataGatewayConfig:
    identity: ServiceIdentity
    runtime: RuntimeConfig = field(default_factory=lambda: DEFAULT_RUNTIME_CONFIG)
    runtime_paths: ServiceRuntimePaths = field(default_factory=lambda: DEFAULT_RUNTIME_PATHS)
    bundle: XtquantBundleConfig = field(default_factory=lambda: DEFAULT_BUNDLE_CONFIG)
    qmt: QmtInstallConfig = field(default_factory=QmtInstallConfig)
    transport: TransportConfig = field(default_factory=lambda: TransportConfig(bind_port=8766))
    audit: DataAuditConfig = field(default_factory=DataAuditConfig)
    service: DataGatewayRuntimeConfig = field(default_factory=DataGatewayRuntimeConfig)
    enabled_tools: tuple[str, ...] = DEFAULT_TOOL_NAMES
    enabled_resources: tuple[str, ...] = DEFAULT_RESOURCE_URIS
    enabled_prompts: tuple[str, ...] = DEFAULT_PROMPT_NAMES
    config_path: str = DEFAULT_CONFIG_PATH


def load_data_gateway_config(
    path: str | Path | None = None,
    *,
    env: dict[str, str] | None = None,
) -> DataGatewayConfig:
    active_env = env or os.environ
    explicit_path = str(path or "").strip()
    env_path = env_text(active_env, "XTQMT_DATA_CONFIG")
    resolved_path = explicit_path or env_path or DEFAULT_CONFIG_PATH
    payload = load_yaml_payload(resolved_path, required=bool(explicit_path or env_path))

    server_payload = section(payload, "server")
    runtime_payload = section(payload, "runtime")
    paths_payload = section(payload, "paths")
    bundle_payload = section(payload, "bundle")
    qmt_payload = section(payload, "qmt")
    transport_payload = section(payload, "transport")
    audit_payload = section(payload, "audit")
    service_payload = section(payload, "data")

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
        xtdata_port=coerce_int(pick(qmt_payload, "xtdata_port"), 58610),
    )
    transport_cfg = TransportConfig(
        bind_host=env_text(active_env, "XTQMT_DATA_BIND_HOST") or str(pick(transport_payload, "bind_host", "127.0.0.1") or "127.0.0.1"),
        bind_port=coerce_int(env_text(active_env, "XTQMT_DATA_BIND_PORT") or pick(transport_payload, "bind_port"), 8766),
        mcp_path=normalize_http_path(str(pick(transport_payload, "mcp_path", "/mcp") or "/mcp"), "/mcp"),
        health_path=normalize_http_path(str(pick(transport_payload, "health_path", "/healthz") or "/healthz"), "/healthz"),
        protocol_version_http=str(pick(transport_payload, "protocol_version_http", "2025-03-26") or "2025-03-26"),
        allow_origin_hosts=coerce_str_tuple(pick(transport_payload, "allow_origin_hosts"), ("127.0.0.1", "localhost", "::1")),
    )
    audit_root_default = str(Path(paths_cfg.artifact_root) / "data_gateway")
    audit_cfg = DataAuditConfig(
        enabled=coerce_bool(pick(audit_payload, "enabled"), True),
        call_log_root=str(pick(audit_payload, "call_log_root", audit_root_default) or audit_root_default),
        call_log_name=str(pick(audit_payload, "call_log_name", "data_gateway_calls.jsonl") or "data_gateway_calls.jsonl"),
    )
    service_cfg = DataGatewayRuntimeConfig(
        jobs_root=str(pick(service_payload, "jobs_root", Path(paths_cfg.state_root) / "data_jobs") or (Path(paths_cfg.state_root) / "data_jobs")),
        subscriptions_root=str(pick(service_payload, "subscriptions_root", Path(paths_cfg.state_root) / "subscriptions") or (Path(paths_cfg.state_root) / "subscriptions")),
        download_root=str(pick(service_payload, "download_root", Path(paths_cfg.artifact_root) / "data_downloads") or (Path(paths_cfg.artifact_root) / "data_downloads")),
        max_concurrent_jobs=coerce_int(pick(service_payload, "max_concurrent_jobs"), 1),
        max_query_symbols=coerce_int(pick(service_payload, "max_query_symbols"), 200),
    )
    return DataGatewayConfig(
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
        service=service_cfg,
        enabled_tools=coerce_str_tuple(pick(server_payload, "enabled_tools"), DEFAULT_TOOL_NAMES) or DEFAULT_TOOL_NAMES,
        enabled_resources=coerce_str_tuple(pick(server_payload, "enabled_resources"), DEFAULT_RESOURCE_URIS) or DEFAULT_RESOURCE_URIS,
        enabled_prompts=coerce_str_tuple(pick(server_payload, "enabled_prompts"), DEFAULT_PROMPT_NAMES) or DEFAULT_PROMPT_NAMES,
        config_path=str(Path(resolved_path)),
    )
