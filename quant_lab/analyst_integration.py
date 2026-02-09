"""
四维数据整合模块
将 analyst_base.py 和 analyst_data.py 的数据合并
同时增强信号评估系统，支持估值、业绩维度的判断
"""

import logging
import re
from analyst_base import fetch_stock_data as fetch_base_data
from analyst_data import (
    fetch_valuation_data,
    fetch_performance_data,
    fetch_sentiment_data,
    fetch_macro_etf_data,
    fetch_consensus_data,
    fetch_market_env_data,
    fetch_lockup_data,
    fetch_chip_data,
    fetch_institution_data,
    fetch_competitor_data,
    fetch_smart_money_data,
    fetch_theme_sentiment_data,
    fetch_support_resistance_data,
)

logger = logging.getLogger(__name__)

# 上证指数代码白名单 (000开头的指数，避免与深圳主板股票冲突)
SH_INDEX_CODES = {
    "000001", "000016", "000300", "000688", "000852", "000905",
    "000906", "000932", "000985", "000991", "000993",
}


def detect_asset_type(code: str) -> str:
    """自动检测资产类型"""
    if code.startswith(("1A", "1B", "399", "931", "930", "H30", "sh000", "sz399")) or code in SH_INDEX_CODES:
        return "index"
    if code.startswith(("15", "16", "51", "56", "58")):
        return "etf"
    return "stock"


def fetch_stock_data(symbol: str, stock_name: str) -> dict:
    """
    兼容性接口：获取完整四维数据（默认使用缓存）
    直接替换原有 analyst_integration_cached.fetch_stock_data
    """
    return fetch_integrated_data(symbol, stock_name, use_cache=True)


def fetch_integrated_data(symbol: str, stock_name: str, asset_type: str = None, use_cache: bool = True) -> dict:
    """
    整合获取完整四维数据（统一入口）
    """
    if asset_type is None:
        asset_type = detect_asset_type(symbol)

    # 港股识别 (5位数字或HK后缀)
    is_hk = (len(symbol) == 5 and symbol.isdigit()) or symbol.endswith('.HK')

    if use_cache:
        # 动态导入以避免潜在的循环依赖，并利用现有的缓存层逻辑
        from analyst_cache import fetch_full_stock_data_cached
        try:
            return fetch_full_stock_data_cached(symbol, stock_name, asset_type)
        except Exception as e:
            logger.warning(f"⚠️ 缓存抓取失败，尝试实时抓取: {e}")

    # --- 以下为非缓存抓取逻辑 ---
    logger.info(f"\n{'='*60}\n🔄 实时抓取数据: {stock_name} ({symbol})\n{'='*60}\n")

    # A. 港股逻辑
    if is_hk:
        try:
            import akshare as ak
            df_hk = ak.stock_hk_main_board_spot_em()
            clean_symbol = symbol.replace('.HK', '').zfill(5)
            row = df_hk[df_hk['代码'] == clean_symbol].iloc[0]
            base_data = {
                'type': 'stock', 'name': stock_name, 'code': symbol,
                'price': float(row['最新价']), 'change_pct': float(row['涨跌幅']),
                'pe_ttm': f"{row['市盈率']:.2f}", 'pb': f"{row['市净率']:.2f}",
                'market_cap_display': f"{row['总市值']/1e8:.0f}亿港元",
                'news_summary': '港股暂不支持电报匹配', 'news_context': '无', 'money_summary': '暂无'
            }
            return base_data
        except Exception as e:
            logger.error(f"❌ 港股抓取失败: {e}")
            return {'error': str(e)}

    # B. A股逻辑 (原有逻辑增强)
    # 1. 获取基础数据 (自带内部重试)
    try:
        base_data = fetch_base_data(symbol, stock_name)
    except Exception as e:
        logger.error(f"❌ 基础数据抓取彻底失败: {e}")
        base_data = {'type': asset_type, 'name': stock_name, 'code': symbol, 'error': str(e)}

    # 2. 获取四维增强数据
    enhanced_data = {}

    def safe_fetch(func, name, *args, **kwargs):
        """带容错的抓取助手"""
        for attempt in range(2): # 简单重试一次
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == 0:
                    import time
                    time.sleep(1)
                    continue
                logger.warning(f"⚠️ {name} 获取失败: {type(e).__name__}")
        return {}

    if asset_type == "stock":
        # 估值维度
        valuation = safe_fetch(fetch_valuation_data, "估值", symbol, stock_name)
        enhanced_data.update(valuation)

        # 业绩维度
        performance = safe_fetch(fetch_performance_data, "业绩", symbol, stock_name)
        enhanced_data.update(performance)

        # 计算市销率 PS-TTM
        try:
            market_cap = enhanced_data.get('market_cap')
            revenue_raw = enhanced_data.get('revenue_ttm_raw')
            if market_cap and revenue_raw and revenue_raw > 0:
                ps_ttm = market_cap / revenue_raw
                enhanced_data['ps_ttm'] = f"{ps_ttm:.2f}"
                enhanced_data['ps_ttm_raw'] = ps_ttm
        except:
            pass

    # 资金情绪维度
    sentiment = safe_fetch(fetch_sentiment_data, "资金情绪", symbol, stock_name)
    enhanced_data.update(sentiment)

    # 宏观数据
    macro = safe_fetch(fetch_macro_etf_data, "宏观", symbol, asset_type)
    enhanced_data.update(macro)

    # 新增6个维度
    if asset_type == "stock":
        enhanced_data.update(safe_fetch(fetch_consensus_data, "一致预期", symbol, stock_name))
        enhanced_data.update(safe_fetch(fetch_market_env_data, "大盘环境", symbol, stock_name))
        enhanced_data.update(safe_fetch(fetch_lockup_data, "解禁风险", symbol, stock_name))
        enhanced_data.update(safe_fetch(fetch_chip_data, "筹码分布", symbol, stock_name))
        enhanced_data.update(safe_fetch(fetch_institution_data, "机构持仓", symbol, stock_name))
        enhanced_data.update(safe_fetch(fetch_competitor_data, "竞争对手", symbol, stock_name))
        enhanced_data.update(safe_fetch(fetch_smart_money_data, "聪明钱", symbol, stock_name))
        enhanced_data.update(safe_fetch(fetch_theme_sentiment_data, "情绪题材", symbol, stock_name))

    # 3. 合并数据
    integrated_data = {**base_data, **enhanced_data}

    # 3.5 支撑压力位需要合并后的 context（MA/BOLL/筹码数据）
    if asset_type == "stock":
        sr_data = safe_fetch(fetch_support_resistance_data, "支撑压力", symbol, stock_name, context=integrated_data)
        integrated_data.update(sr_data)

    # 4. 交叉计算：PEG
    try:
        pe_ttm_raw = integrated_data.get('pe_ttm_raw')
        eps_growth = integrated_data.get('eps_growth_rate_raw')
        if pe_ttm_raw and eps_growth and eps_growth > 0:
            peg = pe_ttm_raw / eps_growth
            integrated_data['peg'] = f"{peg:.2f}"
            integrated_data['peg_raw'] = peg
            if peg < 0.5:
                integrated_data['peg_signal'] = f"极度低估(PEG={peg:.2f}<0.5)"
            elif peg < 1:
                integrated_data['peg_signal'] = f"偏低估(PEG={peg:.2f}<1)"
            elif peg < 1.5:
                integrated_data['peg_signal'] = f"合理(PEG={peg:.2f})"
            elif peg < 2:
                integrated_data['peg_signal'] = f"偏高估(PEG={peg:.2f})"
            else:
                integrated_data['peg_signal'] = f"高估(PEG={peg:.2f}>2)"
    except Exception as e:
        logger.debug(f"PEG计算失败: {e}")

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

    # ==================== 原有信号（导入Brain逻辑）====================
    # 这里可以直接调用 AnalystBrain 的评估方法
    # 或者重新实现，以下是简化版示例

    # 1. 资金流向信号（优化版：适配市值）
    money_summary = data.get('money_summary', '')
    if '亿' in money_summary:
        import re
        match = re.search(r'([\d.]+)亿', money_summary)
        if match:
            amount = float(match.group(1))

            # 获取市值（亿元），如果没有市值数据则使用绝对金额阈值
            market_cap = data.get('market_cap_yi') or data.get('market_cap')
            if market_cap and market_cap > 0:
                # 计算资金占市值的百分比
                amount_ratio = (abs(amount) / market_cap) * 100

                if amount_ratio >= 5.0:  # 资金≥5%市值
                    signal_score += 3
                    triggers.append(f"💰 巨额资金异动: {amount}亿 (占市值{amount_ratio:.1f}%)")
                elif amount_ratio >= 2.0:  # 资金≥2%市值
                    signal_score += 2
                    triggers.append(f"💰 大额资金异动: {amount}亿 (占市值{amount_ratio:.1f}%)")
                elif amount_ratio >= 1.0:  # 资金≥1%市值
                    signal_score += 1
                    triggers.append(f"💰 资金异动: {amount}亿 (占市值{amount_ratio:.1f}%)")
            else:
                # 降级方案：无市值数据时使用绝对金额
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
            if div_rate >= 4.0:  # 降低阈值到4%
                signal_score += 2
                triggers.append(f"💵 高股息机会: {div_rate:.2f}% (≥4%)")
            elif div_rate >= 3.0:  # 新增：中等股息
                signal_score += 1
                triggers.append(f"💵 稳定股息: {div_rate:.2f}% (≥3%)")
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

            # 业绩翻倍：净利润同比增长>100%
            elif profit_growth > 100:
                signal_score += 3
                triggers.append(f"🚀 业绩翻倍: 净利润同比+{profit_growth:.1f}%")

            # 业绩高增长：净利润同比增长>30%（降低阈值）
            elif profit_growth > 30:
                signal_score += 2
                triggers.append(f"✅ 业绩高增长: 净利润同比+{profit_growth:.1f}%")
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

    # 9. 北向资金大幅流入/流出（优化版：适配市值）
    north_flow = data.get('north_flow_3d', 'N/A')
    if '亿' in north_flow:
        import re
        match = re.search(r'([\d.]+)亿', north_flow)
        if match:
            amount = float(match.group(1))

            # 获取市值，如果有市值数据则按比例计算
            market_cap = data.get('market_cap_yi') or data.get('market_cap')
            if market_cap and market_cap > 0:
                amount_ratio = (amount / market_cap) * 100

                if amount_ratio >= 2.0:  # 北向资金≥2%市值
                    signal_score += 2
                    triggers.append(f"🌏 北向资金大幅异动: {amount}亿 (占市值{amount_ratio:.1f}%)")
                elif amount_ratio >= 0.5:  # 北向资金≥0.5%市值
                    signal_score += 1
                    triggers.append(f"🌏 北向资金异动: {amount}亿 (占市值{amount_ratio:.1f}%)")
            else:
                # 降级方案：无市值数据时使用绝对金额
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

    # ==================== 新增：PEG信号 ====================

    # 10.5. PEG估值信号
    peg_raw = data.get('peg_raw')
    if peg_raw is not None:
        if peg_raw < 0.5:
            signal_score += 3
            triggers.append(f"✅ PEG极度低估: PEG={peg_raw:.2f} (<0.5)")
        elif peg_raw < 1:
            signal_score += 2
            triggers.append(f"✅ PEG偏低估: PEG={peg_raw:.2f} (<1)")
        elif peg_raw > 2:
            signal_score += 1
            triggers.append(f"⚠️ PEG偏高估: PEG={peg_raw:.2f} (>2)")

    # ==================== 新增：解禁/减持风险信号 ====================

    lockup_risk = data.get('lockup_risk_level', '')
    if lockup_risk == '高风险':
        signal_score += 3
        triggers.append(f"⚠️ 解禁高风险: 6月累计{data.get('lockup_6m_total_pct', 'N/A')}")
    elif lockup_risk == '中风险':
        signal_score += 1
        triggers.append(f"⚠️ 解禁中风险: 6月累计{data.get('lockup_6m_total_pct', 'N/A')}")

    # ==================== 新增：筹码信号 ====================

    chip_profit_raw = data.get('chip_profit_ratio_raw')
    if chip_profit_raw is not None:
        if chip_profit_raw > 90:
            signal_score += 2
            triggers.append(f"⚠️ 获利盘过重: {chip_profit_raw:.1f}% (>90%)")
        elif chip_profit_raw < 10:
            signal_score += 2
            triggers.append(f"📉 套牢盘极重: {chip_profit_raw:.1f}% (<10%)")

    # ==================== 新增：机构持仓变化信号 ====================

    fund_change = data.get('fund_holding_change', '')
    if fund_change:
        try:
            change_val = int(fund_change)
            if change_val >= 10:
                signal_score += 2
                triggers.append(f"✅ 基金大幅加仓: 机构数量{fund_change}")
            elif change_val <= -10:
                signal_score += 2
                triggers.append(f"⚠️ 基金大幅减仓: 机构数量{fund_change}")
        except ValueError:
            pass

    # ==================== 新增：大盘环境信号 ====================

    market_sentiment = data.get('market_sentiment', '')
    if market_sentiment == '偏冷':
        signal_score += 1
        triggers.append(f"🌧 大盘环境偏冷: {data.get('market_index_change_5d', 'N/A')}")

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

    # ==================== 新增：聪明钱/情绪信号 ====================

    # 15. 北向连续加仓
    north_consecutive = data.get('north_consecutive_days')
    if north_consecutive is not None:
        try:
            days = int(north_consecutive) if not isinstance(north_consecutive, int) else north_consecutive
            if days >= 5:
                signal_score += 2
                triggers.append(f"🌏 北向连续加仓{days}日: 聪明钱持续看好")
            elif days <= -5:
                signal_score += 2
                triggers.append(f"⚠️ 北向连续减仓{abs(days)}日: 聪明钱持续离场")
        except (ValueError, TypeError):
            pass

    # 16. 融券高位
    short_selling_level = data.get('short_selling_level', '')
    if '偏高' in short_selling_level or '高位' in short_selling_level:
        signal_score += 1
        triggers.append(f"⚠️ 融券占比偏高: {data.get('short_selling_ratio', 'N/A')}%")

    # 17. 情绪偏空+主力流出
    stock_sentiment = data.get('stock_sentiment', '')
    if '偏空' in stock_sentiment and '流出' in money_summary:
        signal_score += 1
        triggers.append(f"⚠️ 情绪偏空+主力流出: 双重利空信号")

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
        # Worker层：快速分析（qwen-flash）— 按优先级排序
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

        # 添加四维数据（如果是个股）
        if asset_type == "stock":
            # 估值维度
            if data.get('valuation_summary'):
                prompt += f"""
### 估值维度 (数据截至: {data.get('valuation_data_date', 'N/A')})
{data.get('valuation_summary', 'N/A')}
- 股息率: {data.get('dividend_yield', 'N/A')} (历史分位: {data.get('dividend_percentile', 'N/A')})
- PEG: {data.get('peg', 'N/A')} ({data.get('peg_signal', 'N/A')})
"""

            # 业绩维度
            if data.get('performance_summary'):
                prompt += f"""
### 业绩维度 (数据截至: {data.get('performance_data_date', 'N/A')})
{data.get('performance_summary', 'N/A')}
- 营收环比(QoQ): {data.get('revenue_qoq', 'N/A')}
- 净利润环比(QoQ): {data.get('profit_qoq', 'N/A')}
- 现金流质量: {data.get('cf_quality', 'N/A')}
"""

            # 分析师一致预期
            if data.get('consensus_summary'):
                prompt += f"""
### 分析师预期 (数据截至: {data.get('consensus_data_date', 'N/A')})
{data.get('consensus_summary', 'N/A')}
"""

        # 舆情面
        prompt += f"""
### 舆情面
{data.get('news_summary', 'N/A')}
{data.get('news_context', '')}

### 情绪与题材
{data.get('theme_sentiment_summary', 'N/A')}

### 支撑压力位
{data.get('support_resistance_summary', 'N/A')}
"""

        if asset_type == "stock":
            # 大盘/板块环境
            if data.get('market_env_summary'):
                prompt += f"""
### 大盘环境 (数据截至: {data.get('market_env_data_date', 'N/A')})
{data.get('market_env_summary', 'N/A')}
"""

            # 解禁风险
            if data.get('lockup_summary'):
                prompt += f"""
### 解禁风险 (数据截至: {data.get('lockup_data_date', 'N/A')})
{data.get('lockup_summary', 'N/A')}
"""

            # 筹码分布
            if data.get('chip_summary'):
                prompt += f"""
### 筹码分布 (数据截至: {data.get('chip_data_date', 'N/A')})
{data.get('chip_summary', 'N/A')}
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
- PEG: {data.get('peg', 'N/A')} ({data.get('peg_signal', 'N/A')})
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

    # 分析师一致预期区块
    consensus_section = ""
    if asset_type == "stock" and data.get('consensus_summary'):
        consensus_section = f"""
- {data.get('consensus_summary', 'N/A')}
- 预测EPS(当期): {data.get('eps_forecast_current', 'N/A')} | 预测EPS(下期): {data.get('eps_forecast_next', 'N/A')}
- 目标均价: {data.get('target_price_avg', 'N/A')} (区间: {data.get('target_price_low', 'N/A')} ~ {data.get('target_price_high', 'N/A')})
"""

    # 大盘/板块环境区块
    market_env_section = ""
    if asset_type == "stock" and data.get('market_env_summary'):
        market_env_section = f"""
- {data.get('market_env_summary', 'N/A')}
- 上证5日: {data.get('market_index_change_5d', 'N/A')} | 20日: {data.get('market_index_change_20d', 'N/A')}
- 板块: {data.get('sector_name', 'N/A')} 排名{data.get('sector_rank', 'N/A')} 今日{data.get('sector_change_today', 'N/A')}
"""

    # 解禁风险区块
    lockup_section = ""
    if asset_type == "stock" and data.get('lockup_summary'):
        lockup_section = f"""
- {data.get('lockup_summary', 'N/A')}
- 风险等级: {data.get('lockup_risk_level', 'N/A')}
"""
        lockup_events = data.get('lockup_events', [])
        for evt in lockup_events[:3]:
            lockup_section += f"  - {evt.get('date', 'N/A')} {evt.get('shares_display', '')} {evt.get('pct_of_float', '')}\n"

    # 筹码分布区块
    chip_section = ""
    if asset_type == "stock" and data.get('chip_summary'):
        chip_section = f"""
- {data.get('chip_summary', 'N/A')}
- 获利比例: {data.get('chip_profit_ratio', 'N/A')} | 平均成本: {data.get('chip_avg_cost', 'N/A')}
- 70%集中度: {data.get('chip_concentration_70', 'N/A')} | 90%集中度: {data.get('chip_concentration_90', 'N/A')}
"""

    # 机构持仓区块
    institution_section = ""
    if asset_type == "stock" and data.get('institution_summary'):
        institution_section = f"""
- {data.get('institution_summary', 'N/A')}
"""
        top_funds = data.get('top_funds', [])
        for f in top_funds[:3]:
            institution_section += f"  - {f.get('name', 'N/A')}: {f.get('shares', 'N/A')} {f.get('change', '')}\n"

    # 竞争对手区块
    competitor_section = ""
    if asset_type == "stock" and data.get('competitor_summary'):
        competitor_section = f"""
- {data.get('competitor_summary', 'N/A')}
"""
        competitors = data.get('competitors', [])
        for c in competitors[:5]:
            competitor_section += f"  - {c.get('name', 'N/A')}: ROE={c.get('roe', 'N/A')} 营收增速={c.get('revenue_yoy', 'N/A')} 毛利率={c.get('gross_margin', 'N/A')}\n"

    # 聪明钱区块
    smart_money_section = ""
    if asset_type == "stock" and data.get('smart_money_summary'):
        smart_money_section = f"""
- {data.get('smart_money_summary', 'N/A')}
- 北向连续: {data.get('north_consecutive_days', 'N/A')}日 | 3日变动: {data.get('north_change_pct_3d', 'N/A')}%
- 融资余额: {data.get('margin_balance', 'N/A')}亿 ({data.get('margin_balance_trend', 'N/A')})
- 融券占比: {data.get('short_selling_ratio', 'N/A')}% ({data.get('short_selling_level', 'N/A')})
"""

    # 情绪与题材区块
    theme_sentiment_section = ""
    if asset_type == "stock" and data.get('theme_sentiment_summary'):
        theme_sentiment_section = f"""
- {data.get('theme_sentiment_summary', 'N/A')}
"""

    # 支撑压力区块
    support_resistance_section = ""
    if asset_type == "stock" and data.get('support_resistance_summary'):
        support_resistance_section = f"""
- {data.get('support_resistance_summary', 'N/A')}
"""

    # 数据时效性标注
    data_dates = ""
    if asset_type == "stock":
        data_dates = f"""
**数据时效性标注**:
- 估值数据截至: {data.get('valuation_data_date', 'N/A')} (实时)
- 业绩数据截至: {data.get('performance_data_date', 'N/A')} (季报)
- 资金情绪截至: {data.get('sentiment_data_date', 'N/A')} (实时)
- 分析师预期截至: {data.get('consensus_data_date', 'N/A')} (近期研报)
- 大盘环境截至: {data.get('market_env_data_date', 'N/A')} (实时)
- 解禁日程截至: {data.get('lockup_data_date', 'N/A')} (日程表)
- 筹码分布截至: {data.get('chip_data_date', 'N/A')} (每日)
- 机构持仓截至: {data.get('institution_data_date', 'N/A')} (季报)
- 竞争对手截至: {data.get('competitor_data_date', 'N/A')} (季报)
- 聪明钱数据截至: {data.get('smart_money_data_date', 'N/A')} (近期)
- 情绪题材截至: {data.get('theme_sentiment_data_date', 'N/A')} (实时)
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

    # 扩展数据区块（BOLL、行业对比、季度趋势、十大股东）
    extended_section = ""
    if asset_type == "stock":
        # BOLL布林带
        boll_part = ""
        if data.get('boll_mid'):
            boll_part = f"""
**布林带(BOLL)**:
- 上轨: {data.get('boll_upper', 'N/A')} | 中轨: {data.get('boll_mid', 'N/A')} | 下轨: {data.get('boll_lower', 'N/A')}
- 当前位置: {data.get('boll_position', 'N/A')}% ({data.get('boll_status', 'N/A')})
- 带宽: {data.get('boll_width', 'N/A')}%
"""

        # 行业对比
        industry_part = ""
        if data.get('industry_name'):
            industry_part = f"""
**行业对比** ({data.get('industry_name', 'N/A')}，共{data.get('peer_count', '?')}家):
- ROE: 本公司 {data.get('roe_value', 'N/A')}% vs 行业中位数 {data.get('roe_median', 'N/A')}% (排名 {data.get('roe_rank', '?')}/{data.get('roe_total', '?')})
- 毛利率: 本公司 {data.get('gross_margin_value', 'N/A')}% vs 行业中位数 {data.get('gross_margin_median', 'N/A')}% (排名 {data.get('gross_margin_rank', '?')}/{data.get('gross_margin_total', '?')})
- 营收增速: 本公司 {data.get('revenue_yoy_value', 'N/A')}% vs 行业中位数 {data.get('revenue_yoy_median', 'N/A')}%
- 利润增速: 本公司 {data.get('profit_yoy_value', 'N/A')}% vs 行业中位数 {data.get('profit_yoy_median', 'N/A')}%
"""

        # 季度趋势
        quarterly_part = ""
        quarterly_trend = data.get('quarterly_trend', [])
        if quarterly_trend:
            quarterly_lines = []
            for q in quarterly_trend[:4]:  # 只取最近4期
                rev = f"{q['revenue']/1e8:.1f}亿" if q.get('revenue') else '-'
                rev_yoy = f"{q['revenue_yoy']:+.1f}%" if q.get('revenue_yoy') is not None else '-'
                profit = f"{q['net_profit']/1e8:.1f}亿" if q.get('net_profit') else '-'
                profit_yoy = f"{q['net_profit_yoy']:+.1f}%" if q.get('net_profit_yoy') is not None else '-'
                quarterly_lines.append(f"  - {q.get('report_name', '-')}: 营收{rev}({rev_yoy}), 归母净利{profit}({profit_yoy})")
            quarterly_part = f"""
**近4季度趋势**:
{chr(10).join(quarterly_lines)}
"""

        # 十大股东变动
        holders_part = ""
        top_holders = data.get('top_holders', [])
        if top_holders:
            prev_map = data.get('holders_prev_map', {})
            holder_lines = []
            for h in top_holders[:5]:  # 只取前5大
                name = h['name'][:15] + '...' if len(h['name']) > 15 else h['name']
                prev = prev_map.get(h['name'])
                if prev:
                    diff = h['shares'] - prev['shares']
                    change = f"+{diff/10000:.0f}万" if diff > 0 else (f"{diff/10000:.0f}万" if diff < 0 else "不变")
                else:
                    change = "新进"
                holder_lines.append(f"  - {name}: {h['shares']/10000:.0f}万股({h['pct']:.2f}%) [{change}]")
            holders_part = f"""
**十大流通股东变动** (截止{data.get('holders_report_date', '?')}):
{chr(10).join(holder_lines)}
"""

        extended_section = boll_part + industry_part + quarterly_part + holders_part

    # ========== 2. 根据版本选择 Prompt 模板 ==========

    if version == "value_first":
        prompt = _prompt_value_first(stock_name, stock_code, asset_type,
                                     valuation_section, performance_section,
                                     technical_section, sentiment_section, news_section, extended_section,
                                     consensus_section, market_env_section, lockup_section,
                                     chip_section, institution_section, competitor_section, data_dates,
                                     smart_money_section, theme_sentiment_section, support_resistance_section)
    elif version == "quant_hybrid":
        prompt = _prompt_quant_hybrid(stock_name, stock_code, asset_type,
                                      valuation_section, performance_section,
                                      technical_section, sentiment_section, news_section, extended_section,
                                      consensus_section, market_env_section, lockup_section,
                                      chip_section, institution_section, competitor_section, data_dates,
                                      smart_money_section, theme_sentiment_section, support_resistance_section)
    else:  # professional (default)
        prompt = _prompt_professional(stock_name, stock_code, asset_type,
                                      valuation_section, performance_section,
                                      technical_section, sentiment_section, news_section, extended_section,
                                      consensus_section, market_env_section, lockup_section,
                                      chip_section, institution_section, competitor_section, data_dates,
                                      smart_money_section, theme_sentiment_section, support_resistance_section)

    return prompt


def _prompt_value_first(name, code, asset_type, valuation, performance, technical, sentiment, news, extended="",
                        consensus="", market_env="", lockup="", chip="", institution="", competitor="", data_dates="",
                        smart_money="", theme_sentiment="", support_resistance="") -> str:
    """价值优先型 Prompt - 适合中长期价值投资"""
    if asset_type == "index":
        return _prompt_index_analysis(name, code, technical)
    if asset_type == "etf":
        return _prompt_etf_analysis(name, code, technical, sentiment, news)

    return f"""You are a senior quantitative analyst specializing in value investing with tactical trading.
Your investment philosophy: Long-term value as the anchor, technical indicators for timing.
Respond in Chinese (中文回答).

Analyze 【{name}】({code})

{data_dates}

**重要：数据时效性权重**
- 实时数据（今日行情/资金/筹码）：权重最高，直接影响短期判断
- 近期数据（1周内研报/解禁日程）：权重高
- 季度数据（财报/机构持仓/股东）：权重中，注意可能已滞后数月
- 年度数据（历史分位/年报）：权重低，仅作背景参考
请在分析中明确指出哪些结论基于滞后数据，可能存在偏差。

## Complete Data Matrix

### Valuation & Quote (估值行情)
{valuation}

### Technical Picture (技术面)
{technical}
{support_resistance}

### Capital & Smart Money (资金与聪明钱)
{sentiment}
{smart_money}
{chip}

### Fundamental Analysis (基本面)
{performance}

### Analyst Consensus & Institutions (预期与机构)
{consensus}
{institution}

### Risk Factors (风险因素)
{lockup}
{competitor}
{market_env}

### News & Sentiment (舆情与题材)
{news}
{theme_sentiment}

### Extended Data (扩展数据)
{extended}

## Analysis Framework

### Step 1: Valuation Assessment (价值评估)
- **Absolute Value**: Is current PE/PB historically cheap or expensive?
- **PEG Assessment**: Is growth-adjusted valuation attractive?
- **Dividend Shield**: Does dividend yield provide downside protection?
- **Quality-Adjusted Value**: Is valuation justified by cash flow quality?
- **Analyst Consensus**: What's the consensus target price upside?

### Step 2: Trend Confirmation (趋势确认)
- **Primary Trend**: Price vs MA250 (annual line) - bullish or bearish?
- **Secondary Trend**: Price vs MA20 - short-term direction
- **Momentum**: RSI/MACD signals - overbought/oversold?
- **Chip Distribution**: Profit ratio and concentration
- **Support/Resistance**: Key price levels from multiple indicators

### Step 3: Smart Money & Catalyst Check (聪明钱与催化剂)
- Smart money flow direction (northbound, margin trading)
- Capital flow direction and magnitude
- Market/sector environment support
- News events and theme sentiment
- Lockup expiry impact

### Step 4: Risk Assessment (风险评估)
- Lockup/restricted shares risk
- Institutional positioning changes
- Competitive landscape pressure

## Output Format (请用以下格式输出)

### 综合评级
**[看多/中性偏多/中性/中性偏空/看空]** | 置信度：[X]%

### 核心逻辑
[2-3句话，概括投资论点]

### 关键信号
1. [价值面信号 - 估值是否合理，PEG如何]
2. [技术面信号 - 趋势和择时，筹码支撑]
3. [资金面信号 - 聪明钱方向，主力资金流向]
4. [催化剂信号 - 事件或情绪驱动]
5. [风险信号 - 解禁/机构/竞争]

### 操作策略
- **短线（1-4周）**: [具体建议，包含入场点/目标位/止损位]
- **中线（1-6个月）**: [建仓区间/持仓策略/止盈条件]

### 风险提示
1. [技术面风险]
2. [基本面风险]
3. [市场系统性风险/解禁风险]
"""


def _prompt_quant_hybrid(name, code, asset_type, valuation, performance, technical, sentiment, news, extended="",
                         consensus="", market_env="", lockup="", chip="", institution="", competitor="", data_dates="",
                         smart_money="", theme_sentiment="", support_resistance="") -> str:
    """量化混合型 Prompt - 多因子打分系统"""
    if asset_type == "index":
        return _prompt_index_analysis(name, code, technical)
    if asset_type == "etf":
        return _prompt_etf_analysis(name, code, technical, sentiment, news)

    return f"""You are a quantitative analyst using a multi-factor scoring model.
Respond in Chinese (中文回答).

Analyze 【{name}】({code}) systematically.

{data_dates}

**重要：数据时效性权重**
- 实时数据（今日行情/资金/筹码）：权重最高，直接影响短期判断
- 近期数据（1周内研报/解禁日程）：权重高
- 季度数据（财报/机构持仓/股东）：权重中，注意可能已滞后数月
请在分析中明确指出哪些结论基于滞后数据，可能存在偏差。

## Data Matrix

### Factor 1: Valuation (权重25%)
{valuation}

### Factor 2: Momentum & Technical (权重15%)
{technical}
{support_resistance}

### Factor 3: Capital & Smart Money (权重15%)
{sentiment}
{smart_money}
{chip}

### Factor 4: Quality (权重20%)
{performance}

### Factor 5: Growth/Consensus (权重15%)
{consensus}
{institution}

### Factor 6: Environment & Risk (权重10%)
- 大盘环境:
{market_env}
- 解禁风险:
{lockup}
- 竞争对手:
{competitor}

### Catalyst Events & Sentiment
{news}
{theme_sentiment}

### Extended Data
{extended}

## Multi-Factor Scoring Framework

For each factor, assign a score from -2 to +2:
- +2: Strongly Bullish | +1: Mildly Bullish | 0: Neutral | -1: Mildly Bearish | -2: Strongly Bearish

**Valuation Scoring Guide:**
- PE<15 & PB<2 → +2 | PE<25 & PB<3 → +1 | PE 25-40 → 0 | PE>40 → -1 | PE>60 → -2
- Dividend yield >4% adds +1; PEG<1 adds +1

**Quality Scoring Guide:**
- Profit growth >30% with good cash flow → +2 | Growth >10% → +1 | Growth 0-10% → 0
- Profit decline 0-20% → -1 | Decline >20% or poor cash flow → -2

**Growth/Consensus Scoring Guide:**
- Strong buy consensus + high EPS growth forecast → +2 | Positive consensus → +1
- Mixed consensus → 0 | Downgrades → -1 | No coverage → 0

**Momentum Scoring Guide:**
- Above MA250, MACD bullish, RSI 40-60 → +2 | Above MA20 → +1 | Mixed signals → 0
- Below MA20 → -1 | Below MA250, bearish indicators → -2

**Sentiment & Smart Money Scoring Guide:**
- Large inflow + northbound accumulation + holder concentration → +2 | Moderate inflow → +1 | Neutral → 0
- Moderate outflow → -1 | Large outflow + margin selling + holder dispersion → -2

**Environment & Risk Scoring Guide:**
- Bullish market + hot sector + low lockup risk → +2 | Normal env → 0
- Bear market + cold sector + high lockup risk → -2

## Output Format (请用以下格式输出)

### 多因子评分

| 因子 | 得分 | 权重 | 加权分 |
|------|------|------|--------|
| 估值 | [X] | 25% | [Y] |
| 动量/技术 | [X] | 15% | [Y] |
| 资金/聪明钱 | [X] | 15% | [Y] |
| 质量 | [X] | 20% | [Y] |
| 增长/预期 | [X] | 15% | [Y] |
| 环境/风险 | [X] | 10% | [Y] |
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


def _prompt_professional(name, code, asset_type, valuation, performance, technical, sentiment, news, extended="",
                         consensus="", market_env="", lockup="", chip="", institution="", competitor="", data_dates="",
                         smart_money="", theme_sentiment="", support_resistance="") -> str:
    """专业分析师型 Prompt - 机构研报风格 (默认)"""
    if asset_type == "index":
        return _prompt_index_analysis(name, code, technical)
    if asset_type == "etf":
        return _prompt_etf_analysis(name, code, technical, sentiment, news)

    return f"""You are a buy-side equity analyst at a top asset management firm.
Write a concise investment memo in Chinese (中文).

【{name}】({code}) Investment Analysis

{data_dates}

**重要：数据时效性权重**
- 实时数据（今日行情/资金/筹码）：权重最高，直接影响短期判断
- 近期数据（1周内研报/解禁日程）：权重高
- 季度数据（财报/机构持仓/股东）：权重中，注意可能已滞后数月
- 年度数据（历史分位/年报）：权重低，仅作背景参考
请在分析中明确指出哪些结论基于滞后数据，可能存在偏差。

## Research Data

### Valuation & Quote (估值行情)
{valuation}

### Technical Picture (技术面)
{technical}
{support_resistance}

### Capital & Smart Money (资金与聪明钱)
{sentiment}
{smart_money}
{chip}

### Fundamental Analysis (基本面)
{performance}

### Analyst Consensus & Institutions (预期与机构)
{consensus}
{institution}

### Risk Factors (风险因素)
{lockup}
{competitor}
{market_env}

### News & Sentiment (舆情与题材)
{news}
{theme_sentiment}

### Extended Data (扩展数据)
{extended}

## Output Format (请用以下格式输出投资备忘录)

---

### 综合评级
**[看多/中性偏多/中性/中性偏空/看空]** | 置信度：[高/中/低] ([X]%)

### 核心逻辑
[1-2句话概括投资论点]

---

### 关键信号
1. **[估值信号]**: [具体描述，引用数据]
2. **[技术面信号]**: [具体描述，引用数据]
3. **[资金/聪明钱信号]**: [具体描述，引用数据]
4. **[基本面信号]**: [具体描述，引用数据]
5. **[风险/催化信号]**: [具体描述，引用数据]

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
1. **[风险类型]**: [风险描述] *(注明数据时效性)*
2. **[风险类型]**: [风险描述] *(注明数据时效性)*
3. **[解禁/减持风险]**: [风险描述]

---

**免责声明**：本分析基于公开数据和量化模型，不构成投资建议。股市有风险，投资需谨慎。
"""


def _prompt_etf_analysis(name, code, technical, sentiment="", news="") -> str:
    """ETF/LOF 专用分析 Prompt"""
    return f"""You are a senior ETF strategist and sector rotation analyst.
Respond in Chinese (中文回答).

Analyze ETF/LOF 【{name}】({code})

## Technical Data
{technical}

## Capital Flow & Sentiment
{sentiment}

## News & Events
{news}

## ETF Analysis Framework

### 1. Sector Trend (赛道趋势)
- Is the underlying sector/theme in an uptrend, downtrend, or consolidation?
- Price vs key moving averages (MA20, MA60, MA250)
- Momentum indicators (RSI, MACD)

### 2. Capital Flow (资金动向)
- Volume changes and turnover rate
- Premium/discount to NAV if available
- Institutional flow signals

### 3. Rotation Timing (轮动时机)
- Is this sector leading or lagging the broader market?
- Relative strength vs major indices
- Seasonal or policy catalysts

## Output Format (请用以下格式输出)

### 赛道判断
**[强势/中性/弱势]** | 趋势阶段: [上升/震荡/下行]

### 核心逻辑
[2-3句话概括当前赛道状态和预期方向]

### 关键技术位
- 支撑位: [价位] (依据)
- 压力位: [价位] (依据)

### 配置建议
- **短线（1-4周）**: [加仓/持有/减仓] — [理由]
- **中线（1-6月）**: [建议仓位比例] — [理由]

### 风险提示
1. [赛道风险]
2. [流动性风险]
3. [系统性风险]

**免责声明**：本分析基于公开数据和量化模型，不构成投资建议。
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

