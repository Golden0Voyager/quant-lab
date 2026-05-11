"""Chip distribution dimension fetcher."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.sources._utils import no_proxy, safe_float

logger = logging.getLogger(__name__)


class ChipFetcher:
    """Fetch chip distribution data (profit ratio, avg cost, concentration)."""

    name = "chip"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str, **kwargs: Any) -> dict[str, Any]:
        """Return chip distribution data for *symbol*."""
        data: dict[str, Any] = {
            "chip_data_date": datetime.now().strftime("%Y-%m-%d")
        }

        # Strategy 1: ak.stock_cyq_em
        chip_fetched = False
        try:
            with no_proxy():
                chip_df = ak.stock_cyq_em(symbol=symbol, adjust="")
            if chip_df is not None and not chip_df.empty:
                latest = chip_df.iloc[-1]
                profit_ratio: float | None = None
                for col in chip_df.columns:
                    if "获利" in str(col) and "比例" in str(col):
                        profit_ratio = safe_float(latest.get(col))
                        if profit_ratio is not None:
                            data["chip_profit_ratio"] = f"{profit_ratio:.1f}%"
                            data["chip_profit_ratio_raw"] = profit_ratio
                            break

                avg_cost: float | None = None
                for col in chip_df.columns:
                    if "平均" in str(col) and "成本" in str(col):
                        avg_cost = safe_float(latest.get(col))
                        if avg_cost is not None:
                            data["chip_avg_cost"] = f"{avg_cost:.2f}"
                            data["chip_avg_cost_raw"] = avg_cost
                            break

                for col in chip_df.columns:
                    if "90" in str(col) and ("集中" in str(col) or "成本" in str(col)):
                        val = latest.get(col)
                        if val is not None:
                            data["chip_concentration_90"] = str(val)
                    elif "70" in str(col) and ("集中" in str(col) or "成本" in str(col)):
                        val = latest.get(col)
                        if val is not None:
                            data["chip_concentration_70"] = str(val)

                if profit_ratio is not None:
                    if profit_ratio > 80:
                        data["chip_signal"] = "获利盘过多，注意回调风险"
                    elif profit_ratio > 50:
                        data["chip_signal"] = "筹码偏集中，支撑较强"
                    elif profit_ratio < 20:
                        data["chip_signal"] = "套牢盘较重，下方有支撑"
                    else:
                        data["chip_signal"] = "筹码分布均衡"
                    chip_fetched = True
        except Exception:
            pass

        # Strategy 2: datacenter fallback
        if not chip_fetched:
            try:
                dc_data = self._fetch_from_datacenter(symbol)
                if dc_data and dc_data.get("avg_cost"):
                    avg_cost = float(dc_data["avg_cost"])
                    current_price = safe_float(dc_data.get("current_price")) or 0
                    data["chip_avg_cost"] = f"{avg_cost:.2f}"
                    data["chip_avg_cost_raw"] = avg_cost

                    if current_price and avg_cost:
                        price_vs_cost = (current_price - avg_cost) / avg_cost * 100
                        if price_vs_cost > 10:
                            data["chip_signal"] = f"价格高于主力成本{price_vs_cost:.1f}%"
                            data["chip_profit_ratio"] = f">{60 + min(price_vs_cost, 30):.0f}%"
                        elif price_vs_cost > 0:
                            data["chip_signal"] = f"略高于主力成本{price_vs_cost:.1f}%"
                            data["chip_profit_ratio"] = f"~{50 + price_vs_cost:.0f}%"
                        elif price_vs_cost > -10:
                            data["chip_signal"] = "接近主力成本"
                            data["chip_profit_ratio"] = f"~{50 + price_vs_cost:.0f}%"
                        else:
                            data["chip_signal"] = f"价格低于主力成本{-price_vs_cost:.1f}%"
                            data["chip_profit_ratio"] = f"<{40 + price_vs_cost:.0f}%"

                    if dc_data.get("avg_cost_20d") and dc_data.get("avg_cost_60d"):
                        data["chip_concentration_70"] = f"20日成本:{float(dc_data['avg_cost_20d']):.2f}"
                        data["chip_concentration_90"] = f"60日成本:{float(dc_data['avg_cost_60d']):.2f}"

                    chip_fetched = True
            except Exception:
                pass

        if not chip_fetched:
            data["chip_signal"] = "数据暂不可用"

        parts: list[str] = []
        if data.get("chip_profit_ratio"):
            parts.append(f"获利{data['chip_profit_ratio']}")
        if data.get("chip_avg_cost"):
            parts.append(f"均价{data['chip_avg_cost']}")
        if data.get("chip_signal") and data["chip_signal"] not in ("N/A", "数据暂不可用"):
            parts.append(data["chip_signal"])

        data["chip_summary"] = " | ".join(parts) if parts else "筹码数据不可用"

        return data

    def _fetch_from_datacenter(self, symbol: str) -> dict[str, Any] | None:
        """Fetch chip data from Eastmoney datacenter API (fallback)."""
        try:
            import requests  # type: ignore[import-untyped]

            url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
            params = {
                "reportName": "RPT_DMSK_TS_STOCKNEW",
                "columns": "ALL",
                "filter": f'(SECURITY_CODE="{symbol}")',
                "pageNumber": 1,
                "pageSize": 1,
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json",
            }
            session = requests.Session()
            response = session.get(url, params=params, headers=headers, timeout=15)

            if response.status_code == 200:
                resp_data = response.json()
                if resp_data.get("result") and resp_data["result"].get("data"):
                    item = resp_data["result"]["data"][0]
                    return {
                        "avg_cost": item.get("PRIME_COST"),
                        "avg_cost_20d": item.get("PRIME_COST_20DAYS"),
                        "avg_cost_60d": item.get("PRIME_COST_60DAYS"),
                        "current_price": item.get("CLOSE_PRICE"),
                        "turnover_rate": item.get("TURNOVERRATE"),
                    }
        except Exception:
            pass
        return None
