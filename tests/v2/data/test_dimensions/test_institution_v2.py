"""Extended tests for InstitutionFetcher — covering uncovered branches."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.institution import InstitutionFetcher


class TestInstitutionFetcherV2:
    @patch("quant_lab.core.data.dimensions.institution.get_report_date")
    @patch("quant_lab.core.data.dimensions.institution.ak")
    def test_quarter_0630(self, mock_ak: MagicMock, mock_report_date: MagicMock) -> None:
        """Quarter ending 0630 → 中报 (line 29)."""
        mock_report_date.return_value = "20250630"
        mock_ak.stock_report_fund_hold.return_value = pd.DataFrame(
            {
                "基金名称": ["基金A"],
                "持股数": [1000000],
                "占流通股比": [1.0],
            }
        )

        fetcher = InstitutionFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert "中报" in result["institution_data_date"]

    @patch("quant_lab.core.data.dimensions.institution.get_report_date")
    @patch("quant_lab.core.data.dimensions.institution.ak")
    def test_quarter_0331(self, mock_ak: MagicMock, mock_report_date: MagicMock) -> None:
        """Quarter ending 0331 → 一季报 (line 31)."""
        mock_report_date.return_value = "20250331"
        mock_ak.stock_report_fund_hold.return_value = pd.DataFrame(
            {
                "基金名称": ["基金A"],
                "持股数": [1000000],
                "占流通股比": [1.0],
            }
        )

        fetcher = InstitutionFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert "一季报" in result["institution_data_date"]

    @patch("quant_lab.core.data.dimensions.institution.get_report_date")
    @patch("quant_lab.core.data.dimensions.institution.ak")
    def test_quarter_1231(self, mock_ak: MagicMock, mock_report_date: MagicMock) -> None:
        """Quarter ending 1231 → 年报 (line 33)."""
        mock_report_date.return_value = "20241231"
        mock_ak.stock_report_fund_hold.return_value = pd.DataFrame(
            {
                "基金名称": ["基金A"],
                "持股数": [1000000],
                "占流通股比": [1.0],
            }
        )

        fetcher = InstitutionFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert "年报" in result["institution_data_date"]

    @patch("quant_lab.core.data.dimensions.institution.get_report_date")
    @patch("quant_lab.core.data.dimensions.institution.ak")
    def test_sina_fallback_exception(self, mock_ak: MagicMock, mock_report_date: MagicMock) -> None:
        """Sina fallback exception (lines 108-109)."""
        mock_report_date.return_value = "20250930"
        mock_ak.stock_report_fund_hold.return_value = pd.DataFrame()
        mock_ak.stock_circulate_stock_holder.side_effect = Exception("sina fail")

        fetcher = InstitutionFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.institution.get_report_date")
    @patch("quant_lab.core.data.dimensions.institution.ak")
    def test_cross_quarter_0630(self, mock_ak: MagicMock, mock_report_date: MagicMock) -> None:
        """Cross-quarter comparison with 0630 → prev 0331 (line 117)."""
        mock_report_date.return_value = "20250630"
        mock_ak.stock_report_fund_hold.side_effect = [
            pd.DataFrame(
                {
                    "基金名称": ["基金A"],
                    "持股数": [1000000],
                    "占流通股比": [1.0],
                }
            ),
            pd.DataFrame(
                {
                    "基金名称": ["基金B"],
                    "持股数": [800000],
                    "占流通股比": [0.8],
                }
            ),
        ]

        fetcher = InstitutionFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result.get("fund_holding_count_prev") == 1
        assert result.get("fund_holding_change") is not None

    @patch("quant_lab.core.data.dimensions.institution.get_report_date")
    @patch("quant_lab.core.data.dimensions.institution.ak")
    def test_cross_quarter_0331(self, mock_ak: MagicMock, mock_report_date: MagicMock) -> None:
        """Cross-quarter comparison with 0331 → prev year 1231 (line 119)."""
        mock_report_date.return_value = "20250331"
        mock_ak.stock_report_fund_hold.side_effect = [
            pd.DataFrame(
                {
                    "基金名称": ["基金A"],
                    "持股数": [1000000],
                    "占流通股比": [1.0],
                }
            ),
            pd.DataFrame(
                {
                    "基金名称": ["基金B", "基金C"],
                    "持股数": [800000, 600000],
                    "占流通股比": [0.8, 0.6],
                }
            ),
        ]

        fetcher = InstitutionFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result.get("fund_holding_count_prev") == 2
        assert result.get("fund_holding_change") == "-1"

    @patch("quant_lab.core.data.dimensions.institution.get_report_date")
    @patch("quant_lab.core.data.dimensions.institution.ak")
    def test_cross_quarter_1231(self, mock_ak: MagicMock, mock_report_date: MagicMock) -> None:
        """Cross-quarter comparison with 1231 → prev 0930 (line 121)."""
        mock_report_date.return_value = "20241231"
        mock_ak.stock_report_fund_hold.side_effect = [
            pd.DataFrame(
                {
                    "基金名称": ["基金A"],
                    "持股数": [1000000],
                    "占流通股比": [1.0],
                }
            ),
            pd.DataFrame(
                {
                    "基金名称": ["基金B"],
                    "持股数": [800000],
                    "占流通股比": [0.8],
                }
            ),
        ]

        fetcher = InstitutionFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result.get("fund_holding_count_prev") == 1

    @patch("quant_lab.core.data.dimensions.institution.get_report_date")
    @patch("quant_lab.core.data.dimensions.institution.ak")
    def test_cross_quarter_exception(self, mock_ak: MagicMock, mock_report_date: MagicMock) -> None:
        """Cross-quarter comparison exception (lines 129-130)."""
        mock_report_date.return_value = "20250930"
        mock_ak.stock_report_fund_hold.side_effect = [
            pd.DataFrame(
                {
                    "基金名称": ["基金A"],
                    "持股数": [1000000],
                    "占流通股比": [1.0],
                }
            ),
            Exception("cross-quarter fail"),
        ]

        fetcher = InstitutionFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["fund_holding_count"] == 1
