"""Consensus dimension fetcher (analyst forecasts + ratings)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.sources._utils import safe_float

logger = logging.getLogger(__name__)


class ConsensusFetcher:
    """Fetch analyst consensus: EPS forecasts, ratings, target prices."""

    name = "consensus"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str) -> dict[str, Any]:
        """Return consensus data for *symbol*."""
        data: dict[str, Any] = {
            "consensus_data_date": datetime.now().strftime("%Y-%m-%d")
        }

        # 1. Profit forecast (同花顺)
        try:
            forecast_df = ak.stock_profit_forecast_ths(symbol=symbol)
            if forecast_df is not None and not forecast_df.empty:
                if len(forecast_df) >= 2:
                    data["eps_forecast_current"] = f"{forecast_df.iloc[0]['均值']:.2f}"
                    data["eps_forecast_current_raw"] = float(forecast_df.iloc[0]["均值"])
                    data["eps_forecast_next"] = f"{forecast_df.iloc[1]['均值']:.2f}"
                    data["eps_forecast_next_raw"] = float(forecast_df.iloc[1]["均值"])
                elif len(forecast_df) == 1:
                    data["eps_forecast_current"] = f"{forecast_df.iloc[0]['均值']:.2f}"
                    data["eps_forecast_current_raw"] = float(forecast_df.iloc[0]["均值"])
        except Exception as exc:  # noqa: BLE001
            logger.debug("Profit forecast failed for %s: %s", symbol, exc)

        # 2. Institution ratings
        try:
            recommend_df = ak.stock_institute_recommend_detail(symbol=symbol)
            if recommend_df is not None and not recommend_df.empty:
                recent = recommend_df.head(20)

                # Date column
                date_col = next(
                    (c for c in recent.columns if "日期" in c or "date" in c.lower()),
                    None,
                )
                if date_col and recent[date_col].iloc[0]:
                    data["consensus_data_date"] = str(recent[date_col].iloc[0])[:10]

                # Target prices
                target_prices: list[float] = []
                for col in recent.columns:
                    if "目标价" in col:
                        for _, r in recent.iterrows():
                            tp = safe_float(r.get(col))
                            if tp and tp > 0:
                                target_prices.append(tp)
                if target_prices:
                    data["target_price_avg"] = f"{sum(target_prices) / len(target_prices):.2f}"
                    data["target_price_high"] = f"{max(target_prices):.2f}"
                    data["target_price_low"] = f"{min(target_prices):.2f}"

                # Rating distribution
                rating_col = next(
                    (
                        c
                        for c in recent.columns
                        if "评级" in c and "日期" not in c and "机构" not in c
                    ),
                    None,
                )
                if rating_col:
                    ratings = recent[rating_col].value_counts()
                    data["rating_buy"] = int(ratings.get("买入", 0))
                    data["rating_overweight"] = int(ratings.get("增持", 0))
                    data["rating_hold"] = int(
                        ratings.get("中性", 0) + ratings.get("持有", 0)
                    )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Institution ratings failed for %s: %s", symbol, exc)

        # 3. EPS growth & PEG signal
        eps_current = data.get("eps_forecast_current_raw")
        eps_next = data.get("eps_forecast_next_raw")
        if eps_current and eps_next and eps_current > 0:
            growth_rate = (eps_next / eps_current - 1) * 100
            data["eps_growth_rate_raw"] = round(growth_rate, 2)
            data["eps_growth_rate"] = f"{growth_rate:.2f}%"
            data["peg_signal"] = (
                f"预期EPS增速{growth_rate:.1f}%"
                if growth_rate > 0
                else f"预期EPS下降{growth_rate:.1f}%"
            )

        # 4. Summary
        parts: list[str] = []
        if data.get("rating_buy") or data.get("rating_overweight"):
            buy = data.get("rating_buy", 0)
            overweight = data.get("rating_overweight", 0)
            hold = data.get("rating_hold", 0)
            parts.append(f"评级: 买入{buy}/增持{overweight}/持有{hold}")
        if data.get("target_price_avg"):
            parts.append(f"均价目标: {data['target_price_avg']}元")
        if data.get("eps_growth_rate"):
            parts.append(f"预期EPS增速: {data['eps_growth_rate']}")

        data["consensus_summary"] = " | ".join(parts) if parts else "暂无分析师覆盖"

        return data
