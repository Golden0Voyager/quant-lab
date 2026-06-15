"""Shared test helpers for quant_lab v2 test suite."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from quant_lab.core.pipeline.state import AnalysisState
from quant_lab.core.schemas.stock import StockAnalysis, StockRating


def make_mock_fetcher(payload: dict[str, Any]) -> MagicMock:
    """Create a mock fetcher that returns the given payload."""
    m = MagicMock()
    m.fetch.return_value = payload
    return m


def make_analysis_state(
    symbol: str = "000001",
    stock_name: str = "平安银行",
    raw_data: dict[str, Any] | None = None,
    **kwargs: Any,
) -> AnalysisState:
    """Create an AnalysisState with sensible defaults."""
    return AnalysisState(
        symbol=symbol,
        stock_name=stock_name,
        raw_data=raw_data or {},
        **kwargs,
    )


def make_stock_analysis(
    ticker: str = "000001",
    name: str = "平安银行",
    rating: StockRating = StockRating.HOLD,
    confidence: float = 0.75,
    core_logic: str = "估值合理",
) -> StockAnalysis:
    """Create a StockAnalysis with sensible defaults."""
    return StockAnalysis(
        ticker=ticker,
        name=name,
        rating=rating,
        confidence=confidence,
        core_logic=core_logic,
    )


def make_mock_client(response: str = "持有。市场震荡，估值合理。") -> MagicMock:
    """Create a mock LLM client that returns the given response."""
    client = MagicMock()
    client.chat.return_value = response
    return client
