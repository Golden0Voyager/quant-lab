"""Parity test: SentimentFetcher vs legacy fetch_sentiment_data."""

from __future__ import annotations

import sys
from pathlib import Path

from quant_lab.core.data.dimensions.sentiment import SentimentFetcher
from tests.v2.data.parity._critical_keys import CRITICAL_KEYS, IGNORED_KEYS
from tests.v2.data.parity.conftest import load_fixture, mock_akshare
from tests.v2.data.parity.test_valuation_parity import _approx_equal

# Make legacy analyst_data importable
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import analyst_data  # type: ignore[import-not-found]  # noqa: E402


def test_sentiment_parity_happy() -> None:
    fixture = load_fixture("sentiment_000001")

    with mock_akshare(fixture):
        legacy_out = analyst_data.fetch_sentiment_data("000001", "平安银行")

    with mock_akshare(fixture):
        v2_out = SentimentFetcher().fetch("000001", "平安银行")

    legacy_keys = set(legacy_out.keys()) - IGNORED_KEYS
    v2_keys = set(v2_out.keys())
    missing = legacy_keys - v2_keys
    assert not missing, f"v2 missing: {missing}"

    for key in CRITICAL_KEYS["sentiment"]:
        if key not in legacy_out and key not in v2_out:
            continue
        assert _approx_equal(v2_out.get(key), legacy_out.get(key)), (
            f"{key}: v2={v2_out.get(key)!r} vs legacy={legacy_out.get(key)!r}"
        )


def test_sentiment_parity_fallback() -> None:
    fixture = {
        "stock_individual_spot_xq": None,
        "stock_individual_info_em": None,
        "stock_hsgt_individual_em": None,
    }

    with mock_akshare(fixture):
        legacy_out = analyst_data.fetch_sentiment_data("000001", "平安银行")

    with mock_akshare(fixture):
        v2_out = SentimentFetcher().fetch("000001", "平安银行")

    assert "sentiment_summary" in legacy_out or "_error" in legacy_out
    assert "sentiment_summary" in v2_out or "_error" in v2_out
