"""FetchDataStep — 调用 v2 aggregator 获取数据."""

from __future__ import annotations

import logging

from quant_lab.core.data.aggregator import aggregate
from quant_lab.core.data.cache import DataCacheFacade
from quant_lab.core.pipeline.base import PipelineStep
from quant_lab.core.pipeline.state import AnalysisState

logger = logging.getLogger(__name__)


class FetchDataStep(PipelineStep):
    """抓取并聚合所有数据维度.

    Args:
        use_cache: 是否优先读取缓存.
        cache: 可选的 ``DataCacheFacade`` 实例；为 *None* 时惰性创建.
    """

    name = "fetch_data"

    def __init__(
        self,
        *,
        use_cache: bool = True,
        cache: DataCacheFacade | None = None,
    ) -> None:
        self.use_cache = use_cache
        self._cache = cache

    @property
    def cache(self) -> DataCacheFacade:
        if self._cache is None:
            self._cache = DataCacheFacade()
        return self._cache

    def run(self, state: AnalysisState) -> AnalysisState:
        symbol = state.symbol
        stock_name = state.stock_name
        asset_type = state.asset_type

        # 1. 尝试缓存
        if self.use_cache:
            cached = self.cache.get("extended", symbol)
            if cached is not None:
                logger.info("✅ 缓存命中: %s", symbol)
                return self._stamp(
                    state.model_copy(
                        update={"raw_data": cached, "stage": "fetch_data_cached"}
                    ),
                    "fetch_data",
                )

        # 2. 实时抓取
        logger.info("🔄 实时抓取: %s (%s)", stock_name, symbol)
        data = aggregate(symbol, stock_name, asset_type=asset_type)

        # 3. 写入缓存
        if self.use_cache:
            self.cache.set("extended", symbol, data)

        return self._stamp(
            state.model_copy(update={"raw_data": data}),
            "fetch_data",
        )
