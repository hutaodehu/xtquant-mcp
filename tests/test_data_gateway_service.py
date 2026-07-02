from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import pandas as pd
import shutil
import time
from types import SimpleNamespace
import unittest
from unittest import mock
import uuid
from unittest.mock import patch

from xtqmt_mcp.data_gateway.config import DataAuditConfig, DataGatewayConfig, DataGatewayRuntimeConfig
from xtqmt_mcp.data_gateway.jobs import DownloadJobRequest
from xtqmt_mcp.data_gateway import qlib_runtime
from xtqmt_mcp.data_gateway.qlib_runtime import (
    _normalize_time_column,
    build_integrity_plan,
    import_parquet_chunk,
    inspect_trade_day,
    pull_history_chunk,
    resolve_runtime_qlib_path,
)
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
        self.sector_member_calls: list[tuple[str, object]] = []
        self.market_data_ex_calls: list[dict[str, object]] = []

    def get_sector_list(self) -> list[str]:
        return ["沪深A股", "上证A股", "GN上海", "THS人工智能"]

    def get_stock_list_in_sector(self, sector_name: str, real_timetag: int = -1) -> list[str]:
        self.sector_member_calls.append((sector_name, real_timetag))
        if sector_name == "GN上海" and str(real_timetag) == "20260327":
            return ["000001.SZ"]
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
        self.market_data_ex_calls.append(
            {
                "field_list": list(field_list),
                "stock_list": list(stock_list),
                "period": period,
                "start_time": start_time,
                "end_time": end_time,
                "count": count,
                "dividend_type": dividend_type,
                "fill_data": fill_data,
            }
        )
        if period == "stocklistchange":
            return {
                code: [
                    {"time": "2026-03-26", "0": "000001.SZ,600000.SH", "1": ""},
                    {"time": "2026-03-27", "0": "", "1": "600000.SH"},
                ]
                for code in stock_list
            }
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


class _NoStockListChangeBackend(_FakeBackend):
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
        self.market_data_ex_calls.append(
            {
                "field_list": list(field_list),
                "stock_list": list(stock_list),
                "period": period,
                "start_time": start_time,
                "end_time": end_time,
                "count": count,
                "dividend_type": dividend_type,
                "fill_data": fill_data,
            }
        )
        if period == "stocklistchange":
            return {code: [] for code in stock_list}
        return super().get_market_data_ex(field_list, stock_list, period, start_time, end_time, count, dividend_type, fill_data)


class _UnsupportedStockListChangeBackend(_FakeBackend):
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
        if period == "stocklistchange":
            raise RuntimeError("function not realize")
        return super().get_market_data_ex(field_list, stock_list, period, start_time, end_time, count, dividend_type, fill_data)


class _FailingNativeProbeBackend(_FakeBackend):
    def get_trading_dates(self, market: str, start_time: str = "", end_time: str = "", count: int = -1) -> list[int]:
        raise RuntimeError("native xtdata probe failed")


class _FreshTradeDateBackend(_FakeBackend):
    def get_trading_dates(self, market: str, start_time: str = "", end_time: str = "", count: int = -1) -> list[int]:
        del market, start_time, end_time, count
        return [
            int(datetime(2026, 4, 14, tzinfo=timezone.utc).timestamp() * 1000),
            int(datetime(2026, 4, 15, tzinfo=timezone.utc).timestamp() * 1000),
        ]

    def get_trading_calendar(self, market: str, start_time: str = "", end_time: str = "") -> list[str]:
        del market, start_time, end_time
        return ["20260414"]


class _ShiftedTradeDateBackend(_FakeBackend):
    def get_trading_dates(self, market: str, start_time: str = "", end_time: str = "", count: int = -1) -> list[int]:
        del market, start_time, end_time, count
        return [
            int(datetime(2026, 4, 13, 16, 0, tzinfo=timezone.utc).timestamp() * 1000),
            int(datetime(2026, 4, 14, 16, 0, tzinfo=timezone.utc).timestamp() * 1000),
        ]

    def get_trading_calendar(self, market: str, start_time: str = "", end_time: str = "") -> list[str]:
        del market, start_time, end_time
        return ["20260414"]


class _TargetDayNoBarBackend(_FakeBackend):
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
        del field_list, start_time, end_time, count, dividend_type, fill_data
        if period != "1d":
            return super().get_market_data_ex(["time", "open", "high", "low", "close", "volume", "amount"], stock_list, period)
        return {
            code: [
                {"time": "2026-04-14", "open": 10.0, "high": 10.2, "low": 9.8, "close": 10.1, "volume": 1000, "amount": 10100.0},
                {"time": "2026-04-15", "open": float("nan"), "high": float("nan"), "low": float("nan"), "close": float("nan"), "volume": 0, "amount": 0.0},
            ]
            for code in stock_list
        }


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
            qmt=QmtInstallConfig(xtdata_port=58888),
            transport=TransportConfig(bind_port=0),
            audit=DataAuditConfig(call_log_root=str(root / "artifacts" / "data_gateway")),
            service=DataGatewayRuntimeConfig(
                jobs_root=str(root / "state" / "data_jobs"),
                subscriptions_root=str(root / "state" / "subscriptions"),
                download_root=str(root / "artifacts" / "data_downloads"),
                wsl_distro_name="SampleDistro",
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

    def test_sector_list_filters_by_keyword_without_membership_dates(self) -> None:
        result = self.service.sector_list({"keyword": "GN", "limit": 10})
        self.assertTrue(result.ok)
        self.assertEqual(result.payload["count"], 1)
        self.assertEqual(result.payload["items"][0]["sector_name"], "GN上海")
        self.assertFalse(result.payload["items"][0]["contains_add_date"])
        self.assertIn("membership_snapshot_only", result.payload["date_semantics"])

    def test_sector_members_at_uses_real_timetag_and_marks_membership_semantics(self) -> None:
        result = self.service.sector_members_at({"sector_name": "GN上海", "asof_date": "2026-03-27"})
        self.assertTrue(result.ok)
        self.assertEqual(self.backend.sector_member_calls[-1], ("GN上海", "20260327"))
        self.assertEqual(result.payload["sector_name"], "GN上海")
        self.assertEqual(result.payload["asof_date"], "20260327")
        self.assertTrue(result.payload["point_in_time"])
        self.assertFalse(result.payload["contains_add_date"])
        self.assertEqual(result.payload["items"], [{"sector_name": "GN上海", "stock_code": "000001.SZ"}])
        self.assertIn("membership_as_of", result.payload["date_semantics"])

    def test_sector_change_history_uses_stocklistchange_events_and_no_latest_backfill(self) -> None:
        result = self.service.sector_change_history(
            {"sector_name": "GN上海", "start_date": "2026-03-26", "end_date": "2026-03-27"}
        )
        self.assertTrue(result.ok)
        self.assertEqual(self.backend.sector_member_calls, [])
        self.assertEqual(self.backend.market_data_ex_calls[-1]["period"], "stocklistchange")
        self.assertEqual(self.backend.market_data_ex_calls[-1]["stock_list"], ["GN上海"])
        self.assertEqual(self.backend.market_data_ex_calls[-1]["start_time"], "20260326")
        self.assertEqual(self.backend.market_data_ex_calls[-1]["end_time"], "20260327")
        self.assertFalse(self.backend.market_data_ex_calls[-1]["fill_data"])
        events = result.payload["items"]
        self.assertTrue(
            any(
                event["sector_name"] == "GN上海"
                and event["stock_code"] == "000001.SZ"
                and event["action"] == "add"
                and event["effective_date"] == "20260326"
                and event["source_period"] == "stocklistchange"
                for event in events
            )
        )
        self.assertTrue(
            any(
                event["sector_name"] == "GN上海"
                and event["stock_code"] == "600000.SH"
                and event["action"] == "remove"
                and event["effective_date"] == "20260327"
                and event["source_period"] == "stocklistchange"
                for event in events
            )
        )
        self.assertTrue(result.payload["date_available"])
        self.assertEqual(result.payload["backtest_guard"], "effective_date_lte_decision_date_only")

    def test_sector_change_history_fails_closed_when_stocklistchange_is_missing(self) -> None:
        service = DataGatewayService(
            self.config,
            backend=_NoStockListChangeBackend(),
            now_fn=lambda: self.now_box[0],
            uuid_factory=lambda: "sub-no-stocklistchange",
        )
        result = service.sector_change_history({"sector_name": "GN上海", "start_date": "2026-03-26", "end_date": "2026-03-27"})
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "point_in_time_source_missing")
        self.assertEqual(result.category, "validation")
        self.assertFalse(result.payload["date_available"])
        self.assertEqual(result.payload["failure_policy"], "do_not_backfill_latest_membership")
        self.assertIn("source_not_point_in_time", result.payload["reason"])

    def test_sector_change_history_fails_closed_when_stocklistchange_is_unsupported(self) -> None:
        service = DataGatewayService(
            self.config,
            backend=_UnsupportedStockListChangeBackend(),
            now_fn=lambda: self.now_box[0],
            uuid_factory=lambda: "sub-unsupported-stocklistchange",
        )
        result = service.sector_change_history({"sector_name": "GN上海", "start_date": "2026-03-26", "end_date": "2026-03-27"})
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "point_in_time_source_missing")
        self.assertEqual(result.category, "environment")
        self.assertTrue(result.retryable)
        self.assertFalse(result.payload["date_available"])
        self.assertEqual(result.payload["failure_policy"], "do_not_backfill_latest_membership")
        self.assertIn("function not realize", result.payload["source_error"])

    def test_resolve_runtime_endpoint_prefers_env_port_over_log_and_config(self) -> None:
        log_root = Path(self.config.qmt.qmt_userdata or self.tempdir.path / "userdata_mini")
        log_dir = log_root / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "XtMiniQuote_test.log").write_text("listen port: 59999\n", encoding="utf-8")
        cfg = DataGatewayConfig(
            identity=self.config.identity,
            runtime_paths=self.config.runtime_paths,
            bundle=self.config.bundle,
            qmt=QmtInstallConfig(qmt_userdata=str(log_root), xtdata_port=0),
            transport=self.config.transport,
            audit=self.config.audit,
            service=self.config.service,
        )
        service = DataGatewayService(cfg, backend=self.backend, now_fn=lambda: self.now_box[0], uuid_factory=lambda: "sub-1")
        with patch.dict("os.environ", {"XTDATA_PORT": "58888"}, clear=False), patch(
            "xtqmt_mcp.data_gateway.service.port_ready", return_value=True
        ):
            _, resolved_runtime_endpoint, connectivity_ready = service._resolve_runtime_endpoint(probe_connect=True)
        self.assertTrue(connectivity_ready)
        self.assertEqual(resolved_runtime_endpoint["port"], 58888)
        self.assertEqual(resolved_runtime_endpoint["port_source"], "env:XTDATA_PORT")

    def test_resolve_runtime_endpoint_can_use_xtdatacenter_default_when_unconfigured(self) -> None:
        cfg = DataGatewayConfig(
            identity=self.config.identity,
            runtime_paths=self.config.runtime_paths,
            bundle=self.config.bundle,
            qmt=QmtInstallConfig(xtdata_port=0),
            transport=self.config.transport,
            audit=self.config.audit,
            service=self.config.service,
        )
        service = DataGatewayService(cfg, backend=self.backend, now_fn=lambda: self.now_box[0], uuid_factory=lambda: "sub-1")
        with patch.dict("os.environ", {}, clear=True), patch(
            "xtqmt_mcp.data_gateway.service._xtdatacenter_listen_default_port",
            return_value=58610,
        ), patch("xtqmt_mcp.data_gateway.service.port_ready", return_value=True):
            _, resolved_runtime_endpoint, connectivity_ready = service._resolve_runtime_endpoint(probe_connect=True)
        self.assertTrue(connectivity_ready)
        self.assertEqual(resolved_runtime_endpoint["port"], 58610)
        self.assertEqual(resolved_runtime_endpoint["port_source"], "xtdatacenter.listen_default")

    def test_configured_58610_can_be_ready_when_native_xtdata_probe_passes(self) -> None:
        cfg = DataGatewayConfig(
            identity=self.config.identity,
            runtime_paths=self.config.runtime_paths,
            bundle=self.config.bundle,
            qmt=QmtInstallConfig(xtdata_port=58610),
            transport=self.config.transport,
            audit=self.config.audit,
            service=self.config.service,
        )
        service = DataGatewayService(cfg, backend=self.backend, now_fn=lambda: self.now_box[0], uuid_factory=lambda: "sub-1")
        bundle_result = SimpleNamespace(
            ok=True,
            as_dict=lambda: {
                "ok": True,
                "bundle_root": cfg.bundle.bundle_root,
                "package_root": str(Path(cfg.bundle.bundle_root) / "xtquant"),
                "abi_tag": cfg.bundle.abi_tag,
                "required_files": [],
                "missing_files": [],
            },
        )
        with mock.patch("xtqmt_mcp.data_gateway.service.validate_xtquant_bundle", return_value=bundle_result), mock.patch(
            "xtqmt_mcp.data_gateway.service.xtquant_import_spec",
            return_value=SimpleNamespace(origin="vendor://xtquant"),
        ), mock.patch("xtqmt_mcp.data_gateway.service.port_ready", return_value=True):
            status = service.status_summary()

        self.assertTrue(status.ok)
        self.assertTrue(status.payload["ready"])
        self.assertEqual(status.payload["reason"], "ok")
        self.assertFalse(status.payload["legacy_port_detected"])
        self.assertEqual(status.payload["resolved_runtime_endpoint"]["port"], 58610)
        self.assertTrue(status.payload["xtdata_port"]["ready"])
        self.assertTrue(status.payload["readiness"]["layers"]["basic_query"]["ready"])
        self.assertEqual(status.payload["readiness"]["layers"]["basic_query"]["sample_count"], 2)

    def test_socket_ready_without_native_xtdata_query_is_not_ready(self) -> None:
        cfg = DataGatewayConfig(
            identity=self.config.identity,
            runtime_paths=self.config.runtime_paths,
            bundle=self.config.bundle,
            qmt=QmtInstallConfig(xtdata_port=58610),
            transport=self.config.transport,
            audit=self.config.audit,
            service=self.config.service,
        )
        service = DataGatewayService(cfg, backend=_FailingNativeProbeBackend(), now_fn=lambda: self.now_box[0], uuid_factory=lambda: "sub-1")
        bundle_result = SimpleNamespace(
            ok=True,
            as_dict=lambda: {
                "ok": True,
                "bundle_root": cfg.bundle.bundle_root,
                "package_root": str(Path(cfg.bundle.bundle_root) / "xtquant"),
                "abi_tag": cfg.bundle.abi_tag,
                "required_files": [],
                "missing_files": [],
            },
        )
        with mock.patch("xtqmt_mcp.data_gateway.service.validate_xtquant_bundle", return_value=bundle_result), mock.patch(
            "xtqmt_mcp.data_gateway.service.xtquant_import_spec",
            return_value=SimpleNamespace(origin="vendor://xtquant"),
        ), mock.patch("xtqmt_mcp.data_gateway.service.port_ready", return_value=True):
            status = service.status_summary()

        self.assertFalse(status.ok)
        self.assertEqual(status.code, "xtdata_basic_query_failed")
        self.assertFalse(status.payload["ready"])
        self.assertEqual(status.payload["blocking_reason"], "xtdata_basic_query_failed")
        self.assertFalse(status.payload["legacy_port_detected"])
        self.assertTrue(status.payload["readiness"]["layers"]["connectivity"]["ready"])
        self.assertFalse(status.payload["readiness"]["layers"]["basic_query"]["ready"])
        self.assertIn("native xtdata probe failed", status.message)

    def test_gateway_health_preserves_historical_58610_port_evidence(self) -> None:
        legacy_job = {
            "job_id": "job-legacy",
            "request": {"target_date": "20260521", "periods": ["1d"], "symbols_scope": "all_a"},
            "status": "completed",
            "created_at": "2026-05-21T09:00:00Z",
            "started_at": "2026-05-21T09:00:01Z",
            "finished_at": "2026-05-21T09:10:00Z",
            "progress_finished": 1,
            "progress_total": 1,
            "progress_message": "done",
            "result": {
                "force_status": "completed",
                "completion_reason": "process_exit",
                "port_evidence": {
                    "configured_endpoint": {"host": "127.0.0.1", "port": 58610, "source": "configured", "port_ready": None},
                    "resolved_runtime_endpoint": {
                        "host": "127.0.0.1",
                        "port": 58610,
                        "source": "connectivity_probe",
                        "port_ready": True,
                    },
                },
                "manifest": {
                    "port_evidence": {
                        "configured_endpoint": {"host": "127.0.0.1", "port": 58610, "source": "configured", "port_ready": None},
                        "resolved_runtime_endpoint": {
                            "host": "127.0.0.1",
                            "port": 58610,
                            "source": "connectivity_probe",
                            "port_ready": True,
                        },
                    }
                },
            },
            "error": None,
            "artifacts": [],
            "warnings": [],
            "progress_samples": [],
        }
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
        ), mock.patch("xtqmt_mcp.data_gateway.service.port_ready", return_value=True), mock.patch.object(
            self.service._jobs,
            "list_active",
            return_value=[],
        ), mock.patch.object(self.service._jobs, "list_all", return_value=[legacy_job]):
            status = self.service.status_summary()

        self.assertTrue(status.ok)
        recent = status.payload["jobs"]["recent"][0]
        self.assertNotIn("result", recent)
        self.assertEqual(recent["port_evidence"]["configured_endpoint"]["port"], 58610)
        self.assertEqual(recent["port_evidence"]["resolved_runtime_endpoint"]["port"], 58610)
        self.assertNotIn("redacted_reason", recent["port_evidence"]["resolved_runtime_endpoint"])

    def test_bulk_sync_job_status_preserves_historical_58610_job_result(self) -> None:
        legacy_job = {
            "job_id": "job-legacy",
            "request": {"target_date": "20260521", "periods": ["1d"], "symbols_scope": "all_a"},
            "status": "completed",
            "created_at": "2026-05-21T09:00:00Z",
            "started_at": "2026-05-21T09:00:01Z",
            "finished_at": "2026-05-21T09:10:00Z",
            "progress_finished": 1,
            "progress_total": 1,
            "progress_message": "done",
            "result": {
                "force_status": "completed",
                "completion_reason": "process_exit",
                "port_evidence": {
                    "configured_endpoint": {"host": "127.0.0.1", "port": 58610, "source": "configured", "port_ready": None},
                    "resolved_runtime_endpoint": {
                        "host": "127.0.0.1",
                        "port": 58610,
                        "source": "connectivity_probe",
                        "port_ready": True,
                    },
                },
                "manifest": {
                    "port_evidence": {
                        "configured_endpoint": {"host": "127.0.0.1", "port": 58610, "source": "configured", "port_ready": None},
                        "resolved_runtime_endpoint": {
                            "host": "127.0.0.1",
                            "port": 58610,
                            "source": "connectivity_probe",
                            "port_ready": True,
                        },
                    }
                },
            },
            "error": None,
            "artifacts": [],
            "warnings": [],
            "progress_samples": [],
        }
        with mock.patch.object(self.service._jobs, "list_active", return_value=[]), mock.patch.object(
            self.service._jobs,
            "list_all",
            return_value=[legacy_job],
        ):
            result = self.service.bulk_sync_job_status({})

        self.assertTrue(result.ok)
        recent = result.payload["recent"][0]
        self.assertEqual(recent["port_evidence"]["resolved_runtime_endpoint"]["port"], 58610)
        self.assertEqual(recent["result"]["port_evidence"]["resolved_runtime_endpoint"]["port"], 58610)
        self.assertEqual(recent["result"]["manifest"]["port_evidence"]["resolved_runtime_endpoint"]["port"], 58610)

    def test_qlib_acceptance_check_returns_boundary_verdict(self) -> None:
        result = self.service.qlib_acceptance_check(
            {
                "qlib_dir": str(self.tempdir.path),
                "target_trade_day": "20260331",
                "periods": [],
                "residuals": [{"symbol": "300123.SZ", "periods_missing": ["1m"]}],
            }
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.payload["verdict"], "pass_with_boundary_residuals")

    def test_qlib_acceptance_check_allows_boundary_stale_tail_residuals(self) -> None:
        with mock.patch(
            "xtqmt_mcp.data_gateway.service.assess_qlib_acceptance",
            return_value={
                "passed": False,
                "blocking_issues": ["feature_tail_stale:day:count=1", "feature_tail_stale:1min:count=1"],
                "warnings": [],
                "instrument_end_consistency": {
                    "day": {
                        "target_stale_count": 1,
                        "target_stale_examples": [{"symbol": "000001.SZ", "target_trade_day": "2026-03-31"}],
                    },
                    "1min": {
                        "target_stale_count": 1,
                        "target_stale_examples": [{"symbol": "000001.SZ", "target_trade_day": "2026-03-31"}],
                    },
                },
            },
        ):
            result = self.service.qlib_acceptance_check(
                {
                    "qlib_dir": str(self.tempdir.path),
                    "target_trade_day": "20260331",
                    "periods": ["1d", "1m"],
                    "residuals": [
                        {
                            "symbol": "000001.SZ",
                            "classification": "upstream_no_bar",
                            "periods_stale": ["1d", "1m"],
                        }
                    ],
                }
            )
        self.assertTrue(result.ok)
        self.assertEqual(result.payload["verdict"], "pass_with_boundary_residuals")
        self.assertEqual(result.payload["acceptance_summary"]["blocking_issues"], [])

    def test_artifact_manifest_reads_completed_manifest_file(self) -> None:
        manifest_path = self.tempdir.path / "manifest.json"
        manifest_path.write_text('{"job_id": "job-1", "changed_files": ["calendars/day.txt"]}', encoding="utf-8")
        with mock.patch.object(self.service, "bulk_sync_job_status", return_value=SimpleNamespace(payload={"manifest_path": str(manifest_path)})):
            result = self.service.artifact_manifest({"job_id": "job-1"})
        self.assertTrue(result.ok)
        self.assertEqual(result.payload["job_id"], "job-1")
        self.assertEqual(result.payload["changed_files"], ["calendars/day.txt"])

    def test_search_history_snapshot_download_and_subscription(self) -> None:
        search = self.service.instruments_search({"query": "ping"})
        self.assertTrue(search.ok)
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

    def test_bulk_sync_job_submit_and_status_return_manifest_and_acceptance(self) -> None:
        def _fake_bulk_runner(request: DownloadJobRequest, progress_cb) -> dict[str, object]:
            progress_cb(
                {
                    "finished": 3,
                    "total": 5,
                    "message": "sync_wsl:done",
                    "current_phase": "sync_wsl",
                    "copied_count": 7,
                    "expected_next": "manifest:start",
                }
            )
            return {
                "force_status": "completed",
                "completion_reason": "process_exit",
                "manifest_path": str(self.tempdir.path / "manifest.json"),
                "acceptance_path": str(self.tempdir.path / "acceptance.json"),
                "artifact_readiness": {"ready": True},
                "acceptance_summary": {"verdict": "pass"},
                "residual_summary": {"count": 0},
            }

        with mock.patch.object(
            self.service._jobs,
            "_run_download",
            side_effect=_fake_bulk_runner,
        ):
            submit = self.service.bulk_sync_job_submit(
                {
                    "target_date": "2026-03-31",
                    "periods": ["1d", "1m"],
                    "calendar_snapshot_year": 2026,
                    "future_day_calendar": ["2026-04-01", "2026-04-02"],
                }
            )
            self.assertTrue(submit.ok)
            job_id = submit.payload["job_id"]
            job_state = self.service._jobs.status(job_id)
            deadline = time.time() + 3.0
            status_payload = {}
            while time.time() < deadline:
                status_result = self.service.bulk_sync_job_status({"job_id": job_id})
                status_payload = status_result.payload
                if status_payload.get("state") == "completed":
                    break
                time.sleep(0.05)
        self.assertEqual(status_payload.get("state"), "completed")
        self.assertTrue(status_payload["artifact_readiness"]["ready"])
        self.assertEqual(status_payload["acceptance_summary"]["verdict"], "pass")
        self.assertTrue(status_payload["manifest_path"].endswith("manifest.json"))
        self.assertEqual(job_state["request"]["calendar_snapshot_year"], 2026)
        self.assertEqual(job_state["request"]["future_day_calendar"], ["2026-04-01", "2026-04-02"])
        self.assertEqual(status_payload["current_phase"], "sync_wsl")
        self.assertEqual(status_payload["last_progress_message"], "sync_wsl:done")
        self.assertEqual(status_payload["expected_next"], "manifest:start")
        self.assertTrue(status_payload["terminal_artifacts_ready"])
        self.assertGreaterEqual(status_payload["age_seconds"], 0)
        self.assertEqual(status_payload["progress_samples"][-1]["copied_count"], 7)

    def test_bulk_sync_job_status_handles_naive_local_now_against_utc_job_time(self) -> None:
        self.now_box[0] = "2026-05-08T19:18:59"
        payload = self.service._format_bulk_job_status(
            {
                "job_id": "job-utc",
                "status": "running",
                "created_at": "2026-05-08T11:18:58Z",
                "started_at": "2026-05-08T11:18:58Z",
                "request": {
                    "target_date": "20260508",
                    "periods": ["1d", "1m"],
                    "symbols_scope": "all_a",
                },
                "progress_samples": [
                    {
                        "ts": "2026-05-08T11:18:58Z",
                        "message": "download:1m",
                        "current_phase": "download",
                    }
                ],
            }
        )

        self.assertLess(payload["age_seconds"], 60)
        self.assertLess(payload["last_heartbeat_age_seconds"], 60)

    def test_bulk_sync_job_status_marks_stale_running_job_recoverable(self) -> None:
        self.now_box[0] = "2026-05-08T19:50:00"
        payload = self.service._format_bulk_job_status(
            {
                "job_id": "job-stale",
                "status": "running",
                "created_at": "2026-05-08T11:18:58Z",
                "started_at": "2026-05-08T11:18:58Z",
                "request": {
                    "target_date": "20260508",
                    "periods": ["1d", "1m"],
                    "symbols_scope": "all_a",
                },
                "progress_samples": [
                    {
                        "ts": "2026-05-08T11:34:34Z",
                        "message": "002453.SZ",
                        "current_phase": "download",
                    }
                ],
            }
        )

        self.assertTrue(payload["stale_job_detected"])
        self.assertTrue(payload["can_cancel"])
        self.assertEqual(payload["stale_threshold_seconds"], self.config.service.stale_job_seconds)
        self.assertEqual(payload["recovery_action"], "cancel_then_resubmit_same_target")

    def test_bulk_sync_job_cancel_removes_job_from_active_list(self) -> None:
        def _fake_slow_runner(request: DownloadJobRequest, progress_cb) -> dict[str, object]:
            progress_cb({"finished": 1, "total": 2, "message": "download:1m"})
            time.sleep(0.3)
            return {"force_status": "completed"}

        with mock.patch.object(self.service._jobs, "_run_download", side_effect=_fake_slow_runner):
            submit = self.service.bulk_sync_job_submit({"target_date": "2026-03-31", "periods": ["1d", "1m"]})
            self.assertTrue(submit.ok)
            job_id = submit.payload["job_id"]
            cancel = self.service.bulk_sync_job_cancel({"job_id": job_id})

        self.assertTrue(cancel.ok)
        self.assertIn(cancel.payload["state"], {"cancel_requested", "cancelled"})
        active = self.service.bulk_sync_job_status({}).payload["active"]
        self.assertNotIn(job_id, {item["job_id"] for item in active})
        self.assertTrue(self.backend.stop_called)

    def test_bulk_sync_job_status_marks_terminal_artifacts_not_ready_without_acceptance(self) -> None:
        with mock.patch.object(
            self.service._jobs,
            "_run_download",
            return_value={
                "force_status": "completed",
                "completion_reason": "process_exit",
                "manifest_path": str(self.tempdir.path / "manifest.json"),
                "artifact_readiness": {"ready": True},
                "acceptance_summary": {},
                "residual_summary": {},
            },
        ):
            submit = self.service.bulk_sync_job_submit({"target_date": "2026-03-31", "periods": ["1d"]})
            self.assertTrue(submit.ok)
            job_id = submit.payload["job_id"]
            status_payload = {}
            deadline = time.time() + 3.0
            while time.time() < deadline:
                status_payload = self.service.bulk_sync_job_status({"job_id": job_id}).payload
                if status_payload.get("state") == "completed":
                    break
                time.sleep(0.05)

        self.assertEqual(status_payload.get("state"), "completed")
        self.assertFalse(status_payload["terminal_artifacts_ready"])
        self.assertEqual(status_payload["split_retry_count"], 0)
        self.assertEqual(status_payload["download_timeout_count"], 0)
        self.assertEqual(status_payload["skipped_symbol_count"], 0)
        self.assertEqual(status_payload["current_chunk_size"], 0)
        self.assertEqual(status_payload["phase_elapsed_seconds"], 0)

    def test_calendar_resolve_trade_day_prefers_backend_trading_dates_when_local_calendar_is_stale(self) -> None:
        stale_root = self.tempdir.path / "stale_qlib"
        calendar_dir = stale_root / "calendars"
        calendar_dir.mkdir(parents=True, exist_ok=True)
        (calendar_dir / "day.txt").write_text("20260414\n", encoding="utf-8")
        (calendar_dir / "day_future.txt").write_text("20260414\n", encoding="utf-8")

        cfg = replace(
            self.config,
            service=replace(
                self.config.service,
                windows_qlib_root=str(stale_root),
                wsl_qlib_root=str(stale_root),
            ),
        )
        service = DataGatewayService(
            cfg,
            backend=_FreshTradeDateBackend(),
            now_fn=lambda: self.now_box[0],
            uuid_factory=lambda: "sub-fresh-trade-day",
        )

        with mock.patch.object(
            qlib_runtime,
            "_fetch_official_trade_calendar_sources",
            return_value={
                "sse": {"ok": True, "url": "https://www.sse.com.cn", "trade_days": ["2026-04-15"], "closed_ranges": [], "content_hash": "sse-hash"},
                "szse": {"ok": True, "url": "https://www.szse.cn", "trade_days": ["2026-04-15"], "closed_ranges": [], "content_hash": "szse-hash"},
            },
        ):
            result = service.calendar_resolve_trade_day({"target_date": "2026-04-15"})

        self.assertTrue(result.ok)
        self.assertEqual(result.payload["target_trading_day"], "20260415")
        self.assertFalse(result.payload["target_date_mapped"])
        self.assertEqual(result.payload["confirmation_source"], "official_online")

    def test_calendar_resolve_trade_day_supports_xtdata_millisecond_trade_dates(self) -> None:
        stale_root = self.tempdir.path / "shifted_stale_qlib"
        calendar_dir = stale_root / "calendars"
        calendar_dir.mkdir(parents=True, exist_ok=True)
        (calendar_dir / "day.txt").write_text("20260414\n", encoding="utf-8")
        (calendar_dir / "day_future.txt").write_text("20260414\n", encoding="utf-8")

        cfg = replace(
            self.config,
            service=replace(
                self.config.service,
                windows_qlib_root=str(stale_root),
                wsl_qlib_root=str(stale_root),
            ),
        )
        service = DataGatewayService(
            cfg,
            backend=_ShiftedTradeDateBackend(),
            now_fn=lambda: self.now_box[0],
            uuid_factory=lambda: "sub-shifted-trade-day",
        )

        with mock.patch.object(
            qlib_runtime,
            "_fetch_official_trade_calendar_sources",
            return_value={
                "sse": {"ok": True, "url": "https://www.sse.com.cn", "trade_days": ["2026-04-15"], "closed_ranges": [], "content_hash": "sse-hash"},
                "szse": {"ok": True, "url": "https://www.szse.cn", "trade_days": ["2026-04-15"], "closed_ranges": [], "content_hash": "szse-hash"},
            },
        ):
            result = service.calendar_resolve_trade_day({"target_date": "2026-04-15"})

        self.assertTrue(result.ok)
        self.assertEqual(result.payload["target_trading_day"], "20260415")
        self.assertFalse(result.payload["target_date_mapped"])
        self.assertEqual(result.payload["confirmation_source"], "official_online")

    def test_calendar_resolve_trade_day_keeps_official_verdict_and_reports_runtime_inconsistency_when_backend_misses_target(self) -> None:
        windows_root = self.tempdir.path / "windows_qlib"
        wsl_root = self.tempdir.path / "wsl_qlib"
        (windows_root / "calendars").mkdir(parents=True, exist_ok=True)
        (wsl_root / "calendars").mkdir(parents=True, exist_ok=True)
        (windows_root / "calendars" / "day.txt").write_text("20260414\n", encoding="utf-8")
        (windows_root / "calendars" / "day_future.txt").write_text("20260414\n", encoding="utf-8")
        (wsl_root / "calendars" / "day.txt").write_text("20260414\n", encoding="utf-8")
        (wsl_root / "calendars" / "day_future.txt").write_text("20260415\n", encoding="utf-8")

        class _PreviousTradeDayBackend(_FakeBackend):
            def get_trading_dates(self, market: str, start_time: str = "", end_time: str = "", count: int = -1) -> list[int]:
                del market, start_time, end_time, count
                return [int(datetime(2026, 4, 14, tzinfo=timezone.utc).timestamp() * 1000)]

            def get_trading_calendar(self, market: str, start_time: str = "", end_time: str = "") -> list[str]:
                del market, start_time, end_time
                return ["20260414"]

        cfg = replace(
            self.config,
            service=replace(
                self.config.service,
                windows_qlib_root=str(windows_root),
                wsl_qlib_root=str(wsl_root),
                wsl_distro_name="SampleDistro",
            ),
        )
        service = DataGatewayService(
            cfg,
            backend=_PreviousTradeDayBackend(),
            now_fn=lambda: self.now_box[0],
            uuid_factory=lambda: "sub-wsl-authority",
        )

        with mock.patch.object(
            qlib_runtime,
            "_fetch_official_trade_calendar_sources",
            return_value={
                "sse": {"ok": True, "url": "https://www.sse.com.cn", "trade_days": ["2026-04-15"], "closed_ranges": [], "content_hash": "sse-hash"},
                "szse": {"ok": True, "url": "https://www.szse.cn", "trade_days": ["2026-04-15"], "closed_ranges": [], "content_hash": "szse-hash"},
            },
        ):
            result = service.calendar_resolve_trade_day({"target_date": "2026-04-15"})

        self.assertTrue(result.ok)
        self.assertTrue(result.payload["is_target_trade_day"])
        self.assertEqual(result.payload["target_trading_day"], "20260415")
        self.assertEqual(result.payload["confirmation_source"], "official_online")
        self.assertEqual(result.payload["runtime_consistency"], "inconsistent")
        self.assertIn("runtime_backend_miss_target", result.payload["warnings"])

    def test_calendar_resolve_trade_day_returns_structured_no_go_without_previous_day_mapping(self) -> None:
        stale_root = self.tempdir.path / "strict_no_go_qlib"
        calendar_dir = stale_root / "calendars"
        calendar_dir.mkdir(parents=True, exist_ok=True)
        (calendar_dir / "day.txt").write_text("20260414\n", encoding="utf-8")
        (calendar_dir / "day_future.txt").write_text("20260414\n", encoding="utf-8")

        class _PreviousTradeDayBackend(_FakeBackend):
            def get_trading_dates(self, market: str, start_time: str = "", end_time: str = "", count: int = -1) -> list[int]:
                del market, start_time, end_time, count
                return [int(datetime(2026, 4, 14, tzinfo=timezone.utc).timestamp() * 1000)]

            def get_trading_calendar(self, market: str, start_time: str = "", end_time: str = "") -> list[str]:
                del market, start_time, end_time
                return ["20260414"]

        cfg = replace(
            self.config,
            service=replace(
                self.config.service,
                windows_qlib_root=str(stale_root),
                wsl_qlib_root=str(stale_root),
            ),
        )
        service = DataGatewayService(
            cfg,
            backend=_PreviousTradeDayBackend(),
            now_fn=lambda: self.now_box[0],
            uuid_factory=lambda: "sub-strict-no-go",
        )

        with mock.patch.object(
            qlib_runtime,
            "_fetch_official_trade_calendar_sources",
            return_value={
                "sse": {"ok": True, "url": "https://www.sse.com.cn", "trade_days": [], "closed_ranges": [], "content_hash": "sse-hash"},
                "szse": {"ok": True, "url": "https://www.szse.cn", "trade_days": [], "closed_ranges": [], "content_hash": "szse-hash"},
            },
        ):
            result = service.calendar_resolve_trade_day({"target_date": "2026-04-15"})

        self.assertFalse(result.ok)
        self.assertEqual(result.code, "target_date_not_trade_day")
        self.assertIn("未被确认是交易日", result.message)
        self.assertFalse(result.payload["is_target_trade_day"])
        self.assertEqual(result.payload["target_trading_day"], "")
        self.assertEqual(result.payload["previous_trade_day"], "20260414")
        self.assertFalse(result.payload["target_date_mapped"])

    def test_inspect_trade_day_blocks_when_official_sources_conflict(self) -> None:
        with mock.patch.object(
            qlib_runtime,
            "_fetch_official_trade_calendar_sources",
            return_value={
                "sse": {
                    "ok": True,
                    "url": "https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml",
                    "trade_days": ["2026-04-15"],
                    "closed_ranges": [],
                    "content_hash": "sse-hash",
                },
                "szse": {
                    "ok": True,
                    "url": "https://www.szse.cn/disclosure/notice/general/t20251222_618087.html",
                    "trade_days": [],
                    "closed_ranges": [],
                    "content_hash": "szse-hash",
                },
            },
        ):
            payload = inspect_trade_day(self.backend, "2026-04-15")

        self.assertFalse(payload["is_target_trade_day"])
        self.assertTrue(payload["official_conflict"])
        self.assertEqual(payload["official_status_code"], "official_calendar_conflict")

    def test_calendar_resolve_trade_day_returns_official_unreachable_code(self) -> None:
        service = DataGatewayService(
            self.config,
            backend=_FakeBackend(),
            now_fn=lambda: self.now_box[0],
            uuid_factory=lambda: "sub-official-unreachable",
        )
        payload = {
            "target_date": "20260415",
            "target_trading_day": "",
            "target_date_mapped": False,
            "is_target_trade_day": False,
            "previous_trade_day": "20260414",
            "official_status_code": "official_calendar_unreachable",
            "official_summary": "官方在线双源不可达",
            "official_conflict": False,
            "source_status": {"sse": "ok", "szse": "unreachable"},
        }

        with mock.patch("xtqmt_mcp.data_gateway.service.inspect_trade_day", return_value=payload):
            result = service.calendar_resolve_trade_day({"target_date": "2026-04-15"})

        self.assertFalse(result.ok)
        self.assertEqual(result.code, "official_calendar_unreachable")
        self.assertIn("官方在线双源不可达", result.message)

    def test_build_integrity_plan_raises_when_target_date_is_not_confirmed_trade_day(self) -> None:
        stale_root = self.tempdir.path / "integrity_plan_strict_qlib"
        calendar_dir = stale_root / "calendars"
        calendar_dir.mkdir(parents=True, exist_ok=True)
        (calendar_dir / "day.txt").write_text("20260414\n", encoding="utf-8")
        (calendar_dir / "day_future.txt").write_text("20260414\n", encoding="utf-8")

        class _PreviousTradeDayBackend(_FakeBackend):
            def get_trading_dates(self, market: str, start_time: str = "", end_time: str = "", count: int = -1) -> list[int]:
                del market, start_time, end_time, count
                return [int(datetime(2026, 4, 14, tzinfo=timezone.utc).timestamp() * 1000)]

            def get_trading_calendar(self, market: str, start_time: str = "", end_time: str = "") -> list[str]:
                del market, start_time, end_time
                return ["20260414"]

        with self.assertRaisesRegex(ValueError, "未被确认是交易日"):
            with mock.patch.object(
                qlib_runtime,
                "_fetch_official_trade_calendar_sources",
                return_value={
                    "sse": {"ok": True, "url": "https://www.sse.com.cn", "trade_days": [], "closed_ranges": [], "content_hash": "sse-hash"},
                    "szse": {"ok": True, "url": "https://www.szse.cn", "trade_days": [], "closed_ranges": [], "content_hash": "szse-hash"},
                },
            ):
                build_integrity_plan(
                    _PreviousTradeDayBackend(),
                    target_date="2026-04-15",
                    periods=["1d"],
                    calendar_roots=(str(stale_root), str(stale_root)),
                )

    def test_normalize_time_column_converts_xtdata_epoch_values_to_china_market_time(self) -> None:
        day_df = pd.DataFrame(
            [
                {
                    "time": int(datetime(2026, 4, 14, 16, 0, tzinfo=timezone.utc).timestamp() * 1000),
                    "open": 10.0,
                }
            ]
        )
        minute_df = pd.DataFrame(
            [
                {
                    "time": int(datetime(2026, 4, 15, 1, 30, tzinfo=timezone.utc).timestamp() * 1000),
                    "open": 10.0,
                },
                {
                    "time": int(datetime(2026, 4, 15, 7, 0, tzinfo=timezone.utc).timestamp() * 1000),
                    "open": 10.5,
                },
            ]
        )

        normalized_day = _normalize_time_column(day_df, "1d")
        normalized_minute = _normalize_time_column(minute_df, "1m")

        self.assertEqual(normalized_day["time"].tolist(), ["2026-04-15"])
        self.assertEqual(
            normalized_minute["time"].tolist(),
            ["2026-04-15 09:30:00", "2026-04-15 15:00:00"],
        )

    def test_pull_history_chunk_marks_target_day_no_bar_as_boundary_residual(self) -> None:
        result = pull_history_chunk(
            _TargetDayNoBarBackend(),
            symbols=["000001.SZ"],
            period="1d",
            start_time="20260414",
            end_time="20260415",
            adjusted_mode="raw",
            chunks_root=self.tempdir.path / "chunks",
        )

        self.assertEqual(
            result["boundary_residuals"],
            [
                {
                    "symbol": "000001.SZ",
                    "classification": "upstream_no_bar",
                    "periods_stale": ["1d"],
                    "target_trade_day": "2026-04-15",
                    "last_bar_time": "2026-04-15",
                    "reason": "target_day_rows_without_price_bar",
                }
            ],
        )

    def test_import_parquet_chunk_skips_feature_paths_without_actual_writes(self) -> None:
        qlib_dir = self.tempdir.path / "local_qlib_import"
        chunk_path = self.tempdir.path / "chunk_partial.parquet"
        pd.DataFrame(
            [
                {
                    "symbol": "001312.SZ",
                    "time": "2026-04-15",
                    "open": 10.0,
                    "close": float("nan"),
                }
            ]
        ).to_parquet(chunk_path)

        result = import_parquet_chunk(chunk_path, qlib_dir, "1d")

        self.assertIn("features/sz001312/open.day.bin", result["changed_files"])
        self.assertNotIn("features/sz001312/close.day.bin", result["changed_files"])
        self.assertTrue((qlib_dir / "features" / "sz001312" / "open.day.bin").exists())
        self.assertFalse((qlib_dir / "features" / "sz001312" / "close.day.bin").exists())

    def test_import_parquet_chunk_excludes_symbol_without_any_written_features(self) -> None:
        qlib_dir = self.tempdir.path / "local_qlib_empty_symbol"
        chunk_path = self.tempdir.path / "chunk_empty_symbol.parquet"
        pd.DataFrame(
            [
                {
                    "symbol": "688811.SH",
                    "time": "2026-04-15",
                    "open": float("nan"),
                    "close": float("nan"),
                    "factor": float("nan"),
                }
            ]
        ).to_parquet(chunk_path)

        result = import_parquet_chunk(chunk_path, qlib_dir, "1d")

        self.assertEqual(result["imported_symbols"], [])
        self.assertEqual(result["metadata_updates"], {})
        self.assertNotIn("features/sh688811/open.day.bin", result["changed_files"])
        self.assertNotIn("features/sh688811/close.day.bin", result["changed_files"])
        self.assertNotIn("features/sh688811/factor.day.bin", result["changed_files"])

    def test_import_parquet_chunk_uses_future_day_calendar_override_for_target_year(self) -> None:
        qlib_dir = self.tempdir.path / "local_qlib_future_override"
        chunk_path = self.tempdir.path / "chunk_future_override.parquet"
        pd.DataFrame(
            [
                {
                    "symbol": "001312.SZ",
                    "time": "2026-04-15",
                    "open": 10.0,
                    "close": 10.2,
                    "factor": 1.0,
                }
            ]
        ).to_parquet(chunk_path)
        calendar_dir = qlib_dir / "calendars"
        calendar_dir.mkdir(parents=True, exist_ok=True)
        (calendar_dir / "day_future.txt").write_text("2025-12-31\n2026-04-14\n2026-04-15\n", encoding="utf-8")

        result = import_parquet_chunk(
            chunk_path,
            qlib_dir,
            "1d",
            future_day_calendar=["2026-04-16", "2026-04-17", "2026-12-31"],
            calendar_snapshot_year=2026,
        )

        self.assertIn("calendars/day_future.txt", result["changed_files"])
        self.assertEqual(
            (calendar_dir / "day_future.txt").read_text(encoding="utf-8").splitlines(),
            ["2025-12-31", "2026-04-16", "2026-04-17", "2026-12-31"],
        )

    def test_import_parquet_chunk_without_future_day_calendar_keeps_backend_fallback(self) -> None:
        qlib_dir = self.tempdir.path / "local_qlib_future_fallback"
        chunk_path = self.tempdir.path / "chunk_future_fallback.parquet"
        pd.DataFrame(
            [
                {
                    "symbol": "001312.SZ",
                    "time": "2026-04-15",
                    "open": 10.0,
                    "close": 10.2,
                    "factor": 1.0,
                }
            ]
        ).to_parquet(chunk_path)

        class _FutureCalendarBackend(_FakeBackend):
            def get_trading_calendar(self, market: str, start_time: str = "", end_time: str = "") -> list[str]:
                del market, start_time, end_time
                return ["20260416", "20260417"]

        result = import_parquet_chunk(chunk_path, qlib_dir, "1d", backend=_FutureCalendarBackend())

        self.assertIn("calendars/day_future.txt", result["changed_files"])
        self.assertEqual(
            (qlib_dir / "calendars" / "day_future.txt").read_text(encoding="utf-8").splitlines(),
            ["2026-04-16", "2026-04-17"],
        )

    def test_sync_manifest_files_has_no_missing_sources_for_partial_nan_chunk(self) -> None:
        qlib_dir = self.tempdir.path / "local_qlib_sync"
        wsl_dir = self.tempdir.path / "wsl_qlib_sync"
        chunk_path = self.tempdir.path / "chunk_sync.parquet"
        pd.DataFrame(
            [
                {
                    "symbol": "001312.SZ",
                    "time": "2026-04-15",
                    "open": 10.0,
                    "close": float("nan"),
                    "factor": float("nan"),
                }
            ]
        ).to_parquet(chunk_path)

        import_result = import_parquet_chunk(chunk_path, qlib_dir, "1d")
        from xtqmt_mcp.data_gateway.qlib_runtime import sync_manifest_files

        sync_result = sync_manifest_files(
            {
                "changed_files": import_result["changed_files"],
                "local_qlib_dir_windows": str(qlib_dir),
            },
            qlib_dir=wsl_dir,
            local_qlib_dir_windows=str(qlib_dir),
        )

        self.assertEqual(sync_result["missing_sources_count"], 0)
        self.assertNotIn("features/sz001312/close.day.bin", import_result["changed_files"])
        self.assertNotIn("features/sz001312/factor.day.bin", import_result["changed_files"])

    def test_sync_manifest_files_emits_copy_heartbeat(self) -> None:
        local_root = self.tempdir.path / "local_qlib_copy_heartbeat"
        wsl_root = self.tempdir.path / "wsl_qlib_copy_heartbeat"
        changed_files = [
            "calendars/day.txt",
            "calendars/1min.txt",
            "instruments/day/all.txt",
        ]
        for index, rel_path in enumerate(changed_files):
            path = local_root / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"payload-{index}", encoding="utf-8")

        progress_events: list[dict[str, object]] = []
        from xtqmt_mcp.data_gateway.qlib_runtime import sync_manifest_files

        sync_result = sync_manifest_files(
            {
                "changed_files": changed_files,
                "local_qlib_dir_windows": str(local_root),
            },
            qlib_dir=wsl_root,
            local_qlib_dir_windows=str(local_root),
            progress_callback=lambda payload: progress_events.append(dict(payload)),
            progress_interval=2,
        )

        self.assertEqual(sync_result["copied_count"], 3)
        copy_events = [event for event in progress_events if event.get("message") == "sync_wsl:copy"]
        self.assertTrue(copy_events)
        self.assertEqual(copy_events[0]["copied_count"], 2)
        self.assertEqual(copy_events[0]["total_count"], 3)
        self.assertEqual(copy_events[-1]["copied_count"], 3)

    def test_resolve_runtime_qlib_path_maps_wsl_root_to_unc_on_windows(self) -> None:
        with mock.patch("xtqmt_mcp.data_gateway.qlib_runtime._host_is_windows", return_value=True):
            resolved, mapping = resolve_runtime_qlib_path(
                "/opt/xtquant-mcp-example/qlib_data/xtdata_export_local",
                wsl_distro_name="SampleDistro",
            )

        self.assertEqual(
            str(resolved),
            r"\\wsl.localhost\SampleDistro\opt\xtquant-mcp-example\qlib_data\xtdata_export_local",
        )
        self.assertEqual(mapping["path_mapping_source"], "wsl_unc")
        self.assertEqual(mapping["requested_qlib_dir"], "/opt/xtquant-mcp-example/qlib_data/xtdata_export_local")
        self.assertEqual(
            mapping["resolved_host_path"],
            r"\\wsl.localhost\SampleDistro\opt\xtquant-mcp-example\qlib_data\xtdata_export_local",
        )

    def test_run_bulk_sync_job_writes_manifest_and_acceptance_files(self) -> None:
        local_root = self.tempdir.path / "local_qlib"
        wsl_root = self.tempdir.path / "wsl_qlib"
        request = DownloadJobRequest(
            codes=(),
            period="1d",
            job_kind="bulk_sync",
            target_date="20260331",
            periods=("1d", "1m"),
            symbols_scope="all_a",
            local_qlib_dir=str(local_root),
            wsl_qlib_dir=str(wsl_root),
        )

        with mock.patch("xtqmt_mcp.data_gateway.service.resolve_trade_day", return_value={"target_trading_day": "20260331"}), mock.patch(
            "xtqmt_mcp.data_gateway.service.build_integrity_plan",
            return_value={"candidate_symbols": ["000001.SZ"], "expected_days": ["20260331"]},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.pull_history_chunk",
            return_value={"chunk_path": str(self.tempdir.path / "chunk.parquet"), "next_cursor": None},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.import_parquet_chunk",
            return_value={
                "imported_symbols": ["000001.SZ"],
                "changed_files": [
                    "calendars/day.txt",
                    "calendars/day_future.txt",
                    "calendars/1min.txt",
                    "instruments/day/all.txt",
                    "instruments/1min/all.txt",
                ],
                "metadata_updates": {},
            },
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.required_manifest_files",
            return_value=[
                "calendars/day.txt",
                "calendars/day_future.txt",
                "calendars/1min.txt",
                "instruments/day/all.txt",
                "instruments/1min/all.txt",
            ],
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.summarize_residuals",
            return_value={"count": 0, "items": []},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.sync_manifest_files",
            return_value={"copied_count": 5, "missing_sources_count": 0},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.check_qlib_health",
            return_value={"passed": True},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.assess_qlib_acceptance",
            return_value={"passed": True, "blocking_issues": [], "warnings": []},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.build_acceptance_verdict",
            return_value="pass",
        ), mock.patch.object(
            self.service,
            "_resolve_runtime_endpoint",
            return_value=(
                {"host": "127.0.0.1", "port": 58888},
                {"host": "127.0.0.1", "port": 58888},
                True,
            ),
        ):
            result = self.service._run_bulk_sync_job(request, lambda payload: True)

        self.assertEqual(result["force_status"], "completed")
        self.assertTrue(Path(result["manifest_path"]).exists())
        self.assertTrue(Path(result["acceptance_path"]).exists())
        self.assertEqual(result["acceptance_summary"]["verdict"], "pass")

    def test_run_bulk_sync_job_writes_three_node_acceptance_to_manifest(self) -> None:
        local_root = self.tempdir.path / "local_qlib_nodes"
        wsl_root = "/opt/xtquant-mcp-example/qlib_data/xtdata_export_local"
        request = DownloadJobRequest(
            codes=(),
            period="1d",
            job_kind="bulk_sync",
            target_date="20260331",
            periods=("1d", "1m"),
            symbols_scope="all_a",
            local_qlib_dir=str(local_root),
            wsl_qlib_dir=wsl_root,
        )

        with mock.patch("xtqmt_mcp.data_gateway.service.resolve_trade_day", return_value={"target_trading_day": "20260331"}), mock.patch(
            "xtqmt_mcp.data_gateway.service.build_integrity_plan",
            return_value={"candidate_symbols": ["000001.SZ"], "expected_days": ["20260331"]},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.pull_history_chunk",
            return_value={"chunk_path": str(self.tempdir.path / "chunk.parquet"), "next_cursor": None},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.import_parquet_chunk",
            return_value={
                "imported_symbols": ["000001.SZ"],
                "changed_files": [
                    "calendars/day.txt",
                    "calendars/day_future.txt",
                    "calendars/1min.txt",
                    "instruments/day/all.txt",
                    "instruments/1min/all.txt",
                ],
                "metadata_updates": {},
            },
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.required_manifest_files",
            return_value=[
                "calendars/day.txt",
                "calendars/day_future.txt",
                "calendars/1min.txt",
                "instruments/day/all.txt",
                "instruments/1min/all.txt",
            ],
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.summarize_residuals",
            return_value={"count": 0, "allowed_count": 0, "disallowed_count": 0, "items": []},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.sync_manifest_files",
            return_value={
                "copied_count": 5,
                "missing_sources_count": 0,
                "requested_qlib_dir": wsl_root,
                "resolved_host_path": r"\\wsl.localhost\SampleDistro\opt\xtquant-mcp-example\qlib_data\xtdata_export_local",
                "path_mapping_source": "wsl_unc",
            },
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.check_qlib_health",
            return_value={"passed": True},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.assess_qlib_acceptance",
            return_value={"passed": True, "blocking_issues": [], "warnings": []},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.build_acceptance_verdict",
            side_effect=["pass", "pass", "pass"],
        ), mock.patch.object(
            self.service,
            "_resolve_runtime_endpoint",
            return_value=(
                {"host": "127.0.0.1", "port": 58888},
                {"host": "127.0.0.1", "port": 58888},
                True,
            ),
        ):
            result = self.service._run_bulk_sync_job(request, lambda payload: True)

        manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
        acceptance = json.loads(Path(result["acceptance_path"]).read_text(encoding="utf-8"))
        self.assertEqual(result["force_status"], "completed")
        self.assertIn("node_acceptance", manifest)
        self.assertEqual(sorted(manifest["node_acceptance"].keys()), ["qmt_cache", "windows_qlib", "wsl_qlib"])
        self.assertIn("quality_summary", acceptance)
        self.assertEqual(
            acceptance["quality_summary"]["node_verdicts"],
            {"qmt_cache": "pass", "windows_qlib": "pass", "wsl_qlib": "pass"},
        )
        self.assertEqual(acceptance["quality_summary"]["copied_count"], 5)
        self.assertEqual(acceptance["quality_summary"]["missing_sources_count"], 0)

    def test_run_bulk_sync_job_emits_chunk_heartbeat_progress(self) -> None:
        local_root = self.tempdir.path / "local_qlib_progress"
        wsl_root = self.tempdir.path / "wsl_qlib_progress"
        request = DownloadJobRequest(
            codes=(),
            period="1m",
            job_kind="bulk_sync",
            target_date="20260331",
            periods=("1m",),
            symbols_scope="all_a",
            local_qlib_dir=str(local_root),
            wsl_qlib_dir=str(wsl_root),
        )
        progress_events: list[dict[str, object]] = []

        with mock.patch("xtqmt_mcp.data_gateway.service.resolve_trade_day", return_value={"target_trading_day": "20260331"}), mock.patch(
            "xtqmt_mcp.data_gateway.service.build_integrity_plan",
            return_value={
                "candidate_symbols": [
                    "000001.SZ",
                    "000002.SZ",
                    "000004.SZ",
                    "000006.SZ",
                    "000007.SZ",
                    "000008.SZ",
                ],
                "expected_days": ["20260331"],
            },
        ), mock.patch.object(
            self.service._backend,
            "download_history_data2",
            return_value={},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.pull_history_chunk",
            side_effect=[
                {
                    "chunk_path": str(self.tempdir.path / "chunk_00000.parquet"),
                    "cursor": 0,
                    "next_cursor": 5,
                    "chunk_symbols_count": 5,
                    "symbols_total": 6,
                    "rows": 1200,
                    "boundary_residuals": [],
                },
                {
                    "chunk_path": str(self.tempdir.path / "chunk_00005.parquet"),
                    "cursor": 5,
                    "next_cursor": None,
                    "chunk_symbols_count": 1,
                    "symbols_total": 6,
                    "rows": 240,
                    "boundary_residuals": [],
                },
            ],
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.import_parquet_chunk",
            side_effect=[
                {
                    "imported_symbols": ["000001.SZ", "000002.SZ", "000004.SZ", "000006.SZ", "000007.SZ"],
                    "changed_files": ["calendars/1min.txt", "instruments/1min/all.txt"],
                    "metadata_updates": {},
                },
                {
                    "imported_symbols": ["000008.SZ"],
                    "changed_files": ["features/sz000008/open.1min.bin"],
                    "metadata_updates": {},
                },
            ],
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.required_manifest_files",
            return_value=["calendars/1min.txt", "instruments/1min/all.txt"],
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.summarize_residuals",
            return_value={"count": 0, "allowed_count": 0, "disallowed_count": 0, "items": []},
        ), mock.patch.object(
            self.service,
            "_build_qmt_cache_acceptance",
            return_value={"verdict": "pass"},
        ), mock.patch.object(
            self.service,
            "_build_qlib_node_acceptance",
            side_effect=[
                {"verdict": "pass", "acceptance_summary": {"passed": True, "blocking_issues": [], "warnings": []}},
                {"verdict": "pass", "acceptance_summary": {"passed": True, "blocking_issues": [], "warnings": []}},
            ],
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.sync_manifest_files",
            return_value={"copied_count": 2, "missing_sources_count": 0},
        ), mock.patch.object(
            self.service,
            "_resolve_runtime_endpoint",
            return_value=(
                {"host": "127.0.0.1", "port": 58888},
                {"host": "127.0.0.1", "port": 58888},
                True,
            ),
        ):
            result = self.service._run_bulk_sync_job(request, lambda payload: progress_events.append(dict(payload)) or True)

        self.assertEqual(result["force_status"], "completed")
        messages = [str(item.get("message") or "") for item in progress_events]
        self.assertTrue(any("pull:1m" in item and "chunk=1/2" in item and "cursor=0" in item for item in messages))
        self.assertTrue(any("import:1m" in item and "chunk=1/2" in item and "cursor=0" in item for item in messages))
        self.assertTrue(any("pull:1m" in item and "chunk=2/2" in item and "cursor=5" in item for item in messages))
        self.assertTrue(any("import:1m" in item and "chunk=2/2" in item and "cursor=5" in item for item in messages))
        self.assertTrue(any("download:1m" in item and "chunk=1/2" in item and "cursor=0" in item for item in messages))
        self.assertTrue(any("download:1m" in item and "chunk=2/2" in item and "cursor=5" in item for item in messages))
        self.assertIn("manifest:start", messages)
        self.assertIn("manifest:done", messages)
        self.assertIn("sync_wsl:start", messages)
        self.assertIn("sync_wsl:done", messages)
        self.assertIn("acceptance:start", messages)
        self.assertIn("acceptance:done", messages)
        sync_done = next(item for item in progress_events if item.get("message") == "sync_wsl:done")
        self.assertEqual(sync_done["copied_count"], 2)
        manifest_done = next(item for item in progress_events if item.get("message") == "manifest:done")
        self.assertEqual(manifest_done["missing_required_files"], [])
        acceptance_done = next(item for item in progress_events if item.get("message") == "acceptance:done")
        self.assertEqual(acceptance_done["verdict"], "pass")
        self.assertEqual(acceptance_done["release_state"], "ready")
        self.assertEqual(acceptance_done["current_phase"], "acceptance")
        self.assertEqual(progress_events[-1]["message"], "acceptance:done")
        self.assertEqual(progress_events[-1]["finished"], progress_events[-1]["total"])

    def test_run_bulk_sync_job_does_not_timeout_while_download_callback_progresses(self) -> None:
        config = replace(
            self.config,
            service=replace(self.config.service, stale_job_seconds=1, max_query_symbols=5),
        )
        service = DataGatewayService(
            config,
            backend=self.backend,
            now_fn=lambda: self.now_box[0],
            uuid_factory=lambda: "sub-1",
        )
        local_root = self.tempdir.path / "local_qlib_idle_timeout"
        wsl_root = self.tempdir.path / "wsl_qlib_idle_timeout"
        request = DownloadJobRequest(
            codes=(),
            period="1d",
            job_kind="bulk_sync",
            target_date="20260331",
            periods=("1d",),
            symbols_scope="all_a",
            local_qlib_dir=str(local_root),
            wsl_qlib_dir=str(wsl_root),
        )
        progress_events: list[dict[str, object]] = []

        def _slow_download_with_progress(stock_list, period, start_time, end_time, callback, incrementally):
            del stock_list, period, start_time, end_time, incrementally
            for code in ["000001.SZ", "000002.SZ", "000004.SZ"]:
                callback({"message": code})
                time.sleep(0.45)
            return {}

        with mock.patch("xtqmt_mcp.data_gateway.service.resolve_trade_day", return_value={"target_trading_day": "20260331"}), mock.patch(
            "xtqmt_mcp.data_gateway.service.build_integrity_plan",
            return_value={
                "candidate_symbols": ["000001.SZ", "000002.SZ", "000004.SZ"],
                "expected_days": ["20260331"],
            },
        ), mock.patch.object(
            service._backend,
            "download_history_data2",
            side_effect=_slow_download_with_progress,
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.pull_history_chunk",
            return_value={
                "chunk_path": str(self.tempdir.path / "chunk_idle.parquet"),
                "cursor": 0,
                "next_cursor": None,
                "chunk_symbols_count": 3,
                "symbols_total": 3,
                "rows": 300,
                "boundary_residuals": [],
            },
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.import_parquet_chunk",
            return_value={
                "imported_symbols": ["000001.SZ", "000002.SZ", "000004.SZ"],
                "changed_files": ["calendars/day.txt", "instruments/day/all.txt"],
                "metadata_updates": {},
            },
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.required_manifest_files",
            return_value=["calendars/day.txt", "instruments/day/all.txt"],
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.summarize_residuals",
            return_value={"count": 0, "allowed_count": 0, "disallowed_count": 0, "items": []},
        ), mock.patch.object(
            service,
            "_build_qmt_cache_acceptance",
            return_value={"verdict": "pass"},
        ), mock.patch.object(
            service,
            "_build_qlib_node_acceptance",
            side_effect=[
                {"verdict": "pass", "acceptance_summary": {"passed": True, "blocking_issues": [], "warnings": []}},
                {"verdict": "pass", "acceptance_summary": {"passed": True, "blocking_issues": [], "warnings": []}},
            ],
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.sync_manifest_files",
            return_value={"copied_count": 2, "missing_sources_count": 0},
        ), mock.patch.object(
            service,
            "_resolve_runtime_endpoint",
            return_value=(
                {"host": "127.0.0.1", "port": 58888},
                {"host": "127.0.0.1", "port": 58888},
                True,
            ),
        ):
            result = service._run_bulk_sync_job(request, lambda payload: progress_events.append(dict(payload)) or True)

        self.assertEqual(result["force_status"], "completed")
        self.assertFalse(self.backend.stop_called)
        messages = [str(item.get("message") or "") for item in progress_events]
        self.assertIn("000001.SZ", messages)
        self.assertIn("000004.SZ", messages)

    def test_run_bulk_sync_job_splits_1m_download_chunk_after_idle_timeout(self) -> None:
        config = replace(
            self.config,
            service=replace(self.config.service, stale_job_seconds=1, max_query_symbols=4),
        )
        service = DataGatewayService(
            config,
            backend=self.backend,
            now_fn=lambda: self.now_box[0],
            uuid_factory=lambda: "sub-1",
        )
        local_root = self.tempdir.path / "local_qlib_split_timeout"
        wsl_root = self.tempdir.path / "wsl_qlib_split_timeout"
        request = DownloadJobRequest(
            codes=(),
            period="1m",
            job_kind="bulk_sync",
            target_date="20260331",
            periods=("1m",),
            symbols_scope="all_a",
            local_qlib_dir=str(local_root),
            wsl_qlib_dir=str(wsl_root),
        )
        progress_events: list[dict[str, object]] = []
        download_calls: list[tuple[str, ...]] = []

        def _download_with_first_chunk_timeout(stock_list, period, start_time, end_time, callback, incrementally):
            del period, start_time, end_time, incrementally
            symbols = tuple(stock_list)
            download_calls.append(symbols)
            if len(symbols) == 4:
                time.sleep(1.2)
                return {}
            if callback is not None:
                for code in symbols:
                    callback({"message": code})
            return {}

        with mock.patch("xtqmt_mcp.data_gateway.service.resolve_trade_day", return_value={"target_trading_day": "20260331"}), mock.patch(
            "xtqmt_mcp.data_gateway.service.build_integrity_plan",
            return_value={
                "candidate_symbols": ["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ"],
                "expected_days": ["20260331"],
            },
        ), mock.patch.object(
            service._backend,
            "download_history_data2",
            side_effect=_download_with_first_chunk_timeout,
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.pull_history_chunk",
            return_value={
                "chunk_path": str(self.tempdir.path / "chunk_split.parquet"),
                "cursor": 0,
                "next_cursor": None,
                "chunk_symbols_count": 4,
                "symbols_total": 4,
                "rows": 400,
                "boundary_residuals": [],
            },
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.import_parquet_chunk",
            return_value={
                "imported_symbols": ["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ"],
                "changed_files": ["calendars/1min.txt", "instruments/1min/all.txt"],
                "metadata_updates": {},
            },
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.required_manifest_files",
            return_value=["calendars/1min.txt", "instruments/1min/all.txt"],
        ), mock.patch.object(
            service,
            "_build_qmt_cache_acceptance",
            return_value={"verdict": "pass"},
        ), mock.patch.object(
            service,
            "_build_qlib_node_acceptance",
            side_effect=[
                {"verdict": "pass", "acceptance_summary": {"passed": True, "blocking_issues": [], "warnings": []}},
                {"verdict": "pass", "acceptance_summary": {"passed": True, "blocking_issues": [], "warnings": []}},
            ],
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.sync_manifest_files",
            return_value={"copied_count": 2, "missing_sources_count": 0},
        ), mock.patch.object(
            service,
            "_resolve_runtime_endpoint",
            return_value=(
                {"host": "127.0.0.1", "port": 58888},
                {"host": "127.0.0.1", "port": 58888},
                True,
            ),
        ):
            result = service._run_bulk_sync_job(request, lambda payload: progress_events.append(dict(payload)) or True)

        self.assertEqual(result["force_status"], "completed")
        self.assertTrue(service._backend.stop_called)
        self.assertEqual(result["split_retry_count"], 1)
        self.assertEqual(result["download_timeout_count"], 1)
        self.assertEqual(result["skipped_symbol_count"], 0)
        self.assertEqual(result["download_recovery_summary"]["current_chunk_size"], 2)
        self.assertIn(("000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ"), download_calls)
        self.assertIn(("000001.SZ", "000002.SZ"), download_calls)
        self.assertIn(("000003.SZ", "000004.SZ"), download_calls)
        messages = [str(item.get("message") or "") for item in progress_events]
        self.assertTrue(any("download:1m split_retry" in item for item in messages))

    def test_run_bulk_sync_job_skips_single_1m_symbol_after_idle_timeout(self) -> None:
        config = replace(
            self.config,
            service=replace(self.config.service, stale_job_seconds=1, max_query_symbols=2),
        )
        service = DataGatewayService(
            config,
            backend=self.backend,
            now_fn=lambda: self.now_box[0],
            uuid_factory=lambda: "sub-1",
        )
        local_root = self.tempdir.path / "local_qlib_skip_timeout"
        wsl_root = self.tempdir.path / "wsl_qlib_skip_timeout"
        request = DownloadJobRequest(
            codes=(),
            period="1m",
            job_kind="bulk_sync",
            target_date="20260331",
            periods=("1m",),
            symbols_scope="all_a",
            local_qlib_dir=str(local_root),
            wsl_qlib_dir=str(wsl_root),
        )
        progress_events: list[dict[str, object]] = []
        pulled_symbols: list[list[str]] = []

        def _download_with_single_symbol_timeout(stock_list, period, start_time, end_time, callback, incrementally):
            del period, start_time, end_time, incrementally
            symbols = tuple(stock_list)
            if "000002.SZ" in symbols:
                time.sleep(1.2)
                return {}
            if callback is not None:
                for code in symbols:
                    callback({"message": code})
            return {}

        def _pull_chunk(backend, *, symbols, period, start_time, end_time, cursor, chunk_symbols, adjusted_mode, metadata_path, chunks_root):
            del backend, start_time, end_time, chunk_symbols, adjusted_mode, metadata_path, chunks_root
            pulled_symbols.append(list(symbols))
            return {
                "chunk_path": str(self.tempdir.path / "chunk_skip.parquet"),
                "cursor": cursor,
                "next_cursor": None,
                "chunk_symbols_count": len(symbols),
                "symbols_total": len(symbols),
                "rows": 100,
                "boundary_residuals": [],
            }

        with mock.patch("xtqmt_mcp.data_gateway.service.resolve_trade_day", return_value={"target_trading_day": "20260331"}), mock.patch(
            "xtqmt_mcp.data_gateway.service.build_integrity_plan",
            return_value={
                "candidate_symbols": ["000001.SZ", "000002.SZ"],
                "expected_days": ["20260331"],
            },
        ), mock.patch.object(
            service._backend,
            "download_history_data2",
            side_effect=_download_with_single_symbol_timeout,
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.pull_history_chunk",
            side_effect=_pull_chunk,
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.import_parquet_chunk",
            return_value={
                "imported_symbols": ["000001.SZ"],
                "changed_files": ["calendars/1min.txt", "instruments/1min/all.txt"],
                "metadata_updates": {},
            },
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.required_manifest_files",
            return_value=["calendars/1min.txt", "instruments/1min/all.txt"],
        ), mock.patch.object(
            service,
            "_build_qlib_node_acceptance",
            side_effect=[
                {"verdict": "pass", "acceptance_summary": {"passed": True, "blocking_issues": [], "warnings": []}},
                {"verdict": "pass", "acceptance_summary": {"passed": True, "blocking_issues": [], "warnings": []}},
            ],
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.sync_manifest_files",
            return_value={"copied_count": 2, "missing_sources_count": 0},
        ), mock.patch.object(
            service,
            "_resolve_runtime_endpoint",
            return_value=(
                {"host": "127.0.0.1", "port": 58888},
                {"host": "127.0.0.1", "port": 58888},
                True,
            ),
        ):
            result = service._run_bulk_sync_job(request, lambda payload: progress_events.append(dict(payload)) or True)

        self.assertEqual(result["force_status"], "completed")
        self.assertEqual(pulled_symbols, [["000001.SZ"]])
        self.assertEqual(result["split_retry_count"], 1)
        self.assertEqual(result["download_timeout_count"], 2)
        self.assertEqual(result["skipped_symbol_count"], 1)
        self.assertEqual(result["slow_symbols_sample"], ["000002.SZ"])
        self.assertEqual(result["acceptance_summary"]["verdict"], "pass_with_boundary_residuals")
        self.assertEqual(result["residual_summary"]["allowed_count"], 1)
        residual = result["residual_summary"]["items"][0]
        self.assertEqual(residual["symbol"], "000002.SZ")
        self.assertEqual(residual["classification"], "vendor_boundary")
        self.assertEqual(residual["periods_missing"], ["1m"])
        self.assertEqual(residual["reason"], "download_history_data2_idle_timeout")
        messages = [str(item.get("message") or "") for item in progress_events]
        self.assertTrue(any("download:1m skip symbol=000002.SZ reason=idle_timeout" in item for item in messages))

    def test_run_bulk_sync_job_fails_when_wsl_node_acceptance_fails(self) -> None:
        local_root = self.tempdir.path / "local_qlib_wsl_fail"
        wsl_root = "/opt/xtquant-mcp-example/qlib_data/xtdata_export_local"
        request = DownloadJobRequest(
            codes=(),
            period="1d",
            job_kind="bulk_sync",
            target_date="20260331",
            periods=("1d", "1m"),
            symbols_scope="all_a",
            local_qlib_dir=str(local_root),
            wsl_qlib_dir=wsl_root,
        )

        with mock.patch("xtqmt_mcp.data_gateway.service.resolve_trade_day", return_value={"target_trading_day": "20260331"}), mock.patch(
            "xtqmt_mcp.data_gateway.service.build_integrity_plan",
            return_value={"candidate_symbols": ["000001.SZ"], "expected_days": ["20260331"]},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.pull_history_chunk",
            return_value={"chunk_path": str(self.tempdir.path / "chunk.parquet"), "next_cursor": None},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.import_parquet_chunk",
            return_value={
                "imported_symbols": ["000001.SZ"],
                "changed_files": [
                    "calendars/day.txt",
                    "calendars/day_future.txt",
                    "calendars/1min.txt",
                    "instruments/day/all.txt",
                    "instruments/1min/all.txt",
                ],
                "metadata_updates": {},
            },
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.required_manifest_files",
            return_value=[
                "calendars/day.txt",
                "calendars/day_future.txt",
                "calendars/1min.txt",
                "instruments/day/all.txt",
                "instruments/1min/all.txt",
            ],
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.summarize_residuals",
            return_value={"count": 0, "allowed_count": 0, "disallowed_count": 0, "items": []},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.sync_manifest_files",
            return_value={
                "copied_count": 5,
                "missing_sources_count": 0,
                "requested_qlib_dir": wsl_root,
                "resolved_host_path": r"\\wsl.localhost\SampleDistro\opt\xtquant-mcp-example\qlib_data\xtdata_export_local",
                "path_mapping_source": "wsl_unc",
            },
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.check_qlib_health",
            return_value={"passed": True},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.assess_qlib_acceptance",
            return_value={"passed": True, "blocking_issues": [], "warnings": []},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.build_acceptance_verdict",
            side_effect=["pass", "pass", "fail"],
        ), mock.patch.object(
            self.service,
            "_resolve_runtime_endpoint",
            return_value=(
                {"host": "127.0.0.1", "port": 58888},
                {"host": "127.0.0.1", "port": 58888},
                True,
            ),
        ):
            result = self.service._run_bulk_sync_job(request, lambda payload: True)

        self.assertEqual(result["force_status"], "failed")

    def test_run_bulk_sync_job_marks_stale_symbol_outside_candidate_universe_as_boundary_residual(self) -> None:
        local_root = self.tempdir.path / "local_qlib_residual"
        wsl_root = self.tempdir.path / "wsl_qlib_residual"
        request = DownloadJobRequest(
            codes=(),
            period="1d",
            job_kind="bulk_sync",
            target_date="20260331",
            periods=("1d", "1m"),
            symbols_scope="all_a",
            local_qlib_dir=str(local_root),
            wsl_qlib_dir=str(wsl_root),
        )

        acceptance_summary = {
            "passed": False,
            "blocking_issues": ["feature_tail_stale:day:count=1", "feature_tail_stale:1min:count=1"],
            "warnings": [],
            "calendar_tails": {"day": "2026-03-31", "1min": "2026-03-31 15:00:00", "day_future": "2026-04-01"},
            "instrument_counts": {"day": 2, "1min": 2},
            "instrument_diff": {"day_only": [], "min_only": [], "day_only_count": 0, "min_only_count": 0},
            "instrument_end_consistency": {
                "day": {
                    "target_stale_count": 1,
                    "target_stale_examples": [{"symbol": "000002.SZ", "target_trade_day": "2026-03-31"}],
                    "lagging_count": 0,
                },
                "1min": {
                    "target_stale_count": 1,
                    "target_stale_examples": [{"symbol": "000002.SZ", "target_trade_day": "2026-03-31"}],
                    "lagging_count": 0,
                },
            },
        }

        with mock.patch("xtqmt_mcp.data_gateway.service.resolve_trade_day", return_value={"target_trading_day": "20260331"}), mock.patch(
            "xtqmt_mcp.data_gateway.service.build_integrity_plan",
            return_value={"candidate_symbols": ["000001.SZ"], "expected_days": ["20260331"]},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.pull_history_chunk",
            side_effect=[
                {
                    "chunk_path": str(self.tempdir.path / "chunk_day.parquet"),
                    "next_cursor": None,
                    "imported_symbols": ["000001.SZ"],
                    "boundary_residuals": [],
                },
                {
                    "chunk_path": str(self.tempdir.path / "chunk_min.parquet"),
                    "next_cursor": None,
                    "imported_symbols": ["000001.SZ"],
                    "boundary_residuals": [],
                },
            ],
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.import_parquet_chunk",
            return_value={
                "imported_symbols": ["000001.SZ"],
                "changed_files": [
                    "calendars/day.txt",
                    "calendars/day_future.txt",
                    "calendars/1min.txt",
                    "instruments/day/all.txt",
                    "instruments/1min/all.txt",
                ],
                "metadata_updates": {},
            },
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.required_manifest_files",
            return_value=[
                "calendars/day.txt",
                "calendars/day_future.txt",
                "calendars/1min.txt",
                "instruments/day/all.txt",
                "instruments/1min/all.txt",
            ],
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.sync_manifest_files",
            return_value={"copied_count": 5, "missing_sources_count": 0},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.check_qlib_health",
            return_value={"passed": True},
        ), mock.patch(
            "xtqmt_mcp.data_gateway.service.assess_qlib_acceptance",
            return_value=acceptance_summary,
        ), mock.patch.object(
            self.service,
            "_resolve_runtime_endpoint",
            return_value=(
                {"host": "127.0.0.1", "port": 58888},
                {"host": "127.0.0.1", "port": 58888},
                True,
            ),
        ):
            result = self.service._run_bulk_sync_job(request, lambda payload: True)

        self.assertEqual(result["force_status"], "completed")
        self.assertEqual(result["acceptance_summary"]["verdict"], "pass_with_boundary_residuals")
        self.assertEqual(result["acceptance_summary"]["blocking_issues"], [])
        self.assertEqual(result["residual_summary"]["allowed_count"], 1)
        self.assertEqual(result["residual_summary"]["items"][0]["symbol"], "000002.SZ")
        self.assertEqual(result["residual_summary"]["items"][0]["classification"], "vendor_boundary")

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
