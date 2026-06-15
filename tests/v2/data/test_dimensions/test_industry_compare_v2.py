"""Extended tests for IndustryCompareFetcher — covering uncovered branches."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.industry_compare import (
    IndustryCompareFetcher,
    _get_industry,
    _industry_cache,
    _yjbb_cache,
)


class TestGetIndustryV2:
    def setup_method(self) -> None:
        _industry_cache.clear()
        _yjbb_cache.clear()

    @patch("quant_lab.core.data.dimensions.industry_compare.ak")
    def test_cache_hit(self, mock_ak: MagicMock) -> None:
        _industry_cache["000001"] = "银行"
        result = _get_industry("000001")
        assert result == "银行"
        mock_ak.stock_yjbb_em.assert_not_called()

    @patch("quant_lab.core.data.dimensions.industry_compare.ak")
    def test_strategy1_exception(self, mock_ak: MagicMock) -> None:
        """stock_yjbb_em raises → strategy 2 fallback (lines 42-43)."""
        mock_ak.stock_yjbb_em.side_effect = Exception("fail")
        mock_ak.stock_individual_info_em.return_value = pd.DataFrame(
            {"item": ["行业"], "value": ["银行"]}
        )
        result = _get_industry("000001")
        assert result == "银行"

    @patch("quant_lab.core.data.dimensions.industry_compare.ak")
    def test_strategy2_exception(self, mock_ak: MagicMock) -> None:
        """Both strategies fail → return None (lines 56-57)."""
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame()
        mock_ak.stock_individual_info_em.side_effect = Exception("fail")
        result = _get_industry("000001")
        assert result is None


class TestIndustryCompareFetcherV2:
    def setup_method(self) -> None:
        _industry_cache.clear()
        _yjbb_cache.clear()

    @patch("quant_lab.core.data.dimensions.industry_compare.ak")
    def test_empty_df(self, mock_ak: MagicMock) -> None:
        """yjbb returns empty df → raise (line 83)."""
        mock_ak.stock_yjbb_em.side_effect = [
            pd.DataFrame({"股票代码": ["000001"], "所处行业": ["银行"]}),
            pd.DataFrame(),
        ]
        fetcher = IndustryCompareFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert "_error" in result

    @patch("quant_lab.core.data.dimensions.industry_compare.ak")
    def test_peers_empty(self, mock_ak: MagicMock) -> None:
        """No peers in same industry → raise (line 87)."""
        mock_ak.stock_yjbb_em.side_effect = [
            pd.DataFrame({"股票代码": ["000001"], "所处行业": ["银行"]}),
            pd.DataFrame(
                {
                    "股票代码": ["000001"],
                    "所处行业": ["科技"],
                    "净资产收益率": ["12.0"],
                    "销售毛利率": ["50.0"],
                    "营业总收入-同比增长": ["5.0"],
                    "净利润-同比增长": ["8.0"],
                }
            ),
        ]
        fetcher = IndustryCompareFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert "_error" in result

    @patch("quant_lab.core.data.dimensions.industry_compare.ak")
    def test_valid_empty_continue(self, mock_ak: MagicMock) -> None:
        """All metric columns have NaN → skip (line 100)."""
        mock_ak.stock_yjbb_em.side_effect = [
            pd.DataFrame({"股票代码": ["000001"], "所处行业": ["银行"]}),
            pd.DataFrame(
                {
                    "股票代码": ["000001", "000002"],
                    "所处行业": ["银行", "银行"],
                    "净资产收益率": [None, None],
                    "销售毛利率": [None, None],
                    "营业总收入-同比增长": [None, None],
                    "净利润-同比增长": [None, None],
                }
            ),
        ]
        fetcher = IndustryCompareFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert "roe_median" not in result
        assert result["peer_count"] == 2
