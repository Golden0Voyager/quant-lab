"""Tests for MacroETFFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.macro_etf import MacroETFFetcher


class TestMacroETFFetcher:
    @patch("quant_lab.core.data.dimensions.macro_etf.ak")
    def test_happy_path(self, mock_ak: MagicMock) -> None:
        mock_ak.fx_spot_quote.return_value = pd.DataFrame(
            {
                "货币对": ["USDCNH", "EURUSD"],
                "买价": [7.1234, 1.0856],
            }
        )

        fetcher = MacroETFFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["usdcnh_rate"] == "7.1234"
        # OpenBB is in a separate try/except and may or may not be available
        # so we only assert the fx part

    @patch("quant_lab.core.data.dimensions.macro_etf.ak")
    def test_empty_fx_dataframe(self, mock_ak: MagicMock) -> None:
        mock_ak.fx_spot_quote.return_value = pd.DataFrame()

        fetcher = MacroETFFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["usdcnh_rate"] == "N/A"

    @patch("quant_lab.core.data.dimensions.macro_etf.ak")
    def test_exception(self, mock_ak: MagicMock) -> None:
        mock_ak.fx_spot_quote.side_effect = Exception("API down")

        fetcher = MacroETFFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" in result
        assert result["_dimension"] == "macro_etf"
