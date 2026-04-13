from __future__ import annotations

from pathlib import Path
import shutil
import time
from types import SimpleNamespace
import unittest
from unittest import mock
import uuid

from xtqmt_mcp.data_gateway.config import DataAuditConfig, DataGatewayConfig, DataGatewayRuntimeConfig
from xtqmt_mcp.data_gateway.service import DataGatewayService, _frame_records
from xtqmt_mcp.settings import QmtInstallConfig, ServiceIdentity, ServiceRuntimePaths, TransportConfig, XtquantBundleConfig


ROOT = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = ROOT / ".tmp" / "tests"
TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)


class _WorkspaceTempDir:
    def __init__(self) -> None:
        self.path = TEST_TMP_ROOT / f"case_{uuid.uuid4().hex}"

    def __enter__(self) -> Path:
        self.path.mkdir(parents=True, exist_ok=False)
        return self.path

    def __exit__(self, exc_type, exc, tb) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


class _FakeBackend:
    def __init__(self) -> None:
        self.unsubscribed: list[int] = []
        self._next_seq = 100
        self.stop_called = False

    def get_sector_list(self) -> list[str]:
        return ["沪深A股", "上证A股"]

    def get_stock_list_in_sector(self, sector_name: str, real_timetag: int = -1) -> list[str]:
        return ["000001.SZ", "600000.SH"]

    def get_instrument_detail_list(self, stock_list: list[str], iscomplete: bool = False) -> dict[str, dict[str, object]]:
        mapping = {
            "000001.SZ": {"InstrumentName": "PingAn", "ExchangeCode": "SZ"},
            "600000.SH": {"InstrumentName": "PFBank", "ExchangeCode": "SH"},
        }
        return {code: mapping.get(code, {}) for code in stock_list}

    def get_trading_dates(self, market: str, start_time: str = "", end_time: str = "", count: int = -1) -> list[int]:
        return [1743033600000, 1743292800000]

    def get_trading_calendar(self, market: str, start_time: str = "", end_time: str = "") -> list[str]:
        return ["20260327", "20260330"]

    def get_full_tick(self, code_list: list[str]) -> dict[str, object]:
        return {code: {"time": "20260327093000", "lastPrice": 10.0} for code in code_list}

    def get_market_data_ex(
        self,
        field_list: list[str],
        stock_list: list[str],
        period: str,
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        dividend_type: str = "none",
        fill_data: bool = True,
    ) -> dict[str, list[dict[str, object]]]:
        return {
            code: [
                {"time": "2026-03-26", "open": 10.0, "close": 10.1},
                {"time": "2026-03-27", "open": 10.1, "close": 10.3},
            ]
            for code in stock_list
        }

    def get_market_data(
        self,
        field_list: list[str],
        stock_list: list[str],
        period: str,
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        dividend_type: str = "none",
        fill_data: bool = True,
    ) -> dict[str, list[dict[str, object]]]:
        return {
            code: [
                {"time": "20260327093000", "lastPrice": 10.0},
                {"time": "20260327093100", "lastPrice": 10.2},
            ]
            for code in stock_list
        }

    def download_history_data2(
        self,
        stock_list: list[str],
        period: str,
        start_time: str = "",
        end_time: str = "",
        callback=None,
        incrementally: bool | None = None,
    ) -> dict[str, dict[str, object]]:
        if callback is not None:
            callback({"finished": 1, "total": 2, "message": "half"})
            callback({"finished": 2, "total": 2, "message": "done"})
        return {code: {"period": period, "start_time": start_time, "end_time": end_time} for code in stock_list}

    def stop_download(self) -> None:
        self.stop_called = True

    def subscribe_quote2(
        self,
        stock_code: str,
        period: str = "tick",
        start_time: str = "",
        end_time: str = "",
        count: int = 0,
        dividend_type: str | None = None,
        callback=None,
    ) -> int:
        self._next_seq += 1
        if callback is not None:
            callback({stock_code: [{"time": "20260327093000", "lastPrice": 10.5}]})
        return self._next_seq

    def subscribe_quote(
        self,
        stock_code: str,
        period: str = "tick",
        start_time: str = "",
        end_time: str = "",
        count: int = 0,
        callback=None,
    ) -> int:
        return self.subscribe_quote2(stock_code, period, start_time, end_time, count, None, callback)

    def unsubscribe_quote(self, seq: int) -> None:
        self.unsubscribed.append(int(seq))


class _NoEventBackend(_FakeBackend):
    def subscribe_quote2(
        self,
        stock_code: str,
        period: str = "tick",
        start_time: str = "",
        end_time: str = "",
        count: int = 0,
        dividend_type: str | None = None,
        callback=None,
    ) -> int:
        self._next_seq += 1
        return self._next_seq


class _AmbiguousBoolColumns:
    def __init__(self, values: list[str]) -> None:
        self._values = list(values)

    def __iter__(self):
        return iter(self._values)

    def __bool__(self) -> bool:
        raise ValueError("ambiguous truth value")


class _FrameWithAmbiguousColumns:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self._records = [dict(item) for item in records]
        columns = list(self._records[0].keys()) if self._records else []
        self.columns = _AmbiguousBoolColumns(columns)

    def reset_index(self) -> "_FrameWithAmbiguousColumns":
        return self

    def rename(self, *, columns: dict[str, str]) -> "_FrameWithAmbiguousColumns":
        renamed = [{columns.get(key, key): value for key, value in row.items()} for row in self._records]
        return _FrameWithAmbiguousColumns(renamed)

    def to_dict(self, orient: str = "records") -> list[dict[str, object]]:
        if orient != "records":
            raise ValueError("only records orient is supported")
        return [dict(item) for item in self._records]


class DataGatewayServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = _WorkspaceTempDir()
        root = self.tempdir.__enter__()
        self.backend = _FakeBackend()
        self.now_box = ["2026-03-27T09:30:00"]
        self.config = DataGatewayConfig(
            identity=ServiceIdentity(server_name="xtqmtDataGateway", server_version="test"),
            runtime_paths=ServiceRuntimePaths(
                config_root=str(root / "config"),
                logs_root=str(root / "logs"),
                state_root=str(root / "state"),
                artifact_root=str(root / "artifacts"),
            ),
            bundle=XtquantBundleConfig(bundle_root=str(root / "vendor")),
            qmt=QmtInstallConfig(),
            transport=TransportConfig(bind_port=0),
            audit=DataAuditConfig(call_log_root=str(root / "artifacts" / "data_gateway")),
            service=DataGatewayRuntimeConfig(
                jobs_root=str(root / "state" / "data_jobs"),
                subscriptions_root=str(root / "state" / "subscriptions"),
                download_root=str(root / "artifacts" / "data_downloads"),
                max_concurrent_jobs=1,
                max_query_symbols=5,
            ),
        )
        self.service = DataGatewayService(
            self.config,
            backend=self.backend,
            now_fn=lambda: self.now_box[0],
            uuid_factory=lambda: "sub-1",
        )

    def tearDown(self) -> None:
        self.tempdir.__exit__(None, None, None)

    def test_frame_records_supports_columns_with_ambiguous_truth_value(self) -> None:
        frame = _FrameWithAmbiguousColumns(
            [
                {"index": "20260331", "open": 11.0, "close": 11.08},
            ]
        )
        rows = _frame_records(frame)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["time"], "20260331")
        self.assertEqual(rows[0]["open"], 11.0)

    def test_status_search_history_download_and_subscription(self) -> None:
        bundle_result = SimpleNamespace(
            ok=True,
            as_dict=lambda: {
                "ok": True,
                "bundle_root": self.config.bundle.bundle_root,
                "package_root": str(Path(self.config.bundle.bundle_root) / "xtquant"),
                "abi_tag": self.config.bundle.abi_tag,
                "required_files": [],
                "missing_files": [],
            },
        )
        with mock.patch("xtqmt_mcp.data_gateway.service.validate_xtquant_bundle", return_value=bundle_result), mock.patch(
            "xtqmt_mcp.data_gateway.service.xtquant_import_spec",
            return_value=SimpleNamespace(origin="vendor://xtquant"),
        ), mock.patch("xtqmt_mcp.data_gateway.service.port_ready", return_value=True):
            status = self.service.status_summary()
        self.assertTrue(status.ok)
        self.assertTrue(status.payload["ready"])

        search = self.service.instruments_search({"query": "ping"})
        self.assertTrue(search.ok)
        self.assertEqual(search.payload["count"], 1)
        self.assertEqual(search.payload["items"][0]["code"], "000001.SZ")

        bars = self.service.history_get_bars({"codes": ["000001.SZ"], "period": "1d"})
        self.assertTrue(bars.ok)
        self.assertEqual(len(bars.payload["items"]["000001.SZ"]), 2)

        ticks = self.service.history_get_ticks({"codes": ["000001.SZ"]})
        self.assertTrue(ticks.ok)
        self.assertEqual(len(ticks.payload["items"]["000001.SZ"]), 2)

        snapshot = self.service.snapshot_batch({"codes": ["000001.SZ"]})
        self.assertTrue(snapshot.ok)
        self.assertEqual(snapshot.payload["items"][0]["lastPrice"], 10.0)

        submit = self.service.download_submit({"codes": ["000001.SZ"], "period": "1d", "start_time": "20260301", "end_time": "20260327"})
        self.assertTrue(submit.ok)
        job_id = submit.payload["job_id"]
        deadline = time.time() + 3.0
        status_payload = {}
        while time.time() < deadline:
            status_result = self.service.download_status({"job_id": job_id})
            status_payload = status_result.payload
            if status_payload.get("status") == "completed":
                break
            time.sleep(0.05)
        self.assertEqual(status_payload.get("status"), "completed")
        self.assertEqual(status_payload["progress_finished"], 2)

        with mock.patch("xtqmt_mcp.data_gateway.service.port_ready", return_value=True):
            started = self.service.subscribe_start({"codes": ["000001.SZ"], "period": "tick"})
        self.assertTrue(started.ok)
        self.assertEqual(started.payload["subscription_id"], "sub-1")
        self.assertEqual(started.payload["capability"]["stability"], "experimental")
        self.assertEqual(started.payload["capability"]["reconnect_strategy"], "explicit_rebuild_required")
        self.assertTrue(started.payload["callback_loop_alive"])
        self.assertTrue(started.payload["observed_event"])
        self.assertFalse(started.payload["needs_rebuild"])
        self.assertEqual(started.payload["rebuild_reason"], "ok")
        self.assertEqual(started.payload["recovery_action"], "hold_lease")
        self.assertEqual(started.payload["recovery"]["lease_state"], "active")
        self.assertFalse(started.payload["recovery"]["proven_live_reconnect"])
        with mock.patch("xtqmt_mcp.data_gateway.service.port_ready", return_value=True):
            leases = self.service.list_subscriptions_payload()
        self.assertEqual(leases["capability"]["stability"], "experimental")
        self.assertEqual(leases["capability"]["reconnect_strategy"], "explicit_rebuild_required")
        self.assertEqual(leases["count"], 1)
        self.assertEqual(leases["active_count"], 1)
        self.assertEqual(leases["stale_count"], 0)
        self.assertEqual(leases["needs_rebuild_count"], 0)
        self.assertEqual(leases["rebuild_reasons"], {"ok": 1})
        self.assertEqual(leases["recovery_summary"]["active"], 1)
        self.assertEqual(leases["items"][0]["lease_state"], "active")
        self.assertEqual(leases["items"][0]["resolved_runtime_endpoint"]["host"], "127.0.0.1")
        self.assertTrue(leases["items"][0]["resolved_runtime_endpoint"]["matches_configured"])
        with mock.patch("xtqmt_mcp.data_gateway.service.port_ready", return_value=True):
            stopped = self.service.subscribe_stop({"subscription_id": "sub-1"})
        self.assertTrue(stopped.ok)
        self.assertEqual(stopped.payload["lease_state"], "stopped")
        self.assertTrue(stopped.payload["needs_rebuild"])
        self.assertEqual(stopped.payload["rebuild_reason"], "client_stop")
        self.assertEqual(stopped.payload["recovery"]["stop_reason"], "client_stop")
        self.assertEqual(stopped.payload["recovery_action"], "explicit_rebuild_required")
        self.assertTrue(self.backend.unsubscribed)

    def test_subscription_lease_marks_stale_when_no_events_arrive(self) -> None:
        service = DataGatewayService(
            self.config,
            backend=_NoEventBackend(),
            now_fn=lambda: self.now_box[0],
            uuid_factory=lambda: "sub-noevent",
        )
        with mock.patch("xtqmt_mcp.data_gateway.service.port_ready", return_value=True):
            started = service.subscribe_start({"codes": ["000001.SZ"], "period": "tick"})
        self.assertTrue(started.ok)
        self.now_box[0] = "2026-03-27T09:31:00"
        with mock.patch("xtqmt_mcp.data_gateway.service.port_ready", return_value=True):
            leases = service.list_subscriptions_payload()
        self.assertEqual(leases["stale_count"], 1)
        self.assertEqual(leases["needs_rebuild_count"], 1)
        self.assertEqual(leases["items"][0]["lease_state"], "stale")
        self.assertTrue(leases["items"][0]["needs_rebuild"])
        self.assertEqual(leases["items"][0]["rebuild_reason"], "lease_never_observed_event")
        self.assertEqual(leases["items"][0]["recovery"]["recovery_action"], "explicit_rebuild_required")

    def test_subscription_lease_marks_stale_when_connection_is_lost(self) -> None:
        with mock.patch("xtqmt_mcp.data_gateway.service.port_ready", return_value=True):
            started = self.service.subscribe_start({"codes": ["000001.SZ"], "period": "tick"})
        self.assertTrue(started.ok)
        self.now_box[0] = "2026-03-27T09:30:30"
        with mock.patch("xtqmt_mcp.data_gateway.service.port_ready", return_value=False):
            leases = self.service.list_subscriptions_payload()
        self.assertEqual(leases["stale_count"], 1)
        self.assertEqual(leases["needs_rebuild_count"], 1)
        self.assertEqual(leases["rebuild_reasons"], {"xtdata_connection_lost": 1})
        self.assertFalse(leases["items"][0]["connection_alive"])
        self.assertEqual(leases["items"][0]["lease_state"], "stale")
        self.assertEqual(leases["items"][0]["rebuild_reason"], "xtdata_connection_lost")
        self.assertEqual(leases["items"][0]["recovery"]["resolved_runtime_endpoint"]["port_ready"], False)

    def test_subscription_lease_marks_stale_when_callback_loop_is_missing(self) -> None:
        with mock.patch("xtqmt_mcp.data_gateway.service.port_ready", return_value=True):
            started = self.service.subscribe_start({"codes": ["000001.SZ"], "period": "tick"})
        self.assertTrue(started.ok)
        self.service._subscription_callbacks.pop("sub-1", None)
        self.now_box[0] = "2026-03-27T09:30:05"
        with mock.patch("xtqmt_mcp.data_gateway.service.port_ready", return_value=True):
            leases = self.service.list_subscriptions_payload()
        self.assertEqual(leases["stale_count"], 1)
        self.assertFalse(leases["items"][0]["callback_loop_alive"])
        self.assertEqual(leases["items"][0]["rebuild_reason"], "callback_loop_not_alive")
        self.assertEqual(leases["rebuild_reasons"], {"callback_loop_not_alive": 1})


if __name__ == "__main__":
    unittest.main()
