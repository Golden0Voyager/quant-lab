"""Self-test for the mock_akshare context manager."""

from __future__ import annotations

import akshare as ak  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]
import pytest

from tests.v2.data.parity.conftest import mock_akshare


def test_mock_dataframe_return() -> None:
    fixture = {
        "stock_yjbb_em": {
            "_columns": ["股票代码", "每股收益"],
            "_rows": [["000001", "2.5"]],
        }
    }
    with mock_akshare(fixture):
        df = ak.stock_yjbb_em(date="20251231")
    assert isinstance(df, pd.DataFrame)
    assert df.iloc[0]["股票代码"] == "000001"
    assert df.iloc[0]["每股收益"] == "2.5"


def test_mock_none_raises() -> None:
    fixture = {"stock_yjbb_em": None}
    with (
        mock_akshare(fixture),
        pytest.raises(Exception, match="mocked: stock_yjbb_em"),
    ):
        ak.stock_yjbb_em(date="20251231")


def test_mock_unpatch_after_context() -> None:
    fixture = {"stock_yjbb_em": None}
    original = ak.stock_yjbb_em
    with mock_akshare(fixture):
        pass
    assert ak.stock_yjbb_em is original


def test_mock_skips_unknown_function() -> None:
    fixture = {"definitely_not_a_real_akshare_function": None}
    with mock_akshare(fixture):
        pass
