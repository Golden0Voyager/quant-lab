"""Tests for quant_lab.core.data.aggregator."""

from __future__ import annotations

from typing import Any

import pytest

from quant_lab.core.data.aggregator import StockAggregator
from quant_lab.core.data.registry import DimensionRegistry


class TestStockAggregator:
    def test_aggregate_merges_dimensions(self) -> None:
        reg = DimensionRegistry()
        reg.register("valuation", _FakeFetcher("valuation", {"pe_ttm": "15.2"}))
        reg.register("performance", _FakeFetcher("performance", {"roe": "12.5%"}))

        agg = StockAggregator(reg)
        result = agg.aggregate("000001", "平安银行")

        assert result["code"] == "000001"
        assert result["name"] == "平安银行"
        assert result["pe_ttm"] == "15.2"
        assert result["roe"] == "12.5%"
        assert "timestamp" in result

    def test_aggregate_merges_error_keys(self) -> None:
        reg = DimensionRegistry()
        reg.register("ok", _FakeFetcher("ok", {"good": True}))
        reg.register("fail", _FakeFetcher("fail", {"_error": "boom"}))

        agg = StockAggregator(reg)
        result = agg.aggregate("000001", "平安银行")

        assert result["good"] is True
        assert "_error" in result  # error keys are merged like any other data

    def test_aggregate_with_asset_type(self) -> None:
        reg = DimensionRegistry()
        agg = StockAggregator(reg)
        result = agg.aggregate("000001", "平安银行", asset_type="etf")
        assert result["type"] == "etf"

    def test_calc_peg(self) -> None:
        reg = DimensionRegistry()
        reg.register(
            "consensus",
            _FakeFetcher(
                "consensus",
                {
                    "eps_forecast_current_raw": 2.0,
                    "eps_forecast_next_raw": 2.4,
                    "eps_growth_rate_raw": 20.0,
                },
            ),
        )
        reg.register(
            "valuation",
            _FakeFetcher("valuation", {"pe_ttm_raw": 20.0}),
        )

        agg = StockAggregator(reg)
        result = agg.aggregate("000001", "平安银行")

        # peg = 20.0 / 20.0 = 1.0
        assert result["peg_raw"] == pytest.approx(1.0)
        assert "合理" in result["peg_signal"]


class _FakeFetcher:
    def __init__(self, name: str, return_value: dict[str, Any]) -> None:
        self.name = name
        self._return_value = return_value

    def fetch(self, symbol: str, stock_name: str) -> dict[str, Any]:
        return self._return_value
