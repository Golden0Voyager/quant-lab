"""StoreMemoryStep — 将结果写入缓存 / 记忆层."""

from __future__ import annotations

import logging
from typing import Any

from quant_lab.core.data.cache import DataCacheFacade
from quant_lab.core.pipeline.base import PipelineStep
from quant_lab.core.pipeline.state import AnalysisState

logger = logging.getLogger(__name__)


class StoreMemoryStep(PipelineStep):
    """将分析结果持久化到缓存层.

    Args:
        cache: 可选的 ``DataCacheFacade`` 实例；为 *None* 时惰性创建.
    """

    name = "store_memory"

    def __init__(self, cache: DataCacheFacade | None = None) -> None:
        self._cache = cache

    @property
    def cache(self) -> DataCacheFacade:
        if self._cache is None:
            self._cache = DataCacheFacade()
        return self._cache

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

        logger.info("💾 记忆已存储: %s", symbol)
        return self._stamp(state, "store_memory")
