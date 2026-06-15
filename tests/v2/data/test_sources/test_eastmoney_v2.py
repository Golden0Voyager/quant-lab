"""Extended tests for eastmoney sources — covering uncovered branches."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.sources.eastmoney import (
    fetch_financial_report,
    fetch_stock_info_eastmoney,
    fetch_profit_sheet,
)


class TestFinancialReportMonthBranches:
    """Cover all month branches in fetch_financial_report (lines 25-31)."""

    @patch("quant_lab.core.data.sources.eastmoney.ak")
    def test_october_month(self, mock_ak: MagicMock) -> None:
        """Line 25: month >= 10 → report_date ends with 0930."""
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
            {"股票代码": ["000001"], "每股收益": ["2.5"]}
        )
        with patch("quant_lab.core.data.sources.eastmoney.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 10, 15)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = fetch_financial_report("000001")
            assert result is not None

    @patch("quant_lab.core.data.sources.eastmoney.ak")
    def test_july_month(self, mock_ak: MagicMock) -> None:
        """Line 27: month >= 7 → report_date ends with 0630."""
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
            {"股票代码": ["000001"], "每股收益": ["2.5"]}
        )
        with patch("quant_lab.core.data.sources.eastmoney.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 7, 15)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = fetch_financial_report("000001")
            assert result is not None

    @patch("quant_lab.core.data.sources.eastmoney.ak")
    def test_april_month(self, mock_ak: MagicMock) -> None:
        """Line 29: month >= 4 → report_date ends with 0331."""
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
            {"股票代码": ["000001"], "每股收益": ["2.5"]}
        )
        with patch("quant_lab.core.data.sources.eastmoney.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 4, 15)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = fetch_financial_report("000001")
            assert result is not None

    @patch("quant_lab.core.data.sources.eastmoney.ak")
    def test_january_month(self, mock_ak: MagicMock) -> None:
        """Line 31: month < 4 → report_date uses prev year 1231."""
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
            {"股票代码": ["000001"], "每股收益": ["2.5"]}
        )
        with patch("quant_lab.core.data.sources.eastmoney.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = fetch_financial_report("000001")
            assert result is not None


class TestStockInfoEastmoney:
    """Cover empty df (line 81)."""

    @patch("quant_lab.core.data.sources.eastmoney.ak")
    def test_empty_df(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_individual_info_em.return_value = pd.DataFrame()
        result = fetch_stock_info_eastmoney("000001")
        assert result is None


class TestProfitSheet:
    """Cover empty df (line 98)."""

    @patch("quant_lab.core.data.sources.eastmoney.ak")
    def test_empty_df(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_profit_sheet_by_report_em.return_value = pd.DataFrame()
        result = fetch_profit_sheet("000001")
        assert result is None
