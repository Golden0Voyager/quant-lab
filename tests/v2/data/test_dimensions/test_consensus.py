"""Tests for ConsensusFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.consensus import ConsensusFetcher


class TestConsensusFetcher:
    @patch("quant_lab.core.data.dimensions.consensus.ak")
    def test_full_forecast_and_ratings(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_profit_forecast_ths.return_value = pd.DataFrame(
            {"均值": [2.5, 3.0]}
        )
        mock_ak.stock_institute_recommend_detail.return_value = pd.DataFrame(
            {
                "评级": ["买入", "买入", "增持"],
                "目标价": [25.0, 26.0, 24.0],
                "评级日期": ["2026-04-30", "2026-04-29", "2026-04-28"],
            }
        )

        fetcher = ConsensusFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["eps_forecast_current_raw"] == 2.5
        assert result["eps_forecast_next_raw"] == 3.0
        assert result["eps_growth_rate_raw"] == 20.0
        assert result["target_price_avg"] == "25.00"
        assert result["rating_buy"] == 2
        assert result["rating_overweight"] == 1
        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.consensus.ak")
    def test_no_data_returns_summary_placeholder(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_profit_forecast_ths.return_value = pd.DataFrame()
        mock_ak.stock_institute_recommend_detail.return_value = pd.DataFrame()

        fetcher = ConsensusFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["consensus_summary"] == "暂无分析师覆盖"
        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.consensus.ak")
    def test_forecast_only_no_ratings(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_profit_forecast_ths.return_value = pd.DataFrame(
            {"均值": [1.5]}
        )
        mock_ak.stock_institute_recommend_detail.side_effect = Exception("API down")

        fetcher = ConsensusFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["eps_forecast_current_raw"] == 1.5
        assert "rating_buy" not in result
        assert "_error" not in result
