from __future__ import annotations

"""Tiny CLI shim that keeps the repo root on ``sys.path`` before
delegating to ``xtqmt_mcp.data_gateway.server.main`` so the service can be
started with ``python scripts/run_data_gateway_http.py``.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.data_gateway.server import main


if __name__ == "__main__":
    raise SystemExit(main())
