from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.miniqmt_login import MiniQmtLoginConfig, ensure_miniqmt_logged_in


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="launch MiniQMT and ensure login")
    parser.add_argument("--qmt-exe", default="", help="XtMiniQmt.exe path")
    parser.add_argument("--account-id", default="", help="MiniQMT account id")
    parser.add_argument("--credential-target", default="", help="Windows Credential Manager target")
    parser.add_argument("--login-timeout-seconds", type=int, default=45, help="login timeout seconds")
    parser.add_argument("--qmt-userdata", default="", help="optional userdata_mini path")
    parser.add_argument("--report-json", default="", help="optional output report path")
    return parser.parse_args()


def resolve_report_path(raw_path: str) -> Path:
    explicit_path = str(raw_path or "").strip()
    if explicit_path:
        return Path(explicit_path).expanduser()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(r"D:\xtquant-mcp\instance\prod\artifacts\miniqmt_login") / f"miniqmt_login_{timestamp}.json"


def main() -> int:
    args = parse_args()
    result = ensure_miniqmt_logged_in(
        MiniQmtLoginConfig(
            qmt_exe=str(args.qmt_exe or "").strip(),
            account_id=str(args.account_id or "").strip(),
            credential_target=str(args.credential_target or "").strip(),
            login_timeout_seconds=int(args.login_timeout_seconds),
            qmt_userdata=str(args.qmt_userdata or "").strip(),
        )
    )
    payload = result.as_payload()
    report_path = resolve_report_path(str(args.report_json or ""))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if bool(result.ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())

