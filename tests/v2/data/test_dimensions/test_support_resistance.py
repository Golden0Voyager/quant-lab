"""Tests for SupportResistanceFetcher."""

from __future__ import annotations

from quant_lab.core.data.dimensions.support_resistance import (
    SupportResistanceFetcher,
)


class TestSupportResistanceFetcher:
    def test_happy_path(self) -> None:
        context = {
            "current_price": 100.0,
            "ma20": 95.0,
            "ma60": 90.0,
            "ma120": 85.0,
            "ma250": 80.0,
            "boll_upper": 110.0,
            "boll_lower": 90.0,
            "chip_avg_cost_raw": 98.0,
            "recent_20d_data": [
                {"high": 105.0, "low": 95.0},
                {"high": 108.0, "low": 92.0},
            ],
            "industry_name": "电子元器件",
        }

        fetcher = SupportResistanceFetcher()
        result = fetcher.fetch("000001", "平安银行", context=context)

        assert "_error" not in result
        # Levels: 95(MA20), 90(MA60), 85(MA120), 80(MA250), 110(BOLL上), 90(BOLL下), 98(套牢盘), 108(近期高), 92(近期低)
        # Resistance (>100.5): 110, 108
        # Sorted: 108, 110 → nearest = 108
        assert result["resistance_price"] == 108.0
        assert result["resistance_type"] == "近期高点"
        # Support (<99.5): 95, 90, 85, 80, 90, 98, 92
        # Sorted desc: 98, 95, 92, 90, 85, 80
        # Nearest = 98
        assert result["support_price"] == 98.0
        assert result["support_type"] == "套牢盘密集"
        assert result["fx_sensitivity"] == "人民币贬值受益"
        assert "上方压力位" in result["support_resistance_summary"]

    def test_no_price(self) -> None:
        fetcher = SupportResistanceFetcher()
        result = fetcher.fetch("000001", "平安银行", context={})

        assert "_error" not in result
        assert result["support_resistance_summary"] == "无当前价格，无法计算"

    def test_fx_appreciate_benefit(self) -> None:
        context = {
            "current_price": 100.0,
            "ma20": 105.0,
            "industry_name": "航空运输",
        }

        fetcher = SupportResistanceFetcher()
        result = fetcher.fetch("000001", "平安银行", context=context)

        assert result.get("fx_sensitivity") == "人民币升值受益"

    def test_no_context(self) -> None:
        """Without context the fetcher should gracefully handle missing data."""
        fetcher = SupportResistanceFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["support_resistance_summary"] == "无当前价格，无法计算"
