"""Tests for AnalysisState."""

from __future__ import annotations

from quant_lab.core.pipeline.state import AnalysisState
from quant_lab.core.schemas import StockAnalysis, StockRating


class TestAnalysisState:
    def test_basic_creation(self) -> None:
        state = AnalysisState(symbol="000001", stock_name="平安银行")
        assert state.symbol == "000001"
        assert state.stock_name == "平安银行"
        assert state.asset_type == "stock"
        assert state.stage == "init"
        assert state.raw_data == {}

    def test_to_dict(self) -> None:
        state = AnalysisState(
            symbol="000001",
            stock_name="平安银行",
            raw_data={"pe_ttm": "15.2"},
            signal_score=5,
            triggers=["资金异动"],
        )
        d = state.to_dict()
        assert d["code"] == "000001"
        assert d["name"] == "平安银行"
        assert d["pe_ttm"] == "15.2"
        assert d["signal_score"] == 5
        assert d["triggers"] == ["资金异动"]

    def test_model_copy(self) -> None:
        state = AnalysisState(symbol="000001", stock_name="平安银行")
        new_state = state.model_copy(update={"stage": "fetch_data", "signal_score": 3})
        assert new_state.stage == "fetch_data"
        assert new_state.signal_score == 3
        # Original unchanged
        assert state.stage == "init"
        assert state.signal_score == 0

    def test_structured_output(self) -> None:
        analysis = StockAnalysis(
            ticker="000001",
            name="平安银行",
            rating=StockRating.BUY,
            confidence=0.85,
            key_signals=["低估值", "资金流入"],
        )
        state = AnalysisState(
            symbol="000001",
            stock_name="平安银行",
            structured_output=analysis,
        )
        assert state.structured_output is not None
        assert state.structured_output.rating == StockRating.BUY
