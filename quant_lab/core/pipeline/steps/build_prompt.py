"""BuildPromptStep — 根据数据和模式构建 LLM prompt."""

from __future__ import annotations

import logging
from typing import Any

from quant_lab.core.pipeline.base import PipelineStep
from quant_lab.core.pipeline.state import AnalysisState

logger = logging.getLogger(__name__)


def _build_worker_prompt(data: dict[str, Any]) -> str:
    """Worker 层快速分析 prompt (~300 字)."""
    stock_name = data.get("name", "N/A")
    stock_code = data.get("code", "N/A")
    asset_type = data.get("type", "stock")

    prompt = f"""
你是一位金融数据分析师，请对【{stock_name}】({stock_code})进行快速分析。

## 核心数据

### 技术面
{data.get('tech_summary', 'N/A')}
- 均线状态: {data.get('ma_alignment', 'N/A')}
- 涨跌幅: 5日 {data.get('change_5d', 'N/A')}% | 20日 {data.get('change_20d', 'N/A')}%
- RSI: {data.get('rsi_signal', 'N/A')} | MACD: {data.get('macd_signal', 'N/A')}
- 量比: {data.get('volume_alert', 'N/A')}

### 资金面
{data.get('money_summary', 'N/A')}
{data.get('money_context', '')}

### 聪明钱动向
{data.get('smart_money_summary', 'N/A')}
"""

    if asset_type == "stock":
        if data.get("valuation_summary"):
            prompt += f"""
### 估值维度 (数据截至: {data.get('valuation_data_date', 'N/A')})
{data.get('valuation_summary', 'N/A')}
- 股息率: {data.get('dividend_yield', 'N/A')} (历史分位: {data.get('dividend_percentile', 'N/A')})
- PEG: {data.get('peg', 'N/A')} ({data.get('peg_signal', 'N/A')})
"""
        if data.get("performance_summary"):
            prompt += f"""
### 业绩维度 (数据截至: {data.get('performance_data_date', 'N/A')})
{data.get('performance_summary', 'N/A')}
- 营收环比(QoQ): {data.get('revenue_qoq', 'N/A')}
- 净利润环比(QoQ): {data.get('profit_qoq', 'N/A')}
- 现金流质量: {data.get('cf_quality', 'N/A')}
"""
        if data.get("consensus_summary"):
            prompt += f"""
### 分析师预期 (数据截至: {data.get('consensus_data_date', 'N/A')})
{data.get('consensus_summary', 'N/A')}
"""

    prompt += f"""
### 舆情面
{data.get('news_summary', 'N/A')}
{data.get('news_context', '')}

### 情绪与题材
{data.get('theme_sentiment_summary', 'N/A')}

### 支撑压力位
{data.get('support_resistance_summary', 'N/A')}
"""

    if asset_type == "stock" and data.get("market_env_summary"):
        prompt += f"""
### 大盘环境 (数据截至: {data.get('market_env_data_date', 'N/A')})
{data.get('market_env_summary', 'N/A')}
- 主要指数: {data.get('indices_overview', 'N/A')}
- 成交量: {data.get('market_total_volume', '')} vs5日均{data.get('market_volume_vs_5d', 'N/A')} ({data.get('market_volume_signal', 'N/A')})
- 涨跌: 涨{data.get('market_up_count', '?')}家/跌{data.get('market_down_count', '?')}家/平{data.get('market_flat_count', '?')}家 涨停{data.get('market_limit_up', '?')}/跌停{data.get('market_limit_down', '?')}
- 北向资金: {data.get('north_total_net_flow', '已停止实时披露')}
- 南向资金(港股通): {data.get('south_total_net_flow', 'N/A')} ({data.get('south_flow_direction', 'N/A')})
- Shibor: 隔夜{data.get('shibor_overnight', 'N/A')}({data.get('shibor_overnight_change', 'N/A')}) | 1周{data.get('shibor_1w', 'N/A')} ({data.get('monetary_signal', 'N/A')})
- 热门板块: {', '.join(data.get('hot_sectors_top3', [])) or 'N/A'}
"""
        if data.get("global_macro_summary") and data.get("global_macro_summary") != "N/A":
            prompt += f"""
### 全球宏观背景
{data.get('global_macro_summary', 'N/A')}
- 数据更新: {data.get('global_macro_update', 'N/A')}
"""
        if data.get("lockup_summary"):
            prompt += f"""
### 解禁风险 (数据截至: {data.get('lockup_data_date', 'N/A')})
{data.get('lockup_summary', 'N/A')}
"""
        if data.get("chip_summary"):
            prompt += f"""
### 筹码分布 (数据截至: {data.get('chip_data_date', 'N/A')})
{data.get('chip_summary', 'N/A')}
"""

    if data.get("sentiment_summary"):
        prompt += f"""
### 资金情绪
{data.get('sentiment_summary', 'N/A')}
- 量比异动: {data.get('volume_alert', '正常')}
- 股东人数: {data.get('holder_count', 'N/A')} (变化: {data.get('holder_change', 'N/A')})
- 筹码趋势: {data.get('holder_trend', 'N/A')}
- 北向资金(3日): {data.get('north_flow_3d', 'N/A')}
"""

    prompt += """
## 分析要求
请用1-2段话总结：
1. 当前市场状态（技术+资金+情绪）
2. 关键风险点或机会点（如有全球宏观数据，请结合美债收益率、美元指数等分析对该标的的影响）
3. 简要建议（买入/观望/回避）

请保持简洁，控制在300字以内。
"""
    return prompt.strip()


def _build_brain_prompt(data: dict[str, Any], prompt_version: str = "professional") -> str:
    """Brain 层深度分析 prompt.

    目前提供 professional 骨架，后续迭代可扩展 value_first / quant_hybrid 风格.
    """
    stock_name = data.get("name", "N/A")
    stock_code = data.get("code", "N/A")

    sections: list[str] = [
        f"你是一位顶级量化分析师，请对【{stock_name}】({stock_code})进行深度研判。",
        "",
        "## 核心数据",
    ]

    for key, label in (
        ("tech_summary", "技术面"),
        ("money_summary", "资金面"),
        ("valuation_summary", "估值维度"),
        ("performance_summary", "业绩维度"),
        ("consensus_summary", "一致预期"),
        ("market_env_summary", "大盘环境"),
        ("smart_money_summary", "聪明钱动向"),
        ("chip_summary", "筹码分布"),
        ("lockup_summary", "解禁风险"),
        ("theme_sentiment_summary", "情绪与题材"),
        ("support_resistance_summary", "支撑压力位"),
    ):
        if data.get(key):
            sections.append(f"### {label}\n{data[key]}\n")

    sections.extend(
        [
            "",
            "## 分析要求",
            "1. 综合技术面、基本面、资金面给出投资评级（强烈买入/买入/持有/减持/卖出）。",
            "2. 给出目标价区间和时间窗口。",
            "3. 列出3-5条核心逻辑和2-3个主要风险点。",
            "4. 给出短线和中线操作策略。",
            "",
            "请保持专业、客观，字数在 800-1200 字之间。",
        ]
    )

    return "\n".join(sections)


class BuildPromptStep(PipelineStep):
    """根据当前 state 构建 LLM prompt.

    Args:
        prompt_version: brain 模式的风格 (professional / value_first / quant_hybrid).
    """

    name = "build_prompt"

    def __init__(self, prompt_version: str = "professional") -> None:
        self.prompt_version = prompt_version

    def run(self, state: AnalysisState) -> AnalysisState:
        data = state.raw_data
        if state.need_deep_analysis:
            prompt = _build_brain_prompt(data, self.prompt_version)
            logger.info("🧠 构建 Brain 深度 prompt (version=%s)", self.prompt_version)
        else:
            prompt = _build_worker_prompt(data)
            logger.info("🤖 构建 Worker 快速 prompt")

        return self._stamp(
            state.model_copy(update={"prompt": prompt}),
            "build_prompt",
        )
