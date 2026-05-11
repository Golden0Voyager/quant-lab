"""Tests for ChipFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.chip import ChipFetcher


class TestChipFetcher:
    @patch("quant_lab.core.data.dimensions.chip.ak")
    def test_happy_path(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_cyq_em.return_value = pd.DataFrame(
            {
                "日期": ["2025-01-01"],
                "获利比例": [65.0],
                "平均成本": [25.5],
                "90%集中度": [15.0],
                "70%集中度": [10.0],
            }
        )

        fetcher = ChipFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["chip_profit_ratio_raw"] == 65.0
        assert result["chip_avg_cost_raw"] == 25.5
        assert result["chip_signal"] == "筹码偏集中，支撑较强"
        assert "获利65.0%" in result["chip_summary"]

    @patch.object(ChipFetcher, "_fetch_from_datacenter", return_value=None)
    @patch("quant_lab.core.data.dimensions.chip.ak")
    def test_empty_dataframe(self, mock_ak: MagicMock, _mock_dc: MagicMock) -> None:
        mock_ak.stock_cyq_em.return_value = pd.DataFrame()

        fetcher = ChipFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["chip_signal"] == "数据暂不可用"

    @patch.object(ChipFetcher, "_fetch_from_datacenter", return_value=None)
    @patch("quant_lab.core.data.dimensions.chip.ak")
    def test_exception(self, mock_ak: MagicMock, _mock_dc: MagicMock) -> None:
        mock_ak.stock_cyq_em.side_effect = Exception("API down")

        fetcher = ChipFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["chip_signal"] == "数据暂不可用"
