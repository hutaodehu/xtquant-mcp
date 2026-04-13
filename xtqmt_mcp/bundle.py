from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys
from typing import Any

from .settings import XtquantBundleConfig


@dataclass(frozen=True)
class BundleValidationResult:
    ok: bool
    bundle_root: str
    package_root: str
    abi_tag: str
    required_files: tuple[str, ...]
    missing_files: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "bundle_root": self.bundle_root,
            "package_root": self.package_root,
            "abi_tag": self.abi_tag,
            "required_files": list(self.required_files),
            "missing_files": list(self.missing_files),
        }


def _required_binary_names(abi_tag: str) -> tuple[str, ...]:
    return (
        f"xtpythonclient.{abi_tag}.pyd",
        f"datacenter.{abi_tag}.pyd",
        "datacenter_shared.dll",
    )


def validate_xtquant_bundle(config: XtquantBundleConfig) -> BundleValidationResult:
    package_root = config.package_root()
    required = _required_binary_names(config.abi_tag)
    missing = tuple(name for name in required if not (package_root / name).exists())
    return BundleValidationResult(
        ok=package_root.exists() and not missing,
        bundle_root=str(Path(config.bundle_root).expanduser().resolve()),
        package_root=str(package_root),
        abi_tag=config.abi_tag,
        required_files=required,
        missing_files=missing,
    )


def ensure_bundle_package_on_sys_path(config: XtquantBundleConfig) -> Path:
    package_root = config.package_root()
    bundle_root = package_root.parent
    token = str(bundle_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return bundle_root


def write_vendor_pth(config: XtquantBundleConfig, site_packages_dir: str | Path) -> Path:
    site_root = Path(site_packages_dir).expanduser().resolve()
    site_root.mkdir(parents=True, exist_ok=True)
    pth_path = site_root / config.pth_filename
    pth_path.write_text(str(Path(config.bundle_root).expanduser().resolve()) + "\n", encoding="utf-8")
    return pth_path


def xtquant_import_spec(config: XtquantBundleConfig):
    ensure_bundle_package_on_sys_path(config)
    return importlib.util.find_spec("xtquant")
