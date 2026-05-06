"""Schema → Markdown 渲染工具."""

from __future__ import annotations

from .batch import BatchValuationResult
from .fund import FundAnalysis
from .index import IndexAnalysis
from .stock import StockAnalysis


def render_stock_analysis(analysis: StockAnalysis) -> str:
    """将 StockAnalysis 渲染为 markdown 报告片段."""
    lines: list[str] = [
        f"## {analysis.name} ({analysis.ticker})",
        "",
        f"**综合评级**: {analysis.rating.value}  (信心度: {analysis.confidence:.0%})",
        "",
    ]

    if analysis.core_logic:
        lines.extend(["### 核心逻辑", f"{analysis.core_logic}", ""])

    if analysis.key_signals:
        lines.extend(["### 关键信号", *[f"- {s}" for s in analysis.key_signals], ""])

    if analysis.risk_alerts:
        lines.extend(["### 风险提示", *[f"- {r}" for r in analysis.risk_alerts], ""])

    if analysis.target_price is not None:
        lines.append(f"**目标价**: ¥{analysis.target_price:.2f}")

    if analysis.time_horizon:
        lines.append(f"**时间窗口**: {analysis.time_horizon}")

    if analysis.strategy_short_term or analysis.strategy_mid_term:
        lines.extend(["", "### 操作策略"])
        if analysis.strategy_short_term:
            lines.append(f"- **短线**: {analysis.strategy_short_term}")
        if analysis.strategy_mid_term:
            lines.append(f"- **中线**: {analysis.strategy_mid_term}")

    return "\n".join(lines)


def render_fund_analysis(analysis: FundAnalysis) -> str:
    """将 FundAnalysis 渲染为 markdown 报告片段."""
    lines: list[str] = [
        f"## {analysis.name} ({analysis.ticker})",
        "",
        f"**综合评级**: {analysis.rating.value}  (信心度: {analysis.confidence:.0%})",
        "",
    ]

    if analysis.core_logic:
        lines.extend(["### 核心逻辑", f"{analysis.core_logic}", ""])

    if analysis.key_signals:
        lines.extend(["### 关键信号", *[f"- {s}" for s in analysis.key_signals], ""])

    if analysis.risk_alerts:
        lines.extend(["### 风险提示", *[f"- {r}" for r in analysis.risk_alerts], ""])

    if analysis.holdings_penetration_summary:
        lines.extend([
            "### 持仓穿透",
            f"{analysis.holdings_penetration_summary}",
            "",
        ])

    if analysis.target_nav is not None:
        lines.append(f"**目标净值**: {analysis.target_nav:.4f}")

    if analysis.time_horizon:
        lines.append(f"**建议持有周期**: {analysis.time_horizon}")

    return "\n".join(lines)


def render_index_analysis(analysis: IndexAnalysis) -> str:
    """将 IndexAnalysis 渲染为 markdown 报告片段."""
    lines: list[str] = [
        f"## {analysis.name} ({analysis.ticker})",
        "",
        f"**市场环境**: {analysis.market_assessment.value}  "
        f"(信心度: {analysis.confidence:.0%}, 风险等级: {analysis.risk_level}/5)",
        "",
    ]

    if analysis.core_logic:
        lines.extend(["### 核心逻辑", f"{analysis.core_logic}", ""])

    if analysis.key_signals:
        lines.extend(["### 关键信号", *[f"- {s}" for s in analysis.key_signals], ""])

    if analysis.risk_alerts:
        lines.extend(["### 风险提示", *[f"- {r}" for r in analysis.risk_alerts], ""])

    lines.append(f"**建议仓位**: {analysis.suggested_position}")

    return "\n".join(lines)


def render_batch_result(result: BatchValuationResult) -> str:
    """将 BatchValuationResult 渲染为 markdown 报告片段."""
    lines: list[str] = [
        render_stock_analysis(result.analysis),
        "",
    ]
    if result.metrics_digest:
        lines.extend(["### 估值指标摘要", result.metrics_digest, ""])
    return "\n".join(lines)
