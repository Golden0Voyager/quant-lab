"""基金 / ETF 结构化输出 schema."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class FundRating(str, Enum):
    """基金五档评级."""

    STRONG_BUY = "强烈买入"
    BUY = "买入"
    HOLD = "持有"
    REDUCE = "减持"
    SELL = "卖出"


class FundAnalysis(BaseModel):
    """基金 / ETF 深度分析的结构化输出."""

    ticker: str = Field(description="基金/ETF 代码")
    name: str = Field(description="基金/ETF 名称")

    rating: FundRating = Field(description="综合评级")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="信心度 (0.0-1.0)",
    )
    key_signals: list[str] = Field(
        default_factory=list,
        description="关键信号",
    )
    risk_alerts: list[str] = Field(
        default_factory=list,
        description="主要风险点",
    )
    holdings_penetration_summary: str | None = Field(
        default=None,
        description="持仓穿透摘要 (前十大重仓及行业分布)",
    )
    target_nav: float | None = Field(
        default=None,
        description="目标净值",
    )
    time_horizon: str | None = Field(
        default=None,
        description="建议持有周期",
    )
    core_logic: str | None = Field(
        default=None,
        description="核心逻辑: 2-3 句话",
    )
