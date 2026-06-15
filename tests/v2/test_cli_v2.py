"""Extended tests for quant_lab.core.cli — covering uncovered branches."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, mock_open, patch

from quant_lab.core.cli import (
    _load_watchlist,
    _print_result,
    _save_single_report,
    _select_builder,
    run_memory_migration,
    run_memory_stats,
    run_v2_monitor_mode,
)


class TestLoadWatchlistV2:
    def test_loads_from_watchlists_json(self) -> None:
        config = {"my": {"stocks": [{"code": "000001", "name": "平安银行", "tags": ["test"]}]}}
        with patch("quant_lab.core.cli.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=json.dumps(config))):
            stocks = _load_watchlist("my")
            assert len(stocks) == 1
            assert stocks[0]["code"] == "000001"

    def test_watchlists_json_exception(self) -> None:
        with patch("quant_lab.core.cli.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data="not json")):
            stocks = _load_watchlist("my")
            assert len(stocks) > 0


class TestPrintResult:
    def test_print_result_basic(self, capsys) -> None:
        state = MagicMock()
        state.need_deep_analysis = False
        state.raw_data = {"money_summary": "资金正常", "tech_summary": "技术面好"}
        state.response = "持有"
        state.structured_output = None
        _print_result(state, [])
        captured = capsys.readouterr()
        assert "Worker 快速分析" in captured.out

    def test_print_result_deep(self, capsys) -> None:
        state = MagicMock()
        state.need_deep_analysis = True
        state.raw_data = {}
        state.response = "深度分析结果"
        state.structured_output = None
        _print_result(state, [])
        captured = capsys.readouterr()
        assert "Brain 深度分析" in captured.out

    def test_print_result_with_structured(self, capsys) -> None:
        state = MagicMock()
        state.need_deep_analysis = False
        state.raw_data = {}
        state.response = "结果"
        so = MagicMock()
        so.rating = "买入"
        so.confidence = 0.85
        so.target_price = 25.0
        state.structured_output = so
        _print_result(state, [])
        captured = capsys.readouterr()
        assert "买入" in captured.out

    def test_print_result_with_failed_steps(self, capsys) -> None:
        state = MagicMock()
        state.need_deep_analysis = False
        state.raw_data = {}
        state.response = "结果"
        state.structured_output = None
        _print_result(state, [("fetch_data", "timeout")])
        captured = capsys.readouterr()
        assert "fetch_data" in captured.out


class TestSaveSingleReport:
    @patch("quant_lab.core.cli._report_dir", return_value="/tmp/test_report")
    @patch("os.makedirs")
    @patch("builtins.open", mock_open())
    @patch("quant_lab.core.cli.datetime")
    def test_save_basic(self, mock_dt, mock_makedirs, mock_report_dir) -> None:
        mock_dt.now.return_value.strftime.return_value = "250101"
        state = MagicMock()
        state.need_deep_analysis = False
        state.stock_name = "平安银行"
        state.symbol = "000001"
        state.raw_data = {"money_summary": "正常"}
        state.response = "持有"
        state.structured_output = None
        _save_single_report(state)
        assert mock_makedirs.call_count >= 1

    @patch("quant_lab.core.cli._report_dir", return_value="/tmp/test_report")
    @patch("os.makedirs")
    @patch("builtins.open", mock_open())
    @patch("quant_lab.core.cli.datetime")
    def test_save_deep_mode(self, mock_dt, mock_makedirs, mock_report_dir) -> None:
        mock_dt.now.return_value.strftime.return_value = "250101"
        state = MagicMock()
        state.need_deep_analysis = True
        state.stock_name = "平安银行"
        state.symbol = "000001"
        state.raw_data = {}
        state.response = "深度结果"
        state.structured_output = None
        _save_single_report(state)

    @patch("quant_lab.core.cli._report_dir", return_value="/tmp/test_report")
    @patch("os.makedirs")
    @patch("builtins.open", mock_open())
    @patch("quant_lab.core.cli.datetime")
    def test_save_with_structured_output(self, mock_dt, mock_makedirs, mock_report_dir) -> None:
        mock_dt.now.return_value.strftime.return_value = "250101"
        state = MagicMock()
        state.need_deep_analysis = False
        state.stock_name = "平安银行"
        state.symbol = "000001"
        state.raw_data = {}
        state.response = "结果"
        from tests.v2.helpers import make_stock_analysis
        state.structured_output = make_stock_analysis()
        _save_single_report(state)

    @patch("quant_lab.core.cli._report_dir", return_value="/tmp/test_report")
    @patch("os.makedirs")
    @patch("quant_lab.core.cli.datetime")
    def test_save_pdf_success(self, mock_report_dir, mock_makedirs, mock_dt) -> None:
        mock_dt.now.return_value.strftime.return_value = "250101"
        state = MagicMock()
        state.need_deep_analysis = False
        state.stock_name = "平安银行"
        state.symbol = "000001"
        state.raw_data = {}
        state.response = "结果"
        state.structured_output = None
        fake_md2pdf = MagicMock()
        fake_md2pdf.md_to_pdf = MagicMock(return_value=True)
        with patch("builtins.open", mock_open()), \
             patch.dict("sys.modules", {"md2pdf_tool": fake_md2pdf}):
            _save_single_report(state)

    @patch("quant_lab.core.cli._report_dir", return_value="/tmp/test_report")
    @patch("os.makedirs")
    @patch("quant_lab.core.cli.datetime")
    def test_save_pdf_exception(self, mock_report_dir, mock_makedirs, mock_dt) -> None:
        mock_dt.now.return_value.strftime.return_value = "250101"
        state = MagicMock()
        state.need_deep_analysis = False
        state.stock_name = "平安银行"
        state.symbol = "000001"
        state.raw_data = {}
        state.response = "结果"
        state.structured_output = None
        fake_md2pdf = MagicMock()
        fake_md2pdf.md_to_pdf = MagicMock(side_effect=Exception("pdf fail"))
        with patch("builtins.open", mock_open()), \
             patch.dict("sys.modules", {"md2pdf_tool": fake_md2pdf}):
            _save_single_report(state)


class TestRunMemoryMigration:
    @patch("quant_lab.core.memory.migration.run_migration")
    def test_dry_run(self, mock_run_migration) -> None:
        mock_run_migration.return_value = {"total": 10, "imported": 5, "skipped": 3, "errors": 2}
        run_memory_migration(dry_run=True)
        mock_run_migration.assert_called_once_with(dry_run=True)


class TestRunMemoryStats:
    @patch("quant_lab.core.memory.log.AnalysisMemoryLog")
    def test_with_alpha(self, mock_log_cls, capsys) -> None:
        mock_log = MagicMock()
        mock_log.get_stats.return_value = {
            "total": 100, "pending": 10, "resolved": 80, "symbols": 20, "avg_alpha": 0.05,
        }
        mock_log_cls.return_value = mock_log
        run_memory_stats()
        captured = capsys.readouterr()
        assert "5.00%" in captured.out

    @patch("quant_lab.core.memory.log.AnalysisMemoryLog")
    def test_without_alpha(self, mock_log_cls, capsys) -> None:
        mock_log = MagicMock()
        mock_log.get_stats.return_value = {
            "total": 0, "pending": 0, "resolved": 0, "symbols": 0, "avg_alpha": None,
        }
        mock_log_cls.return_value = mock_log
        run_memory_stats()
        captured = capsys.readouterr()
        assert "Total entries: 0" in captured.out


class TestMonitorModeEdgeCases:
    @patch("quant_lab.core.cli.time.sleep")
    @patch("os.makedirs")
    @patch("builtins.open")
    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    @patch("quant_lab.core.data.aggregator.aggregate")
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_all_fetches_fail(self, mock_agg_step, mock_agg, mock_create_client, mock_open_fn, mock_makedirs, mock_sleep) -> None:
        mock_agg.side_effect = Exception("fail")
        with patch("quant_lab.core.cli._load_watchlist", return_value=[{"code": "000001", "name": "平安银行", "tags": []}]):
            run_v2_monitor_mode(watchlist_name="my", analysis_mode="fast", use_cache=False, max_workers=1)
        mock_create_client.assert_not_called()

    @patch("quant_lab.core.cli.time.sleep")
    @patch("os.makedirs")
    @patch("builtins.open")
    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    @patch("quant_lab.core.data.aggregator.aggregate")
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_ai_analysis_exception(self, mock_agg_step, mock_agg, mock_create_client, mock_open_fn, mock_makedirs, mock_sleep) -> None:
        mock_agg.return_value = {"name": "平安银行", "code": "000001", "type": "stock", "tech_summary": "正常", "money_summary": "正常"}
        mock_create_client.side_effect = Exception("LLM fail")
        with patch("quant_lab.core.cli._load_watchlist", return_value=[{"code": "000001", "name": "平安银行", "tags": []}]):
            run_v2_monitor_mode(watchlist_name="my", analysis_mode="fast", use_cache=False, max_workers=1)

    @patch("quant_lab.core.cli.time.sleep")
    @patch("os.makedirs")
    @patch("builtins.open")
    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    @patch("quant_lab.core.data.aggregator.aggregate")
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_deep_count_in_report(self, mock_agg_step, mock_agg, mock_create_client, mock_open_fn, mock_makedirs, mock_sleep) -> None:
        mock_agg.return_value = {"name": "平安银行", "code": "000001", "type": "stock", "tech_summary": "正常", "money_summary": "正常"}
        client = MagicMock()
        mock_create_client.return_value = client

        def _run_pipeline(state):
            result = MagicMock()
            result.state = MagicMock()
            result.state.need_deep_analysis = True
            result.state.response = "深度分析"
            result.state.raw_data = {"tech_summary": "正常", "money_summary": "正常", "news_summary": "N/A"}
            result.failed_steps = []
            return result

        with patch("quant_lab.core.cli._load_watchlist", return_value=[{"code": "000001", "name": "平安银行", "tags": []}]), \
             patch("quant_lab.core.pipeline.runner.PipelineRunner.run", side_effect=_run_pipeline):
            run_v2_monitor_mode(watchlist_name="my", analysis_mode="deep", use_cache=False, max_workers=1)

    @patch("quant_lab.core.cli.time.sleep")
    @patch("os.makedirs")
    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    @patch("quant_lab.core.data.aggregator.aggregate")
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_pdf_generation_in_monitor(self, mock_agg_step, mock_agg, mock_create_client, mock_makedirs, mock_sleep) -> None:
        mock_agg.return_value = {"name": "平安银行", "code": "000001", "type": "stock", "tech_summary": "正常", "money_summary": "正常"}
        client = MagicMock()
        mock_create_client.return_value = client
        fake_md2pdf = MagicMock()
        fake_md2pdf.md_to_pdf = MagicMock(return_value=True)

        def _run_pipeline(state):
            result = MagicMock()
            result.state = MagicMock()
            result.state.need_deep_analysis = False
            result.state.response = "分析结果文本"
            result.state.raw_data = {"tech_summary": "正常", "money_summary": "正常", "news_summary": "N/A"}
            result.failed_steps = []
            return result

        m = mock_open()
        with patch("quant_lab.core.cli._load_watchlist", return_value=[{"code": "000001", "name": "平安银行", "tags": []}]), \
             patch.dict("sys.modules", {"md2pdf_tool": fake_md2pdf}), \
             patch("builtins.open", m), \
             patch("quant_lab.core.pipeline.runner.PipelineRunner.run", side_effect=_run_pipeline):
            run_v2_monitor_mode(watchlist_name="my", analysis_mode="fast", use_cache=False, max_workers=1)


class TestSelectBuilder:
    def test_deep(self) -> None:
        from quant_lab.core.pipeline.builders import build_deep_pipeline
        assert _select_builder("deep") is build_deep_pipeline

    def test_fast(self) -> None:
        from quant_lab.core.pipeline.builders import build_fast_pipeline
        assert _select_builder("fast") is build_fast_pipeline

    def test_auto(self) -> None:
        from quant_lab.core.pipeline.builders import build_auto_pipeline
        assert _select_builder("auto") is build_auto_pipeline
