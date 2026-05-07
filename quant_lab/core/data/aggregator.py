"""Multi-dimension aggregator for quant_lab.

Combines results from multiple ``DimensionFetcher`` objects into a
single flat dict compatible with the legacy
``analyst_data.fetch_full_stock_data`` output.
"""

from __future__ import annotations

import logging
from typing import Any

from quant_lab.core.data.registry import DimensionRegistry

logger = logging.getLogger(__name__)


class StockAggregator:
    """Orchestrator that fetches and merges dimension data for a stock.

    Usage::

        registry = DimensionRegistry(cache=...)
        registry.register("valuation", ValuationFetcher())
        ...

        agg = StockAggregator(registry)
        result = agg.aggregate("000001", "平安银行")
    """

    def __init__(self, registry: DimensionRegistry) -> None:
        self._registry = registry

    def aggregate(
        self,
        symbol: str,
        stock_name: str,
        dimensions: list[str] | None = None,
        *,
        asset_type: str = "stock",
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Fetch *dimensions* and return a unified flat dict.

        The returned dict always contains:

        - ``code`` – *symbol*
        - ``name`` – *stock_name*
        - ``type`` – *asset_type*
        - ``timestamp`` – ISO-8601 fetch time

        plus the merged fields from every dimension fetcher.
        """
        from datetime import datetime

        result: dict[str, Any] = {
            "code": symbol,
            "name": stock_name,
            "type": asset_type,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        fetched = self._registry.fetch_all(
            symbol, stock_name, names=dimensions, use_cache=use_cache
        )

        for dim_name, dim_data in fetched.items():
            if "_error" in dim_data:
                logger.warning(
                    "Dimension %s failed for %s: %s",
                    dim_name,
                    symbol,
                    dim_data["_error"],
                )
            # Merge dimension data into the main result dict.
            # Dimension keys that collide with base keys (code/name/type/timestamp)
            # are silently overwritten – this matches the legacy behaviour where
            # ``result.update(valuation_data)`` was used.
            result.update(dim_data)

        # Cross-calculation: PEG = PE-TTM / expected earnings growth
        self._calc_peg(result)

        return result

    @staticmethod
    def _calc_peg(data: dict[str, Any]) -> None:
        """Compute PEG in-place when PE-TTM and growth rate are available."""
        pe_ttm = data.get("pe_ttm_raw")
        eps_growth = data.get("eps_growth_rate_raw")
        if pe_ttm is None or eps_growth is None:
            return
        try:
            pe_val = float(pe_ttm)
            growth_val = float(eps_growth)
        except (TypeError, ValueError):
            return

        if growth_val <= 0:
            return

        peg = pe_val / growth_val
        data["peg"] = f"{peg:.2f}"
        data["peg_raw"] = peg
        if peg < 0.5:
            signal = f"极度低估(PEG={peg:.2f}<0.5)"
        elif peg < 1:
            signal = f"偏低估(PEG={peg:.2f}<1)"
        elif peg < 1.5:
            signal = f"合理(PEG={peg:.2f})"
        elif peg < 2:
            signal = f"偏高估(PEG={peg:.2f})"
        else:
            signal = f"高估(PEG={peg:.2f}>2)"
        data["peg_signal"] = signal
        logger.info("✓ PEG计算成功: %s", signal)
