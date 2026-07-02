from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ServiceRuntimePaths:
    config_root: str
    logs_root: str
    state_root: str
    artifact_root: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class XtquantBundleConfig:
    bundle_root: str
    abi_tag: str = "cp313-win_amd64"
    package_dir_name: str = "xtquant"
    pth_filename: str = "xtquant_vendor.pth"

    def package_root(self) -> Path:
        return Path(self.bundle_root).expanduser().resolve() / self.package_dir_name

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QmtInstallConfig:
    account_id: str = ""
    qmt_exe: str = ""
    qmt_userdata: str = ""
    credential_target: str = ""
    xtdata_host: str = "127.0.0.1"
    xtdata_port: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ServiceIdentity:
    server_name: str
    server_version: str
    protocol_version: str = "2025-03-26"


@dataclass(frozen=True)
class TransportConfig:
    bind_host: str = "127.0.0.1"
    bind_port: int = 8765
    mcp_path: str = "/mcp"
    health_path: str = "/healthz"
    protocol_version_http: str = "2025-03-26"
    allow_origin_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "::1")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeConfig:
    python_home: str = r"C:\Python313\python.exe"
    venv_path: str = r"C:\xtquant-mcp-example\venv313"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_RUNTIME_PATHS = ServiceRuntimePaths(
    config_root=r"C:\xtquant-mcp-example\instance\prod\config",
    logs_root=r"C:\xtquant-mcp-example\instance\prod\logs",
    state_root=r"C:\xtquant-mcp-example\instance\prod\state",
    artifact_root=r"C:\xtquant-mcp-example\instance\prod\artifacts",
)

DEFAULT_BUNDLE_CONFIG = XtquantBundleConfig(bundle_root=r"C:\xtquant-mcp-example\vendor\xtquant_250807")
DEFAULT_RUNTIME_CONFIG = RuntimeConfig()
