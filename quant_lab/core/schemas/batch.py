"""批量估值结构化输出 schema."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .stock import StockAnalysis


class BatchValuationResult(BaseModel):
    """批量估值中单个标的的结构化输出."""

    ticker: str = Field(description="股票代码")
    name: str = Field(description="股票名称")
    analysis: StockAnalysis = Field(description="结构化分析结论")
    metrics_digest: str = Field(
        default="",
        description="17 维估值指标摘要 (markdown)",
    )
