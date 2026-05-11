"""Tests for IndustryCompareFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.industry_compare import (
    IndustryCompareFetcher,
    _get_industry,
    _industry_cache,
    _yjbb_cache,
)


class TestIndustryCompareFetcher:
    def setup_method(self) -> None:
        _industry_cache.clear()
        _yjbb_cache.clear()

    @patch("quant_lab.core.data.dimensions.industry_compare.ak")
    def test_full_comparison(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
            {
                "股票代码": ["000001", "000002", "000003"],
                "所处行业": ["银行", "银行", "银行"],
                "净资产收益率": ["12.0", "10.0", "8.0"],
                "销售毛利率": ["50.0", "45.0", "40.0"],
                "营业总收入-同比增长": ["5.0", "3.0", "1.0"],
                "净利润-同比增长": ["8.0", "6.0", "4.0"],
            }
        )

        fetcher = IndustryCompareFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["industry_name"] == "银行"
        assert result["peer_count"] == 3
        assert result["roe_median"] == 10.0
        assert result["roe_rank"] == 3  # 12.0 is highest -> 2 below + 1
        assert result["roe_total"] == 3
        assert result["roe_value"] == 12.0
        assert result["gross_margin_median"] == 45.0

    @patch("quant_lab.core.data.dimensions.industry_compare.ak")
    def test_industry_from_info_em(self, mock_ak: MagicMock) -> None:
        """When stock_yjbb_em lacks the symbol, fall back to stock_individual_info_em."""
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
            {
                "股票代码": ["999999"],
                "所处行业": ["银行"],
            }
        )
        mock_ak.stock_individual_info_em.return_value = pd.DataFrame(
            {"item": ["行业"], "value": ["银行"]}
        )
        mock_ak.stock_yjbb_em.side_effect = [
            pd.DataFrame({"股票代码": ["999999"], "所处行业": ["银行"]}),
            pd.DataFrame(
                {
                    "股票代码": ["000001", "000002"],
                    "所处行业": ["银行", "银行"],
                    "净资产收益率": ["12.0", "10.0"],
                    "销售毛利率": ["50.0", "45.0"],
                    "营业总收入-同比增长": ["5.0", "3.0"],
                    "净利润-同比增长": ["8.0", "6.0"],
                }
            ),
        ]

        fetcher = IndustryCompareFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["industry_name"] == "银行"

    @patch("quant_lab.core.data.dimensions.industry_compare.ak")
    def test_empty_peers(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
            {
                "股票代码": ["000001"],
                "所处行业": ["银行"],
                "净资产收益率": ["12.0"],
                "销售毛利率": ["50.0"],
                "营业总收入-同比增长": ["5.0"],
                "净利润-同比增长": ["8.0"],
            }
        )

        fetcher = IndustryCompareFetcher()
        result = fetcher.fetch("999999", "虚构股票")

        assert "_error" in result
        assert result["_dimension"] == "industry_compare"

    @patch("quant_lab.core.data.dimensions.industry_compare.ak")
    def test_no_industry(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
            {"股票代码": [], "所处行业": []}
        )
        mock_ak.stock_individual_info_em.return_value = pd.DataFrame(
            {"item": [], "value": []}
        )

        fetcher = IndustryCompareFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" in result
        assert result["_dimension"] == "industry_compare"
