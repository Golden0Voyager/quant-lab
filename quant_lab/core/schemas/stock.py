"""A股个股结构化输出 schema."""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import BaseModel, Field, model_validator


class StockRating(str, Enum):
    """五档综合评级."""

    STRONG_BUY = "强烈买入"
    BUY = "买入"
    HOLD = "持有"
    REDUCE = "减持"
    SELL = "卖出"


class StockAnalysis(BaseModel):
    """个股深度分析的结构化输出."""

    ticker: str = Field(description="股票代码")
    name: str = Field(description="股票名称")

    rating: StockRating = Field(description="综合评级: 强烈买入/买入/持有/减持/卖出")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="对评级的信心度 (0.0-1.0)",
    )
    key_signals: list[str] = Field(
        default_factory=list,
        description="3-5 条触发评级的关键信号",
    )
    risk_alerts: list[str] = Field(
        default_factory=list,
        description="主要风险点",
    )
    target_price: float | None = Field(
        default=None,
        description="目标价 (人民币)",
    )
    time_horizon: str | None = Field(
        default=None,
        description="时间窗口: 短线/中线/长线",
    )
    core_logic: str | None = Field(
        default=None,
        description="核心逻辑: 2-3 句话说明主要理由",
    )
    strategy_short_term: str | None = Field(
        default=None,
        description="短线操作策略",
    )
    strategy_mid_term: str | None = Field(
        default=None,
        description="中线操作策略",
    )

    @model_validator(mode="after")
    def _round_confidence(self) -> Self:
        if self.confidence is not None:
            self.confidence = round(self.confidence, 2)
        return self
