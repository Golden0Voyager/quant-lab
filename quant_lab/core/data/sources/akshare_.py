"""Thin typed wrappers around AkShare functions.

Each wrapper catches exceptions, returns a plain dict (or *None* on
failure), and never leaks a raw pandas DataFrame to callers.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

from quant_lab.core.data.sources._utils import no_proxy

logger = logging.getLogger(__name__)


def fetch_xueqiu_spot(symbol: str, token: str | None = None) -> dict[str, Any] | None:
    """Fetch real-time spot data from Xueqiu.

    *symbol* should be the 6-digit code (e.g. ``"000001"``).
    The function builds the Xueqiu ticker format internally.
    """
    if token is None:
        token = os.getenv("XUEQIU_TOKEN") or os.getenv("XQ_TOKEN")
    if not token:
        return None

    xq_symbol = (
        f"SZ{symbol}"
        if symbol.startswith(("000", "001", "002", "003", "300"))
        else f"SH{symbol}"
    )
    try:
        df = ak.stock_individual_spot_xq(symbol=xq_symbol, token=token)
        if df is None or df.empty:
            return None
        return dict(zip(df["item"], df["value"], strict=False))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Xueqiu spot failed for %s: %s", symbol, exc)
        return None


def fetch_financial_report(symbol: str) -> dict[str, Any] | None:
    """Fetch the latest financial report row from Eastmoney.

    Returns a dict of financial metrics for *symbol*, or *None*.
    """
    now = datetime.now()
    month = now.month
    if month >= 10:
        report_date = f"{now.year}0930"
    elif month >= 7:
        report_date = f"{now.year}0630"
    elif month >= 4:
        report_date = f"{now.year}0331"
    else:
        report_date = f"{now.year - 1}1231"

    try:
        with no_proxy():
            df = ak.stock_yjbb_em(date=report_date)
        row = df[df["股票代码"] == symbol]
        if row.empty:
            return None
        return dict(row.iloc[0])
    except Exception as exc:  # noqa: BLE001
        logger.debug("Financial report failed for %s: %s", symbol, exc)
        return None


def fetch_eastmoney_kline(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str = "daily",
    adjust: str = "qfq",
) -> dict[str, Any] | None:
    """Fetch K-line from Eastmoney.

    *start_date* and *end_date* are expected in ``YYYYMMDD`` format.
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

    try:
        with no_proxy():
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
        if df is None or df.empty:
            return None
        # Return the most recent row as a dict
        return dict(df.iloc[-1])
    except Exception as exc:  # noqa: BLE001
        logger.debug("Eastmoney K-line failed for %s: %s", symbol, exc)
        return None


def fetch_sina_kline(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
    adjust: str = "",
) -> dict[str, Any] | None:
    """Fetch K-line from Sina as a fallback."""
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
        # Normalise column names to match Eastmoney conventions
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


def fetch_stock_info_eastmoney(symbol: str) -> dict[str, Any] | None:
    """Fetch individual stock info from Eastmoney (market cap, etc.)."""
    try:
        with no_proxy():
            df = ak.stock_individual_info_em(symbol=symbol)
        if df is None or df.empty:
            return None
        return dict(zip(df["item"], df["value"], strict=False))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Eastmoney info failed for %s: %s", symbol, exc)
        return None
