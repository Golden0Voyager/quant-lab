"""Parity test: ConsensusFetcher vs legacy fetch_consensus_data."""

from __future__ import annotations

import sys
from pathlib import Path

from quant_lab.core.data.dimensions.consensus import ConsensusFetcher
from tests.v2.data.parity._critical_keys import CRITICAL_KEYS, IGNORED_KEYS
from tests.v2.data.parity.conftest import load_fixture, mock_akshare
from tests.v2.data.parity.test_valuation_parity import _approx_equal

# Make legacy analyst_data importable
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import analyst_data  # type: ignore[import-not-found]  # noqa: E402


def test_consensus_parity_happy() -> None:
    fixture = load_fixture("consensus_000001")

    with mock_akshare(fixture):
        legacy_out = analyst_data.fetch_consensus_data("000001", "平安银行")

    with mock_akshare(fixture):
        v2_out = ConsensusFetcher().fetch("000001", "平安银行")

    legacy_keys = set(legacy_out.keys()) - IGNORED_KEYS
    v2_keys = set(v2_out.keys())
    missing = legacy_keys - v2_keys
    assert not missing, f"v2 missing: {missing}"

    for key in CRITICAL_KEYS["consensus"]:
        if key not in legacy_out and key not in v2_out:
            continue
        assert _approx_equal(v2_out.get(key), legacy_out.get(key)), (
            f"{key}: v2={v2_out.get(key)!r} vs legacy={legacy_out.get(key)!r}"
        )


def test_consensus_parity_no_coverage() -> None:
    fixture = {
        "stock_profit_forecast_ths": None,
        "stock_institute_recommend_detail": None,
    }

    with mock_akshare(fixture):
        legacy_out = analyst_data.fetch_consensus_data("000001", "平安银行")

    with mock_akshare(fixture):
        v2_out = ConsensusFetcher().fetch("000001", "平安银行")

    assert v2_out["consensus_summary"] == "暂无分析师覆盖"
    assert legacy_out.get("consensus_summary", "暂无分析师覆盖") == "暂无分析师覆盖"
