"""Tests for sources.tencent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.sources.tencent import fetch_tencent_kline


@patch("quant_lab.core.data.sources.tencent.ak")
def test_kline_sh_symbol(mock_ak: MagicMock) -> None:
    mock_ak.stock_zh_a_hist_tx.return_value = pd.DataFrame(
        {"close": [25.0]}
    )
    fetch_tencent_kline("600519")
    assert mock_ak.stock_zh_a_hist_tx.call_args.kwargs["symbol"] == "sh600519"


@patch("quant_lab.core.data.sources.tencent.ak")
def test_kline_sz_symbol(mock_ak: MagicMock) -> None:
    mock_ak.stock_zh_a_hist_tx.return_value = pd.DataFrame(
        {"close": [10.0]}
    )
    fetch_tencent_kline("000001")
    assert mock_ak.stock_zh_a_hist_tx.call_args.kwargs["symbol"] == "sz000001"


@patch("quant_lab.core.data.sources.tencent.ak")
def test_kline_renamed_columns(mock_ak: MagicMock) -> None:
    mock_ak.stock_zh_a_hist_tx.return_value = pd.DataFrame(
        {
            "close": [25.0],
            "open": [24.0],
            "high": [26.0],
            "low": [23.0],
            "volume": [1000],
            "amount": [50000],
        }
    )
    result = fetch_tencent_kline("600519")
    assert result is not None
    assert result["收盘"] == 25.0
    assert result["开盘"] == 24.0
    assert result["最高"] == 26.0
    assert result["最低"] == 23.0
    assert result["成交额"] == 50000


@patch("quant_lab.core.data.sources.tencent.ak")
def test_kline_empty(mock_ak: MagicMock) -> None:
    mock_ak.stock_zh_a_hist_tx.return_value = pd.DataFrame()
    assert fetch_tencent_kline("000001") is None


@patch("quant_lab.core.data.sources.tencent.ak")
def test_kline_exception(mock_ak: MagicMock) -> None:
    mock_ak.stock_zh_a_hist_tx.side_effect = Exception("timeout")
    assert fetch_tencent_kline("000001") is None
