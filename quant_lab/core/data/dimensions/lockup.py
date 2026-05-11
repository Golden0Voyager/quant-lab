"""Lockup / restricted-release dimension fetcher."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import akshare as ak  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.sources._utils import no_proxy, safe_float

logger = logging.getLogger(__name__)


class LockupFetcher:
    """Fetch upcoming restricted-share release events and risk assessment."""

    name = "lockup"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str, **kwargs: Any) -> dict[str, Any]:
        """Return lockup events and risk level for *symbol*."""
        data: dict[str, Any] = {
            "lockup_data_date": datetime.now().strftime("%Y-%m-%d")
        }

        with no_proxy():
            lockup_df = ak.stock_restricted_release_queue_em(symbol=symbol)

        if lockup_df is None or lockup_df.empty:
            data["lockup_events"] = []
            data["lockup_risk_level"] = "低风险"
            data["lockup_6m_total_pct"] = "0%"
            data["lockup_summary"] = "近期无解禁"
            return data

        today = date.today()
        six_months_later = today + timedelta(days=180)

        events: list[dict[str, Any]] = []
        total_pct_6m = 0.0

        for _, row in lockup_df.iterrows():
            release_date: date | None = None
            for col in lockup_df.columns:
                if "解禁" in str(col) and "日期" in str(col):
                    try:  # noqa: SIM105
                        release_date = pd.to_datetime(row[col]).date()
                    except Exception:
                        pass
                    break

            if release_date is None or release_date < today:
                continue

            shares: float | None = None
            for col in lockup_df.columns:
                if "解禁" in str(col) and ("股" in str(col) or "数量" in str(col)):
                    shares = safe_float(row.get(col))
                    break

            pct: float | None = None
            for col in lockup_df.columns:
                if "占" in str(col) and ("流通" in str(col) or "比" in str(col) or "%" in str(col)):
                    pct = safe_float(row.get(col))
                    break

            event: dict[str, Any] = {"date": str(release_date)}
            if shares:
                if shares > 1e8:
                    event["shares_display"] = f"{shares / 1e8:.2f}亿股"
                else:
                    event["shares_display"] = f"{shares / 1e4:.0f}万股"
            if pct:
                event["pct_of_float"] = f"{pct:.2f}%"
                if release_date <= six_months_later:
                    total_pct_6m += pct

            events.append(event)

        data["lockup_events"] = events[:10]
        if events:
            data["lockup_nearest_date"] = events[0]["date"]
        data["lockup_6m_total_pct"] = f"{total_pct_6m:.1f}%"

        max_single_pct = 0.0
        for e in events:
            pct_str = e.get("pct_of_float", "0%")
            try:  # noqa: SIM105
                max_single_pct = max(max_single_pct, float(pct_str.rstrip("%")))
            except ValueError:
                pass

        if max_single_pct > 5 or total_pct_6m > 10:
            data["lockup_risk_level"] = "高风险"
        elif total_pct_6m > 3:
            data["lockup_risk_level"] = "中风险"
        else:
            data["lockup_risk_level"] = "低风险"

        nearest = events[0] if events else {}
        data["lockup_summary"] = (
            f"最近解禁: {nearest.get('date', 'N/A')} {nearest.get('shares_display', '')} "
            f"| 6月累计: {data['lockup_6m_total_pct']} | 风险: {data['lockup_risk_level']}"
            if events
            else "近期无解禁"
        )

        return data
