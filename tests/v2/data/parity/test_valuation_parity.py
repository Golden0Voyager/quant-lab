"""Parity test: ValuationFetcher vs legacy fetch_valuation_data."""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import pytest

from quant_lab.core.data.dimensions.valuation import ValuationFetcher
from tests.v2.data.parity._critical_keys import CRITICAL_KEYS, IGNORED_KEYS
from tests.v2.data.parity.conftest import load_fixture, mock_akshare

# Make legacy analyst_data importable
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import analyst_data  # type: ignore[import-not-found]  # noqa: E402


def _approx_equal(a: Any, b: Any) -> bool:
    if a is None and b is None:
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if math.isnan(a) and math.isnan(b):
            return True
        return a == pytest.approx(b, rel=1e-6, abs=1e-9)
    return a == b


def test_valuation_parity_happy() -> None:
    fixture = load_fixture("valuation_000001")

    with mock_akshare(fixture):
        legacy_out = analyst_data.fetch_valuation_data("000001", "平安银行")

    with mock_akshare(fixture):
        v2_out = ValuationFetcher().fetch("000001", "平安银行")

    legacy_keys = set(legacy_out.keys()) - IGNORED_KEYS
    v2_keys = set(v2_out.keys())
    missing = legacy_keys - v2_keys
    assert not missing, f"v2 missing keys present in legacy: {missing}"

    for key in CRITICAL_KEYS["valuation"]:
        if key not in legacy_out and key not in v2_out:
            continue
        assert _approx_equal(v2_out.get(key), legacy_out.get(key)), (
            f"Critical key {key} mismatch: "
            f"v2={v2_out.get(key)!r} vs legacy={legacy_out.get(key)!r}"
        )


def test_valuation_parity_fallback() -> None:
    """Both v2 and legacy should produce a dict (no _error) when all sources fail."""
    fixture = {
        "stock_individual_spot_xq": None,
        "stock_yjbb_em": None,
        "stock_zh_a_hist": None,
        "stock_zh_a_daily": None,
        "stock_individual_info_em": None,
        "stock_zh_valuation_baidu": None,
    }

    with mock_akshare(fixture):
        legacy_out = analyst_data.fetch_valuation_data("000001", "平安银行")

    with mock_akshare(fixture):
        v2_out = ValuationFetcher().fetch("000001", "平安银行")

    assert "_error" not in v2_out
    assert v2_out.get("pe_ttm") == "N/A"
    assert legacy_out.get("pe_ttm", "N/A") == "N/A"
