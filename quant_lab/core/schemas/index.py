"""指数 / 大盘结构化输出 schema."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class MarketAssessment(str, Enum):
    """市场环境判断."""

    BULL = "牛市"
    BEAR = "熊市"
    CONSOLIDATION = "震荡市"
    RECOVERY = "复苏市"
    CORRECTION = "调整市"


class IndexAnalysis(BaseModel):
    """指数 / 大盘宏观分析的结构化输出."""

    ticker: str = Field(description="指数代码")
    name: str = Field(description="指数名称")

    market_assessment: MarketAssessment = Field(description="市场环境判断")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="信心度 (0.0-1.0)",
    )
    risk_level: int = Field(
        ge=1,
        le=5,
        description="系统性风险等级 (1-5, 5 最高)",
    )
    key_signals: list[str] = Field(
        default_factory=list,
        description="关键信号",
    )
    risk_alerts: list[str] = Field(
        default_factory=list,
        description="风险点",
    )
    suggested_position: str = Field(
        description="建议仓位 (如: 满仓/半仓/空仓)",
    )
    core_logic: str | None = Field(
        default=None,
        description="核心逻辑: 2-3 句话",
    )
