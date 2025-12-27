"""
量化分析核心模块 - 增强版（四维数据）
作者：AI + 投资顾问指导
版本：2.0
功能：抓取估值、业绩、资金情绪、宏观折溢价四大维度数据
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import logging
import numpy as np

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)


# ==================== 维度1：估值数据 ====================

def fetch_valuation_data(symbol: str, stock_name: str) -> dict:
    """
    获取估值维度数据

    包含指标：
    - PE-TTM (滚动市盈率)
    - PB (市净率)
    - PS-TTM (市销率，需配合营收数据计算)
    - 股息率(TTM)

    Args:
        symbol: 股票代码
        stock_name: 股票名称

    Returns:
        估值数据字典
    """
    data = {}

    try:
        logging.info(f"📊 获取估值数据: {stock_name}")

        # 1. 获取基础估值指标（PE-TTM、PB、股息率）- 使用雪球实时数据
        try:
            # 转换代码格式: 000988 -> SZ000988, 600519 -> SH600519
            if symbol.startswith(('000', '001', '002', '003', '300')):
                xq_symbol = f"SZ{symbol}"
            else:
                xq_symbol = f"SH{symbol}"

            # 获取雪球实时行情数据
            spot_df = ak.stock_individual_spot_xq(symbol=xq_symbol)

            if not spot_df.empty:
                # 转换为字典方便查询
                spot_dict = dict(zip(spot_df['item'], spot_df['value']))

                # 提取关键估值指标
                pe_ttm = spot_dict.get('市盈率(TTM)', None)
                pb = spot_dict.get('市净率', None)
                dividend_yield = spot_dict.get('股息率(TTM)', None)
                market_cap = spot_dict.get('资产净值/总市值', None)  # 总市值

                # 格式化输出
                if pd.notna(pe_ttm) and pe_ttm > 0:
                    data['pe_ttm'] = f"{float(pe_ttm):.2f}"
                    data['pe_ttm_raw'] = float(pe_ttm)  # 原始数值供计算用
                else:
                    data['pe_ttm'] = "N/A"
                    data['pe_ttm_raw'] = None

                if pd.notna(pb) and pb > 0:
                    data['pb'] = f"{float(pb):.2f}"
                    data['pb_raw'] = float(pb)
                else:
                    data['pb'] = "N/A"
                    data['pb_raw'] = None

                # 市值（用于计算 PS）
                if pd.notna(market_cap) and market_cap > 0:
                    data['market_cap'] = float(market_cap)
                    data['market_cap_display'] = f"{float(market_cap)/1e8:.0f}亿"
                else:
                    data['market_cap'] = None
                    data['market_cap_display'] = "N/A"

                # PS 暂设为 N/A，将在整合数据时根据营收计算
                data['ps_ttm'] = "N/A"
                data['ps_ttm_raw'] = None

                # 股息率(TTM)
                if pd.notna(dividend_yield) and dividend_yield > 0:
                    data['dividend_yield'] = f"{float(dividend_yield):.2f}%"
                    data['dividend_yield_raw'] = float(dividend_yield)
                else:
                    data['dividend_yield'] = "无分红"
                    data['dividend_yield_raw'] = 0

                # 历史分位点暂不可用（需要历史数据）
                data['pe_percentile'] = "N/A"
                data['pb_percentile'] = "N/A"
                data['dividend_percentile'] = "N/A"

                # 生成 LLM 可读的摘要（后续会在整合时更新包含 PS）
                data['valuation_summary'] = (
                    f"PE-TTM: {data['pe_ttm']} | "
                    f"PB: {data['pb']} | "
                    f"PS-TTM: {data['ps_ttm']} | "
                    f"股息率(TTM): {data['dividend_yield']}"
                )

                logging.info(f"✓ 估值数据获取成功: PE-TTM={data['pe_ttm']}, PB={data['pb']}, 股息率={data['dividend_yield']}")
            else:
                raise ValueError("雪球数据为空")

        except Exception as e:
            logging.warning(f"估值指标获取失败: {type(e).__name__}")
            data['valuation_summary'] = "估值数据缺失"
            data['pe_ttm'] = "N/A"
            data['pb'] = "N/A"
            data['ps_ttm'] = "N/A"
            data['dividend_yield'] = "N/A"
            data['market_cap'] = None
            data['pe_percentile'] = "N/A"
            data['pb_percentile'] = "N/A"
            data['dividend_percentile'] = "N/A"

    except Exception as e:
        logging.error(f"❌ 估值维度数据获取失败: {type(e).__name__}")
        data['valuation_summary'] = "估值数据不可用"
        data['dividend_yield'] = "N/A"

    return data


# ==================== 维度2：业绩数据 ====================

# 业绩报表缓存（避免重复请求）
_yjbb_cache = {}

def fetch_performance_data(symbol: str, stock_name: str) -> dict:
    """
    获取业绩维度数据

    包含指标：
    - 营收增长率（YoY、QoQ）
    - 净利润增长率（YoY、QoQ）
    - 毛利率
    - 净资产收益率 (ROE)
    - 每股经营现金流

    Args:
        symbol: 股票代码
        stock_name: 股票名称

    Returns:
        业绩数据字典
    """
    global _yjbb_cache
    data = {}

    try:
        logging.info(f"📈 获取业绩数据: {stock_name}")

        # 使用业绩报表API（stock_yjbb_em）- 更稳定
        try:
            # 获取最近一期业绩报表（如 20240930 或 20240630）
            from datetime import datetime
            current_date = datetime.now()

            # 确定最近的报告期
            year = current_date.year
            month = current_date.month
            if month >= 10:
                report_date = f"{year}0930"  # 三季报
            elif month >= 7:
                report_date = f"{year}0630"  # 中报
            elif month >= 4:
                report_date = f"{year}0331"  # 一季报
            else:
                report_date = f"{year-1}1231"  # 上年年报

            # 检查缓存
            cache_key = report_date
            if cache_key not in _yjbb_cache:
                _yjbb_cache[cache_key] = ak.stock_yjbb_em(date=report_date)

            yjbb_df = _yjbb_cache[cache_key]

            if yjbb_df is not None and not yjbb_df.empty:
                # 查找当前股票
                stock_row = yjbb_df[yjbb_df['股票代码'] == symbol]

                if not stock_row.empty:
                    row = stock_row.iloc[0]

                    # 提取关键指标
                    revenue_yoy = row.get('营业总收入-同比增长', None)
                    revenue_qoq = row.get('营业总收入-季度环比增长', None)
                    profit_yoy = row.get('净利润-同比增长', None)
                    profit_qoq = row.get('净利润-季度环比增长', None)
                    gross_margin = row.get('销售毛利率', None)
                    roe = row.get('净资产收益率', None)
                    cf_per_share = row.get('每股经营现金流量', None)
                    eps = row.get('每股收益', None)
                    revenue_cumulative = row.get('营业总收入-营业总收入', None)  # 累计营收

                    # 计算 TTM 营收（用于 PS 计算）
                    # 根据报告期推算年化营收
                    if pd.notna(revenue_cumulative) and revenue_cumulative > 0:
                        if report_date.endswith('0930'):  # Q3: 9个月数据
                            revenue_ttm = revenue_cumulative * (4 / 3)
                        elif report_date.endswith('0630'):  # Q2: 6个月数据
                            revenue_ttm = revenue_cumulative * 2
                        elif report_date.endswith('0331'):  # Q1: 3个月数据
                            revenue_ttm = revenue_cumulative * 4
                        else:  # 年报: 12个月数据
                            revenue_ttm = revenue_cumulative
                        data['revenue_ttm_raw'] = revenue_ttm
                        data['revenue_ttm_display'] = f"{revenue_ttm/1e8:.2f}亿"
                    else:
                        data['revenue_ttm_raw'] = None
                        data['revenue_ttm_display'] = "N/A"

                    # 格式化输出
                    data['revenue_yoy'] = f"{revenue_yoy:.2f}%" if pd.notna(revenue_yoy) else "N/A"
                    data['revenue_qoq'] = f"{revenue_qoq:.2f}%" if pd.notna(revenue_qoq) else "N/A"
                    data['profit_yoy'] = f"{profit_yoy:.2f}%" if pd.notna(profit_yoy) else "N/A"
                    data['profit_qoq'] = f"{profit_qoq:.2f}%" if pd.notna(profit_qoq) else "N/A"
                    data['gross_margin'] = f"{gross_margin:.2f}%" if pd.notna(gross_margin) else "N/A"
                    data['net_margin'] = "N/A"  # 此 API 不提供净利率
                    data['roe'] = f"{roe:.2f}%" if pd.notna(roe) else "N/A"
                    data['eps'] = f"{eps:.2f}" if pd.notna(eps) else "N/A"

                    # 现金流质量评估
                    if pd.notna(cf_per_share) and pd.notna(eps) and eps != 0:
                        cf_ratio = cf_per_share / eps
                        data['cf_profit_ratio'] = f"{cf_ratio:.2f}"
                        if cf_ratio < 0.8:
                            data['cf_quality'] = "⚠️ 利润含金量较低"
                        elif cf_ratio > 1.2:
                            data['cf_quality'] = "✅ 优质现金流"
                        else:
                            data['cf_quality'] = "正常水平"
                    else:
                        data['cf_profit_ratio'] = "N/A"
                        data['cf_quality'] = "数据不足"

                    # 生成摘要
                    data['performance_summary'] = (
                        f"营收增长(YoY): {data['revenue_yoy']} | "
                        f"净利润增长(YoY): {data['profit_yoy']} | "
                        f"毛利率: {data['gross_margin']} | ROE: {data['roe']}"
                    )

                    logging.info(f"✓ 业绩数据获取成功")
                else:
                    raise ValueError(f"未找到 {symbol} 的业绩数据")
            else:
                raise ValueError("业绩报表数据为空")

        except Exception as e:
            logging.warning(f"利润表数据获取失败: {type(e).__name__}")
            data['performance_summary'] = "业绩数据缺失"
            data['revenue_yoy'] = "N/A"
            data['profit_yoy'] = "N/A"
            data['gross_margin'] = "N/A"
            data['net_margin'] = "N/A"
            data['cf_profit_ratio'] = "N/A"
            data['cf_quality'] = "数据缺失"

    except Exception as e:
        logging.error(f"❌ 业绩维度数据获取失败: {type(e).__name__}")
        data['performance_summary'] = "业绩数据不可用"

    return data


# ==================== 维度3：资金与情绪数据 ====================

# 实时行情缓存（避免重复请求大量数据）
_realtime_cache = {'data': None, 'time': None}

def fetch_sentiment_data(symbol: str, stock_name: str) -> dict:
    """
    获取资金与情绪维度数据

    包含指标：
    - 量比、换手率
    - 北向资金持仓变化
    - 主力资金流向

    Args:
        symbol: 股票代码
        stock_name: 股票名称

    Returns:
        资金情绪数据字典
    """
    global _realtime_cache
    data = {}

    try:
        logging.info(f"💰 获取资金情绪数据: {stock_name}")

        # 1. 获取实时行情（量比、换手率）- 使用雪球数据更稳定
        try:
            # 转换代码格式
            if symbol.startswith(('000', '001', '002', '003', '300')):
                xq_symbol = f"SZ{symbol}"
            else:
                xq_symbol = f"SH{symbol}"

            spot_df = ak.stock_individual_spot_xq(symbol=xq_symbol)

            if not spot_df.empty:
                spot_dict = dict(zip(spot_df['item'], spot_df['value']))

                volume_ratio = spot_dict.get('量比', None)  # 雪球可能没有量比
                turnover_rate = spot_dict.get('周转率', None)

                # 雪球用周转率表示换手率
                if pd.isna(turnover_rate):
                    turnover_rate = spot_dict.get('换手率', None)

                data['volume_ratio'] = f"{float(volume_ratio):.2f}" if pd.notna(volume_ratio) else "N/A"
                data['turnover_rate'] = f"{float(turnover_rate):.2f}%" if pd.notna(turnover_rate) else "N/A"

                # LLM 异动判断
                if pd.notna(volume_ratio):
                    vr = float(volume_ratio)
                    if vr > 2.0:
                        data['volume_alert'] = "⚠️ 放量异动（量比>2）"
                    elif vr < 0.5:
                        data['volume_alert'] = "缩量"
                    else:
                        data['volume_alert'] = "正常"
                else:
                    data['volume_alert'] = "N/A"

                logging.info(f"✓ 量比: {data['volume_ratio']}, 换手率: {data['turnover_rate']}")

        except Exception as e:
            logging.warning(f"实时行情获取失败: {type(e).__name__}")
            data['volume_ratio'] = "N/A"
            data['turnover_rate'] = "N/A"
            data['volume_alert'] = "N/A"

        # 2. 获取北向资金持仓数据
        try:
            north_df = ak.stock_hsgt_individual_em(symbol=symbol)

            if north_df is not None and not north_df.empty:
                # 取最近10个交易日
                recent = north_df.tail(10)

                # 计算最近变化
                if len(recent) >= 2:
                    latest_shares = recent.iloc[-1].get('持股数量', 0)
                    prev_shares = recent.iloc[0].get('持股数量', 0)

                    if prev_shares > 0:
                        change_pct = (latest_shares / prev_shares - 1) * 100
                        if change_pct > 0:
                            data['north_flow_3d'] = f"增持 {change_pct:.1f}%"
                        else:
                            data['north_flow_3d'] = f"减持 {abs(change_pct):.1f}%"
                    else:
                        data['north_flow_3d'] = "新进"

                    logging.info(f"✓ 北向资金: {data['north_flow_3d']}")
                else:
                    data['north_flow_3d'] = "数据不足"
            else:
                data['north_flow_3d'] = "无北向持仓"

        except Exception as e:
            logging.warning(f"北向资金获取失败: {type(e).__name__}")
            data['north_flow_3d'] = "N/A"

        # 3. 股东人数和机构持仓 - 这些 API 不稳定，暂时跳过
        data['holder_count'] = "N/A"
        data['holder_trend'] = "数据源维护中"
        data['institute_holding'] = "N/A"

        # 生成摘要
        data['sentiment_summary'] = (
            f"量比: {data.get('volume_ratio', 'N/A')} | "
            f"换手率: {data.get('turnover_rate', 'N/A')} | "
            f"北向资金: {data.get('north_flow_3d', 'N/A')}"
        )

    except Exception as e:
        logging.error(f"❌ 资金情绪维度数据获取失败: {type(e).__name__}")
        data['sentiment_summary'] = "资金情绪数据不可用"

    return data


# ==================== 维度4：宏观与ETF折溢价 ====================

def fetch_macro_etf_data(symbol: str, asset_type: str = "stock") -> dict:
    """
    获取宏观与ETF折溢价数据

    包含指标：
    - ETF折溢价率（仅ETF）
    - 离岸人民币汇率（USDCNH）

    Args:
        symbol: 代码
        asset_type: 资产类型（stock/etf/index）

    Returns:
        宏观数据字典
    """
    data = {}

    try:
        logging.info(f"🌍 获取宏观数据")

        # 1. ETF折溢价（仅针对ETF）
        if asset_type == "etf":
            try:
                etf_spot_df = ak.fund_etf_spot_em()

                etf_info = etf_spot_df[etf_spot_df['代码'] == symbol]

                if not etf_info.empty:
                    market_price = etf_info.iloc[0].get('最新价', 0)
                    nav = etf_info.iloc[0].get('实时净值', market_price)

                    # 计算折溢价率
                    premium_rate = (market_price / nav - 1) * 100 if nav > 0 else 0

                    data['etf_premium'] = f"{premium_rate:+.2f}%"

                    # LLM 交易建议
                    if premium_rate > 1.0:
                        data['premium_alert'] = "⚠️ 溢价超过1%，不建议买入"
                    elif premium_rate < -1.0:
                        data['premium_alert'] = "✅ 折价超过1%，可考虑买入"
                    else:
                        data['premium_alert'] = "正常范围"

                    logging.info(f"✓ ETF折溢价: {data['etf_premium']}")

            except Exception as e:
                logging.warning(f"ETF折溢价获取失败: {type(e).__name__}")
                data['etf_premium'] = "N/A"

        # 2. 离岸人民币汇率（全局宏观数据）
        try:
            # 获取USDCNH汇率
            fx_df = ak.fx_spot_quote()

            usdcnh_data = fx_df[fx_df['货币对'] == 'USDCNH']

            if not usdcnh_data.empty:
                current_rate = usdcnh_data.iloc[0]['买价']
                data['usdcnh_rate'] = f"{current_rate:.4f}"

                logging.info(f"✓ 离岸人民币汇率: {data['usdcnh_rate']}")
            else:
                data['usdcnh_rate'] = "N/A"

        except Exception as e:
            logging.warning(f"汇率数据获取失败: {type(e).__name__}")
            data['usdcnh_rate'] = "N/A"

    except Exception as e:
        logging.error(f"❌ 宏观维度数据获取失败: {type(e).__name__}")

    return data


# ==================== 主函数：整合四维数据 ====================

def fetch_full_stock_data(symbol: str, stock_name: str, asset_type: str = "stock") -> dict:
    """
    获取完整的四维数据

    Args:
        symbol: 股票代码
        stock_name: 股票名称
        asset_type: 资产类型（stock/etf/index）

    Returns:
        完整数据字典
    """
    logging.info(f"\n{'='*60}")
    logging.info(f"开始抓取四维数据: {stock_name} ({symbol})")
    logging.info(f"{'='*60}\n")

    result = {
        'code': symbol,
        'name': stock_name,
        'type': asset_type,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    # 维度1：估值
    if asset_type == "stock":
        valuation_data = fetch_valuation_data(symbol, stock_name)
        result.update(valuation_data)

    # 维度2：业绩
    if asset_type == "stock":
        performance_data = fetch_performance_data(symbol, stock_name)
        result.update(performance_data)

    # 维度3：资金情绪
    sentiment_data = fetch_sentiment_data(symbol, stock_name)
    result.update(sentiment_data)

    # 维度4：宏观与折溢价
    macro_data = fetch_macro_etf_data(symbol, asset_type)
    result.update(macro_data)

    logging.info(f"\n✅ 四维数据抓取完成！\n")

    return result


# ==================== 测试代码 ====================

if __name__ == "__main__":
    # 测试：广东宏大（002683）
    test_symbol = "002683"
    test_name = "广东宏大"

    data = fetch_full_stock_data(test_symbol, test_name, "stock")

    print("\n" + "="*60)
    print("四维数据抓取结果：")
    print("="*60)

    for key, value in data.items():
        print(f"{key}: {value}")
