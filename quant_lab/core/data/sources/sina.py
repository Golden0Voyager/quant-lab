"""Sina K-line fallback source wrapper."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


def fetch_sina_kline(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
    adjust: str = "",
) -> dict[str, Any] | None:
    """Fetch K-line from Sina (fallback when Eastmoney fails)."""
    sina_sym = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

    try:
        df = ak.stock_zh_a_daily(
            symbol=sina_sym, start_date=start_date, end_date=end_date, adjust=adjust
        )
        if df is None or df.empty:
            return None
        df = df.rename(
            columns={
                "close": "收盘",
                "open": "开盘",
                "high": "最高",
                "low": "最低",
                "volume": "成交量",
            }
        )
        return dict(df.iloc[-1])
    except Exception as exc:  # noqa: BLE001
        logger.debug("Sina K-line failed for %s: %s", symbol, exc)
        return None
