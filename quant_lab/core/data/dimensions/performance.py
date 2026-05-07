"""Performance dimension fetcher."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import akshare as ak  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.sources._utils import no_proxy

logger = logging.getLogger(__name__)

# Module-level cache for financial reports (shared across symbols).
_yjbb_cache: dict[str, Any] = {}


def _get_report_date() -> str:
    """Return the most recently available report date string (YYYYMMDD)."""
    now = datetime.now()
    year, month = now.year, now.month
    if month >= 11:
        return f"{year}0930"
    elif month >= 8:
        return f"{year}0630"
    elif month >= 5:
        return f"{year}0331"
    return f"{year - 1}0930"


class PerformanceFetcher:
    """Fetch revenue, profit, ROE, margins and quarterly trends."""

    name = "performance"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str) -> dict[str, Any]:
        """Return performance data for *symbol*."""
        data: dict[str, Any] = {}
        report_date = _get_report_date()

        # Fetch or reuse cached report DataFrame
        if report_date not in _yjbb_cache:
            with no_proxy():
                _yjbb_cache[report_date] = ak.stock_yjbb_em(date=report_date)

        yjbb_df = _yjbb_cache[report_date]
        if yjbb_df is None or yjbb_df.empty:
            raise ValueError(f"业绩报表为空 (date={report_date})")

        stock_row = yjbb_df[yjbb_df["股票代码"] == symbol]
        if stock_row.empty:
            raise ValueError(f"业绩报表中未找到 {symbol}")

        row = stock_row.iloc[0]

        # Extract raw metrics
        revenue_yoy = row.get("营业总收入-同比增长")
        revenue_qoq = row.get("营业总收入-季度环比增长")
        profit_yoy = row.get("净利润-同比增长")
        profit_qoq = row.get("净利润-季度环比增长")
        gross_margin = row.get("销售毛利率")
        roe = row.get("净资产收益率")
        cf_per_share = row.get("每股经营现金流量")
        eps = row.get("每股收益")
        revenue_cumulative = row.get("营业总收入-营业总收入")

        # Calculate TTM revenue for PS calculation
        if pd.notna(revenue_cumulative) and revenue_cumulative > 0:
            if report_date.endswith("0930"):
                revenue_ttm = revenue_cumulative * (4 / 3)
            elif report_date.endswith("0630"):
                revenue_ttm = revenue_cumulative * 2
            elif report_date.endswith("0331"):
                revenue_ttm = revenue_cumulative * 4
            else:
                revenue_ttm = revenue_cumulative
            data["revenue_ttm_raw"] = revenue_ttm
            data["revenue_ttm_display"] = f"{revenue_ttm / 1e8:.2f}亿"
        else:
            data["revenue_ttm_raw"] = None
            data["revenue_ttm_display"] = "N/A"

        # Formatting
        data["revenue_yoy"] = f"{revenue_yoy:.2f}%" if pd.notna(revenue_yoy) else "N/A"
        data["revenue_qoq"] = f"{revenue_qoq:.2f}%" if pd.notna(revenue_qoq) else "N/A"
        data["profit_yoy"] = f"{profit_yoy:.2f}%" if pd.notna(profit_yoy) else "N/A"
        data["profit_qoq"] = f"{profit_qoq:.2f}%" if pd.notna(profit_qoq) else "N/A"
        data["gross_margin"] = f"{gross_margin:.2f}%" if pd.notna(gross_margin) else "N/A"
        data["net_margin"] = "N/A"
        data["roe"] = f"{roe:.2f}%" if pd.notna(roe) else "N/A"
        data["eps"] = f"{eps:.2f}" if pd.notna(eps) else "N/A"

        # Cash-flow quality
        if pd.notna(cf_per_share) and pd.notna(eps) and eps != 0:
            cf_ratio = cf_per_share / eps
            data["cf_profit_ratio"] = f"{cf_ratio:.2f}"
            if cf_ratio < 0.8:
                data["cf_quality"] = "⚠️ 利润含金量较低"
            elif cf_ratio > 1.2:
                data["cf_quality"] = "✅ 优质现金流"
            else:
                data["cf_quality"] = "正常水平"
        else:
            data["cf_profit_ratio"] = "N/A"
            data["cf_quality"] = "数据不足"

        data["performance_summary"] = (
            f"营收增长(YoY): {data['revenue_yoy']} | "
            f"净利润增长(YoY): {data['profit_yoy']} | "
            f"毛利率: {data['gross_margin']} | ROE: {data['roe']}"
        )
        data["performance_data_date"] = (
            f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
        )

        return data
