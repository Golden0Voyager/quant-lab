"""Quarterly trend dimension fetcher."""

from __future__ import annotations

import logging
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.sources._utils import no_proxy, safe_float

logger = logging.getLogger(__name__)


class QuarterlyTrendFetcher:
    """Fetch quarterly revenue / profit trend data."""

    name = "quarterly_trend"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str) -> dict[str, Any]:
        """Return up to 8 quarters of revenue and profit trends."""
        data: dict[str, Any] = {}

        prefix = "SH" if symbol.startswith("6") else "SZ"
        with no_proxy():
            df = ak.stock_profit_sheet_by_report_em(symbol=f"{prefix}{symbol}")

        if df is None or df.empty:
            raise ValueError("利润表数据为空")

        data["quarterly_trend"] = []
        for _, row in df.head(8).iterrows():
            data["quarterly_trend"].append(
                {
                    "report_date": str(row.get("REPORT_DATE", ""))[:10],
                    "report_name": row.get("REPORT_DATE_NAME", ""),
                    "revenue": safe_float(row.get("OPERATE_INCOME")),
                    "revenue_yoy": safe_float(row.get("OPERATE_INCOME_YOY")),
                    "net_profit": safe_float(row.get("PARENT_NETPROFIT")),
                    "net_profit_yoy": safe_float(row.get("PARENT_NETPROFIT_YOY")),
                }
            )

        return data
