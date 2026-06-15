"""Pytest fixtures for quant_lab v2 test suite."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from quant_lab.core.pipeline.state import AnalysisState
from quant_lab.core.schemas.stock import StockAnalysis
from tests.v2.helpers import make_mock_fetcher, make_stock_analysis


@pytest.fixture
def sample_stock_data() -> dict[str, Any]:
    """Return a sample integrated data dict for stock analysis."""
    return {
        "ticker": "000001.SZ",
        "name": "平安银行",
        "price": 12.5,
        "pe_ttm": 5.2,
        "pb": 0.8,
        "market_cap": 2400.0,
        "sector": "银行",
        "kline_summary": "近20日上涨3.2%",
        "valuation_summary": "PE处于历史10%分位",
        "sentiment_summary": "融资余额下降",
        "macro_summary": "LPR下调利好",
    }


@pytest.fixture
def mock_llm_client() -> Generator[MagicMock, None, None]:
    """Return a mock LLM client that echoes prompts."""
    client = MagicMock()
    client.chat.return_value = "持有。市场震荡，估值合理。"
    yield client


@pytest.fixture
def mock_structured_llm_client() -> Generator[MagicMock, None, None]:
    """Return a mock LLM client that returns structured dicts."""
    client = MagicMock()

    def _structured_chat(prompt: str, *, schema: Any | None = None, **kwargs: Any) -> Any:
        if schema is not None:
            # Return a valid instance of the schema
            return schema(
                rating="持有",
                key_signals=["估值处于历史低位", "宏观政策宽松"],
                risk_alerts=["资产质量压力"],
                confidence=0.72,
            )
        return "持有。估值处于历史低位，宏观政策宽松。"

    client.chat.side_effect = _structured_chat
    yield client


@pytest.fixture
def temp_report_dir(tmp_path: Path) -> Path:
    """Provide a temporary report directory."""
    d = tmp_path / "reports"
    d.mkdir()
    return d


@pytest.fixture
def default_analysis_state() -> AnalysisState:
    """Return an AnalysisState with sensible defaults for testing."""
    return AnalysisState(symbol="000001", stock_name="平安银行")


@pytest.fixture
def sample_stock_analysis() -> StockAnalysis:
    """Return a StockAnalysis with sensible defaults for testing."""
    return make_stock_analysis()


@pytest.fixture
def mock_aggregator_fetchers() -> dict[str, MagicMock]:
    """Return a dict of mock fetchers for all aggregator dimensions."""
    return {
        "valuation": make_mock_fetcher({"pe_ttm_raw": 15.0}),
        "performance": make_mock_fetcher({"revenue_ttm_raw": 100.0, "market_cap": 500.0}),
        "sentiment": make_mock_fetcher({"sentiment": "中性"}),
        "macro_etf": make_mock_fetcher({"usdcnh_rate": 7.2}),
        "consensus": make_mock_fetcher({"eps_growth_rate_raw": 0.2}),
        "recent_kline": make_mock_fetcher({"current_price": 50.0, "ma20": 48.0}),
        "quarterly_trend": make_mock_fetcher({"qt_signal": "上升"}),
        "industry_compare": make_mock_fetcher({"peer_count": 10}),
        "top_holders": make_mock_fetcher({"holder_count": 5}),
        "theme_sentiment": make_mock_fetcher({"stock_sentiment": "偏多"}),
        "market_env": make_mock_fetcher({"market_sentiment": "偏暖"}),
        "lockup": make_mock_fetcher({"lockup_risk_level": "低风险"}),
        "chip": make_mock_fetcher({"chip_profit_ratio_raw": 60.0}),
        "institution": make_mock_fetcher({"fund_holding_count": 20}),
        "competitor": make_mock_fetcher({"competitors": []}),
        "smart_money": make_mock_fetcher({"north_consecutive_days": 3}),
        "news": make_mock_fetcher({"news_source": "东财公告"}),
        "support_resistance": make_mock_fetcher({"resistance_price": 55.0}),
    }
