"""Valuation dimension fetcher."""

from __future__ import annotations

import logging
from typing import Any

from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.sources._utils import safe_float
from quant_lab.core.data.sources.baidu import fetch_valuation_percentile
from quant_lab.core.data.sources.eastmoney import (
    fetch_eastmoney_kline,
    fetch_financial_report,
    fetch_stock_info_eastmoney,
)
from quant_lab.core.data.sources.sina import fetch_sina_kline
from quant_lab.core.data.sources.xueqiu import fetch_xueqiu_spot

logger = logging.getLogger(__name__)


class ValuationFetcher:
    """Fetch PE, PB, PS, PCF and historical percentiles."""

    name = "valuation"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str) -> dict[str, Any]:
        """Return valuation data for *symbol*."""
        data: dict[str, Any] = {"valuation_data_date": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")}

        # --- 1. Current valuation (Xueqiu优先) ---
        xq_data = fetch_xueqiu_spot(symbol)
        if xq_data:
            data["pe_ttm_raw"] = safe_float(xq_data.get("市盈率(TTM)"))
            data["pb_raw"] = safe_float(xq_data.get("市净率"))
            data["dividend_yield_raw"] = safe_float(xq_data.get("股息率(TTM)"))
            cap = xq_data.get("总市值") or xq_data.get("资产净值/总市值")
            data["market_cap"] = safe_float(cap)
        else:
            # 降级: 业绩报表 + K线
            self._fallback_valuation(symbol, data)

        # --- 2. Historical percentiles ---
        pe_pcts = fetch_valuation_percentile(symbol, "市盈率(TTM)")
        if pe_pcts:
            data["pe_percentile"] = f"{pe_pcts.get('10y') or pe_pcts.get('5y') or 'N/A'}%"
            data["pe_percentiles"] = pe_pcts

        pb_pcts = fetch_valuation_percentile(symbol, "市净率")
        if pb_pcts:
            data["pb_percentile"] = f"{pb_pcts.get('10y') or pb_pcts.get('5y') or 'N/A'}%"
            data["pb_percentiles"] = pb_pcts

        # --- 3. Formatting ---
        data["pe_ttm"] = f"{data['pe_ttm_raw']:.2f}" if data.get("pe_ttm_raw") else "N/A"
        data["pb"] = f"{data['pb_raw']:.2f}" if data.get("pb_raw") else "N/A"
        data["dividend_yield"] = (
            f"{data.get('dividend_yield_raw'):.2f}%"
            if data.get("dividend_yield_raw")
            else "N/A"
        )
        data["market_cap_display"] = (
            f"{data['market_cap'] / 1e8:.0f}亿"
            if data.get("market_cap")
            else "N/A"
        )

        data["valuation_summary"] = (
            f"PE-TTM: {data['pe_ttm']} (分位:{data.get('pe_percentile', 'N/A')}) | "
            f"PB: {data['pb']} (分位:{data.get('pb_percentile', 'N/A')}) | "
            f"股息率: {data['dividend_yield']}"
        )

        return data

    def _fallback_valuation(self, symbol: str, data: dict[str, Any]) -> None:
        """Derive valuation from financial reports + latest price."""
        report = fetch_financial_report(symbol)
        eps = safe_float(report.get("每股收益")) if report else None
        bvps = safe_float(report.get("每股净资产")) if report else None

        # 获取最新价格（东财 -> 新浪）
        kline = fetch_eastmoney_kline(symbol)
        if kline is None:
            kline = fetch_sina_kline(symbol)
        price = safe_float(kline.get("收盘")) if kline else None

        if price:
            if eps and eps > 0:
                data["pe_ttm_raw"] = round(price / eps, 2)
            if bvps and bvps > 0:
                data["pb_raw"] = round(price / bvps, 2)

        info = fetch_stock_info_eastmoney(symbol)
        if info:
            data["market_cap"] = safe_float(info.get("总市值"))
