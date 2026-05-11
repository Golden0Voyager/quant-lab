"""Tests for CompetitorFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions import industry_compare
from quant_lab.core.data.dimensions.competitor import CompetitorFetcher


class TestCompetitorFetcher:
    def setup_method(self) -> None:
        self._orig_yjbb_cache = industry_compare._yjbb_cache.copy()
        industry_compare._yjbb_cache.clear()

    def teardown_method(self) -> None:
        industry_compare._yjbb_cache.clear()
        industry_compare._yjbb_cache.update(self._orig_yjbb_cache)

    @patch("quant_lab.core.data.dimensions.competitor._get_industry")
    @patch("quant_lab.core.data.dimensions.competitor.ak")
    def test_happy_path(
        self, mock_ak: MagicMock, mock_industry: MagicMock
    ) -> None:
        mock_industry.return_value = "银行"
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
            {
                "股票代码": ["000001", "000002", "600000"],
                "股票简称": ["平安银行", "万科A", "浦发银行"],
                "所处行业": ["银行", "房地产", "银行"],
                "营业总收入-营业总收入": ["1000", "800", "1200"],
                "净资产收益率": ["12.5", "8.3", "10.1"],
                "营业总收入-同比增长": ["5.2", "-2.1", "3.4"],
                "净利润-同比增长": ["8.1", "-5.2", "4.3"],
                "销售毛利率": ["35.2", "25.1", "30.5"],
            }
        )

        fetcher = CompetitorFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["industry_name"] == "银行"
        assert result["industry_peer_count"] == 2
        assert len(result["competitors"]) == 1
        assert result["competitors"][0]["code"] == "600000"
        assert "银行" in result["competitor_summary"]

    @patch("quant_lab.core.data.dimensions.competitor._get_industry")
    def test_no_industry(self, mock_industry: MagicMock) -> None:
        mock_industry.return_value = None

        fetcher = CompetitorFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["competitor_summary"] == "无法获取行业分类"

    @patch("quant_lab.core.data.dimensions.competitor._get_industry")
    @patch("quant_lab.core.data.dimensions.competitor.ak")
    def test_empty_peers(
        self, mock_ak: MagicMock, mock_industry: MagicMock
    ) -> None:
        mock_industry.return_value = "银行"
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
            {
                "股票代码": ["000002"],
                "股票简称": ["万科A"],
                "所处行业": ["房地产"],
            }
        )

        fetcher = CompetitorFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["competitor_summary"] == "行业: 银行"

    @patch("quant_lab.core.data.dimensions.competitor._get_industry")
    @patch("quant_lab.core.data.dimensions.competitor.ak")
    def test_exception(
        self, mock_ak: MagicMock, mock_industry: MagicMock
    ) -> None:
        mock_industry.return_value = "银行"
        mock_ak.stock_yjbb_em.side_effect = Exception("API down")

        fetcher = CompetitorFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert "银行" in result["competitor_summary"]
