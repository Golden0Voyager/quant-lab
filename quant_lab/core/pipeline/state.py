"""Pipeline state model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from quant_lab.core.schemas import FundAnalysis, IndexAnalysis, StockAnalysis


class AnalysisState(BaseModel):
    """Mutable-but-typed container for pipeline execution state.

    Wraps the flat ``dict`` produced by :func:`quant_lab.core.data.aggregator.aggregate`
    and adds pipeline-level metadata (timestamps, signal scores, provenance).
    """

    symbol: str
    stock_name: str
    asset_type: str = "stock"
    stage: str = "init"
    raw_data: dict[str, Any] = Field(default_factory=dict)
    signal_score: int = 0
    triggers: list[str] = Field(default_factory=list)
    need_deep_analysis: bool = False
    prompt: str = ""
    response: str = ""
    structured_output: StockAnalysis | FundAnalysis | IndexAnalysis | None = None
    report_path: str | None = None
    error: str | None = None
    timestamps: dict[str, str] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Backward-compatible flat dict for legacy consumers."""
        return {
            **self.raw_data,
            "code": self.symbol,
            "name": self.stock_name,
            "type": self.asset_type,
            "signal_score": self.signal_score,
            "triggers": self.triggers,
            "need_deep_analysis": self.need_deep_analysis,
            "prompt": self.prompt,
            "response": self.response,
            "report_path": self.report_path,
            "error": self.error,
        }
