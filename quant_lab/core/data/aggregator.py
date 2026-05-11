"""Data aggregator — orchestrates all DimensionFetchers.

Replaces legacy ``fetch_extended_data`` and ``fetch_full_stock_data``
with a single sequential pipeline that:

1. Runs independent dimensions
2. Injects merged results as *context* for downstream dimensions
   (e.g. ``SupportResistanceFetcher``)
3. Computes cross-metrics (PEG, PS-TTM)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from quant_lab.core.data.dimensions import (
    ChipFetcher,
    CompetitorFetcher,
    ConsensusFetcher,
    IndustryCompareFetcher,
    InstitutionFetcher,
    LockupFetcher,
    MacroETFFetcher,
    MarketEnvFetcher,
    NewsFetcher,
    PerformanceFetcher,
    QuarterlyTrendFetcher,
    RecentKlineFetcher,
    SentimentFetcher,
    SmartMoneyFetcher,
    SupportResistanceFetcher,
    ThemeSentimentFetcher,
    TopHoldersFetcher,
    ValuationFetcher,
)

logger = logging.getLogger(__name__)


class StockAggregator:
    """Backward-compatible wrapper around :func:`aggregate`.

    Legacy code imports ``StockAggregator`` from ``quant_lab.core.data``.
    This class simply delegates to the module-level ``aggregate`` function.
    """

    @staticmethod
    def aggregate(
        symbol: str, stock_name: str, asset_type: str = "stock"
    ) -> dict[str, Any]:
        """Delegate to :func:`aggregate`."""
        return aggregate(symbol, stock_name, asset_type)


def aggregate(
    symbol: str, stock_name: str, asset_type: str = "stock"
) -> dict[str, Any]:
    """Fetch and merge all dimensions for *symbol*.

    Args:
        symbol: Stock / ETF / index code.
        stock_name: Human-readable name.
        asset_type: ``"stock"`` (default) or ``"etf"`` / ``"index"``.

    Returns:
        Flat dictionary containing metadata, all dimension data,
        and cross-computed metrics.
    """
    result: dict[str, Any] = {
        "code": symbol,
        "name": stock_name,
        "type": asset_type,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    if asset_type == "stock":
        _aggregate_stock(result, symbol, stock_name)
    else:
        _aggregate_etf_or_index(result, symbol, stock_name)

    return result


def _aggregate_stock(
    result: dict[str, Any], symbol: str, stock_name: str
) -> None:
    """Run all stock-specific dimensions."""
    fetchers: list[Any] = [
        ValuationFetcher(),
        PerformanceFetcher(),
        SentimentFetcher(),
        MacroETFFetcher(),
        ConsensusFetcher(),
        RecentKlineFetcher(),
        QuarterlyTrendFetcher(),
        IndustryCompareFetcher(),
        TopHoldersFetcher(),
        ThemeSentimentFetcher(),
        MarketEnvFetcher(),
        LockupFetcher(),
        ChipFetcher(),
        InstitutionFetcher(),
        CompetitorFetcher(),
        SmartMoneyFetcher(),
        NewsFetcher(),
    ]

    for fetcher in fetchers:
        result.update(fetcher.fetch(symbol, stock_name))

    # Support/resistance needs upstream context (prices, MA, BOLL)
    sr = SupportResistanceFetcher()
    result.update(sr.fetch(symbol, stock_name, context=result))

    # Cross-computations
    _compute_peg(result)
    _compute_ps_ttm(result)


def _aggregate_etf_or_index(
    result: dict[str, Any], symbol: str, stock_name: str
) -> None:
    """Run lightweight dimensions for ETF / index."""
    fetchers: list[Any] = [
        SentimentFetcher(),
        MacroETFFetcher(),
        MarketEnvFetcher(),
    ]
    for fetcher in fetchers:
        result.update(fetcher.fetch(symbol, stock_name))


def _compute_peg(data: dict[str, Any]) -> None:
    """PEG = PE-TTM / expected earnings growth rate."""
    try:
        pe = data.get("pe_ttm_raw")
        growth = data.get("eps_growth_rate_raw")
        if pe and growth and growth > 0:
            peg = pe / growth
            data["peg"] = f"{peg:.2f}"
            data["peg_raw"] = peg
            if peg < 0.5:
                data["peg_signal"] = f"极度低估(PEG={peg:.2f}<0.5)"
            elif peg < 1:
                data["peg_signal"] = f"偏低估(PEG={peg:.2f}<1)"
            elif peg < 1.5:
                data["peg_signal"] = f"合理(PEG={peg:.2f})"
            elif peg < 2:
                data["peg_signal"] = f"偏高估(PEG={peg:.2f})"
            else:
                data["peg_signal"] = f"高估(PEG={peg:.2f}>2)"
    except Exception:  # noqa: BLE001
        pass


def _compute_ps_ttm(data: dict[str, Any]) -> None:
    """PS-TTM = market cap / revenue TTM."""
    try:
        market_cap = data.get("market_cap")
        revenue = data.get("revenue_ttm_raw")
        if market_cap and revenue and revenue > 0:
            ps = market_cap / revenue
            data["ps_ttm"] = f"{ps:.2f}"
            data["ps_ttm_raw"] = ps
    except Exception:  # noqa: BLE001
        pass
