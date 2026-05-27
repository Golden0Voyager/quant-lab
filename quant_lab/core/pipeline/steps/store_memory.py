"""StoreMemoryStep — 将结果写入缓存 / 记忆层."""

from __future__ import annotations

import logging
from typing import Any

from quant_lab.core.data.cache import DataCacheFacade
from quant_lab.core.memory.log import AnalysisMemoryLog
from quant_lab.core.pipeline.base import PipelineStep
from quant_lab.core.pipeline.state import AnalysisState

logger = logging.getLogger(__name__)


def _extract_rating(state: AnalysisState) -> str | None:
    """Try to extract a rating from structured output or free text."""
    if state.structured_output:
        rating = getattr(state.structured_output, "rating", None)
        if rating:
            return str(rating)
    # Simple text heuristic
    resp = state.response or ""
    for label in ("强烈买入", "买入", "持有", "减持", "卖出"):
        if label in resp:
            return label
    return None


def _extract_confidence(state: AnalysisState) -> float | None:
    """Try to extract confidence from structured output."""
    if state.structured_output:
        confidence = getattr(state.structured_output, "confidence", None)
        if confidence is not None:
            return float(confidence)
    return None


class StoreMemoryStep(PipelineStep):
    """将分析结果持久化到缓存层和记忆日志.

    Args:
        cache: 可选的 ``DataCacheFacade`` 实例；为 *None* 时惰性创建.
        memory_log: 可选的 ``AnalysisMemoryLog`` 实例；为 *None* 时惰性创建.
    """

    name = "store_memory"

    def __init__(
        self,
        cache: DataCacheFacade | None = None,
        memory_log: AnalysisMemoryLog | None = None,
    ) -> None:
        self._cache = cache
        self._memory_log = memory_log

    @property
    def cache(self) -> DataCacheFacade:
        if self._cache is None:
            self._cache = DataCacheFacade()
        return self._cache

    @property
    def memory_log(self) -> AnalysisMemoryLog:
        if self._memory_log is None:
            self._memory_log = AnalysisMemoryLog()
        return self._memory_log

    def run(self, state: AnalysisState) -> AnalysisState:
        symbol = state.symbol

        # 1. 缓存原始数据 (extended)
        if state.raw_data:
            self.cache.set("extended", symbol, state.raw_data)

        # 2. 缓存分析结果 (analysis)
        analysis_record: dict[str, Any] = {
            "signal_score": state.signal_score,
            "triggers": state.triggers,
            "need_deep_analysis": state.need_deep_analysis,
            "response": state.response,
            "report_path": state.report_path,
            "timestamps": state.timestamps,
        }
        if state.structured_output:
            analysis_record["structured_output"] = state.structured_output.model_dump()

        self.cache.set("analysis", symbol, analysis_record, ttl=24 * 60 * 60)

        # 3. 写入记忆日志 (memory_log)
        try:
            today = state.timestamps.get("fetch_data", "")[:10] or __import__("datetime").datetime.now().strftime("%Y-%m-%d")
            self.memory_log.store_decision(
                symbol=symbol,
                stock_name=state.stock_name,
                date=today,
                rating=_extract_rating(state),
                confidence=_extract_confidence(state),
                triggers=state.triggers,
                analysis_mode="deep" if state.need_deep_analysis else "fast",
                report_path=state.report_path,
                raw_data=state.raw_data,
            )
        except Exception as exc:
            logger.warning("Memory log write failed (non-critical): %s", exc)

        logger.info("💾 记忆已存储: %s", symbol)
        return self._stamp(state, "store_memory")
