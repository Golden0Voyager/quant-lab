"""Sentiment dimension fetcher."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.sources._utils import no_proxy, safe_float
from quant_lab.core.data.sources.eastmoney import fetch_stock_info_eastmoney
from quant_lab.core.data.sources.xueqiu import fetch_xueqiu_spot

logger = logging.getLogger(__name__)


class SentimentFetcher:
    """Fetch volume ratio, turnover rate and north-bound flow data."""

    name = "sentiment"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str) -> dict[str, Any]:
        """Return sentiment data for *symbol*."""
        data: dict[str, Any] = {
            "sentiment_data_date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

        # 1. Real-time spot (Xueqiu优先)
        spot = fetch_xueqiu_spot(symbol)
        if spot:
            vr = safe_float(spot.get("量比"))
            tr = safe_float(spot.get("周转率") or spot.get("换手率"))
            data["volume_ratio"] = f"{vr:.2f}" if vr else "N/A"
            data["turnover_rate"] = f"{tr:.2f}%" if tr else "N/A"
            if vr:
                data["volume_alert"] = (
                    "⚠️ 放量" if vr > 2.0 else ("缩量" if vr < 0.5 else "正常")
                )
        else:
            # 降级: 东财基础信息
            info = fetch_stock_info_eastmoney(symbol)
            if info:
                tr = safe_float(info.get("换手率"))
                data["turnover_rate"] = f"{tr:.2f}%" if tr else "N/A"

        # 2. North-bound flow (3-day)
        try:
            with no_proxy():
                north_df = ak.stock_hsgt_individual_em(symbol=symbol)
            if north_df is not None and not north_df.empty:
                recent = north_df.tail(5)
                if len(recent) >= 2:
                    latest = safe_float(recent.iloc[-1].get("持股数量"))
                    prev = safe_float(recent.iloc[0].get("持股数量"))
                    if latest and prev:
                        diff = latest - prev
                        status = "增持" if diff > 0 else "减持"
                        data["north_flow_3d"] = f"{status} {abs(diff) / 1e4:.0f}万股"
        except Exception as exc:  # noqa: BLE001
            logger.debug("North-bound flow failed for %s: %s", symbol, exc)

        data["sentiment_summary"] = (
            f"量比: {data.get('volume_ratio', 'N/A')} | "
            f"换手: {data.get('turnover_rate', 'N/A')} | "
            f"北向: {data.get('north_flow_3d', 'N/A')}"
        )

        return data
