"""Eastmoney data-source wrappers.

All functions return ``dict[str, Any] | None``; failures are caught and
logged at debug level.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

from quant_lab.core.data.sources._utils import no_proxy

logger = logging.getLogger(__name__)


def fetch_financial_report(symbol: str) -> dict[str, Any] | None:
    """Fetch the latest 业绩报表 row from Eastmoney."""
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
        logger.debug("Eastmoney financial report failed for %s: %s", symbol, exc)
        return None


def fetch_eastmoney_kline(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str = "daily",
    adjust: str = "qfq",
) -> dict[str, Any] | None:
    """Fetch Eastmoney K-line; returns most recent row as dict."""
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
        return dict(df.iloc[-1])
    except Exception as exc:  # noqa: BLE001
        logger.debug("Eastmoney K-line failed for %s: %s", symbol, exc)
        return None


def fetch_stock_info_eastmoney(symbol: str) -> dict[str, Any] | None:
    """Fetch individual stock info from Eastmoney."""
    try:
        with no_proxy():
            df = ak.stock_individual_info_em(symbol=symbol)
        if df is None or df.empty:
            return None
        return dict(zip(df["item"], df["value"], strict=False))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Eastmoney info failed for %s: %s", symbol, exc)
        return None


def fetch_profit_sheet(symbol: str) -> dict[str, Any] | None:
    """Fetch profit sheet by report from Eastmoney.

    Returns the *most recent* report row as a dict.
    """
    prefix = "SH" if symbol.startswith("6") else "SZ"
    try:
        with no_proxy():
            df = ak.stock_profit_sheet_by_report_em(symbol=f"{prefix}{symbol}")
        if df is None or df.empty:
            return None
        return dict(df.iloc[0])
    except Exception as exc:  # noqa: BLE001
        logger.debug("Eastmoney profit sheet failed for %s: %s", symbol, exc)
        return None


def fetch_circulate_holders(symbol: str) -> dict[str, Any] | None:
    """Fetch top circulate stock holders from Eastmoney.

    Returns the raw DataFrame so the caller can extract latest / previous
    periods.
    """
    try:
        with no_proxy():
            df = ak.stock_circulate_stock_holder(symbol=symbol)
        if df is None or df.empty:
            return None
        return {"df": df}
    except Exception as exc:  # noqa: BLE001
        logger.debug("Eastmoney circulate holders failed for %s: %s", symbol, exc)
        return None
