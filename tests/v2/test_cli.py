"""Tests for quant_lab.core.cli — v2 CLI entry points."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quant_lab.core.cli import (
    _infer_asset_type,
    _load_watchlist,
    _report_dir,
    run_v2_monitor_mode,
    run_v2_single_stock,
)


class TestLoadWatchlist:
    """Tests for ``_load_watchlist``."""

    def test_loads_builtin_my(self) -> None:
        """Built-in fallback works when watchlists.json is missing."""
        stocks = _load_watchlist("my")
        assert len(stocks) > 0
        assert all("code" in s and "name" in s for s in stocks)

    def test_loads_builtin_dad(self) -> None:
        stocks = _load_watchlist("dad")
        assert len(stocks) > 0

    def test_loads_builtin_erin(self) -> None:
        stocks = _load_watchlist("erin")
        assert len(stocks) > 0

    def test_unknown_returns_empty(self) -> None:
        stocks = _load_watchlist("nonexistent")
        assert stocks == []


class TestInferAssetType:
    """Tests for ``_infer_asset_type``."""

    def test_fund_tag(self) -> None:
        assert _infer_asset_type({"tags": ["基金", "医药"]}) == "fund"
        assert _infer_asset_type({"tags": ["fund"]}) == "fund"

    def test_etf_tag(self) -> None:
        assert _infer_asset_type({"tags": ["ETF", "汽车"]}) == "etf"
        assert _infer_asset_type({"tags": ["etf"]}) == "etf"

    def test_stock_returns_none(self) -> None:
        assert _infer_asset_type({"tags": ["芯片", "半导体"]}) is None
        assert _infer_asset_type({"tags": []}) is None


class TestReportDir:
    """Tests for ``_report_dir``."""

    def test_returns_report_subdirectory(self) -> None:
        path = _report_dir()
        assert "Report" in path
        # Should contain YYMMDD
        import re

        assert re.search(r"Report[/\\]\d{6}$", path)


class TestRunV2SingleStock:
    """Tests for ``run_v2_single_stock`` with mocked external deps."""

    @patch("quant_lab.core.cli._save_single_report")
    @patch("quant_lab.core.cli._print_result")
    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_fast_mode(
        self,
        mock_agg: MagicMock,
        mock_create_client: MagicMock,
        mock_print: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        """Fast mode completes all steps without errors."""
        mock_agg.return_value = {
            "name": "平安银行",
            "code": "000001",
            "type": "stock",
            "tech_summary": "正常",
            "money_summary": "正常",
        }

        client = MagicMock()
        client.chat.return_value = "快速分析结果"
        mock_create_client.return_value = client

        run_v2_single_stock(
            symbol="000001",
            stock_name="平安银行",
            analysis_mode="fast",
            use_cache=False,
        )

        mock_agg.assert_called_once_with("000001", "平安银行", asset_type="stock")
        mock_print.assert_called_once()
        mock_save.assert_called_once()
        args, _ = mock_save.call_args
        assert args[0].response == "快速分析结果"

    @patch("quant_lab.core.cli._save_single_report")
    @patch("quant_lab.core.cli._print_result")
    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_auto_mode_worker_path(
        self,
        mock_agg: MagicMock,
        mock_create_client: MagicMock,
        mock_print: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        """Auto mode with weak signals → worker path."""
        mock_agg.return_value = {
            "name": "平安银行",
            "code": "000001",
            "type": "stock",
            "tech_summary": "正常",
            "money_summary": "正常",
            "volume_alert": "正常",
        }

        client = MagicMock()
        client.chat.return_value = "Worker 结果"
        mock_create_client.return_value = client

        run_v2_single_stock(
            symbol="000001",
            analysis_mode="auto",
            use_cache=False,
        )

        state = mock_save.call_args[0][0]
        assert state.need_deep_analysis is False
        assert state.signal_score < 3

    @patch("quant_lab.core.cli._save_single_report")
    @patch("quant_lab.core.cli._print_result")
    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_deep_mode(
        self,
        mock_agg: MagicMock,
        mock_create_client: MagicMock,
        mock_print: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        """Deep mode always triggers brain analysis."""
        mock_agg.return_value = {
            "name": "平安银行",
            "code": "000001",
            "type": "stock",
            "tech_summary": "正常",
            "money_summary": "正常",
        }

        client = MagicMock()
        client.chat.return_value = "Brain 结果"
        mock_create_client.return_value = client

        run_v2_single_stock(
            symbol="000001",
            analysis_mode="deep",
            use_cache=False,
        )

        state = mock_save.call_args[0][0]
        assert state.need_deep_analysis is True
        assert "深度研判" in state.prompt


class TestRunV2MonitorMode:
    """Tests for ``run_v2_monitor_mode`` with mocked external deps."""

    @patch("quant_lab.core.cli.time.sleep")
    @patch("os.makedirs")
    @patch("builtins.open")
    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    @patch("quant_lab.core.data.aggregator.aggregate")
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_monitor_mode_runs_all_items(
        self,
        mock_agg_step: MagicMock,
        mock_agg: MagicMock,
        mock_create_client: MagicMock,
        mock_open: MagicMock,
        mock_makedirs: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        """Monitor mode fetches data and runs analysis for every stock."""
        mock_agg.return_value = {
            "name": "平安银行",
            "code": "000001",
            "type": "stock",
            "tech_summary": "正常",
            "money_summary": "正常",
            "news_summary": "N/A",
        }

        client = MagicMock()
        client.chat.return_value = "监控分析"
        mock_create_client.return_value = client

        # Patch watchlist to just 2 items for speed
        with patch(
            "quant_lab.core.cli._load_watchlist",
            return_value=[
                {"code": "000001", "name": "平安银行", "tags": []},
                {"code": "000002", "name": "万科A", "tags": []},
            ],
        ):
            run_v2_monitor_mode(
                watchlist_name="my",
                analysis_mode="fast",
                use_cache=False,
                max_workers=2,
            )

        # aggregate called for each stock
        assert mock_agg.call_count == 2
        mock_create_client.assert_called()

        # open should be called to write reports (single + aggregate)
        assert mock_open.call_count >= 1
        write_calls = [c for c in mock_open.call_args_list if c[0][0].endswith("_my_fast.md")]
        assert len(write_calls) >= 1
        args, _ = mock_open.call_args
        assert args[0].endswith(".md")

    @patch("quant_lab.core.cli.time.sleep")
    @patch("os.makedirs")
    @patch("builtins.open")
    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    @patch("quant_lab.core.data.aggregator.aggregate")
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_monitor_mode_skips_failed_fetches(
        self,
        mock_agg_step: MagicMock,
        mock_agg: MagicMock,
        mock_create_client: MagicMock,
        mock_open: MagicMock,
        mock_makedirs: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        """Items that fail data fetching are skipped in the report."""
        mock_agg.side_effect = [
            Exception("network error"),  # first stock fails
            {"name": "万科A", "code": "000002", "type": "stock"},  # second ok
        ]

        client = MagicMock()
        client.chat.return_value = "分析"
        mock_create_client.return_value = client

        with patch(
            "quant_lab.core.cli._load_watchlist",
            return_value=[
                {"code": "000001", "name": "平安银行", "tags": []},
                {"code": "000002", "name": "万科A", "tags": []},
            ],
        ):
            run_v2_monitor_mode(
                watchlist_name="my",
                analysis_mode="fast",
                use_cache=False,
                max_workers=2,
            )

        # Only one LLM call (the successful fetch)
        assert mock_create_client.call_count == 1

        # open should be called to write reports
        assert mock_open.call_count >= 1
        write_calls = [c for c in mock_open.call_args_list if c[0][0].endswith("_my_fast.md")]
        assert len(write_calls) >= 1
