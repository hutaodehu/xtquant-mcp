"""xtquant bundle resolution helpers for the rebuilt runtime."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .bundle import ensure_bundle_package_on_sys_path, validate_xtquant_bundle
from .settings import DEFAULT_BUNDLE_CONFIG, XtquantBundleConfig


def bundle_config_from_env() -> XtquantBundleConfig:
    bundle_root = str(os.environ.get("XTQMT_BUNDLE_ROOT", DEFAULT_BUNDLE_CONFIG.bundle_root) or DEFAULT_BUNDLE_CONFIG.bundle_root).strip()
    abi_tag = str(os.environ.get("XTQMT_ABI_TAG", DEFAULT_BUNDLE_CONFIG.abi_tag) or DEFAULT_BUNDLE_CONFIG.abi_tag).strip()
    package_dir_name = str(os.environ.get("XTQMT_PACKAGE_DIR", DEFAULT_BUNDLE_CONFIG.package_dir_name) or DEFAULT_BUNDLE_CONFIG.package_dir_name).strip()
    return XtquantBundleConfig(
        bundle_root=bundle_root,
        abi_tag=abi_tag,
        package_dir_name=package_dir_name,
        pth_filename=DEFAULT_BUNDLE_CONFIG.pth_filename,
    )


def iter_xtquant_site_candidates() -> list[Path]:
    cfg = bundle_config_from_env()
    return [Path(cfg.bundle_root).expanduser().resolve()]


def locate_xtquant_site() -> Optional[Path]:
    cfg = bundle_config_from_env()
    result = validate_xtquant_bundle(cfg)
    if result.ok:
        return Path(result.bundle_root)
    return None


def ensure_xtquant_on_path() -> Optional[Path]:
    cfg = bundle_config_from_env()
    result = validate_xtquant_bundle(cfg)
    if not result.ok:
        return None
    return ensure_bundle_package_on_sys_path(cfg)
