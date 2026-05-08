"""Tests for ValuationFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quant_lab.core.data.dimensions.valuation import ValuationFetcher


class TestValuationFetcher:
    @patch("quant_lab.core.data.dimensions.valuation.fetch_xueqiu_spot")
    @patch("quant_lab.core.data.dimensions.valuation.fetch_valuation_percentile")
    def test_fetch_xueqiu_success(
        self,
        mock_percentile: MagicMock,
        mock_xueqiu: MagicMock,
    ) -> None:
        mock_xueqiu.return_value = {
            "市盈率(TTM)": "15.5",
            "市净率": "1.2",
            "股息率(TTM)": "3.5",
            "总市值": "5000000000",
        }
        mock_percentile.side_effect = [
            {"10y": 45.2, "5y": 50.0},
            {"10y": 30.1, "5y": 35.0},
        ]

        fetcher = ValuationFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["pe_ttm"] == "15.50"
        assert result["pb"] == "1.20"
        assert result["dividend_yield"] == "3.50%"
        assert result["market_cap_display"] == "50亿"
        assert "pe_percentile" in result
        assert "valuation_summary" in result
        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.valuation.fetch_xueqiu_spot")
    @patch("quant_lab.core.data.dimensions.valuation.fetch_financial_report")
    @patch("quant_lab.core.data.dimensions.valuation.fetch_eastmoney_kline")
    @patch("quant_lab.core.data.dimensions.valuation.fetch_stock_info_eastmoney")
    @patch("quant_lab.core.data.dimensions.valuation.fetch_valuation_percentile")
    def test_fetch_fallback(
        self,
        mock_percentile: MagicMock,
        mock_info: MagicMock,
        mock_kline: MagicMock,
        mock_report: MagicMock,
        mock_xueqiu: MagicMock,
    ) -> None:
        mock_xueqiu.return_value = None
        mock_report.return_value = {"每股收益": "2.5", "每股净资产": "10.0"}
        mock_kline.return_value = {"收盘": "25.0"}
        mock_info.return_value = {"总市值": "8000000000"}
        mock_percentile.side_effect = [{}, {}]

        fetcher = ValuationFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["pe_ttm_raw"] == pytest.approx(10.0)
        assert result["pb_raw"] == pytest.approx(2.5)
        assert result["market_cap"] == 8000000000.0
        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.valuation.fetch_xueqiu_spot")
    @patch("quant_lab.core.data.dimensions.valuation.fetch_financial_report")
    @patch("quant_lab.core.data.dimensions.valuation.fetch_eastmoney_kline")
    @patch("quant_lab.core.data.dimensions.valuation.fetch_sina_kline")
    @patch("quant_lab.core.data.dimensions.valuation.fetch_stock_info_eastmoney")
    @patch("quant_lab.core.data.dimensions.valuation.fetch_valuation_percentile")
    def test_fetch_all_sources_fail(
        self,
        mock_percentile: MagicMock,
        mock_info: MagicMock,
        mock_sina: MagicMock,
        mock_kline: MagicMock,
        mock_report: MagicMock,
        mock_xueqiu: MagicMock,
    ) -> None:
        mock_xueqiu.return_value = None
        mock_report.return_value = None
        mock_kline.return_value = None
        mock_sina.return_value = None
        mock_info.return_value = None
        mock_percentile.side_effect = [{}, {}]

        fetcher = ValuationFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["pe_ttm"] == "N/A"
        assert result["pb"] == "N/A"
        assert "valuation_summary" in result
        assert "_error" not in result
