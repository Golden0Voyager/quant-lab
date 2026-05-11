"""EvaluateSignalsStep — 信号评估，决定是否触发深度分析."""

from __future__ import annotations

import logging
import re
from typing import Any

from quant_lab.core.pipeline.base import PipelineStep
from quant_lab.core.pipeline.state import AnalysisState

logger = logging.getLogger(__name__)


def _extract_amount(text: str) -> float | None:
    """从 'xxx亿' 文本中提取数值."""
    match = re.search(r"([\d.]+)亿", text)
    return float(match.group(1)) if match else None


def _evaluate_signals(data: dict[str, Any]) -> tuple[bool, list[str], int]:
    """评估 17+ 类信号，返回 (need_deep, triggers, score).

    这是 legacy ``evaluate_enhanced_signals`` 的 v2 迁移版本，
    保持相同的打分逻辑和阈值 (score >= 3 触发深度分析).
    """
    triggers: list[str] = []
    score = 0

    # 1. 资金流向信号（适配市值）
    money_summary = data.get("money_summary", "")
    amount = _extract_amount(money_summary)
    if amount:
        market_cap = data.get("market_cap_yi") or data.get("market_cap")
        if market_cap and market_cap > 0:
            ratio = (abs(amount) / market_cap) * 100
            if ratio >= 5.0:
                score += 3
                triggers.append(f"💰 巨额资金异动: {amount}亿 (占市值{ratio:.1f}%)")
            elif ratio >= 2.0:
                score += 2
                triggers.append(f"💰 大额资金异动: {amount}亿 (占市值{ratio:.1f}%)")
            elif ratio >= 1.0:
                score += 1
                triggers.append(f"💰 资金异动: {amount}亿 (占市值{ratio:.1f}%)")
        else:
            if abs(amount) >= 10:
                score += 3
                direction = "流入" if "✅" in money_summary else "流出"
                triggers.append(f"💰 巨额资金{direction}: {amount}亿")
            elif abs(amount) >= 5:
                score += 2
                direction = "流入" if "✅" in money_summary else "流出"
                triggers.append(f"💰 大额资金{direction}: {amount}亿")

    # 2. 估值错位信号
    pe_str = data.get("pe_ttm", "N/A")
    pb_str = data.get("pb", "N/A")
    pe_pct = data.get("pe_percentile", "N/A")
    pb_pct = data.get("pb_percentile", "N/A")
    try:
        if pe_str != "N/A" and pb_str != "N/A" and pe_pct != "N/A" and pb_pct != "N/A":
            pe_percentile = float(str(pe_pct).rstrip("%"))
            pb_percentile = float(str(pb_pct).rstrip("%"))
            if pe_percentile < 30 and pb_percentile > 70:
                score += 3
                triggers.append(
                    f"⚠️ 估值错位: PE低位({pe_percentile:.0f}%) 但PB高位({pb_percentile:.0f}%)"
                )
            elif pe_percentile < 20 and pb_percentile < 20:
                score += 3
                triggers.append(
                    f"✅ 极度低估: PE({pe_percentile:.0f}%) PB({pb_percentile:.0f}%) 均处历史低位"
                )
            elif pe_percentile > 80 and pb_percentile > 80:
                score += 2
                triggers.append(
                    f"⚠️ 高估预警: PE({pe_percentile:.0f}%) PB({pb_percentile:.0f}%) 均处历史高位"
                )
    except Exception:
        pass

    # 3. 高股息机会
    dividend_yield = data.get("dividend_yield", "N/A")
    try:
        if dividend_yield not in ("N/A", "无分红"):
            div_rate = float(str(dividend_yield).rstrip("%"))
            if div_rate >= 4.0:
                score += 2
                triggers.append(f"💵 高股息机会: {div_rate:.2f}% (≥4%)")
            elif div_rate >= 3.0:
                score += 1
                triggers.append(f"💵 稳定股息: {div_rate:.2f}% (≥3%)")
    except Exception:
        pass

    # 4. 业绩增速异常
    profit_yoy = data.get("profit_yoy", "N/A")
    try:
        if profit_yoy != "N/A":
            profit_growth = float(str(profit_yoy).rstrip("%"))
            if profit_growth < -30:
                score += 3
                triggers.append(f"⚠️ 业绩爆雷: 净利润同比{profit_growth:.1f}%")
            elif profit_growth > 100:
                score += 3
                triggers.append(f"🚀 业绩翻倍: 净利润同比+{profit_growth:.1f}%")
            elif profit_growth > 30:
                score += 2
                triggers.append(f"✅ 业绩高增长: 净利润同比+{profit_growth:.1f}%")
    except Exception:
        pass

    # 5. 利润含金量预警
    cf_quality = data.get("cf_quality", "")
    if "⚠️" in cf_quality or "含金量较低" in cf_quality:
        score += 2
        triggers.append(f"⚠️ 现金流预警: {cf_quality}")

    # 6. 毛利率异常
    gross_margin = data.get("gross_margin", "N/A")
    try:
        if gross_margin != "N/A":
            margin = float(str(gross_margin).rstrip("%"))
            if margin < 15:
                score += 1
                triggers.append(f"⚠️ 毛利率偏低: {margin:.1f}% (<15%)")
    except Exception:
        pass

    # 7. 量比异动
    volume_alert = data.get("volume_alert", "")
    if "异动" in volume_alert:
        score += 2
        triggers.append(f"📊 {volume_alert}")

    # 8. 筹码集中度变化
    holder_trend = data.get("holder_trend", "")
    if "筹码集中" in holder_trend or "大户吸筹" in holder_trend:
        score += 2
        triggers.append(f"💎 {holder_trend}")
    elif "筹码分散" in holder_trend or "散户接盘" in holder_trend:
        score += 1
        triggers.append(f"⚠️ {holder_trend}")

    # 9. 北向资金大幅异动
    north_flow = data.get("north_flow_3d", "N/A")
    amount = _extract_amount(north_flow)
    if amount:
        market_cap = data.get("market_cap_yi") or data.get("market_cap")
        if market_cap and market_cap > 0:
            ratio = (amount / market_cap) * 100
            if ratio >= 2.0:
                score += 2
                triggers.append(f"🌏 北向资金大幅异动: {amount}亿 (占市值{ratio:.1f}%)")
            elif ratio >= 0.5:
                score += 1
                triggers.append(f"🌏 北向资金异动: {amount}亿 (占市值{ratio:.1f}%)")
        else:
            if amount >= 5:
                score += 2
                direction = "流入" if "流入" in north_flow else "流出"
                triggers.append(f"🌏 北向资金大幅{direction}: {amount}亿")

    # 10. ETF 折溢价套利
    premium_alert = data.get("premium_alert", "")
    if "折价超过1%" in premium_alert:
        score += 2
        triggers.append(f"💰 ETF折价套利机会: {data.get('etf_premium', 'N/A')}")
    elif "溢价超过1%" in premium_alert:
        score += 1
        triggers.append(f"⚠️ ETF溢价风险: {data.get('etf_premium', 'N/A')}")

    need_deep = score >= 3
    return need_deep, triggers, score


class EvaluateSignalsStep(PipelineStep):
    """评估信号强度，决定是否触发深度分析."""

    name = "evaluate_signals"

    def run(self, state: AnalysisState) -> AnalysisState:
        data = state.raw_data
        need_deep, triggers, score = _evaluate_signals(data)
        logger.info(
            "📊 信号评估: score=%d, need_deep=%s, triggers=%d",
            score,
            need_deep,
            len(triggers),
        )
        return self._stamp(
            state.model_copy(
                update={
                    "signal_score": score,
                    "triggers": triggers,
                    "need_deep_analysis": need_deep,
                }
            ),
            "evaluate_signals",
        )
