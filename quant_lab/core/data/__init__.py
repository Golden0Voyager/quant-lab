"""Data layer: source registry, dimension fetchers, cache, aggregator."""

from quant_lab.core.data.aggregator import StockAggregator
from quant_lab.core.data.cache import DataCacheFacade
from quant_lab.core.data.registry import DimensionRegistry

__all__ = [
    "DataCacheFacade",
    "DimensionRegistry",
    "StockAggregator",
]
