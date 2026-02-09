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
import os  # 用于读取环境变量
from contextlib import contextmanager

# 全局禁用 tqdm 进度条（akshare 内部使用），避免干扰终端输出
os.environ['TQDM_DISABLE'] = '1'

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)


# ==================== 直连模式（已停用：本地代理是必要通道） ====================

@contextmanager
def no_proxy():
    """
    保留接口兼容性，不再实际禁用代理。
    本地代理(如 Clash 127.0.0.1:8118)是访问东方财富等接口的必要网络通道。
    """
    yield


# ==================== 历史分位计算助手 ====================





def _calculate_percentile_from_baidu(symbol: str, indicator: str) -> dict:


    """


    从百度股市通获取历史数据并计算分位


    indicator: '市盈率(TTM)', '市净率', '市现率'


    """


    percentiles = {}


    periods = [('近十年', '10y'), ('近五年', '5y'), ('近三年', '3y'), ('近一年', '1y')]


    


    for period_name, period_key in periods:


        try:


            # 动态导入ak以防万一


            import akshare as ak


            df = ak.stock_zh_valuation_baidu(symbol=symbol, indicator=indicator, period=period_name)


            if df is not None and not df.empty:


                values = df['value'].dropna()


                values = values[values > 0]


                if len(values) > 10:


                    current_value = values.iloc[-1]


                    percentile = (values < current_value).sum() / len(values) * 100


                    percentiles[period_key] = round(float(percentile), 1)


        except:


            continue


    return percentiles





# ==================== 维度1：估值数据 ====================





def fetch_valuation_data(symbol: str, stock_name: str) -> dict:


    """


    获取估值维度数据（智能降级策略 + 历史分位回填）


    """


    data = {}





    try:


        logging.info(f"📊 获取估值数据: {stock_name}")


        data['valuation_data_date'] = datetime.now().strftime('%Y-%m-%d %H:%M')





        # --- 1. 获取当前实时值 (雪球优先) ---


        xq_token = os.getenv('XUEQIU_TOKEN') or os.getenv('XQ_TOKEN')


        xq_success = False





        if xq_token:


            try:


                xq_symbol = f"SZ{symbol}" if symbol.startswith(('000', '001', '002', '003', '300')) else f"SH{symbol}"


                spot_df = ak.stock_individual_spot_xq(symbol=xq_symbol, token=xq_token)


                if not spot_df.empty:


                    spot_dict = dict(zip(spot_df['item'], spot_df['value']))


                    data['pe_ttm_raw'] = _safe_float(spot_dict.get('市盈率(TTM)'))


                    data['pb_raw'] = _safe_float(spot_dict.get('市净率'))


                    data['dividend_yield_raw'] = _safe_float(spot_dict.get('股息率(TTM)'))


                    market_cap = spot_dict.get('总市值') or spot_dict.get('资产净值/总市值')


                    data['market_cap'] = _safe_float(market_cap)


                    xq_success = True


            except: pass





        if not xq_success:


            # 降级到 AKShare 免费接口组合


            try:


                # 获取基础财务数据 (用于计算PE/PB)


                current_date = datetime.now()


                month = current_date.month


                report_date = f"{current_date.year}0930" if month >= 10 else (f"{current_date.year}0630" if month >= 7 else (f"{current_date.year}0331" if month >= 4 else f"{current_date.year-1}1231"))


                yjbb_df = ak.stock_yjbb_em(date=report_date)


                row = yjbb_df[yjbb_df['股票代码'] == symbol].iloc[0]


                eps = _safe_float(row.get('每股收益'))


                bvps = _safe_float(row.get('每股净资产'))


                


                # 获取最新价


                hist_df = ak.stock_zh_a_hist(symbol=symbol, period='daily', start_date=(datetime.now() - timedelta(days=7)).strftime('%Y%m%d'), adjust='')


                price = _safe_float(hist_df.iloc[-1]['收盘'])


                


                if price:


                    if eps and eps > 0: data['pe_ttm_raw'] = round(price / eps, 2)


                    if bvps and bvps > 0: data['pb_raw'] = round(price / bvps, 2)


                


                # 获取市值


                info_df = ak.stock_individual_info_em(symbol=symbol)


                data['market_cap'] = _safe_float(dict(zip(info_df['item'], info_df['value'])).get('总市值'))


            except: pass





        # --- 2. 获取历史分位数据 (新增整合逻辑) ---


        try:


            pe_pcts = _calculate_percentile_from_baidu(symbol, '市盈率(TTM)')


            if pe_pcts:


                data['pe_percentile'] = f"{pe_pcts.get('10y') or pe_pcts.get('5y') or 'N/A'}%"


                data['pe_percentiles'] = pe_pcts # 存入完整字典供后续使用


            


            pb_pcts = _calculate_percentile_from_baidu(symbol, '市净率')


            if pb_pcts:


                data['pb_percentile'] = f"{pb_pcts.get('10y') or pb_pcts.get('5y') or 'N/A'}%"


                data['pb_percentiles'] = pb_pcts


        except: pass





        # --- 3. 格式化输出 ---


        data['pe_ttm'] = f"{data['pe_ttm_raw']:.2f}" if data.get('pe_ttm_raw') else "N/A"


        data['pb'] = f"{data['pb_raw']:.2f}" if data.get('pb_raw') else "N/A"


        data['dividend_yield'] = f"{data.get('dividend_yield_raw'):.2f}%" if data.get('dividend_yield_raw') else "N/A"


        data['market_cap_display'] = f"{data['market_cap']/1e8:.0f}亿" if data.get('market_cap') else "N/A"





        data['valuation_summary'] = (


            f"PE-TTM: {data['pe_ttm']} (分位:{data.get('pe_percentile', 'N/A')}) | "


            f"PB: {data['pb']} (分位:{data.get('pb_percentile', 'N/A')}) | "


            f"股息率: {data['dividend_yield']}"


        )





        return data




    except Exception as e:
        logging.error(f"❌ 估值维度数据获取失败: {type(e).__name__}")
        # 返回降级数据
        data['valuation_summary'] = "估值数据缺失"
        data['pe_ttm'] = "N/A"
        data['pb'] = "N/A"
        data['ps_ttm'] = "N/A"
        data['dividend_yield'] = "N/A"
        data['market_cap'] = None
        data['market_cap_display'] = "N/A"
        data['pe_percentile'] = "N/A"
        data['pb_percentile'] = "N/A"
        data['dividend_percentile'] = "N/A"

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
        data['performance_data_date'] = 'N/A'  # 将在获取到数据后更新

        # 使用业绩报表API（stock_yjbb_em）- 更稳定
        try:
            # 获取最近一期业绩报表（如 20240930 或 20240630）
            from datetime import datetime
            current_date = datetime.now()

            # 确定最近的报告期（考虑财报披露时间）
            year = current_date.year
            month = current_date.month

            # 财报披露通常滞后，需要考虑实际可用性
            if month >= 11:  # 11-12月：当年三季报
                report_date = f"{year}0930"
            elif month >= 8:  # 8-10月：当年中报
                report_date = f"{year}0630"
            elif month >= 5:  # 5-7月：当年一季报
                report_date = f"{year}0331"
            else:  # 1-4月：上年三季报（年报可能未披露）
                report_date = f"{year-1}0930"

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

                    logging.info(f"✅ 业绩数据获取成功 (报告期: {report_date})")
                    data['performance_data_date'] = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
                else:
                    logging.warning(f"⚠️  数据源1: 在业绩报表({report_date})中未找到股票 {symbol}")
                    raise ValueError(f"业绩报表中未找到 {symbol}")
            else:
                logging.warning(f"⚠️  数据源1: 业绩报表数据为空 (date={report_date})")
                raise ValueError(f"业绩报表数据为空 (date={report_date})")

        except Exception as e:
            logging.warning(f"⚠️  利润表数据获取失败: {type(e).__name__} - {str(e)[:100]}")
            logging.info(f"💡 影响: 部分业绩指标不可用，将尝试其他数据源补充")
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
    获取资金与情绪维度数据（雪球优先方案）
    """
    global _realtime_cache
    data = {}

    try:
        logging.info(f"💰 获取资金情绪数据: {stock_name}")
        data['sentiment_data_date'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        xq_token = os.getenv('XUEQIU_TOKEN') or os.getenv('XQ_TOKEN')

        # 策略1: 优先尝试雪球API
        if xq_token:
            try:
                # 转换代码格式
                xq_symbol = f"SZ{symbol}" if symbol.startswith(('0', '3')) else f"SH{symbol}"
                spot_df = ak.stock_individual_spot_xq(symbol=xq_symbol, token=xq_token)

                if not spot_df.empty:
                    spot_dict = dict(zip(spot_df['item'], spot_df['value']))
                    vr = _safe_float(spot_dict.get('量比'))
                    tr = _safe_float(spot_dict.get('周转率') or spot_dict.get('换手率'))

                    data['volume_ratio'] = f"{vr:.2f}" if vr else "N/A"
                    data['turnover_rate'] = f"{tr:.2f}%" if tr else "N/A"
                    
                    if vr:
                        data['volume_alert'] = "⚠️ 放量" if vr > 2.0 else ("缩量" if vr < 0.5 else "正常")
                    
                    logging.info(f"✓ 资金情绪获取成功 (源: 雪球)")
            except: pass

        # 策略2: 降级到东财基础信息
        if 'turnover_rate' not in data:
            try:
                with no_proxy():
                    info_df = ak.stock_individual_info_em(symbol=symbol)
                if not info_df.empty:
                    info_dict = dict(zip(info_df['item'], info_df['value']))
                    tr = _safe_float(info_dict.get('换手率'))
                    data['turnover_rate'] = f"{tr:.2f}%" if tr else "N/A"
            except: pass

        # 2. 获取北向资金持仓数据 (东财此接口目前相对独立且稳定)
        try:
            with no_proxy():
                north_df = ak.stock_hsgt_individual_em(symbol=symbol)
            if north_df is not None and not north_df.empty:
                recent = north_df.tail(5)
                if len(recent) >= 2:
                    latest_shares = _safe_float(recent.iloc[-1].get('持股数量'))
                    prev_shares = _safe_float(recent.iloc[0].get('持股数量'))
                    if latest_shares and prev_shares:
                        diff = latest_shares - prev_shares
                        status = "增持" if diff > 0 else "减持"
                        data['north_flow_3d'] = f"{status} {abs(diff)/1e4:.0f}万股"
        except: pass

        # 生成摘要
        data['sentiment_summary'] = (
            f"量比: {data.get('volume_ratio', 'N/A')} | "
            f"换手: {data.get('turnover_rate', 'N/A')} | "
            f"北向: {data.get('north_flow_3d', 'N/A')}"
        )

    except Exception as e:
        logging.error(f"❌ 资金情绪抓取失败: {e}")
        data['sentiment_summary'] = "资金情绪不可用"

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


# ==================== 维度5：扩展数据（近20日行情、季度趋势、行业对比、十大股东） ====================

def _safe_float(value) -> float:
    """安全转换为浮点数"""
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def fetch_recent_20d_and_boll(symbol: str, stock_name: str) -> dict:
    """获取近20日行情 + BOLL布林带 (多源容错版)"""
    data = {}
    try:
        logging.info(f"📊 获取近20日行情: {stock_name}")
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')
        xq_token = os.getenv('XUEQIU_TOKEN') or os.getenv('XQ_TOKEN')

        hist_df = None
        # 策略1: 东财历史数据（stock_zh_a_hist_xq 已在 akshare 1.17 移除）
        try:
            with no_proxy():
                hist_df = ak.stock_zh_a_hist(symbol=symbol, period='daily', start_date=start_date, end_date=end_date, adjust='qfq')
            if hist_df is not None and not hist_df.empty:
                logging.info("✓ K线数据获取成功 (源: 东财)")
        except: pass

        if hist_df is not None and len(hist_df) >= 20:
            # 近20日行情
            recent_20d = hist_df.tail(20).copy()
            recent_20d['量比'] = recent_20d['成交量'] / recent_20d['成交量'].shift(1).rolling(window=5).mean()
            recent_20d['振幅'] = ((recent_20d['最高'] - recent_20d['最低']) / recent_20d['收盘'].shift(1)) * 100

            data['recent_20d_data'] = []
            for _, row in recent_20d.iterrows():
                day_data = {
                    'date': str(row.get('日期', ''))[:10],
                    'open': _safe_float(row.get('开盘')),
                    'close': _safe_float(row.get('收盘')),
                    'high': _safe_float(row.get('最高')),
                    'low': _safe_float(row.get('最低')),
                    'change_pct': _safe_float(row.get('涨跌幅')),
                    'amplitude': _safe_float(row.get('振幅')),
                    'volume': _safe_float(row.get('成交量')),
                    'amount': _safe_float(row.get('成交额')),
                    'turnover_rate': _safe_float(row.get('换手率')),
                    'volume_ratio': _safe_float(row.get('量比')),
                }
                data['recent_20d_data'].append(day_data)

            # BOLL布林带
            boll_mid = hist_df['收盘'].rolling(window=20).mean()
            boll_std = hist_df['收盘'].rolling(window=20).std()
            boll_upper = boll_mid + 2 * boll_std
            boll_lower = boll_mid - 2 * boll_std

            if pd.notna(boll_mid.iloc[-1]):
                data['boll_mid'] = round(boll_mid.iloc[-1], 2)
                data['boll_upper'] = round(boll_upper.iloc[-1], 2)
                data['boll_lower'] = round(boll_lower.iloc[-1], 2)
                if boll_mid.iloc[-1] > 0:
                    data['boll_width'] = round((boll_upper.iloc[-1] - boll_lower.iloc[-1]) / boll_mid.iloc[-1] * 100, 2)

                # 当前价位置
                current_price = _safe_float(hist_df.iloc[-1]['收盘'])
                if current_price and data['boll_upper'] and data['boll_lower']:
                    boll_range = data['boll_upper'] - data['boll_lower']
                    if boll_range > 0:
                        pos_pct = (current_price - data['boll_lower']) / boll_range * 100
                        data['boll_position'] = round(pos_pct, 1)
                        if pos_pct > 100:
                            data['boll_status'] = "突破上轨，极强"
                        elif pos_pct > 80:
                            data['boll_status'] = "接近上轨，偏强"
                        elif pos_pct < 0:
                            data['boll_status'] = "跌破下轨，极弱"
                        elif pos_pct < 20:
                            data['boll_status'] = "接近下轨，偏弱"
                        else:
                            data['boll_status'] = "中轨附近"

            logging.info(f"✓ 近20日行情获取完成")
    except Exception as e:
        logging.warning(f"近20日行情获取失败: {type(e).__name__}: {str(e)[:80]}")
    return data


def fetch_quarterly_trend(symbol: str, stock_name: str) -> dict:
    """获取近8季度营收/利润趋势"""
    data = {}
    try:
        logging.info(f"📊 获取季度趋势: {stock_name}")
        prefix = 'SH' if symbol.startswith('6') else 'SZ'
        df = ak.stock_profit_sheet_by_report_em(symbol=f'{prefix}{symbol}')

        if df is not None and not df.empty:
            data['quarterly_trend'] = []
            for _, row in df.head(8).iterrows():
                report_date = str(row.get('REPORT_DATE', ''))[:10]
                report_name = row.get('REPORT_DATE_NAME', '')
                revenue = _safe_float(row.get('OPERATE_INCOME'))
                revenue_yoy = _safe_float(row.get('OPERATE_INCOME_YOY'))
                net_profit = _safe_float(row.get('PARENT_NETPROFIT'))
                net_profit_yoy = _safe_float(row.get('PARENT_NETPROFIT_YOY'))

                data['quarterly_trend'].append({
                    'report_date': report_date,
                    'report_name': report_name,
                    'revenue': revenue,
                    'revenue_yoy': revenue_yoy,
                    'net_profit': net_profit,
                    'net_profit_yoy': net_profit_yoy,
                })
            logging.info(f"✓ 季度趋势获取完成 ({len(data['quarterly_trend'])}期)")
    except Exception as e:
        logging.warning(f"季度趋势获取失败: {type(e).__name__}: {str(e)[:80]}")
    return data


def fetch_industry_comparison(symbol: str, stock_name: str, report_date: str = '20250930') -> dict:
    """获取行业对比数据"""
    data = {}
    try:
        logging.info(f"📊 获取行业对比: {stock_name}")
        # 获取行业分类
        info_df = ak.stock_individual_info_em(symbol=symbol)
        industry = None
        if info_df is not None and not info_df.empty:
            row = info_df[info_df['item'] == '行业']
            if not row.empty:
                industry = row.iloc[0]['value']

        if not industry:
            return data

        data['industry_name'] = industry

        # 获取业绩报表
        df = ak.stock_yjbb_em(date=report_date)
        if df is None or df.empty:
            return data

        peers = df[df['所处行业'] == industry].copy()
        if peers.empty:
            return data

        data['peer_count'] = len(peers)
        me = peers[peers['股票代码'] == symbol]

        # 计算行业中位数和排名
        for col, key in [
            ('净资产收益率', 'roe'),
            ('销售毛利率', 'gross_margin'),
            ('营业总收入-同比增长', 'revenue_yoy'),
            ('净利润-同比增长', 'profit_yoy'),
        ]:
            valid = pd.to_numeric(peers[col], errors='coerce').dropna()
            if valid.empty:
                continue
            median_val = valid.median()
            data[f'{key}_median'] = round(median_val, 2)

            if not me.empty:
                my_val = pd.to_numeric(me[col].iloc[0], errors='coerce')
                if pd.notna(my_val):
                    rank = (valid < my_val).sum() + 1
                    data[f'{key}_rank'] = int(rank)
                    data[f'{key}_total'] = len(valid)
                    data[f'{key}_value'] = round(float(my_val), 2)

        logging.info(f"✓ 行业对比完成: {industry} ({data.get('peer_count', 0)}家)")
    except Exception as e:
        logging.warning(f"行业对比获取失败: {type(e).__name__}: {str(e)[:80]}")
    return data


def fetch_top_holders(symbol: str, stock_name: str) -> dict:
    """获取十大流通股东及变化"""
    data = {}
    try:
        logging.info(f"📊 获取十大流通股东: {stock_name}")
        df = ak.stock_circulate_stock_holder(symbol=symbol)

        if df is None or df.empty:
            return data

        dates = df['截止日期'].unique()
        if len(dates) < 1:
            return data

        # 最新一期
        latest_date = dates[0]
        latest = df[df['截止日期'] == latest_date].head(10)
        data['holders_report_date'] = str(latest_date)
        data['top_holders'] = []
        for _, row in latest.iterrows():
            data['top_holders'].append({
                'name': row['股东名称'],
                'shares': int(row['持股数量']),
                'pct': float(row['占流通股比例']),
                'type': row['股本性质'],
            })

        # 上一期（对比变化）
        if len(dates) >= 2:
            prev_date = dates[1]
            prev = df[df['截止日期'] == prev_date].head(10)
            data['holders_prev_date'] = str(prev_date)
            data['holders_prev_map'] = {}
            for _, row in prev.iterrows():
                data['holders_prev_map'][row['股东名称']] = {
                    'shares': int(row['持股数量']),
                    'pct': float(row['占流通股比例']),
                }

        logging.info(f"✓ 十大流通股东获取完成 (截止{latest_date})")
    except Exception as e:
        logging.warning(f"十大流通股东获取失败: {type(e).__name__}: {str(e)[:80]}")
    return data


# ==================== 维度6：分析师一致预期 + PEG ====================

def fetch_consensus_data(symbol: str, stock_name: str) -> dict:
    """
    获取分析师一致预期数据

    数据源：
    - ak.stock_profit_forecast_em() — 全市场盈利预测
    - ak.stock_institute_recommend_detail(symbol) — 个股评级历史 + 目标价

    Args:
        symbol: 股票代码
        stock_name: 股票名称

    Returns:
        分析师预期数据字典
    """
    data = {}

    try:
        logging.info(f"📊 获取分析师一致预期: {stock_name}")
        data['consensus_data_date'] = datetime.now().strftime('%Y-%m-%d')

        # 1. 获取盈利预测数据（优先同花顺，东财接口已不稳定）
        try:
            forecast_df = ak.stock_profit_forecast_ths(symbol=symbol)

            if forecast_df is not None and not forecast_df.empty:
                # 同花顺返回: 年度, 预测机构数, 最小值, 均值, 最大值, 行业平均数
                if len(forecast_df) >= 2:
                    data['eps_forecast_current'] = f"{forecast_df.iloc[0]['均值']:.2f}"
                    data['eps_forecast_current_raw'] = float(forecast_df.iloc[0]['均值'])
                    data['eps_forecast_next'] = f"{forecast_df.iloc[1]['均值']:.2f}"
                    data['eps_forecast_next_raw'] = float(forecast_df.iloc[1]['均值'])
                elif len(forecast_df) == 1:
                    data['eps_forecast_current'] = f"{forecast_df.iloc[0]['均值']:.2f}"
                    data['eps_forecast_current_raw'] = float(forecast_df.iloc[0]['均值'])

                logging.info(f"✓ 盈利预测获取成功 (源: 同花顺)")
        except Exception as e:
            logging.warning(f"盈利预测获取失败: {type(e).__name__}: {str(e)[:80]}")

        # 2. 获取机构评级历史和目标价
        try:
            recommend_df = ak.stock_institute_recommend_detail(symbol=symbol)

            if recommend_df is not None and not recommend_df.empty:
                # 取最近的记录
                recent = recommend_df.head(20)  # 最近20条评级

                if not recent.empty:
                    # 提取最新评级日期
                    date_col = None
                    for col in recent.columns:
                        if '日期' in col or 'date' in col.lower():
                            date_col = col
                            break
                    if date_col and recent[date_col].iloc[0]:
                        data['consensus_data_date'] = str(recent[date_col].iloc[0])[:10]

                    # 提取目标价
                    target_prices = []
                    for col in recent.columns:
                        if '目标价' in col:
                            for _, r in recent.iterrows():
                                tp = _safe_float(r.get(col))
                                if tp and tp > 0:
                                    target_prices.append(tp)

                    if target_prices:
                        data['target_price_avg'] = f"{sum(target_prices) / len(target_prices):.2f}"
                        data['target_price_high'] = f"{max(target_prices):.2f}"
                        data['target_price_low'] = f"{min(target_prices):.2f}"

                    # 统计评级分布（从最新评级列）
                    rating_col = None
                    for col in recent.columns:
                        if '评级' in col and '日期' not in col and '机构' not in col:
                            rating_col = col
                            break
                    if rating_col:
                        ratings = recent[rating_col].value_counts()
                        data['rating_buy'] = int(ratings.get('买入', 0))
                        data['rating_overweight'] = int(ratings.get('增持', 0))
                        data['rating_hold'] = int(ratings.get('中性', 0) + ratings.get('持有', 0))

                logging.info(f"✓ 机构评级获取成功")
        except Exception as e:
            logging.warning(f"机构评级获取失败: {type(e).__name__}: {str(e)[:80]}")

        # 3. 计算EPS增速和PEG（如果有数据）
        eps_current = data.get('eps_forecast_current_raw')
        eps_next = data.get('eps_forecast_next_raw')
        if eps_current and eps_next and eps_current > 0:
            growth_rate = (eps_next / eps_current - 1) * 100
            data['eps_growth_rate_raw'] = round(growth_rate, 2)
            data['eps_growth_rate'] = f"{growth_rate:.2f}%"

            # PEG信号
            if growth_rate > 0:
                data['peg_signal'] = f"预期EPS增速{growth_rate:.1f}%"
            else:
                data['peg_signal'] = f"预期EPS下降{growth_rate:.1f}%"

        # 4. 生成摘要
        parts = []
        if data.get('rating_buy') or data.get('rating_overweight'):
            buy = data.get('rating_buy', 0)
            overweight = data.get('rating_overweight', 0)
            hold = data.get('rating_hold', 0)
            parts.append(f"评级: 买入{buy}/增持{overweight}/持有{hold}")
        if data.get('target_price_avg'):
            parts.append(f"均价目标: {data['target_price_avg']}元")
        if data.get('eps_growth_rate'):
            parts.append(f"预期EPS增速: {data['eps_growth_rate']}")

        data['consensus_summary'] = ' | '.join(parts) if parts else '暂无分析师覆盖'

        logging.info(f"✅ 分析师一致预期获取完成")

    except Exception as e:
        logging.error(f"❌ 分析师一致预期获取失败: {type(e).__name__}")
        data['consensus_data_date'] = datetime.now().strftime('%Y-%m-%d')
        data['consensus_summary'] = '数据获取失败'

    return data


# ==================== 维度7：大盘/板块环境 ====================

# 模块级缓存（多只股票共享）
_index_cache = {'data': None, 'time': None}
_board_cache = {'data': None, 'time': None}

def fetch_market_env_data(symbol: str, stock_name: str) -> dict:
    """
    获取大盘/板块环境数据

    数据源：
    - ak.stock_zh_index_daily(symbol="sh000001") — 上证指数走势
    - ak.stock_board_industry_name_em() — 全行业板块实时排名
    - ak.stock_individual_info_em(symbol) — 个股所属行业

    Args:
        symbol: 股票代码
        stock_name: 股票名称

    Returns:
        大盘环境数据字典
    """
    global _index_cache, _board_cache
    data = {}

    try:
        logging.info(f"🌍 获取大盘/板块环境: {stock_name}")
        data['market_env_data_date'] = datetime.now().strftime('%Y-%m-%d')

        # 1. 上证指数走势（模块级缓存，5分钟内复用）
        now = datetime.now()
        if (_index_cache['data'] is None or _index_cache['time'] is None or
                (now - _index_cache['time']).total_seconds() > 300):
            try:
                index_df = ak.stock_zh_index_daily(symbol="sh000001")
                if index_df is not None and not index_df.empty:
                    _index_cache['data'] = index_df
                    _index_cache['time'] = now
            except Exception as e:
                logging.warning(f"上证指数获取失败: {type(e).__name__}: {str(e)[:80]}")

        if _index_cache['data'] is not None and not _index_cache['data'].empty:
            index_df = _index_cache['data']
            if len(index_df) >= 20:
                latest_close = _safe_float(index_df.iloc[-1]['close'])
                close_5d_ago = _safe_float(index_df.iloc[-6]['close']) if len(index_df) >= 6 else None
                close_20d_ago = _safe_float(index_df.iloc[-21]['close']) if len(index_df) >= 21 else None

                if latest_close and close_5d_ago:
                    change_5d = (latest_close / close_5d_ago - 1) * 100
                    data['market_index_change_5d'] = f"{change_5d:+.2f}%"

                if latest_close and close_20d_ago:
                    change_20d = (latest_close / close_20d_ago - 1) * 100
                    data['market_index_change_20d'] = f"{change_20d:+.2f}%"

                # MA20判断
                if len(index_df) >= 20:
                    ma20 = index_df.tail(20)['close'].astype(float).mean()
                    data['market_index_above_ma20'] = latest_close > ma20

                    # 市场情绪判断
                    if latest_close > ma20 and data.get('market_index_change_5d', '').startswith('+'):
                        data['market_sentiment'] = '偏暖'
                    elif latest_close < ma20 and data.get('market_index_change_5d', '').startswith('-'):
                        data['market_sentiment'] = '偏冷'
                    else:
                        data['market_sentiment'] = '中性'

                logging.info(f"✓ 上证指数: 5日{data.get('market_index_change_5d', 'N/A')}, 情绪{data.get('market_sentiment', 'N/A')}")

        # 2. 获取个股所属行业
        sector_name = None
        try:
            info_df = ak.stock_individual_info_em(symbol=symbol)
            if info_df is not None and not info_df.empty:
                row = info_df[info_df['item'] == '行业']
                if not row.empty:
                    sector_name = row.iloc[0]['value']
                    data['sector_name'] = sector_name
        except Exception as e:
            logging.warning(f"行业信息获取失败: {type(e).__name__}")

        # 3. 行业板块排名（模块级缓存，5分钟内复用）
        if (_board_cache['data'] is None or _board_cache['time'] is None or
                (now - _board_cache['time']).total_seconds() > 300):
            try:
                import requests
                old_timeout = requests.adapters.DEFAULT_RETRIES
                # push2.eastmoney.com 经常超时，限制重试
                board_df = ak.stock_board_industry_name_em()
                if board_df is not None and not board_df.empty:
                    _board_cache['data'] = board_df
                    _board_cache['time'] = now
            except Exception as e:
                logging.debug(f"行业板块排名获取失败: {type(e).__name__}: {str(e)[:60]}")

        if _board_cache['data'] is not None and not _board_cache['data'].empty and sector_name:
            board_df = _board_cache['data']
            total_sectors = len(board_df)

            # 查找当前行业排名
            # 尝试精确匹配
            sector_row = board_df[board_df['板块名称'] == sector_name]
            if sector_row.empty:
                # 尝试模糊匹配
                sector_row = board_df[board_df['板块名称'].str.contains(sector_name[:2], na=False)]

            if not sector_row.empty:
                row = sector_row.iloc[0]
                # 排名
                rank_idx = board_df.index.get_loc(sector_row.index[0]) + 1
                data['sector_rank'] = f"{rank_idx}/{total_sectors}"

                # 涨跌幅
                change_today = _safe_float(row.get('涨跌幅'))
                if change_today is not None:
                    data['sector_change_today'] = f"{change_today:+.2f}%"

                # 主力流入
                main_inflow = _safe_float(row.get('主力净流入'))
                if main_inflow is not None:
                    data['sector_main_inflow'] = f"{main_inflow/1e8:.1f}亿"

                logging.info(f"✓ 板块: {sector_name} 排名{data.get('sector_rank', 'N/A')}")

        # 生成摘要
        parts = []
        if data.get('market_sentiment'):
            parts.append(f"大盘{data['market_sentiment']}")
        if data.get('market_index_change_5d'):
            parts.append(f"5日{data['market_index_change_5d']}")
        if data.get('sector_name'):
            parts.append(f"板块[{data['sector_name']}]")
        if data.get('sector_rank'):
            parts.append(f"排名{data['sector_rank']}")

        data['market_env_summary'] = ' | '.join(parts) if parts else '大盘环境数据不可用'

        logging.info(f"✅ 大盘/板块环境获取完成")

    except Exception as e:
        logging.error(f"❌ 大盘/板块环境获取失败: {type(e).__name__}")
        data['market_env_data_date'] = datetime.now().strftime('%Y-%m-%d')
        data['market_env_summary'] = '数据获取失败'

    return data


# ==================== 维度8：解禁/减持风险 ====================

def fetch_lockup_data(symbol: str, stock_name: str) -> dict:
    """
    获取解禁/减持风险数据

    数据源：ak.stock_restricted_release_queue_em(symbol)

    Args:
        symbol: 股票代码
        stock_name: 股票名称

    Returns:
        解禁风险数据字典
    """
    data = {}

    try:
        logging.info(f"🔓 获取解禁/减持风险: {stock_name}")
        data['lockup_data_date'] = datetime.now().strftime('%Y-%m-%d')

        try:
            lockup_df = ak.stock_restricted_release_queue_em(symbol=symbol)

            if lockup_df is not None and not lockup_df.empty:
                today = datetime.now().date()
                six_months_later = today + timedelta(days=180)

                events = []
                total_pct_6m = 0.0

                for _, row in lockup_df.iterrows():
                    # 解析日期
                    release_date = None
                    for col in lockup_df.columns:
                        if '解禁' in col and '日期' in col:
                            try:
                                release_date = pd.to_datetime(row[col]).date()
                            except Exception:
                                pass
                            break

                    if release_date is None:
                        continue

                    # 只关注未来的解禁事件
                    if release_date < today:
                        continue

                    # 解禁股数
                    shares = None
                    for col in lockup_df.columns:
                        if '解禁' in col and ('股' in col or '数量' in col):
                            shares = _safe_float(row.get(col))
                            break

                    # 占流通比例
                    pct = None
                    for col in lockup_df.columns:
                        if '占' in col and ('流通' in col or '比' in col or '%' in col):
                            pct = _safe_float(row.get(col))
                            break

                    event = {
                        'date': str(release_date),
                    }

                    if shares:
                        if shares > 1e8:
                            event['shares_display'] = f"{shares/1e8:.2f}亿股"
                        else:
                            event['shares_display'] = f"{shares/1e4:.0f}万股"

                    if pct:
                        event['pct_of_float'] = f"{pct:.2f}%"
                        # 累加6个月内的解禁比例
                        if release_date <= six_months_later:
                            total_pct_6m += pct

                    events.append(event)

                data['lockup_events'] = events[:10]  # 最多保留10条

                if events:
                    data['lockup_nearest_date'] = events[0]['date']

                data['lockup_6m_total_pct'] = f"{total_pct_6m:.1f}%"

                # 风险等级评估
                max_single_pct = 0
                for e in events:
                    pct_str = e.get('pct_of_float', '0%')
                    try:
                        pct_val = float(pct_str.rstrip('%'))
                        max_single_pct = max(max_single_pct, pct_val)
                    except ValueError:
                        pass

                if max_single_pct > 5 or total_pct_6m > 10:
                    data['lockup_risk_level'] = '高风险'
                elif total_pct_6m > 3:
                    data['lockup_risk_level'] = '中风险'
                else:
                    data['lockup_risk_level'] = '低风险'

                logging.info(f"✓ 解禁数据: {len(events)}个事件, 6月累计{data['lockup_6m_total_pct']}, 风险{data['lockup_risk_level']}")

            else:
                data['lockup_events'] = []
                data['lockup_risk_level'] = '低风险'
                data['lockup_6m_total_pct'] = '0%'
                logging.info("✓ 无解禁数据")

        except Exception as e:
            logging.warning(f"解禁数据获取失败: {type(e).__name__}: {str(e)[:80]}")
            data['lockup_events'] = []
            data['lockup_risk_level'] = '未知'
            data['lockup_6m_total_pct'] = 'N/A'

        # 生成摘要
        if data.get('lockup_events'):
            nearest = data['lockup_events'][0]
            data['lockup_summary'] = f"最近解禁: {nearest.get('date', 'N/A')} {nearest.get('shares_display', '')} | 6月累计: {data['lockup_6m_total_pct']} | 风险: {data['lockup_risk_level']}"
        else:
            data['lockup_summary'] = '近期无解禁'

        logging.info(f"✅ 解禁/减持风险获取完成")

    except Exception as e:
        logging.error(f"❌ 解禁/减持风险获取失败: {type(e).__name__}")
        data['lockup_data_date'] = datetime.now().strftime('%Y-%m-%d')
        data['lockup_summary'] = '数据获取失败'

    return data


# ==================== 维度9：筹码分布 ====================

def _fetch_chip_from_datacenter(symbol: str) -> dict:
    """
    从东方财富 datacenter API 获取筹码相关数据

    这是一个备用数据源，当 push2his API 不可用时使用。
    返回主力成本等数据，虽然不是完整筹码分布，但可作为参考。

    Args:
        symbol: 股票代码

    Returns:
        筹码数据字典
    """
    import requests

    try:
        url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
        params = {
            "reportName": "RPT_DMSK_TS_STOCKNEW",
            "columns": "ALL",
            "filter": f'(SECURITY_CODE="{symbol}")',
            "pageNumber": 1,
            "pageSize": 1,
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
        }

        session = requests.Session()

        response = session.get(url, params=params, headers=headers, timeout=15)

        if response.status_code == 200:
            data = response.json()
            if data.get('result') and data['result'].get('data'):
                item = data['result']['data'][0]
                return {
                    'avg_cost': item.get('PRIME_COST'),  # 主力成本
                    'avg_cost_20d': item.get('PRIME_COST_20DAYS'),  # 20日成本
                    'avg_cost_60d': item.get('PRIME_COST_60DAYS'),  # 60日成本
                    'current_price': item.get('CLOSE_PRICE'),  # 当前价格
                    'turnover_rate': item.get('TURNOVERRATE'),  # 换手率
                    'source': 'datacenter',
                }

    except Exception as e:
        logging.debug(f"datacenter API 调用失败: {e}")

    return None


def fetch_chip_data(symbol: str, stock_name: str) -> dict:
    """
    获取筹码分布数据

    数据源策略（按优先级）：
    1. ak.stock_cyq_em - 东方财富完整筹码数据
    2. datacenter.eastmoney.com - 主力成本数据（备用）

    Args:
        symbol: 股票代码
        stock_name: 股票名称

    Returns:
        筹码分布数据字典
    """
    data = {}

    try:
        logging.info(f"📊 获取筹码分布: {stock_name}")
        data['chip_data_date'] = datetime.now().strftime('%Y-%m-%d')

        chip_fetched = False

        # 策略1: 东方财富完整筹码数据
        try:
            with no_proxy():
                chip_df = ak.stock_cyq_em(symbol=symbol, adjust="")

            if chip_df is not None and not chip_df.empty:
                latest = chip_df.iloc[-1]

                # 获利比例
                for col in chip_df.columns:
                    if '获利' in col and '比例' in col:
                        profit_ratio = _safe_float(latest.get(col))
                        if profit_ratio is not None:
                            data['chip_profit_ratio'] = f"{profit_ratio:.1f}%"
                            data['chip_profit_ratio_raw'] = profit_ratio
                            break

                # 平均成本
                for col in chip_df.columns:
                    if '平均' in col and '成本' in col:
                        avg_cost = _safe_float(latest.get(col))
                        if avg_cost is not None:
                            data['chip_avg_cost'] = f"{avg_cost:.2f}"
                            data['chip_avg_cost_raw'] = avg_cost
                            break

                # 集中度（70%/90%）
                for col in chip_df.columns:
                    if '90' in col and ('集中' in col or '成本' in col):
                        val = latest.get(col)
                        if val is not None:
                            data['chip_concentration_90'] = str(val)
                    elif '70' in col and ('集中' in col or '成本' in col):
                        val = latest.get(col)
                        if val is not None:
                            data['chip_concentration_70'] = str(val)

                # 筹码信号判断
                profit_ratio = data.get('chip_profit_ratio_raw')
                if profit_ratio is not None:
                    if profit_ratio > 80:
                        data['chip_signal'] = '获利盘过多，注意回调风险'
                    elif profit_ratio > 50:
                        data['chip_signal'] = '筹码偏集中，支撑较强'
                    elif profit_ratio < 20:
                        data['chip_signal'] = '套牢盘较重，下方有支撑'
                    else:
                        data['chip_signal'] = '筹码分布均衡'

                    chip_fetched = True
                    logging.info(f"✓ 筹码: 获利{data.get('chip_profit_ratio', 'N/A')}, 均价{data.get('chip_avg_cost', 'N/A')}")

        except Exception as e:
            logging.debug(f"stock_cyq_em 失败: {type(e).__name__}: {str(e)[:60]}")

        # 策略2: datacenter API（主力成本数据）
        if not chip_fetched:
            try:
                dc_data = _fetch_chip_from_datacenter(symbol)
                if dc_data and dc_data.get('avg_cost'):
                    avg_cost = dc_data['avg_cost']
                    current_price = dc_data.get('current_price', 0)

                    data['chip_avg_cost'] = f"{avg_cost:.2f}"
                    data['chip_avg_cost_raw'] = avg_cost

                    # 根据主力成本与当前价格比较给出信号
                    if current_price and avg_cost:
                        price_vs_cost = (current_price - avg_cost) / avg_cost * 100
                        if price_vs_cost > 10:
                            data['chip_signal'] = f'价格高于主力成本{price_vs_cost:.1f}%'
                            # 估算获利比例
                            data['chip_profit_ratio'] = f">{60 + min(price_vs_cost, 30):.0f}%"
                        elif price_vs_cost > 0:
                            data['chip_signal'] = f'略高于主力成本{price_vs_cost:.1f}%'
                            data['chip_profit_ratio'] = f"~{50 + price_vs_cost:.0f}%"
                        elif price_vs_cost > -10:
                            data['chip_signal'] = f'接近主力成本'
                            data['chip_profit_ratio'] = f"~{50 + price_vs_cost:.0f}%"
                        else:
                            data['chip_signal'] = f'价格低于主力成本{-price_vs_cost:.1f}%'
                            data['chip_profit_ratio'] = f"<{40 + price_vs_cost:.0f}%"

                    # 添加20日/60日成本信息到集中度字段
                    if dc_data.get('avg_cost_20d') and dc_data.get('avg_cost_60d'):
                        data['chip_concentration_70'] = f"20日成本:{dc_data['avg_cost_20d']:.2f}"
                        data['chip_concentration_90'] = f"60日成本:{dc_data['avg_cost_60d']:.2f}"

                    chip_fetched = True
                    logging.info(f"✓ 筹码(datacenter): 主力成本{data['chip_avg_cost']}")

            except Exception as e:
                logging.debug(f"datacenter API 失败: {type(e).__name__}: {str(e)[:60]}")

        if not chip_fetched:
            data['chip_signal'] = '数据暂不可用'
            logging.warning("⚠️  筹码数据: 所有数据源均不可用")

        # 生成摘要
        parts = []
        if data.get('chip_profit_ratio'):
            parts.append(f"获利{data['chip_profit_ratio']}")
        if data.get('chip_avg_cost'):
            parts.append(f"均价{data['chip_avg_cost']}")
        if data.get('chip_signal') and data['chip_signal'] not in ('N/A', '数据暂不可用'):
            parts.append(data['chip_signal'])

        data['chip_summary'] = ' | '.join(parts) if parts else '筹码数据不可用'

        logging.info(f"✅ 筹码分布获取完成")

    except Exception as e:
        logging.error(f"❌ 筹码分布获取失败: {type(e).__name__}")
        data['chip_data_date'] = datetime.now().strftime('%Y-%m-%d')
        data['chip_summary'] = '数据获取失败'

    return data


# ==================== 维度10：机构持仓变化 ====================

def _fetch_circulate_holders_sina(symbol: str) -> dict:
    """
    从新浪获取十大流通股东数据（备用数据源）

    Args:
        symbol: 股票代码

    Returns:
        股东数据字典
    """
    try:
        with no_proxy():
            df = ak.stock_circulate_stock_holder(symbol=symbol)

        if df is None or df.empty:
            return None

        # 获取最新一期的数据
        latest_date = df['截止日期'].max()
        latest_df = df[df['截止日期'] == latest_date]

        # 统计机构类型股东
        fund_count = 0
        fund_holders = []
        for _, row in latest_df.iterrows():
            holder_name = str(row.get('股东名称', ''))
            holder_type = str(row.get('股本性质', ''))
            ratio = row.get('占流通股比例', 0)

            # 判断是否为机构投资者
            is_fund = any(kw in holder_name for kw in ['基金', '社保', '保险', '信托', 'QFII', '证券'])
            is_fund = is_fund or ('境内法人' in holder_type or '境外法人' in holder_type)

            if is_fund and '有限公司' not in holder_name[:10]:  # 排除普通公司
                fund_count += 1
                fund_holders.append({
                    'name': holder_name[:20],
                    'ratio': f"{ratio}%",
                    'type': holder_type,
                })

        return {
            'report_date': str(latest_date)[:10],
            'fund_count': fund_count,
            'top_holders': fund_holders[:5],
            'total_holders': len(latest_df),
            'source': 'sina',
        }

    except Exception as e:
        logging.debug(f"新浪流通股东获取失败: {e}")
        return None


def fetch_institution_data(symbol: str, stock_name: str) -> dict:
    """
    获取机构持仓变化数据

    数据源策略（按优先级）：
    1. ak.stock_report_fund_hold - 东方财富基金持仓
    2. ak.stock_circulate_stock_holder - 新浪十大流通股东（备用）

    Args:
        symbol: 股票代码
        stock_name: 股票名称

    Returns:
        机构持仓数据字典
    """
    data = {}

    try:
        logging.info(f"🏦 获取机构持仓变化: {stock_name}")

        # 确定最近的报告期
        current_date = datetime.now()
        year = current_date.year
        month = current_date.month

        if month >= 11:
            quarter = f"{year}0930"
            quarter_name = f"{year}年三季报"
        elif month >= 8:
            quarter = f"{year}0630"
            quarter_name = f"{year}年中报"
        elif month >= 5:
            quarter = f"{year}0331"
            quarter_name = f"{year}年一季报"
        else:
            quarter = f"{year-1}0930"
            quarter_name = f"{year-1}年三季报"

        data['institution_data_date'] = f"{quarter[:4]}-{quarter[4:6]}-{quarter[6:]} ({quarter_name})"

        institution_fetched = False

        # 策略1: 东方财富基金持仓数据
        try:
            with no_proxy():
                fund_df = ak.stock_report_fund_hold(symbol=symbol, date=quarter)

            if fund_df is not None and not fund_df.empty:
                data['fund_holding_count'] = len(fund_df)

                # 提取前5大基金
                top_funds = []
                for _, row in fund_df.head(5).iterrows():
                    fund_info = {}
                    for col in fund_df.columns:
                        if '基金' in col and '名' in col:
                            fund_info['name'] = str(row[col])[:20]
                        elif '持股' in col and ('数' in col or '量' in col):
                            shares = _safe_float(row[col])
                            if shares:
                                fund_info['shares'] = f"{shares/1e4:.0f}万股"
                        elif '变动' in col or '增减' in col:
                            change = _safe_float(row[col])
                            if change:
                                fund_info['change'] = f"{change/1e4:+.0f}万股"

                    if fund_info.get('name'):
                        top_funds.append(fund_info)

                data['top_funds'] = top_funds

                # 持仓占比
                for col in fund_df.columns:
                    if '占' in col and ('流通' in col or '比' in col):
                        total_pct = fund_df[col].astype(float, errors='ignore').sum()
                        if total_pct > 0:
                            data['fund_holding_pct'] = f"{total_pct:.2f}%"
                            break

                institution_fetched = True
                logging.info(f"✓ 基金持仓: {data['fund_holding_count']}只基金")

        except Exception as e:
            logging.debug(f"东方财富基金持仓失败: {type(e).__name__}: {str(e)[:60]}")

        # 策略2: 新浪十大流通股东（备用）
        if not institution_fetched:
            try:
                sina_data = _fetch_circulate_holders_sina(symbol)
                if sina_data:
                    data['institution_data_date'] = sina_data['report_date']

                    # 统计机构股东
                    fund_count = sina_data.get('fund_count', 0)
                    data['fund_holding_count'] = fund_count

                    # 提取机构股东信息
                    top_funds = []
                    for holder in sina_data.get('top_holders', []):
                        top_funds.append({
                            'name': holder['name'],
                            'shares': holder['ratio'],
                        })
                    data['top_funds'] = top_funds

                    institution_fetched = True
                    logging.info(f"✓ 流通股东(新浪): {sina_data['total_holders']}位, 机构{fund_count}家")

            except Exception as e:
                logging.debug(f"新浪流通股东失败: {type(e).__name__}: {str(e)[:60]}")

        # 尝试获取前一期数据对比（仅东方财富）
        if institution_fetched and data.get('fund_holding_count', 0) > 0:
            try:
                if quarter.endswith('0930'):
                    prev_quarter = quarter[:4] + '0630'
                elif quarter.endswith('0630'):
                    prev_quarter = quarter[:4] + '0331'
                elif quarter.endswith('0331'):
                    prev_quarter = str(int(quarter[:4]) - 1) + '1231'
                else:
                    prev_quarter = quarter[:4] + '0930'

                with no_proxy():
                    prev_fund_df = ak.stock_report_fund_hold(symbol=symbol, date=prev_quarter)

                if prev_fund_df is not None and not prev_fund_df.empty:
                    data['fund_holding_count_prev'] = len(prev_fund_df)
                    change = data.get('fund_holding_count', 0) - data['fund_holding_count_prev']
                    data['fund_holding_change'] = f"{change:+d}"
                    logging.info(f"✓ 基金变动: {data['fund_holding_change']}")
            except Exception as e:
                logging.debug(f"前期数据获取失败: {type(e).__name__}")

        # 生成摘要
        parts = []
        if data.get('fund_holding_count', 0) > 0:
            parts.append(f"{data['fund_holding_count']}家机构持仓")
        if data.get('fund_holding_change'):
            parts.append(f"较上期{data['fund_holding_change']}")
        if data.get('fund_holding_pct'):
            parts.append(f"合计占比{data['fund_holding_pct']}")
        if data.get('top_funds'):
            top_names = [f['name'][:8] for f in data['top_funds'][:2]]
            parts.append(f"含{', '.join(top_names)}")

        data['institution_summary'] = ' | '.join(parts) if parts else '暂无机构持仓数据'

        logging.info(f"✅ 机构持仓变化获取完成")

    except Exception as e:
        logging.error(f"❌ 机构持仓变化获取失败: {type(e).__name__}")
        data['institution_data_date'] = datetime.now().strftime('%Y-%m-%d')
        data['institution_summary'] = '数据获取失败'

    return data


# ==================== 维度11：竞争对手对比 ====================

def _fetch_industry_from_xueqiu(symbol: str) -> str:
    """
    从雪球获取行业分类（备用数据源）

    Args:
        symbol: 股票代码

    Returns:
        行业名称
    """
    try:
        # 转换股票代码格式
        if symbol.startswith('6'):
            xq_symbol = f"SH{symbol}"
        else:
            xq_symbol = f"SZ{symbol}"

        xq_token = os.getenv('XUEQIU_TOKEN') or os.getenv('XQ_TOKEN')
        if not xq_token:
            return None

        # 使用雪球基本信息 API
        with no_proxy():
            df = ak.stock_individual_basic_info_xq(symbol=xq_symbol, token=xq_token)

        if df is not None and not df.empty:
            # 查找行业字段
            for _, row in df.iterrows():
                if row['item'] == 'affiliate_industry':
                    industry_data = row['value']
                    if isinstance(industry_data, dict):
                        return industry_data.get('ind_name')
                    elif isinstance(industry_data, str):
                        return industry_data

    except Exception as e:
        logging.debug(f"雪球行业信息获取失败: {e}")

    return None


def fetch_competitor_data(symbol: str, stock_name: str) -> dict:
    """
    获取竞争对手对比数据

    数据源策略（按优先级）：
    1. ak.stock_individual_info_em + ak.stock_yjbb_em - 东方财富行业+业绩
    2. ak.stock_individual_basic_info_xq - 雪球行业分类（备用）

    Args:
        symbol: 股票代码
        stock_name: 股票名称

    Returns:
        竞争对手对比数据字典
    """
    global _yjbb_cache
    data = {}

    try:
        logging.info(f"🔍 获取竞争对手对比: {stock_name}")

        # 确定报告期
        current_date = datetime.now()
        year = current_date.year
        month = current_date.month

        if month >= 11:
            report_date = f"{year}0930"
        elif month >= 8:
            report_date = f"{year}0630"
        elif month >= 5:
            report_date = f"{year}0331"
        else:
            report_date = f"{year-1}0930"

        data['competitor_data_date'] = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"

        # 1. 获取行业分类 (多源优先逻辑)
        industry = None
        xq_token = os.getenv('XUEQIU_TOKEN') or os.getenv('XQ_TOKEN')

        # 策略1: 优先尝试雪球 (因为东财 push2 最近极其不稳定)
        if xq_token:
            try:
                industry = _fetch_industry_from_xueqiu(symbol)
                if industry: logging.info(f"✓ 行业分类获取成功 (源: 雪球): {industry}")
            except: pass

        # 策略2: 备份尝试东财
        if not industry:
            try:
                with no_proxy():
                    info_df = ak.stock_individual_info_em(symbol=symbol)
                if info_df is not None and not info_df.empty:
                    row = info_df[info_df['item'] == '行业']
                    if not row.empty:
                        industry = row.iloc[0]['value']
                        logging.info(f"✓ 行业分类获取成功 (源: 东财): {industry}")
            except: pass

        if not industry:
            data['competitor_summary'] = '无法获取行业分类'
            logging.warning("⚠️  无法获取行业分类")
            return data

        data['industry_name'] = industry

        # 2. 获取同行业业绩数据（复用缓存）
        try:
            if report_date not in _yjbb_cache:
                with no_proxy():
                    _yjbb_cache[report_date] = ak.stock_yjbb_em(date=report_date)

            yjbb_df = _yjbb_cache[report_date]

            if yjbb_df is not None and not yjbb_df.empty:
                # 筛选同行业
                peers = yjbb_df[yjbb_df['所处行业'] == industry].copy()

                if not peers.empty:
                    # 按市值或营收排序（取前5名竞争对手）
                    # 先排除自身
                    competitors = peers[peers['股票代码'] != symbol]

                    # 尝试按营收排序
                    revenue_col = '营业总收入-营业总收入'
                    if revenue_col in competitors.columns:
                        competitors = competitors.copy()
                        competitors[revenue_col] = pd.to_numeric(competitors[revenue_col], errors='coerce')
                        competitors = competitors.sort_values(revenue_col, ascending=False)

                    comp_list = []
                    for _, row in competitors.head(5).iterrows():
                        comp = {
                            'code': row.get('股票代码', ''),
                            'name': row.get('股票简称', ''),
                        }

                        # PE (需要从其他数据源计算，此处使用业绩报表的基本指标)
                        roe = row.get('净资产收益率')
                        if pd.notna(roe):
                            comp['roe'] = f"{float(roe):.2f}%"

                        revenue_yoy = row.get('营业总收入-同比增长')
                        if pd.notna(revenue_yoy):
                            comp['revenue_yoy'] = f"{float(revenue_yoy):.2f}%"

                        profit_yoy = row.get('净利润-同比增长')
                        if pd.notna(profit_yoy):
                            comp['profit_yoy'] = f"{float(profit_yoy):.2f}%"

                        gross_margin = row.get('销售毛利率')
                        if pd.notna(gross_margin):
                            comp['gross_margin'] = f"{float(gross_margin):.2f}%"

                        comp_list.append(comp)

                    data['competitors'] = comp_list
                    data['industry_peer_count'] = len(peers)

                    logging.info(f"✓ 竞争对手: {industry} ({len(comp_list)}家)")

        except Exception as e:
            logging.debug(f"竞争对手业绩数据失败: {type(e).__name__}: {str(e)[:60]}")

        # 生成摘要
        if data.get('competitors'):
            names = [c.get('name', '') for c in data['competitors'][:3]]
            data['competitor_summary'] = f"行业: {industry} | 主要对手: {', '.join(names)}"
        else:
            data['competitor_summary'] = f"行业: {industry}" if industry else '暂无竞争对手数据'

        logging.info(f"✅ 竞争对手对比获取完成")

    except Exception as e:
        logging.error(f"❌ 竞争对手对比获取失败: {type(e).__name__}")
        data['competitor_data_date'] = datetime.now().strftime('%Y-%m-%d')
        data['competitor_summary'] = '数据获取失败'

    return data


# ==================== 维度14：聪明钱动向 ====================

# 概念板块缓存（5分钟有效）
_concept_board_cache = {'data': None, 'time': None}


def fetch_smart_money_data(symbol: str, stock_name: str) -> dict:
    """
    获取聪明钱动向数据（北向资金 + 融资融券）

    数据源：
    - ak.stock_hsgt_individual_em(symbol) — 北向资金个股持股
    - ak.stock_margin_detail_sse / szse — 融资融券

    Args:
        symbol: 股票代码
        stock_name: 股票名称

    Returns:
        聪明钱动向数据字典
    """
    data = {}

    try:
        logging.info(f"🧠 获取聪明钱动向: {stock_name}")
        data['smart_money_data_date'] = datetime.now().strftime('%Y-%m-%d')

        # 1. 北向资金（沪深港通个股持股）
        try:
            hsgt_df = ak.stock_hsgt_individual_em(symbol=symbol)
            if hsgt_df is not None and not hsgt_df.empty:
                recent = hsgt_df.tail(10).copy()

                # 计算连续加/减仓天数
                if '持股数量' in recent.columns or '持股' in str(recent.columns):
                    hold_col = None
                    for col in recent.columns:
                        if '持股数量' in str(col) or '持股' in str(col):
                            hold_col = col
                            break

                    if hold_col and len(recent) >= 2:
                        diffs = recent[hold_col].diff().dropna()
                        consecutive = 0
                        for d in reversed(diffs.values):
                            d_val = _safe_float(d)
                            if d_val is None:
                                break
                            if d_val > 0:
                                if consecutive >= 0:
                                    consecutive += 1
                                else:
                                    break
                            elif d_val < 0:
                                if consecutive <= 0:
                                    consecutive -= 1
                                else:
                                    break
                            else:
                                break
                        data['north_consecutive_days'] = consecutive

                    # 3日变动百分比
                    if hold_col and len(recent) >= 4:
                        try:
                            val_now = _safe_float(recent[hold_col].iloc[-1])
                            val_3d = _safe_float(recent[hold_col].iloc[-4])
                            if val_now and val_3d and val_3d > 0:
                                data['north_change_pct_3d'] = round((val_now / val_3d - 1) * 100, 2)
                        except Exception:
                            pass

                # 持股占比
                for col in recent.columns:
                    if '占' in str(col) and ('流通' in str(col) or '比' in str(col)):
                        val = _safe_float(recent[col].iloc[-1])
                        if val is not None:
                            data['north_holding_ratio'] = round(val, 2)
                            break

                logging.info(f"✓ 北向资金获取成功")
        except Exception as e:
            logging.debug(f"北向资金获取失败: {type(e).__name__}: {str(e)[:80]}")

        # 2. 融资融券
        try:
            margin_df = None
            if symbol.startswith('6'):
                try:
                    margin_df = ak.stock_margin_detail_sse(symbol=symbol)
                except Exception:
                    pass
            else:
                try:
                    margin_df = ak.stock_margin_detail_szse(symbol=symbol)
                except Exception:
                    pass

            if margin_df is not None and not margin_df.empty:
                recent_m = margin_df.tail(5).copy()

                # 融资余额（亿）
                for col in recent_m.columns:
                    if '融资余额' in str(col):
                        val = _safe_float(recent_m[col].iloc[-1])
                        if val is not None:
                            data['margin_balance'] = round(val / 1e8, 2)
                            # 趋势判断
                            if len(recent_m) >= 3:
                                val_prev = _safe_float(recent_m[col].iloc[-3])
                                if val_prev:
                                    diff_pct = (val / val_prev - 1) * 100
                                    if diff_pct > 1:
                                        data['margin_balance_trend'] = '增'
                                    elif diff_pct < -1:
                                        data['margin_balance_trend'] = '减'
                                    else:
                                        data['margin_balance_trend'] = '平'
                        break

                # 融券余额占比
                rq_col = None
                rz_col = None
                for col in recent_m.columns:
                    if '融券余额' in str(col) and '融券余量' not in str(col):
                        rq_col = col
                    if '融资余额' in str(col):
                        rz_col = col
                if rq_col and rz_col:
                    rq_val = _safe_float(recent_m[rq_col].iloc[-1])
                    rz_val = _safe_float(recent_m[rz_col].iloc[-1])
                    if rq_val and rz_val and rz_val > 0:
                        ratio = rq_val / (rq_val + rz_val) * 100
                        data['short_selling_ratio'] = round(ratio, 2)
                        if ratio > 20:
                            data['short_selling_level'] = '高位'
                        elif ratio < 5:
                            data['short_selling_level'] = '低位'
                        else:
                            data['short_selling_level'] = '正常'

                logging.info(f"✓ 融资融券获取成功")
        except Exception as e:
            logging.debug(f"融资融券获取失败: {type(e).__name__}: {str(e)[:80]}")

        # 3. 生成摘要
        parts = []
        nc = data.get('north_consecutive_days')
        if nc is not None:
            if nc > 0:
                pct_str = f" ({data['north_change_pct_3d']:+.2f}%)" if data.get('north_change_pct_3d') is not None else ""
                parts.append(f"北向连续{nc}日加仓{pct_str}")
            elif nc < 0:
                pct_str = f" ({data['north_change_pct_3d']:+.2f}%)" if data.get('north_change_pct_3d') is not None else ""
                parts.append(f"北向连续{abs(nc)}日减仓{pct_str}")
            else:
                parts.append("北向持仓持平")

        sl = data.get('short_selling_level')
        sr = data.get('short_selling_ratio')
        if sl:
            parts.append(f"融券余额：{sl}({sr:.1f}%)" if sr else f"融券余额：{sl}")

        mb = data.get('margin_balance')
        mt = data.get('margin_balance_trend')
        if mb is not None:
            parts.append(f"融资余额{mb:.1f}亿({mt or '?'})")

        data['smart_money_summary'] = ' | '.join(parts) if parts else '暂无聪明钱数据'

        logging.info(f"✅ 聪明钱动向获取完成")

    except Exception as e:
        logging.error(f"❌ 聪明钱动向获取失败: {type(e).__name__}")
        data['smart_money_data_date'] = datetime.now().strftime('%Y-%m-%d')
        data['smart_money_summary'] = '数据获取失败'

    return data


# ==================== 维度15：情绪与题材 ====================


def fetch_theme_sentiment_data(symbol: str, stock_name: str) -> dict:
    """
    获取情绪与题材数据

    数据源：
    - ak.stock_comment_detail_zlkp_jgcyd_em(symbol) — 机构参与度
    - ak.stock_board_concept_name_em() — 热门概念板块（带缓存）

    Args:
        symbol: 股票代码
        stock_name: 股票名称

    Returns:
        情绪与题材数据字典
    """
    global _concept_board_cache
    data = {}

    try:
        logging.info(f"🎭 获取情绪与题材: {stock_name}")
        data['theme_sentiment_data_date'] = datetime.now().strftime('%Y-%m-%d')

        # 1. 机构参与度/情绪
        try:
            cyd_df = ak.stock_comment_detail_zlkp_jgcyd_em(symbol=symbol)
            if cyd_df is not None and not cyd_df.empty:
                # 取最新一行
                latest = cyd_df.iloc[-1]
                # 寻找参与度数值列
                score = None
                for col in cyd_df.columns:
                    if '参与度' in str(col) or '机构' in str(col):
                        score = _safe_float(latest[col])
                        if score is not None:
                            break
                if score is None:
                    # 尝试取第二列（通常是数值列）
                    if len(cyd_df.columns) >= 2:
                        score = _safe_float(latest.iloc[1])

                if score is not None:
                    if score > 3.5:
                        data['stock_sentiment'] = '偏多'
                    elif score < 1.5:
                        data['stock_sentiment'] = '偏空'
                    else:
                        data['stock_sentiment'] = '中性'

                logging.info(f"✓ 机构参与度获取成功: {data.get('stock_sentiment', 'N/A')}")
        except Exception as e:
            logging.debug(f"机构参与度获取失败: {type(e).__name__}: {str(e)[:80]}")

        # 2. 热门概念板块（带5分钟缓存）
        try:
            now = datetime.now()
            if (_concept_board_cache['data'] is None or
                    _concept_board_cache['time'] is None or
                    (now - _concept_board_cache['time']).seconds > 300):
                concept_df = ak.stock_board_concept_name_em()
                _concept_board_cache['data'] = concept_df
                _concept_board_cache['time'] = now
            else:
                concept_df = _concept_board_cache['data']

            if concept_df is not None and not concept_df.empty:
                # 找涨幅列
                change_col = None
                for col in concept_df.columns:
                    if '涨跌幅' in str(col) or '涨幅' in str(col):
                        change_col = col
                        break

                name_col = None
                for col in concept_df.columns:
                    if '板块名称' in str(col) or '名称' in str(col):
                        name_col = col
                        break

                if change_col and name_col:
                    sorted_df = concept_df.sort_values(by=change_col, ascending=False)
                    top3 = sorted_df.head(3)
                    data['hot_concepts'] = top3[name_col].tolist()

                    # 涨幅变化
                    changes = []
                    for _, row in top3.iterrows():
                        chg = _safe_float(row[change_col])
                        if chg is not None:
                            changes.append(f"{chg:+.2f}%")
                        else:
                            changes.append("N/A")
                    data['hot_concepts_change'] = changes

                logging.info(f"✓ 热门概念获取成功: {data.get('hot_concepts', [])}")
        except Exception as e:
            logging.debug(f"热门概念获取失败: {type(e).__name__}: {str(e)[:80]}")

        # 3. 生成摘要
        parts = []
        if data.get('stock_sentiment'):
            parts.append(f"情绪：{data['stock_sentiment']}")
        if data.get('hot_concepts'):
            parts.append(f"热门概念：{'、'.join(data['hot_concepts'][:3])}")

        data['theme_sentiment_summary'] = ' | '.join(parts) if parts else '暂无情绪题材数据'

        logging.info(f"✅ 情绪与题材获取完成")

    except Exception as e:
        logging.error(f"❌ 情绪与题材获取失败: {type(e).__name__}")
        data['theme_sentiment_data_date'] = datetime.now().strftime('%Y-%m-%d')
        data['theme_sentiment_summary'] = '数据获取失败'

    return data


# ==================== 维度16：支撑压力与风险 ====================

# 汇率敏感行业映射
_FX_DEVALUE_BENEFIT = {'电子', '家用电器', '纺织服饰', '轻工制造', '钢铁', '机械设备', '化工', '有色金属'}
_FX_APPRECIATE_BENEFIT = {'交通运输', '造纸', '航空', '航空运输'}


def fetch_support_resistance_data(symbol: str, stock_name: str, context: dict) -> dict:
    """
    从已有 metrics 数据中计算支撑压力位与汇率敏感性（无需新API调用）

    Args:
        symbol: 股票代码
        stock_name: 股票名称
        context: 包含已获取的 metrics 数据（如 current_price, ma20, ma60, ...）

    Returns:
        支撑压力与风险数据字典
    """
    data = {}

    try:
        logging.info(f"📐 计算支撑压力位: {stock_name}")

        price = context.get('current_price')
        if not price:
            data['support_resistance_summary'] = '无当前价格，无法计算'
            return data

        # 收集所有候选价位
        levels = []

        # 均线价位
        for name, key in [('MA20', 'ma20'), ('MA60', 'ma60'), ('MA120', 'ma120'), ('MA250', 'ma250')]:
            val = context.get(key)
            if val:
                levels.append((val, name))

        # BOLL 上下轨
        boll_upper = context.get('boll_upper')
        boll_lower = context.get('boll_lower')
        if boll_upper:
            levels.append((boll_upper, 'BOLL上轨'))
        if boll_lower:
            levels.append((boll_lower, 'BOLL下轨'))

        # 筹码平均成本
        chip_avg = context.get('chip_avg_cost_raw')
        if chip_avg:
            levels.append((chip_avg, '套牢盘密集'))

        # 近期高低点（从近20日数据中提取）
        recent_data = context.get('recent_20d_data', [])
        if recent_data:
            highs = [d.get('high') for d in recent_data if d.get('high')]
            lows = [d.get('low') for d in recent_data if d.get('low')]
            if highs:
                levels.append((max(highs), '近期高点'))
            if lows:
                levels.append((min(lows), '近期低点'))

        # 分离压力位（在当前价上方）和支撑位（在当前价下方）
        resistance_levels = [(v, n) for v, n in levels if v > price * 1.005]  # 0.5% 以上才算
        support_levels = [(v, n) for v, n in levels if v < price * 0.995]

        # 取最近的压力位和支撑位
        if resistance_levels:
            resistance_levels.sort(key=lambda x: x[0])
            data['resistance_price'] = round(resistance_levels[0][0], 2)
            data['resistance_type'] = resistance_levels[0][1]

        if support_levels:
            support_levels.sort(key=lambda x: x[0], reverse=True)
            data['support_price'] = round(support_levels[0][0], 2)
            data['support_type'] = support_levels[0][1]

        # 汇率敏感性（根据行业名称匹配）
        industry = context.get('industry_name') or context.get('sector_name') or ''
        if industry:
            for kw in _FX_DEVALUE_BENEFIT:
                if kw in industry:
                    data['fx_sensitivity'] = '人民币贬值受益'
                    break
            if not data.get('fx_sensitivity'):
                for kw in _FX_APPRECIATE_BENEFIT:
                    if kw in industry:
                        data['fx_sensitivity'] = '人民币升值受益'
                        break

        # 生成摘要
        parts = []
        if data.get('resistance_price'):
            parts.append(f"上方压力位：{data['resistance_price']:.2f}元 ({data['resistance_type']})")
        if data.get('support_price'):
            parts.append(f"下方支撑：{data['support_price']:.2f}元 ({data['support_type']})")
        if data.get('fx_sensitivity'):
            parts.append(data['fx_sensitivity'])

        data['support_resistance_summary'] = ' | '.join(parts) if parts else '暂无支撑压力数据'

        logging.info(f"✅ 支撑压力位计算完成")

    except Exception as e:
        logging.error(f"❌ 支撑压力位计算失败: {type(e).__name__}")
        data['support_resistance_summary'] = '计算失败'

    return data


# ==================== 舆情数据（供 stock-val 路径调用）====================

def fetch_news_data(symbol: str, stock_name: str) -> dict:
    """
    获取舆情/新闻数据（东财公告 + 财联社电报 + DuckDuckGo）

    复用 analyst_core.py 中已有的新闻获取逻辑，封装为标准 dict 返回格式。

    Args:
        symbol: 股票代码
        stock_name: 股票名称

    Returns:
        {'news_summary': ..., 'news_context': ..., 'news_source': ..., 'news_data_date': ...}
    """
    data = {}

    try:
        from analyst_base import (
            get_eastmoney_announcements,
            match_relevant_telegraphs,
            format_telegraph_for_report,
        )

        news_list = []
        news_source = "无"
        cls_telegraphs = []

        # --- 引擎0: 东方财富公告 (最高优先级) ---
        try:
            announcements = get_eastmoney_announcements(symbol, limit=15)
            if announcements:
                news_list = announcements
                news_source = "东财公告"
                logging.info(f"✓ [fetch_news_data] 东财公告获取 {len(news_list)} 条")
        except Exception as e:
            logging.debug(f"东财公告异常: {type(e).__name__}")

        # --- 引擎1: 财联社电报 (智能匹配) ---
        try:
            cls_telegraphs = match_relevant_telegraphs(
                stock_code=symbol,
                stock_name=stock_name,
                hours=24,
                min_score=5,
                max_items=8,
            )
            if cls_telegraphs:
                if news_list:
                    news_source = "东财公告+财联社电报"
                else:
                    cls_formatted = format_telegraph_for_report(cls_telegraphs)
                    news_list = [cls_formatted]
                    news_source = "财联社电报"
        except Exception as e:
            logging.debug(f"财联社电报失败: {type(e).__name__}")

        # --- 引擎2: DuckDuckGo 联网搜索 (备用) ---
        if not news_list:
            try:
                from ddgs import DDGS
                with DDGS() as ddgs:
                    query = f'{stock_name} 股票'
                    results = list(ddgs.text(query, region='cn-zh', timelimit='w', max_results=15))
                    for r in results:
                        title = r.get('title', '')
                        body = r.get('body', '')
                        if stock_name in (title + ' ' + body) or symbol in (title + ' ' + body):
                            news_list.append(title)
                            if len(news_list) >= 15:
                                break
                    if news_list:
                        news_source = "全网搜索"
            except Exception as e:
                logging.debug(f"DuckDuckGo失败: {type(e).__name__}")

        # --- 数据整合 ---
        if news_list or cls_telegraphs:
            all_news = []
            for item in news_list:
                all_news.append(f"- {item}")
            if cls_telegraphs and news_source == "东财公告+财联社电报":
                all_news.append("\n【财联社行业/政策快讯】")
                cls_formatted = format_telegraph_for_report(cls_telegraphs)
                all_news.append(cls_formatted)

            total_count = len(news_list) + len(cls_telegraphs)
            data['news_summary'] = f"[{news_source}] {total_count}条"
            data['news_context'] = "\n".join(all_news)
            data['news_source'] = news_source
        else:
            data['news_summary'] = "静默"
            data['news_context'] = "当前无任何新闻或资讯"
            data['news_source'] = "无"

        data['news_data_date'] = datetime.now().strftime('%Y-%m-%d %H:%M')

    except ImportError:
        logging.warning("analyst_core 模块不可用，无法获取舆情数据")
        data['news_summary'] = None
        data['news_source'] = None
    except Exception as e:
        logging.error(f"❌ 舆情数据获取失败: {type(e).__name__}: {str(e)[:100]}")
        data['news_summary'] = None
        data['news_source'] = None

    return data


# ==================== 维度5：扩展数据 ====================

def fetch_extended_data(symbol: str, stock_name: str) -> dict:
    """获取扩展数据（近20日、BOLL、季度趋势、行业对比、十大股东 + 6个新维度）"""
    data = {}

    # 1. 近20日行情 + BOLL
    recent_boll = fetch_recent_20d_and_boll(symbol, stock_name)
    data.update(recent_boll)

    # 2. 季度趋势
    quarterly = fetch_quarterly_trend(symbol, stock_name)
    data.update(quarterly)

    # 3. 行业对比
    industry = fetch_industry_comparison(symbol, stock_name)
    data.update(industry)

    # 4. 十大股东
    holders = fetch_top_holders(symbol, stock_name)
    data.update(holders)

    # 5. 分析师一致预期
    consensus = fetch_consensus_data(symbol, stock_name)
    data.update(consensus)

    # 6. 大盘/板块环境
    market_env = fetch_market_env_data(symbol, stock_name)
    data.update(market_env)

    # 7. 解禁/减持风险
    lockup = fetch_lockup_data(symbol, stock_name)
    data.update(lockup)

    # 8. 筹码分布
    chip = fetch_chip_data(symbol, stock_name)
    data.update(chip)

    # 9. 机构持仓变化
    institution = fetch_institution_data(symbol, stock_name)
    data.update(institution)

    # 10. 竞争对手对比
    competitor = fetch_competitor_data(symbol, stock_name)
    data.update(competitor)

    return data


# ==================== 主函数：整合四维数据 ====================

def fetch_full_stock_data(symbol: str, stock_name: str, asset_type: str = "stock") -> dict:
    """
    获取完整的五维数据

    Args:
        symbol: 股票代码
        stock_name: 股票名称
        asset_type: 资产类型（stock/etf/index）

    Returns:
        完整数据字典
    """
    logging.info(f"\n{'='*60}")
    logging.info(f"开始抓取五维数据: {stock_name} ({symbol})")
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

    # 维度5：扩展数据（近20日行情、BOLL、季度趋势、行业对比、十大股东 + 6个新维度）
    if asset_type == "stock":
        extended_data = fetch_extended_data(symbol, stock_name)
        result.update(extended_data)

    # 交叉计算：PEG = PE-TTM / 预期利润增速
    try:
        pe_ttm_raw = result.get('pe_ttm_raw')
        eps_growth = result.get('eps_growth_rate_raw')
        if pe_ttm_raw and eps_growth and eps_growth > 0:
            peg = pe_ttm_raw / eps_growth
            result['peg'] = f"{peg:.2f}"
            result['peg_raw'] = peg
            if peg < 0.5:
                result['peg_signal'] = f"极度低估(PEG={peg:.2f}<0.5)"
            elif peg < 1:
                result['peg_signal'] = f"偏低估(PEG={peg:.2f}<1)"
            elif peg < 1.5:
                result['peg_signal'] = f"合理(PEG={peg:.2f})"
            elif peg < 2:
                result['peg_signal'] = f"偏高估(PEG={peg:.2f})"
            else:
                result['peg_signal'] = f"高估(PEG={peg:.2f}>2)"
            logging.info(f"✓ PEG计算成功: {result['peg_signal']}")
    except Exception as e:
        logging.debug(f"PEG计算失败: {e}")

    logging.info(f"\n✅ 数据抓取完成！\n")

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
