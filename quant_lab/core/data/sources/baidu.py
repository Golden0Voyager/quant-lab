"""Baidu stock data scrapers."""

from __future__ import annotations

import logging

import akshare as ak  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


def fetch_valuation_percentile(
    symbol: str,
    indicator: str,
    periods: list[tuple[str, str]] | None = None,
) -> dict[str, float]:
    """Fetch historical valuation percentiles from Baidu.

    Args:
        symbol: 6-digit stock code.
        indicator: One of ``'市盈率(TTM)'``, ``'市净率'``, ``'市现率'``.
        periods: List of *(akshare_period_name, short_key)* tuples.
            Defaults to ``[('近十年', '10y'), ('近五年', '5y'),
            ('近三年', '3y'), ('近一年', '1y')]``.

    Returns:
        Dict mapping short keys (e.g. ``'10y'``) to percentile values.
    """
    if periods is None:
        periods = [
            ("近十年", "10y"),
            ("近五年", "5y"),
            ("近三年", "3y"),
            ("近一年", "1y"),
        ]

    percentiles: dict[str, float] = {}
    for period_name, period_key in periods:
        try:
            df = ak.stock_zh_valuation_baidu(
                symbol=symbol, indicator=indicator, period=period_name
            )
            if df is None or df.empty:
                continue
            values = df["value"].dropna()
            values = values[values > 0]
            if len(values) <= 10:
                continue
            current = values.iloc[-1]
            pct = (values < current).sum() / len(values) * 100
            percentiles[period_key] = round(float(pct), 1)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Baidu percentile failed for %s %s %s: %s",
                symbol,
                indicator,
                period_name,
                exc,
            )
            continue

    return percentiles
