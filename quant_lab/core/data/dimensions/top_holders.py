"""Top holders dimension fetcher."""

from __future__ import annotations

import logging
from typing import Any

from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.sources.eastmoney import fetch_circulate_holders

logger = logging.getLogger(__name__)


class TopHoldersFetcher:
    """Fetch top circulate stock holders and period-over-period changes."""

    name = "top_holders"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str) -> dict[str, Any]:
        """Return latest top-10 holders and optional previous period map."""
        data: dict[str, Any] = {}

        result = fetch_circulate_holders(symbol)
        if result is None or "df" not in result:
            raise ValueError("流通股东数据为空")

        df = result["df"]
        dates = df["截止日期"].unique()
        if len(dates) < 1:
            raise ValueError("无截止日期数据")

        latest_date = dates[0]
        latest = df[df["截止日期"] == latest_date].head(10)
        data["holders_report_date"] = str(latest_date)
        data["top_holders"] = []
        for _, row in latest.iterrows():
            data["top_holders"].append(
                {
                    "name": row["股东名称"],
                    "shares": int(row["持股数量"]),
                    "pct": float(row["占流通股比例"]),
                    "type": row["股本性质"],
                }
            )

        if len(dates) >= 2:
            prev_date = dates[1]
            prev = df[df["截止日期"] == prev_date].head(10)
            data["holders_prev_date"] = str(prev_date)
            data["holders_prev_map"] = {}
            for _, row in prev.iterrows():
                data["holders_prev_map"][row["股东名称"]] = {
                    "shares": int(row["持股数量"]),
                    "pct": float(row["占流通股比例"]),
                }

        return data
