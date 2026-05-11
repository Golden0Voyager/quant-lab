"""Tests for TopHoldersFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.top_holders import TopHoldersFetcher


class TestTopHoldersFetcher:
    @patch("quant_lab.core.data.dimensions.top_holders.fetch_circulate_holders")
    def test_happy_path(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = {
            "df": pd.DataFrame(
                {
                    "截止日期": ["2025-09-30", "2025-09-30", "2025-06-30"],
                    "股东名称": ["Alice", "Bob", "Alice"],
                    "持股数量": [1000, 800, 900],
                    "占流通股比例": [5.0, 4.0, 4.5],
                    "股本性质": ["自然人", "法人", "自然人"],
                }
            )
        }

        fetcher = TopHoldersFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["holders_report_date"] == "2025-09-30"
        assert len(result["top_holders"]) == 2
        assert result["top_holders"][0]["name"] == "Alice"
        assert result["top_holders"][0]["shares"] == 1000
        assert result["top_holders"][0]["pct"] == 5.0
        assert result["holders_prev_date"] == "2025-06-30"
        assert result["holders_prev_map"]["Alice"]["shares"] == 900

    @patch("quant_lab.core.data.dimensions.top_holders.fetch_circulate_holders")
    def test_single_period(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = {
            "df": pd.DataFrame(
                {
                    "截止日期": ["2025-09-30"],
                    "股东名称": ["Alice"],
                    "持股数量": [1000],
                    "占流通股比例": [5.0],
                    "股本性质": ["自然人"],
                }
            )
        }

        fetcher = TopHoldersFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "holders_prev_date" not in result
        assert "holders_prev_map" not in result

    @patch("quant_lab.core.data.dimensions.top_holders.fetch_circulate_holders")
    def test_empty_df(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = {"df": pd.DataFrame()}

        fetcher = TopHoldersFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" in result
        assert result["_dimension"] == "top_holders"

    @patch("quant_lab.core.data.dimensions.top_holders.fetch_circulate_holders")
    def test_none_return(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = None

        fetcher = TopHoldersFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" in result
        assert result["_dimension"] == "top_holders"
