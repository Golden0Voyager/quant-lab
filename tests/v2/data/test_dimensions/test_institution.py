"""Tests for InstitutionFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.institution import InstitutionFetcher


class TestInstitutionFetcher:
    @patch("quant_lab.core.data.dimensions.institution.ak")
    def test_happy_path(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_report_fund_hold.return_value = pd.DataFrame(
            {
                "基金名称": ["富国天惠", "易方达蓝筹"],
                "持股数": [10000000, 5000000],
                "变动": [2000000, -1000000],
                "占流通股比": [2.5, 1.2],
            }
        )

        fetcher = InstitutionFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["fund_holding_count"] == 2
        assert len(result["top_funds"]) == 2
        assert result["fund_holding_pct"] == "3.70%"
        assert "富国天惠" in result["institution_summary"]

    @patch("quant_lab.core.data.dimensions.institution.ak")
    def test_empty_dataframe(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_report_fund_hold.return_value = pd.DataFrame()
        mock_ak.stock_circulate_stock_holder.return_value = pd.DataFrame()

        fetcher = InstitutionFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["institution_summary"] == "暂无机构持仓数据"

    @patch("quant_lab.core.data.dimensions.institution.ak")
    def test_exception(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_report_fund_hold.side_effect = Exception("API down")
        mock_ak.stock_circulate_stock_holder.side_effect = Exception("API down")

        fetcher = InstitutionFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" in result
        assert result["_dimension"] == "institution"

    @patch("quant_lab.core.data.dimensions.institution.ak")
    def test_sina_fallback(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_report_fund_hold.return_value = pd.DataFrame()
        mock_ak.stock_circulate_stock_holder.return_value = pd.DataFrame(
            {
                "截止日期": ["2025-09-30", "2025-09-30"],
                "股东名称": ["富国天惠基金", "张三"],
                "股本性质": ["境内法人", "自然人"],
                "占流通股比例": [2.5, 1.0],
            }
        )

        fetcher = InstitutionFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["fund_holding_count"] == 1
        assert result["top_funds"][0]["name"] == "富国天惠基金"
