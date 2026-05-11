"""Tencent data-source wrappers (K-line fallback)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


def fetch_tencent_kline(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
    adjust: str = "qfq",
) -> dict[str, Any] | None:
    """Fetch K-line from Tencent; returns most recent row as dict.

    Tencent uses ``sh`` / ``sz`` prefixes (e.g. ``sh600519``).
    """
    tencent_sym = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")

    try:
        df = ak.stock_zh_a_hist_tx(
            symbol=tencent_sym,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
        if df is None or df.empty:
            return None
        df = df.rename(
            columns={
                "close": "收盘",
                "open": "开盘",
                "high": "最高",
                "low": "最低",
                "amount": "成交额",
                "date": "日期",
            }
        )
        if "成交量" not in df.columns:
            df["成交量"] = 0
        return dict(df.iloc[-1])
    except Exception as exc:  # noqa: BLE001
        logger.debug("Tencent K-line failed for %s: %s", symbol, exc)
        return None
