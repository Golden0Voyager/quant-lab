"""Tests for PerformanceFetcher."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd

from quant_lab.core.data.dimensions.performance import PerformanceFetcher, _get_report_date


class TestGetReportDate:
    def test_month_november(self) -> None:
        with patch("quant_lab.core.data.dimensions.performance.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 11, 15)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert _get_report_date() == "20260930"

    def test_month_august(self) -> None:
        with patch("quant_lab.core.data.dimensions.performance.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 8, 15)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert _get_report_date() == "20260630"

    def test_month_may(self) -> None:
        with patch("quant_lab.core.data.dimensions.performance.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 5, 15)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert _get_report_date() == "20260331"

    def test_month_january(self) -> None:
        with patch("quant_lab.core.data.dimensions.performance.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 15)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert _get_report_date() == "20250930"


class TestPerformanceFetcher:
    @patch("quant_lab.core.data.dimensions.performance.ak.stock_yjbb_em")
    def test_fetch_success(self, mock_yjbb: MagicMock) -> None:
        mock_df = pd.DataFrame(
            {
                "股票代码": ["000001"],
                "营业总收入-同比增长": [15.5],
                "营业总收入-季度环比增长": [3.2],
                "净利润-同比增长": [20.1],
                "净利润-季度环比增长": [5.5],
                "销售毛利率": [35.0],
                "净资产收益率": [12.5],
                "每股经营现金流量": [3.1],
                "每股收益": [2.5],
                "营业总收入-营业总收入": [1_000_000_000.0],
            }
        )
        mock_yjbb.return_value = mock_df

        fetcher = PerformanceFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["revenue_yoy"] == "15.50%"
        assert result["profit_yoy"] == "20.10%"
        assert result["gross_margin"] == "35.00%"
        assert result["roe"] == "12.50%"
        assert result["eps"] == "2.50"
        assert result["cf_quality"] == "✅ 优质现金流"
        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.performance.ak.stock_yjbb_em")
    def test_fetch_missing_symbol(self, mock_yjbb: MagicMock) -> None:
        mock_df = pd.DataFrame({"股票代码": []})
        mock_yjbb.return_value = mock_df

        fetcher = PerformanceFetcher()
        result = fetcher.fetch("999999", "不存在")

        assert "_error" in result
        assert "未找到" in result["_error"]

    @patch("quant_lab.core.data.dimensions.performance.ak.stock_yjbb_em")
    def test_fetch_empty_dataframe(self, mock_yjbb: MagicMock) -> None:
        from quant_lab.core.data.dimensions.performance import _yjbb_cache

        _yjbb_cache.clear()
        mock_yjbb.return_value = None

        fetcher = PerformanceFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" in result

    @patch("quant_lab.core.data.dimensions.performance.ak.stock_yjbb_em")
    def test_null_revenue(self, mock_yjbb: MagicMock) -> None:
        from quant_lab.core.data.dimensions.performance import _yjbb_cache

        _yjbb_cache.clear()
        mock_df = pd.DataFrame(
            {
                "股票代码": ["000001"],
                "营业总收入-同比增长": [15.5],
                "营业总收入-季度环比增长": [3.2],
                "净利润-同比增长": [20.1],
                "净利润-季度环比增长": [5.5],
                "销售毛利率": [35.0],
                "净资产收益率": [12.5],
                "每股经营现金流量": [float("nan")],
                "每股收益": [2.5],
                "营业总收入-营业总收入": [float("nan")],
            }
        )
        mock_yjbb.return_value = mock_df

        fetcher = PerformanceFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["revenue_ttm_raw"] is None
        assert result["revenue_ttm_display"] == "N/A"

    @patch("quant_lab.core.data.dimensions.performance.ak.stock_yjbb_em")
    def test_null_cf_per_share(self, mock_yjbb: MagicMock) -> None:
        from quant_lab.core.data.dimensions.performance import _yjbb_cache

        _yjbb_cache.clear()
        mock_df = pd.DataFrame(
            {
                "股票代码": ["000001"],
                "营业总收入-同比增长": [15.5],
                "营业总收入-季度环比增长": [3.2],
                "净利润-同比增长": [20.1],
                "净利润-季度环比增长": [5.5],
                "销售毛利率": [35.0],
                "净资产收益率": [12.5],
                "每股经营现金流量": [float("nan")],
                "每股收益": [2.5],
                "营业总收入-营业总收入": [1_000_000_000.0],
            }
        )
        mock_yjbb.return_value = mock_df

        fetcher = PerformanceFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["cf_profit_ratio"] == "N/A"
        assert result["cf_quality"] == "数据不足"

    @patch("quant_lab.core.data.dimensions.performance.ak.stock_yjbb_em")
    def test_cf_quality_normal(self, mock_yjbb: MagicMock) -> None:
        from quant_lab.core.data.dimensions.performance import _yjbb_cache

        _yjbb_cache.clear()
        mock_df = pd.DataFrame(
            {
                "股票代码": ["000001"],
                "营业总收入-同比增长": [15.5],
                "营业总收入-季度环比增长": [3.2],
                "净利润-同比增长": [20.1],
                "净利润-季度环比增长": [5.5],
                "销售毛利率": [35.0],
                "净资产收益率": [12.5],
                "每股经营现金流量": [1.0],
                "每股收益": [1.0],
                "营业总收入-营业总收入": [1_000_000_000.0],
            }
        )
        mock_yjbb.return_value = mock_df

        fetcher = PerformanceFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["cf_quality"] == "正常水平"

    @patch("quant_lab.core.data.dimensions.performance.ak")
    def test_revenue_0930(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
            {
                "股票代码": ["000001"],
                "营业总收入-营业总收入": [3e9],
                "营业总收入-同比增长": [5.0],
                "营业总收入-季度环比增长": [2.0],
                "净利润-同比增长": [8.0],
                "净利润-季度环比增长": [3.0],
                "销售毛利率": [50.0],
                "净资产收益率": [12.0],
                "每股经营现金流量": [1.5],
                "每股收益": [2.0],
            }
        )
        fetcher = PerformanceFetcher()
        with patch("quant_lab.core.data.dimensions.performance._get_report_date", return_value="20250930"):
            result = fetcher.fetch("000001", "平安银行")
        assert result["revenue_ttm_raw"] == 3e9 * (4 / 3)

    @patch("quant_lab.core.data.dimensions.performance.ak")
    def test_revenue_0630(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
            {
                "股票代码": ["000001"],
                "营业总收入-营业总收入": [2e9],
                "营业总收入-同比增长": [5.0],
                "营业总收入-季度环比增长": [2.0],
                "净利润-同比增长": [8.0],
                "净利润-季度环比增长": [3.0],
                "销售毛利率": [50.0],
                "净资产收益率": [12.0],
                "每股经营现金流量": [1.5],
                "每股收益": [2.0],
            }
        )
        fetcher = PerformanceFetcher()
        with patch("quant_lab.core.data.dimensions.performance._get_report_date", return_value="20250630"):
            result = fetcher.fetch("000001", "平安银行")
        assert result["revenue_ttm_raw"] == 2e9 * 2

    @patch("quant_lab.core.data.dimensions.performance.ak")
    def test_revenue_1231(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
            {
                "股票代码": ["000001"],
                "营业总收入-营业总收入": [5e9],
                "营业总收入-同比增长": [5.0],
                "营业总收入-季度环比增长": [2.0],
                "净利润-同比增长": [8.0],
                "净利润-季度环比增长": [3.0],
                "销售毛利率": [50.0],
                "净资产收益率": [12.0],
                "每股经营现金流量": [1.5],
                "每股收益": [2.0],
            }
        )
        fetcher = PerformanceFetcher()
        with patch("quant_lab.core.data.dimensions.performance._get_report_date", return_value="20241231"):
            result = fetcher.fetch("000001", "平安银行")
        assert result["revenue_ttm_raw"] == 5e9
