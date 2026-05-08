"""Tests for sources.eastmoney."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.sources.eastmoney import (
    fetch_eastmoney_kline,
    fetch_financial_report,
    fetch_stock_info_eastmoney,
)


@patch("quant_lab.core.data.sources.eastmoney.ak")
def test_financial_report_success(mock_ak: MagicMock) -> None:
    mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
        {"股票代码": ["000001"], "每股收益": ["2.5"]}
    )
    result = fetch_financial_report("000001")
    assert result is not None
    assert result["每股收益"] == "2.5"


@patch("quant_lab.core.data.sources.eastmoney.ak")
def test_financial_report_not_found(mock_ak: MagicMock) -> None:
    mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
        {"股票代码": ["999999"], "每股收益": ["1.0"]}
    )
    assert fetch_financial_report("000001") is None


@patch("quant_lab.core.data.sources.eastmoney.ak")
def test_financial_report_exception(mock_ak: MagicMock) -> None:
    mock_ak.stock_yjbb_em.side_effect = Exception("network error")
    assert fetch_financial_report("000001") is None


@patch("quant_lab.core.data.sources.eastmoney.ak")
def test_kline_success(mock_ak: MagicMock) -> None:
    mock_ak.stock_zh_a_hist.return_value = pd.DataFrame({"收盘": [25.0, 26.0]})
    result = fetch_eastmoney_kline("000001")
    assert result is not None
    assert result["收盘"] == 26.0


@patch("quant_lab.core.data.sources.eastmoney.ak")
def test_kline_empty(mock_ak: MagicMock) -> None:
    mock_ak.stock_zh_a_hist.return_value = pd.DataFrame()
    assert fetch_eastmoney_kline("000001") is None


@patch("quant_lab.core.data.sources.eastmoney.ak")
def test_stock_info_success(mock_ak: MagicMock) -> None:
    mock_ak.stock_individual_info_em.return_value = pd.DataFrame(
        {"item": ["总市值"], "value": ["1000"]}
    )
    result = fetch_stock_info_eastmoney("000001")
    assert result == {"总市值": "1000"}
