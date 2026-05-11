"""Business-dimension fetchers for stock analysis."""

from quant_lab.core.data.dimensions.base import DimensionFetcher, safe_fetch
from quant_lab.core.data.dimensions.consensus import ConsensusFetcher
from quant_lab.core.data.dimensions.industry_compare import IndustryCompareFetcher
from quant_lab.core.data.dimensions.performance import PerformanceFetcher
from quant_lab.core.data.dimensions.quarterly_trend import QuarterlyTrendFetcher
from quant_lab.core.data.dimensions.recent_kline import RecentKlineFetcher
from quant_lab.core.data.dimensions.sentiment import SentimentFetcher
from quant_lab.core.data.dimensions.top_holders import TopHoldersFetcher
from quant_lab.core.data.dimensions.valuation import ValuationFetcher

__all__ = [
    "ConsensusFetcher",
    "DimensionFetcher",
    "IndustryCompareFetcher",
    "PerformanceFetcher",
    "QuarterlyTrendFetcher",
    "RecentKlineFetcher",
    "safe_fetch",
    "SentimentFetcher",
    "TopHoldersFetcher",
    "ValuationFetcher",
]
