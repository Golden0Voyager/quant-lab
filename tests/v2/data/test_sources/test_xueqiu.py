"""Tests for sources.xueqiu."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.sources.xueqiu import fetch_xueqiu_spot


@patch.dict("os.environ", {"XUEQIU_TOKEN": "fake-token"})
@patch("quant_lab.core.data.sources.xueqiu.ak")
def test_spot_success(mock_ak: MagicMock) -> None:
    mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
        {"item": ["市盈率(TTM)"], "value": ["15.5"]}
    )
    result = fetch_xueqiu_spot("000001")
    assert result == {"市盈率(TTM)": "15.5"}


@patch.dict("os.environ", {}, clear=True)
def test_spot_no_token() -> None:
    assert fetch_xueqiu_spot("000001", token=None) is None


@patch.dict("os.environ", {"XUEQIU_TOKEN": "fake-token"})
@patch("quant_lab.core.data.sources.xueqiu.ak")
def test_spot_empty_df(mock_ak: MagicMock) -> None:
    mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame()
    assert fetch_xueqiu_spot("000001") is None


@patch.dict("os.environ", {"XUEQIU_TOKEN": "fake-token"})
@patch("quant_lab.core.data.sources.xueqiu.ak")
def test_spot_sh_symbol(mock_ak: MagicMock) -> None:
    mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
        {"item": ["市净率"], "value": ["1.2"]}
    )
    fetch_xueqiu_spot("600519")
    assert mock_ak.stock_individual_spot_xq.call_args.kwargs["symbol"] == "SH600519"


@patch.dict("os.environ", {"XUEQIU_TOKEN": "fake-token"})
@patch("quant_lab.core.data.sources.xueqiu.ak")
def test_spot_exception(mock_ak: MagicMock) -> None:
    mock_ak.stock_individual_spot_xq.side_effect = Exception("auth fail")
    assert fetch_xueqiu_spot("000001") is None
