"""
四维数据整合模块
将 analyst_core.py 和 analyst_core_enhanced.py 的数据合并
同时增强信号评估系统，支持估值、业绩维度的判断
"""

import logging
from analyst_core import fetch_stock_data
from analyst_core_enhanced import (
    fetch_valuation_data,
    fetch_performance_data,
    fetch_sentiment_data,
    fetch_macro_etf_data
)

logger = logging.getLogger(__name__)


def fetch_integrated_data(symbol: str, stock_name: str, asset_type: str = "stock") -> dict:
    """
    整合获取完整四维数据

    Args:
        symbol: 股票代码
        stock_name: 股票名称
        asset_type: 资产类型（stock/etf/index）

    Returns:
        整合后的完整数据字典
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"🔄 整合数据抓取: {stock_name} ({symbol})")
    logger.info(f"{'='*60}\n")

    # 1. 获取基础数据（原有系统）
    base_data = fetch_stock_data(symbol, stock_name)

    # 2. 获取四维增强数据（新系统）
    enhanced_data = {}

    if asset_type == "stock":
        # 估值维度
        try:
            valuation = fetch_valuation_data(symbol, stock_name)
            enhanced_data.update(valuation)
        except Exception as e:
            logger.warning(f"估值数据获取失败: {e}")

        # 业绩维度
        try:
            performance = fetch_performance_data(symbol, stock_name)
            enhanced_data.update(performance)
        except Exception as e:
            logger.warning(f"业绩数据获取失败: {e}")

        # 计算市销率 PS-TTM（需要市值和营收数据）
        try:
            market_cap = enhanced_data.get('market_cap')
            revenue_raw = enhanced_data.get('revenue_ttm_raw')  # TTM 营收

            if market_cap and revenue_raw and revenue_raw > 0:
                ps_ttm = market_cap / revenue_raw
                enhanced_data['ps_ttm'] = f"{ps_ttm:.2f}"
                enhanced_data['ps_ttm_raw'] = ps_ttm

                # 更新估值摘要，包含 PS-TTM
                enhanced_data['valuation_summary'] = (
                    f"PE-TTM: {enhanced_data.get('pe_ttm', 'N/A')} | "
                    f"PB: {enhanced_data.get('pb', 'N/A')} | "
                    f"PS-TTM: {enhanced_data['ps_ttm']} | "
                    f"股息率(TTM): {enhanced_data.get('dividend_yield', 'N/A')}"
                )
                logger.info(f"✓ 市销率计算成功: PS-TTM={enhanced_data['ps_ttm']}")
        except Exception as e:
            logger.debug(f"市销率计算失败: {e}")

    # 资金情绪维度（所有类型）
    try:
        sentiment = fetch_sentiment_data(symbol, stock_name)
        enhanced_data.update(sentiment)
    except Exception as e:
        logger.warning(f"资金情绪数据获取失败: {e}")

    # 宏观数据（ETF折溢价、汇率）
    try:
        macro = fetch_macro_etf_data(symbol, asset_type)
        enhanced_data.update(macro)
    except Exception as e:
        logger.warning(f"宏观数据获取失败: {e}")

    # 3. 合并数据
    integrated_data = {**base_data, **enhanced_data}

    logger.info(f"✅ 数据整合完成！\n")

    return integrated_data


def evaluate_enhanced_signals(data: dict) -> tuple:
    """
    增强版信号评估系统
    在原有V2基础上，新增估值、业绩维度的判断

    Args:
        data: 整合后的完整数据

    Returns:
        (是否触发深度分析, 触发原因列表, 信号得分)
    """
    triggers = []
    signal_score = 0

    # ==================== 原有信号（导入V2逻辑）====================
    # 这里可以直接调用 AnalystBrainV2 的评估方法
    # 或者重新实现，以下是简化版示例

    # 1. 资金流向信号（原有）
    money_summary = data.get('money_summary', '')
    if '亿' in money_summary:
        import re
        match = re.search(r'([\d.]+)亿', money_summary)
        if match:
            amount = float(match.group(1))
            if abs(amount) >= 10:
                signal_score += 3
                triggers.append(f"💰 巨额资金{'流入' if '✅' in money_summary else '流出'}: {amount}亿")
            elif abs(amount) >= 5:
                signal_score += 2
                triggers.append(f"💰 大额资金{'流入' if '✅' in money_summary else '流出'}: {amount}亿")

    # ==================== 新增：估值维度信号 ====================

    # 2. 估值错位信号（投资顾问重点提到的）
    pe_str = data.get('pe_ttm', 'N/A')
    pb_str = data.get('pb', 'N/A')
    pe_pct = data.get('pe_percentile', 'N/A')
    pb_pct = data.get('pb_percentile', 'N/A')

    try:
        # 检测"PE低但PB高"的估值错位
        if pe_str != 'N/A' and pb_str != 'N/A':
            pe = float(pe_str)
            pb = float(pb_str)

            # 解析分位数
            if pe_pct != 'N/A' and pb_pct != 'N/A':
                pe_percentile = float(pe_pct.rstrip('%'))
                pb_percentile = float(pb_pct.rstrip('%'))

                # 估值错位：PE历史分位<30% 但 PB历史分位>70%
                if pe_percentile < 30 and pb_percentile > 70:
                    signal_score += 3
                    triggers.append(f"⚠️ 估值错位: PE低位({pe_percentile:.0f}%) 但PB高位({pb_percentile:.0f}%)")

                # 极低估：PE和PB都在历史20%以下
                elif pe_percentile < 20 and pb_percentile < 20:
                    signal_score += 3
                    triggers.append(f"✅ 极度低估: PE({pe_percentile:.0f}%) PB({pb_percentile:.0f}%) 均处历史低位")

                # 极高估：PE和PB都在历史80%以上
                elif pe_percentile > 80 and pb_percentile > 80:
                    signal_score += 2
                    triggers.append(f"⚠️ 高估预警: PE({pe_percentile:.0f}%) PB({pb_percentile:.0f}%) 均处历史高位")

    except Exception as e:
        logger.debug(f"估值信号评估失败: {e}")

    # 3. 高股息机会（防御性资产识别）
    dividend_yield = data.get('dividend_yield', 'N/A')
    try:
        if dividend_yield != 'N/A' and dividend_yield != '无分红':
            div_rate = float(dividend_yield.rstrip('%'))
            if div_rate >= 5.0:
                signal_score += 2
                triggers.append(f"💵 高股息机会: {div_rate:.2f}% (>5%)")
    except Exception as e:
        logger.debug(f"股息率评估失败: {e}")

    # ==================== 新增：业绩维度信号 ====================

    # 4. 业绩增速异常（爆雷或爆发）
    profit_yoy = data.get('profit_yoy', 'N/A')
    try:
        if profit_yoy != 'N/A':
            profit_growth = float(profit_yoy.rstrip('%'))

            # 业绩爆雷：净利润同比下降>30%
            if profit_growth < -30:
                signal_score += 3
                triggers.append(f"⚠️ 业绩爆雷: 净利润同比{profit_growth:.1f}%")

            # 业绩爆发：净利润同比增长>50%
            elif profit_growth > 50:
                signal_score += 2
                triggers.append(f"✅ 业绩爆发: 净利润同比+{profit_growth:.1f}%")
    except Exception as e:
        logger.debug(f"业绩增速评估失败: {e}")

    # 5. 利润含金量预警
    cf_quality = data.get('cf_quality', '')
    if '⚠️' in cf_quality or '含金量较低' in cf_quality:
        signal_score += 2
        triggers.append(f"⚠️ 现金流预警: {cf_quality}")

    # 6. 毛利率异常（价格战预警）
    gross_margin = data.get('gross_margin', 'N/A')
    try:
        if gross_margin != 'N/A':
            margin = float(gross_margin.rstrip('%'))
            # 毛利率<15% 可能陷入价格战
            if margin < 15:
                signal_score += 1
                triggers.append(f"⚠️ 毛利率偏低: {margin:.1f}% (<15%)")
    except Exception as e:
        logger.debug(f"毛利率评估失败: {e}")

    # ==================== 新增：资金情绪信号（增强版）====================

    # 7. 量比异动
    volume_alert = data.get('volume_alert', '')
    if '异动' in volume_alert:
        signal_score += 2
        triggers.append(f"📊 {volume_alert}")

    # 8. 筹码集中度变化
    holder_trend = data.get('holder_trend', '')
    if '筹码集中' in holder_trend or '大户吸筹' in holder_trend:
        signal_score += 2
        triggers.append(f"💎 {holder_trend}")
    elif '筹码分散' in holder_trend or '散户接盘' in holder_trend:
        signal_score += 1
        triggers.append(f"⚠️ {holder_trend}")

    # 9. 北向资金大幅流入/流出
    north_flow = data.get('north_flow_3d', 'N/A')
    if '亿' in north_flow:
        import re
        match = re.search(r'([\d.]+)亿', north_flow)
        if match:
            amount = float(match.group(1))
            if amount >= 5:
                signal_score += 2
                triggers.append(f"🌏 北向资金大幅{'流入' if '流入' in north_flow else '流出'}: {amount}亿")

    # ==================== 新增：ETF折溢价信号 ====================

    # 10. ETF折溢价套利机会
    premium_alert = data.get('premium_alert', '')
    if '折价超过1%' in premium_alert:
        signal_score += 2
        triggers.append(f"💰 ETF折价套利机会: {data.get('etf_premium', 'N/A')}")
    elif '溢价超过1%' in premium_alert:
        signal_score += 1
        triggers.append(f"⚠️ ETF溢价预警: {data.get('etf_premium', 'N/A')}")

    # ==================== 新增：技术面信号 ====================

    # 11. RSI超买超卖信号
    rsi_signal = data.get('rsi_signal', '')
    if '超买' in rsi_signal:
        signal_score += 2
        triggers.append(f"📈 技术超买: {rsi_signal}")
    elif '超卖' in rsi_signal:
        signal_score += 2
        triggers.append(f"📉 技术超卖: {rsi_signal}")

    # 12. MACD金叉死叉信号
    macd_signal = data.get('macd_signal', '')
    if '金叉' in macd_signal:
        signal_score += 2
        triggers.append(f"✅ MACD金叉: 短期趋势转强")
    elif '死叉' in macd_signal:
        signal_score += 2
        triggers.append(f"⚠️ MACD死叉: 短期趋势转弱")

    # 13. 均线排列信号
    ma_alignment = data.get('ma_alignment', '')
    if '多头排列' in ma_alignment:
        signal_score += 1
        triggers.append(f"📈 均线多头排列: 趋势向上")
    elif '空头排列' in ma_alignment:
        signal_score += 1
        triggers.append(f"📉 均线空头排列: 趋势向下")

    # 14. 短期涨跌幅异常
    change_5d = data.get('change_5d')
    if change_5d is not None:
        if change_5d >= 15:
            signal_score += 2
            triggers.append(f"🚀 短期暴涨: 5日涨幅+{change_5d}%")
        elif change_5d <= -15:
            signal_score += 2
            triggers.append(f"💥 短期暴跌: 5日跌幅{change_5d}%")

    # ==================== 判断是否触发深度分析 ====================

    # 阈值：3分（与V2保持一致）
    need_deep = signal_score >= 3

    return need_deep, triggers, signal_score


def build_enhanced_prompt(data: dict, analysis_type: str = "worker", prompt_version: str = "professional") -> str:
    """
    构建增强版prompt，包含四维数据

    Args:
        data: 完整数据
        analysis_type: 分析类型 ("worker" 或 "brain")
        prompt_version: Prompt版本 ("value_first" / "quant_hybrid" / "professional")

    Returns:
        完整的prompt字符串
    """
    stock_name = data.get('name', 'N/A')
    stock_code = data.get('code', 'N/A')
    asset_type = data.get('type', 'stock')

    if analysis_type == "worker":
        # Worker层：快速分析（qwen-flash）
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

### 舆情面
{data.get('news_summary', 'N/A')}
{data.get('news_context', '')}
"""

        # 添加四维数据（如果是个股）
        if asset_type == "stock":
            # 估值维度
            if data.get('valuation_summary'):
                prompt += f"""
### 估值维度
{data.get('valuation_summary', 'N/A')}
- 股息率: {data.get('dividend_yield', 'N/A')} (历史分位: {data.get('dividend_percentile', 'N/A')})
"""

            # 业绩维度
            if data.get('performance_summary'):
                prompt += f"""
### 业绩维度
{data.get('performance_summary', 'N/A')}
- 营收环比(QoQ): {data.get('revenue_qoq', 'N/A')}
- 净利润环比(QoQ): {data.get('profit_qoq', 'N/A')}
- 现金流质量: {data.get('cf_quality', 'N/A')}
"""

        # 资金情绪（所有类型）
        if data.get('sentiment_summary'):
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
2. 关键风险点或机会点
3. 简要建议（买入/观望/回避）

请保持简洁，控制在200字以内。
"""

    else:  # brain层
        # Brain层：深度分析 - 使用可配置的 Prompt 版本
        prompt = _build_brain_prompt(data, stock_name, stock_code, asset_type, prompt_version)

    return prompt


def _build_brain_prompt(data: dict, stock_name: str, stock_code: str, asset_type: str, version: str) -> str:
    """
    构建 Brain 层深度分析 Prompt

    支持三种风格:
    - value_first: 价值优先型 (适合长期价值投资者)
    - quant_hybrid: 量化混合型 (多因子打分系统)
    - professional: 专业分析师型 (机构研报风格, 默认)
    """
    # ========== 1. 构建数据区块 ==========

    # 估值区块
    valuation_section = ""
    if asset_type == "stock" and data.get('valuation_summary'):
        valuation_section = f"""
- {data.get('valuation_summary', 'N/A')}
- 股息率: {data.get('dividend_yield', 'N/A')} (历史分位: {data.get('dividend_percentile', 'N/A')})
"""

    # 业绩区块
    performance_section = ""
    if asset_type == "stock" and data.get('performance_summary'):
        performance_section = f"""
- {data.get('performance_summary', 'N/A')}
- 营收同比(YoY): {data.get('revenue_yoy', 'N/A')} | 环比(QoQ): {data.get('revenue_qoq', 'N/A')}
- 净利润同比(YoY): {data.get('profit_yoy', 'N/A')} | 环比(QoQ): {data.get('profit_qoq', 'N/A')}
- 毛利率: {data.get('gross_margin', 'N/A')} | 净利率: {data.get('net_margin', 'N/A')}
- 现金流质量: {data.get('cf_quality', 'N/A')}
- 经营现金流/净利润: {data.get('cf_profit_ratio', 'N/A')}
"""

    # 技术区块
    technical_section = f"""
**价格与趋势**:
- 现价: {data.get('price', 'N/A')} | {data.get('trend_position', 'N/A')}

**均线系统**:
- MA5: {data.get('ma5', 'N/A')} | MA10: {data.get('ma10', 'N/A')} | MA20: {data.get('ma20', 'N/A')}
- MA60: {data.get('ma60', 'N/A')} | MA120: {data.get('ma120', 'N/A')} | MA250(年线): {data.get('ma250', 'N/A')}
- 均线状态: {data.get('ma_alignment', 'N/A')}

**涨跌幅**:
- 5日: {data.get('change_5d', 'N/A')}% | 20日: {data.get('change_20d', 'N/A')}% | 60日: {data.get('change_60d', 'N/A')}%

**技术指标**:
- RSI(14): {data.get('rsi', 'N/A')} - {data.get('rsi_signal', 'N/A')}
- MACD: DIF={data.get('macd_dif', 'N/A')} DEA={data.get('macd_dea', 'N/A')} - {data.get('macd_signal', 'N/A')}
- 量比: {data.get('volume_ratio', 'N/A')} ({data.get('volume_alert', 'N/A')})

**支撑压力**:
- 20日区间: 低点 {data.get('low_20d', 'N/A')} (距离-{data.get('dist_to_low', 'N/A')}%) ~ 高点 {data.get('high_20d', 'N/A')} (距离+{data.get('dist_to_high', 'N/A')}%)
- 60日区间: 低点 {data.get('low_60d', 'N/A')} ~ 高点 {data.get('high_60d', 'N/A')}
- 20日波动率: {data.get('volatility_20d', 'N/A')}%
"""

    # 资金情绪区块
    sentiment_section = f"""
- 主力资金(3日): {data.get('money_summary', 'N/A')}
- 量比: {data.get('volume_ratio', 'N/A')} | 异动: {data.get('volume_alert', '正常')}
- 换手率: {data.get('turnover_rate', 'N/A')}
- 股东人数: {data.get('holder_count', 'N/A')} (变化: {data.get('holder_change', 'N/A')})
- 筹码趋势: {data.get('holder_trend', 'N/A')}
- 北向资金(3日): {data.get('north_flow_3d', 'N/A')}
- 机构持仓: {data.get('institute_holding', 'N/A')}
"""

    # 舆情区块
    news_section = f"""
- 新闻来源: {data.get('news_source', 'N/A')}
{data.get('news_context', '无最新新闻')}
"""

    # ========== 2. 根据版本选择 Prompt 模板 ==========

    if version == "value_first":
        prompt = _prompt_value_first(stock_name, stock_code, asset_type,
                                     valuation_section, performance_section,
                                     technical_section, sentiment_section, news_section)
    elif version == "quant_hybrid":
        prompt = _prompt_quant_hybrid(stock_name, stock_code, asset_type,
                                      valuation_section, performance_section,
                                      technical_section, sentiment_section, news_section)
    else:  # professional (default)
        prompt = _prompt_professional(stock_name, stock_code, asset_type,
                                      valuation_section, performance_section,
                                      technical_section, sentiment_section, news_section)

    return prompt


def _prompt_value_first(name, code, asset_type, valuation, performance, technical, sentiment, news) -> str:
    """价值优先型 Prompt - 适合中长期价值投资"""
    if asset_type == "index":
        return _prompt_index_analysis(name, code, technical)

    return f"""You are a senior quantitative analyst specializing in value investing with tactical trading.
Your investment philosophy: Long-term value as the anchor, technical indicators for timing.
Respond in Chinese (中文回答).

Analyze 【{name}】({code})

## Complete Data Matrix

### Valuation Dimension (估值维度)
{valuation}

### Financial Quality (业绩质量)
{performance}

### Technical Analysis (技术分析)
{technical}

### Capital Flow & Sentiment (资金情绪)
{sentiment}

### News & Events (舆情事件)
{news}

## Analysis Framework

### Step 1: Valuation Assessment (价值评估)
- **Absolute Value**: Is current PE/PB historically cheap or expensive?
- **Dividend Shield**: Does dividend yield provide downside protection?
- **Quality-Adjusted Value**: Is valuation justified by cash flow quality?

### Step 2: Trend Confirmation (趋势确认)
- **Primary Trend**: Price vs MA250 (annual line) - bullish or bearish?
- **Secondary Trend**: Price vs MA20 - short-term direction
- **Momentum**: RSI/MACD signals - overbought/oversold?

### Step 3: Catalyst Check (催化剂)
- Capital flow direction and magnitude
- News events that could trigger revaluation

## Output Format (请用以下格式输出)

### 综合评级
**[看多/中性偏多/中性/中性偏空/看空]** | 置信度：[X]%

### 核心逻辑
[2-3句话，概括投资论点]

### 关键信号
1. [价值面信号 - 估值是否合理]
2. [技术面信号 - 趋势和择时]
3. [催化剂信号 - 资金或事件驱动]

### 操作策略
- **短线（1-4周）**: [具体建议，包含入场点/目标位/止损位]
- **中线（1-6个月）**: [建仓区间/持仓策略/止盈条件]

### 风险提示
1. [技术面风险]
2. [基本面风险]
3. [市场系统性风险]
"""


def _prompt_quant_hybrid(name, code, asset_type, valuation, performance, technical, sentiment, news) -> str:
    """量化混合型 Prompt - 多因子打分系统"""
    if asset_type == "index":
        return _prompt_index_analysis(name, code, technical)

    return f"""You are a quantitative analyst using a multi-factor scoring model.
Respond in Chinese (中文回答).

Analyze 【{name}】({code}) systematically.

## Data Matrix

### Factor 1: Valuation (权重30%)
{valuation}

### Factor 2: Quality (权重25%)
{performance}

### Factor 3: Momentum (权重25%)
{technical}

### Factor 4: Sentiment (权重20%)
{sentiment}

### Catalyst Events
{news}

## Multi-Factor Scoring Framework

For each factor, assign a score from -2 to +2:
- +2: Strongly Bullish | +1: Mildly Bullish | 0: Neutral | -1: Mildly Bearish | -2: Strongly Bearish

**Valuation Scoring Guide:**
- PE<15 & PB<2 → +2 | PE<25 & PB<3 → +1 | PE 25-40 → 0 | PE>40 → -1 | PE>60 → -2
- Dividend yield >4% adds +1

**Quality Scoring Guide:**
- Profit growth >30% with good cash flow → +2 | Growth >10% → +1 | Growth 0-10% → 0
- Profit decline 0-20% → -1 | Decline >20% or poor cash flow → -2

**Momentum Scoring Guide:**
- Above MA250, MACD bullish, RSI 40-60 → +2 | Above MA20 → +1 | Mixed signals → 0
- Below MA20 → -1 | Below MA250, bearish indicators → -2

**Sentiment Scoring Guide:**
- Large inflow (>5亿), holder concentration → +2 | Moderate inflow → +1 | Neutral → 0
- Moderate outflow → -1 | Large outflow, holder dispersion → -2

## Output Format (请用以下格式输出)

### 多因子评分

| 因子 | 得分 | 权重 | 加权分 |
|------|------|------|--------|
| 估值 | [X] | 30% | [Y] |
| 质量 | [X] | 25% | [Y] |
| 动量 | [X] | 25% | [Y] |
| 情绪 | [X] | 20% | [Y] |
| **合计** | - | 100% | **[Z]** |

### 综合评级
**[看多/中性/看空]** | 置信度：[X]% | 综合得分：[Z]

### 投资结论
[基于得分的投资建议，2-3句话]

### 关键观察点
1. [最强因子及其信号]
2. [最弱因子及其风险]
3. [需关注的边际变化]

### 操作建议
- **短线策略**: [具体建议，包含价位]
- **中线策略**: [具体建议，包含价位]
- **风险控制**: [止损位和仓位建议]
"""


def _prompt_professional(name, code, asset_type, valuation, performance, technical, sentiment, news) -> str:
    """专业分析师型 Prompt - 机构研报风格 (默认)"""
    if asset_type == "index":
        return _prompt_index_analysis(name, code, technical)

    return f"""You are a buy-side equity analyst at a top asset management firm.
Write a concise investment memo in Chinese (中文).

【{name}】({code}) Investment Analysis

## Research Data

### Valuation Metrics
{valuation}

### Fundamental Analysis
{performance}

### Technical Picture
{technical}

### Flow Analysis
{sentiment}

### Event Catalysts
{news}

## Output Format (请用以下格式输出投资备忘录)

---

### 综合评级
**[看多/中性偏多/中性/中性偏空/看空]** | 置信度：[高/中/低] ([X]%)

### 核心逻辑
[1-2句话概括投资论点]

---

### 关键信号
1. **[信号类型]**: [具体描述，引用数据]
2. **[信号类型]**: [具体描述，引用数据]
3. **[信号类型]**: [具体描述，引用数据]

---

### 操作策略

**短线策略（1-4周）**:
- 建议: [买入/观望/卖出]
- 入场区间: [价格区间]
- 目标位: [价格]
- 止损位: [价格]
- 仓位: [建议比例]

**中线策略（1-6个月）**:
- 建议: [建仓/持有/减仓]
- 理想布局区间: [价格区间]
- 目标位: [价格]
- 止损位: [价格]

---

### 风险提示
1. **[风险类型]**: [风险描述]
2. **[风险类型]**: [风险描述]

---

**免责声明**：本分析基于公开数据和量化模型，不构成投资建议。股市有风险，投资需谨慎。
"""


def _prompt_index_analysis(name, code, technical) -> str:
    """指数专用分析 Prompt"""
    return f"""You are a macro strategist analyzing market indices.
Respond in Chinese (中文回答).

Analyze 【{name}】({code})

## Technical Data
{technical}

## Index Analysis Framework

### 1. Market Regime (大盘环境判断)
Determine current market regime:
- **牛市**: Price above MA250, rising MA trend, expansion volume
- **熊市**: Price below MA250, declining MA trend, capitulation signs
- **震荡市**: Price oscillating around MA250, mixed signals

### 2. Risk Assessment (系统性风险评估)
- Technical breakdown risk (key support levels)
- Macro headwinds (policy, liquidity, external factors)
- Sentiment extremes (RSI overbought/oversold)

### 3. Position Sizing (仓位管理建议)
- 牛市: Higher exposure (60-80%)
- 震荡市: Moderate exposure (40-60%)
- 熊市: Defensive (20-40%)

## Output Format (请用以下格式输出)

### 市场环境
**[牛市/震荡市/熊市]** | 阶段: [具体描述]

### 核心判断
[2-3句话概括当前市场状态和预期方向]

### 关键技术位
- 强支撑: [价位] (依据: [说明])
- 强压力: [价位] (依据: [说明])

### 仓位建议
- 当前建议仓位: [X]%
- 加仓条件: [具体条件]
- 减仓条件: [具体条件]

### 风险提示
[主要系统性风险，2-3点]
"""


# ==================== 测试代码 ====================

if __name__ == "__main__":
    # 测试：广东宏大
    test_symbol = "002683"
    test_name = "广东宏大"

    # 1. 整合数据抓取
    data = fetch_integrated_data(test_symbol, test_name, "stock")

    # 2. 信号评估
    need_deep, triggers, score = evaluate_enhanced_signals(data)

    print(f"\n{'='*60}")
    print(f"信号评估结果:")
    print(f"{'='*60}")
    print(f"综合得分: {score}分")
    print(f"是否触发深度分析: {'是' if need_deep else '否'}")
    if triggers:
        print(f"\n触发原因:")
        for t in triggers:
            print(f"  - {t}")

    # 3. 测试三种 Prompt 版本
    versions = ["professional", "value_first", "quant_hybrid"]

    for version in versions:
        print(f"\n{'='*60}")
        print(f"Brain Prompt ({version}) 预览:")
        print(f"{'='*60}")
        brain_prompt = build_enhanced_prompt(data, "brain", prompt_version=version)
        # 显示前800字符
        print(brain_prompt[:800] + "\n...[truncated]...")

