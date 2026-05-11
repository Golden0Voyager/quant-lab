"""Tests for QuarterlyTrendFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.quarterly_trend import QuarterlyTrendFetcher


class TestQuarterlyTrendFetcher:
    @patch("quant_lab.core.data.dimensions.quarterly_trend.ak")
    def test_happy_path(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_profit_sheet_by_report_em.return_value = pd.DataFrame(
            {
                "REPORT_DATE": ["2025-09-30", "2025-06-30", "2025-03-31"],
                "REPORT_DATE_NAME": ["2025三季报", "2025中报", "2025一季报"],
                "OPERATE_INCOME": [1000.0, 800.0, 400.0],
                "OPERATE_INCOME_YOY": [10.0, 8.0, 5.0],
                "PARENT_NETPROFIT": [200.0, 150.0, 80.0],
                "PARENT_NETPROFIT_YOY": [15.0, 12.0, 10.0],
            }
        )

        fetcher = QuarterlyTrendFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert len(result["quarterly_trend"]) == 3
        first = result["quarterly_trend"][0]
        assert first["report_date"] == "2025-09-30"
        assert first["report_name"] == "2025三季报"
        assert first["revenue"] == 1000.0
        assert first["revenue_yoy"] == 10.0
        assert first["net_profit"] == 200.0
        assert first["net_profit_yoy"] == 15.0

    @patch("quant_lab.core.data.dimensions.quarterly_trend.ak")
    def test_sh_prefix(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_profit_sheet_by_report_em.return_value = pd.DataFrame(
            {"REPORT_DATE": ["2025-09-30"]}
        )

        fetcher = QuarterlyTrendFetcher()
        result = fetcher.fetch("600519", "贵州茅台")

        assert mock_ak.stock_profit_sheet_by_report_em.call_args.kwargs["symbol"] == "SH600519"

    @patch("quant_lab.core.data.dimensions.quarterly_trend.ak")
    def test_empty_dataframe(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_profit_sheet_by_report_em.return_value = pd.DataFrame()

        fetcher = QuarterlyTrendFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" in result
        assert result["_dimension"] == "quarterly_trend"

    @patch("quant_lab.core.data.dimensions.quarterly_trend.ak")
    def test_exception(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_profit_sheet_by_report_em.side_effect = Exception("API down")

        fetcher = QuarterlyTrendFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" in result
        assert result["_dimension"] == "quarterly_trend"
