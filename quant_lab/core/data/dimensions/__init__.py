"""Business-dimension fetchers for stock analysis."""

from quant_lab.core.data.dimensions.base import DimensionFetcher, safe_fetch
from quant_lab.core.data.dimensions.chip import ChipFetcher
from quant_lab.core.data.dimensions.competitor import CompetitorFetcher
from quant_lab.core.data.dimensions.consensus import ConsensusFetcher
from quant_lab.core.data.dimensions.industry_compare import IndustryCompareFetcher
from quant_lab.core.data.dimensions.institution import InstitutionFetcher
from quant_lab.core.data.dimensions.lockup import LockupFetcher
from quant_lab.core.data.dimensions.macro_etf import MacroETFFetcher
from quant_lab.core.data.dimensions.news import NewsFetcher
from quant_lab.core.data.dimensions.performance import PerformanceFetcher
from quant_lab.core.data.dimensions.quarterly_trend import QuarterlyTrendFetcher
from quant_lab.core.data.dimensions.recent_kline import RecentKlineFetcher
from quant_lab.core.data.dimensions.sentiment import SentimentFetcher
from quant_lab.core.data.dimensions.smart_money import SmartMoneyFetcher
from quant_lab.core.data.dimensions.support_resistance import SupportResistanceFetcher
from quant_lab.core.data.dimensions.theme_sentiment import ThemeSentimentFetcher
from quant_lab.core.data.dimensions.top_holders import TopHoldersFetcher
from quant_lab.core.data.dimensions.valuation import ValuationFetcher

__all__ = [
    "ChipFetcher",
    "CompetitorFetcher",
    "ConsensusFetcher",
    "DimensionFetcher",
    "IndustryCompareFetcher",
    "InstitutionFetcher",
    "LockupFetcher",
    "MacroETFFetcher",
    "NewsFetcher",
    "PerformanceFetcher",
    "QuarterlyTrendFetcher",
    "RecentKlineFetcher",
    "safe_fetch",
    "SentimentFetcher",
    "SmartMoneyFetcher",
    "SupportResistanceFetcher",
    "ThemeSentimentFetcher",
    "TopHoldersFetcher",
    "ValuationFetcher",
]
