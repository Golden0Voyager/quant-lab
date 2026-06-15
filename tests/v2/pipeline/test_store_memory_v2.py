"""Extended tests for StoreMemoryStep — covering uncovered branches."""

from __future__ import annotations

from unittest.mock import MagicMock

from quant_lab.core.pipeline.steps.store_memory import StoreMemoryStep
from quant_lab.core.schemas.stock import StockRating
from tests.v2.helpers import make_analysis_state, make_stock_analysis


class TestStoreMemoryStepV2:
    def test_structured_output_rating(self) -> None:
        """structured_output has rating → extract (lines 19-21)."""
        cache = MagicMock()
        memory_log = MagicMock()
        step = StoreMemoryStep(cache=cache, memory_log=memory_log)

        analysis = make_stock_analysis(rating=StockRating.BUY, confidence=0.8)
        state = make_analysis_state(
            raw_data={"pe": 15},
            structured_output=analysis,
            response="分析结果",
            timestamps={"fetch_data": "2025-09-30 10:00:00"},
        )
        result = step.run(state)
        assert result.stage == "store_memory"
        # structured_output.model_dump() should be called
        call_args = cache.set.call_args_list
        assert len(call_args) >= 2

    def test_text_heuristic_rating(self) -> None:
        """Text heuristic finds rating (line 26)."""
        cache = MagicMock()
        memory_log = MagicMock()
        step = StoreMemoryStep(cache=cache, memory_log=memory_log)

        state = make_analysis_state(
            raw_data={"pe": 15},
            response="建议买入该股票",
            timestamps={"fetch_data": "2025-09-30 10:00:00"},
        )
        result = step.run(state)
        assert result.stage == "store_memory"
        # Verify memory_log.store_decision was called with rating="买入"
        call_kwargs = memory_log.store_decision.call_args[1]
        assert call_kwargs["rating"] == "买入"

    def test_structured_output_confidence(self) -> None:
        """structured_output has confidence → extract (lines 33-35)."""
        cache = MagicMock()
        memory_log = MagicMock()
        step = StoreMemoryStep(cache=cache, memory_log=memory_log)

        analysis = make_stock_analysis(rating=StockRating.BUY, confidence=0.85)
        state = make_analysis_state(
            raw_data={"pe": 15},
            structured_output=analysis,
            response="分析结果",
            timestamps={"fetch_data": "2025-09-30 10:00:00"},
        )
        result = step.run(state)
        assert result.stage == "store_memory"
        call_kwargs = memory_log.store_decision.call_args[1]
        assert call_kwargs["confidence"] == 0.85

    def test_structured_output_model_dump(self) -> None:
        """structured_output.model_dump() called (line 86)."""
        cache = MagicMock()
        memory_log = MagicMock()
        step = StoreMemoryStep(cache=cache, memory_log=memory_log)

        analysis = make_stock_analysis(rating=StockRating.BUY, confidence=0.8)
        state = make_analysis_state(
            raw_data={"pe": 15},
            structured_output=analysis,
            response="分析结果",
            timestamps={"fetch_data": "2025-09-30 10:00:00"},
        )
        step.run(state)
        # Check that analysis record includes structured_output
        analysis_call = cache.set.call_args_list[1]
        assert "structured_output" in analysis_call[0][2]

    def test_memory_log_exception(self) -> None:
        """Memory log exception → logged, not raised (lines 104-105)."""
        cache = MagicMock()
        memory_log = MagicMock()
        memory_log.store_decision.side_effect = Exception("memory fail")
        step = StoreMemoryStep(cache=cache, memory_log=memory_log)

        state = make_analysis_state(
            raw_data={"pe": 15},
            response="分析结果",
            timestamps={"fetch_data": "2025-09-30 10:00:00"},
        )
        result = step.run(state)
        assert result.stage == "store_memory"
        # Should not raise, cache.set still called
        assert cache.set.called
