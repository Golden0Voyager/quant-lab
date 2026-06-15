"""Extended tests for MacroETFFetcher — covering all branches."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.macro_etf import MacroETFFetcher


class TestMacroETFFetcherExtended:
    def test_fx_df_none(self) -> None:
        with patch("quant_lab.core.data.dimensions.macro_etf.ak") as mock_ak:
            mock_ak.fx_spot_quote.return_value = None
            fetcher = MacroETFFetcher()
            result = fetcher.fetch("000001", "平安银行")
            assert result["usdcnh_rate"] == "N/A"

    def test_usdcnh_not_found(self) -> None:
        with patch("quant_lab.core.data.dimensions.macro_etf.ak") as mock_ak:
            mock_ak.fx_spot_quote.return_value = pd.DataFrame(
                {"货币对": ["EURUSD"], "买价": [1.08]}
            )
            fetcher = MacroETFFetcher()
            result = fetcher.fetch("000001", "平安银行")
            assert result["usdcnh_rate"] == "N/A"

    def test_openbb_success(self) -> None:
        with patch("quant_lab.core.data.dimensions.macro_etf.ak") as mock_ak:
            mock_ak.fx_spot_quote.return_value = pd.DataFrame(
                {"货币对": ["USDCNH"], "买价": [7.12]}
            )
            mock_macro = MagicMock()
            mock_macro.fetch_global_macro.return_value = {
                "us10y_yield": "4.5%",
                "dxy_index": "103.5",
                "sp500": "5200",
                "nasdaq": "16000",
                "dowjones": "39000",
                "usdcny": "7.24",
                "hsi_index": "18000",
                "nikkei225": "38000",
                "vix_index": "15.5",
                "wti_crude": "78.5",
                "gold": "2350",
                "silver": "28.5",
                "btc": "68000",
                "us10y_yield_chg": "0.05",
                "dxy_index_chg": "-0.12",
                "sp500_chg": "0.8",
                "nasdaq_chg": "1.2",
                "dowjones_chg": "0.5",
                "usdcny_chg": "0.1",
                "hsi_index_chg": "-0.3",
                "nikkei225_chg": "0.7",
                "vix_index_chg": "2.1",
                "wti_crude_chg": "1.5",
                "gold_chg": "0.3",
                "silver_chg": "-0.2",
                "btc_chg": "3.5",
                "vix_level": "Low",
                "update_time": "2025-06-15",
            }
            with patch.dict(
                "sys.modules", {"quant_lab.analyst_openbb": MagicMock(OpenBBAnalyst=MagicMock(return_value=mock_macro))}
            ):
                fetcher = MacroETFFetcher()
                result = fetcher.fetch("000001", "平安银行")
                assert "global_macro_summary" in result
                assert "N/A" != result["global_macro_summary"]
                assert "us10y_yield" in result

    def test_openbb_import_error(self) -> None:
        with patch("quant_lab.core.data.dimensions.macro_etf.ak") as mock_ak:
            mock_ak.fx_spot_quote.return_value = pd.DataFrame(
                {"货币对": ["USDCNH"], "买价": [7.12]}
            )
            with patch.dict("sys.modules", {"quant_lab.analyst_openbb": None}):
                fetcher = MacroETFFetcher()
                result = fetcher.fetch("000001", "平安银行")
                assert result["global_macro_summary"] == "N/A"

    def test_openbb_none_global_macro(self) -> None:
        with patch("quant_lab.core.data.dimensions.macro_etf.ak") as mock_ak:
            mock_ak.fx_spot_quote.return_value = pd.DataFrame(
                {"货币对": ["USDCNH"], "买价": [7.12]}
            )
            mock_macro = MagicMock()
            mock_macro.fetch_global_macro.return_value = None
            with patch.dict(
                "sys.modules", {"quant_lab.analyst_openbb": MagicMock(OpenBBAnalyst=MagicMock(return_value=mock_macro))}
            ):
                fetcher = MacroETFFetcher()
                result = fetcher.fetch("000001", "平安银行")
                # When global_macro is None/falsy, the if block is skipped
                # so global_macro_summary is never set
                assert "global_macro_summary" not in result

    def test_openbb_partial_data(self) -> None:
        with patch("quant_lab.core.data.dimensions.macro_etf.ak") as mock_ak:
            mock_ak.fx_spot_quote.return_value = pd.DataFrame(
                {"货币对": ["USDCNH"], "买价": [7.12]}
            )
            mock_macro = MagicMock()
            mock_macro.fetch_global_macro.return_value = {
                "us10y_yield": "4.5%",
                "update_time": "2025-06-15",
            }
            with patch.dict(
                "sys.modules", {"quant_lab.analyst_openbb": MagicMock(OpenBBAnalyst=MagicMock(return_value=mock_macro))}
            ):
                fetcher = MacroETFFetcher()
                result = fetcher.fetch("000001", "平安银行")
                assert result["global_macro_summary"] is not None

    def test_openbb_na_values(self) -> None:
        with patch("quant_lab.core.data.dimensions.macro_etf.ak") as mock_ak:
            mock_ak.fx_spot_quote.return_value = pd.DataFrame(
                {"货币对": ["USDCNH"], "买价": [7.12]}
            )
            mock_macro = MagicMock()
            mock_macro.fetch_global_macro.return_value = {
                "us10y_yield": "N/A",
                "dxy_index": None,
                "update_time": "2025-06-15",
            }
            with patch.dict(
                "sys.modules", {"quant_lab.analyst_openbb": MagicMock(OpenBBAnalyst=MagicMock(return_value=mock_macro))}
            ):
                fetcher = MacroETFFetcher()
                result = fetcher.fetch("000001", "平安银行")
                assert "global_macro_summary" in result
