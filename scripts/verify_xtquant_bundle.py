from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.bundle import validate_xtquant_bundle, write_vendor_pth, xtquant_import_spec
from xtqmt_mcp.settings import XtquantBundleConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="validate xtquant vendor bundle and optional import mount")
    parser.add_argument("--bundle-root", default=r"D:\xtquant-mcp\vendor\xtquant_250807", help="xtquant bundle root")
    parser.add_argument("--abi-tag", default="cp313-win_amd64", help="expected ABI tag")
    parser.add_argument("--package-dir-name", default="xtquant", help="vendor package dir name")
    parser.add_argument("--write-pth", default="", help="optional site-packages path for xtquant_vendor.pth")
    parser.add_argument("--import-check", action="store_true", help="also test import spec resolution")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = XtquantBundleConfig(
        bundle_root=str(args.bundle_root),
        abi_tag=str(args.abi_tag),
        package_dir_name=str(args.package_dir_name),
    )
    result = validate_xtquant_bundle(cfg)
    payload = {"bundle": result.as_dict()}
    if args.write_pth:
        payload["pth_path"] = str(write_vendor_pth(cfg, args.write_pth))
    if args.import_check:
        spec = xtquant_import_spec(cfg)
        payload["import_spec_found"] = spec is not None
        payload["import_origin"] = str(getattr(spec, "origin", "") or "")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if bool(result.ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
