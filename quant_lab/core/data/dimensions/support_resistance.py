"""Support / resistance dimension fetcher (pure computation)."""

from __future__ import annotations

import logging
from typing import Any

from quant_lab.core.data.dimensions.base import safe_fetch

logger = logging.getLogger(__name__)

_FX_DEVALUE_BENEFIT = {
    "电子",
    "家用电器",
    "纺织服饰",
    "轻工制造",
    "钢铁",
    "机械设备",
    "化工",
    "有色金属",
}
_FX_APPRECIATE_BENEFIT = {"交通运输", "造纸", "航空", "航空运输"}


class SupportResistanceFetcher:
    """Compute support / resistance levels from upstream context."""

    name = "support_resistance"

    @safe_fetch
    def fetch(
        self, symbol: str, stock_name: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Return support / resistance levels and FX sensitivity."""
        context: dict[str, Any] = kwargs.get("context") or {}
        data: dict[str, Any] = {}

        price = context.get("current_price")
        if not price:
            data["support_resistance_summary"] = "无当前价格，无法计算"
            return data

        # Collect candidate levels
        levels: list[tuple[float, str]] = []

        for name, key in [
            ("MA20", "ma20"),
            ("MA60", "ma60"),
            ("MA120", "ma120"),
            ("MA250", "ma250"),
        ]:
            val = context.get(key)
            if val:
                levels.append((float(val), name))

        boll_upper = context.get("boll_upper")
        boll_lower = context.get("boll_lower")
        if boll_upper:
            levels.append((float(boll_upper), "BOLL上轨"))
        if boll_lower:
            levels.append((float(boll_lower), "BOLL下轨"))

        chip_avg = context.get("chip_avg_cost_raw")
        if chip_avg:
            levels.append((float(chip_avg), "套牢盘密集"))

        recent_data = context.get("recent_20d_data", [])
        if recent_data:
            highs = [
                float(d["high"]) for d in recent_data if d.get("high") is not None
            ]
            lows = [
                float(d["low"]) for d in recent_data if d.get("low") is not None
            ]
            if highs:
                levels.append((max(highs), "近期高点"))
            if lows:
                levels.append((min(lows), "近期低点"))

        price_f = float(price)
        resistance = [(v, n) for v, n in levels if v > price_f * 1.005]
        support = [(v, n) for v, n in levels if v < price_f * 0.995]

        if resistance:
            resistance.sort(key=lambda x: x[0])
            data["resistance_price"] = round(resistance[0][0], 2)
            data["resistance_type"] = resistance[0][1]

        if support:
            support.sort(key=lambda x: x[0], reverse=True)
            data["support_price"] = round(support[0][0], 2)
            data["support_type"] = support[0][1]

        # FX sensitivity
        industry = context.get("industry_name") or context.get("sector_name") or ""
        if industry:
            for kw in _FX_DEVALUE_BENEFIT:
                if kw in industry:
                    data["fx_sensitivity"] = "人民币贬值受益"
                    break
            if "fx_sensitivity" not in data:
                for kw in _FX_APPRECIATE_BENEFIT:
                    if kw in industry:
                        data["fx_sensitivity"] = "人民币升值受益"
                        break

        parts: list[str] = []
        if data.get("resistance_price"):
            parts.append(
                f"上方压力位：{data['resistance_price']:.2f}元 ({data['resistance_type']})"
            )
        if data.get("support_price"):
            parts.append(
                f"下方支撑：{data['support_price']:.2f}元 ({data['support_type']})"
            )
        if data.get("fx_sensitivity"):
            parts.append(data["fx_sensitivity"])

        data["support_resistance_summary"] = (
            " | ".join(parts) if parts else "暂无支撑压力数据"
        )

        return data
