"""Tests for PerformanceFetcher."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from quant_lab.core.data.dimensions.performance import PerformanceFetcher


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
