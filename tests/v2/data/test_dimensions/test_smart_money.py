"""Tests for SmartMoneyFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.smart_money import SmartMoneyFetcher


class TestSmartMoneyFetcher:
    @patch("quant_lab.core.data.dimensions.smart_money.ak")
    def test_happy_path(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_hsgt_individual_em.return_value = pd.DataFrame(
            {
                "持股数量": [1000, 1100, 1200, 1300, 1400],
                "占流通股比": [2.5, 2.6, 2.7, 2.8, 2.9],
            }
        )
        mock_ak.stock_margin_detail_sse.return_value = pd.DataFrame(
            {
                "融资余额": [1e9, 1.05e9, 1.1e9, 1.15e9, 1.2e9],
                "融券余额": [1e8, 1.1e8, 1.2e8, 1.3e8, 1.4e8],
            }
        )

        fetcher = SmartMoneyFetcher()
        result = fetcher.fetch("600000", "浦发银行")

        assert "_error" not in result
        assert result["north_consecutive_days"] == 4
        assert result["north_change_pct_3d"] is not None
        assert result["north_holding_ratio"] == 2.9
        assert result["margin_balance"] == 12.0
        assert result["margin_balance_trend"] == "增"
        assert result["short_selling_level"] == "正常"
        assert "北向连续" in result["smart_money_summary"]

    @patch("quant_lab.core.data.dimensions.smart_money.ak")
    def test_northbound_only(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_hsgt_individual_em.return_value = pd.DataFrame(
            {
                "持股数量": [1000, 1000, 1000, 1000, 1000],
                "占流通股比": [2.5, 2.5, 2.5, 2.5, 2.5],
            }
        )
        mock_ak.stock_margin_detail_sse.return_value = None

        fetcher = SmartMoneyFetcher()
        result = fetcher.fetch("600000", "浦发银行")

        assert "_error" not in result
        assert result["north_consecutive_days"] == 0
        assert "margin_balance" not in result
        assert "北向持仓持平" in result["smart_money_summary"]

    @patch("quant_lab.core.data.dimensions.smart_money.ak")
    def test_szse_margin(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_hsgt_individual_em.return_value = pd.DataFrame(
            {"持股数量": [1000], "占流通股比": [1.5]}
        )
        mock_ak.stock_margin_detail_szse.return_value = pd.DataFrame(
            {
                "融资余额": [5e8],
                "融券余额": [1e8],
            }
        )

        fetcher = SmartMoneyFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["margin_balance"] == 5.0
        mock_ak.stock_margin_detail_sse.assert_not_called()

    @patch("quant_lab.core.data.dimensions.smart_money.ak")
    def test_exception(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_hsgt_individual_em.side_effect = Exception("API down")
        mock_ak.stock_margin_detail_sse.return_value = None

        fetcher = SmartMoneyFetcher()
        result = fetcher.fetch("600000", "浦发银行")

        assert "_error" not in result
        assert result["smart_money_summary"] == "暂无聪明钱数据"
