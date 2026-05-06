"""Pytest fixtures for quant_lab v2 test suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock

import pytest


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
