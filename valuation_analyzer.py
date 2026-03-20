"""
快速估值分析模块
功能：获取当前估值 + 历史分位数据 + 实时行情，生成 LLM 可读的估值报告

数据来源：
- 当前估值: 雪球 API (ak.stock_individual_spot_xq)
- 历史分位: 韭圈儿网站爬虫
- PS/PCF: 自行计算
- 实时行情: 雪球API / 东方财富
"""

import logging
import time
import re
import os
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd
import requests
from bs4 import BeautifulSoup

# 导入新增维度的 fetch 函数
try:
    from analyst_data import (
        fetch_consensus_data,
        fetch_market_env_data,
        fetch_lockup_data,
        fetch_chip_data,
        fetch_institution_data,
        fetch_competitor_data,
        fetch_smart_money_data,
        fetch_theme_sentiment_data,
        fetch_support_resistance_data,
        fetch_news_data,
        fetch_kline_multi_source,
    )
except ImportError:
    # 兼容性：如果导入失败，定义空函数
    def fetch_consensus_data(symbol, stock_name): return {}
    def fetch_market_env_data(symbol, stock_name): return {}
    def fetch_lockup_data(symbol, stock_name): return {}
    def fetch_chip_data(symbol, stock_name): return {}
    def fetch_institution_data(symbol, stock_name): return {}
    def fetch_competitor_data(symbol, stock_name): return {}
    def fetch_smart_money_data(symbol, stock_name): return {}
    def fetch_theme_sentiment_data(symbol, stock_name): return {}
    def fetch_support_resistance_data(symbol, stock_name, context=None): return {}
    def fetch_news_data(symbol, stock_name): return {}
    def fetch_kline_multi_source(symbol, start_date, end_date, adjust='qfq'): return None

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class ValuationMetrics:
    """估值指标数据类"""
    # 当前估值
    pe_ttm: Optional[float] = None
    pe_static: Optional[float] = None  # PE-静态（基于上年度全年收益）
    pb: Optional[float] = None
    ps_ttm: Optional[float] = None
    pcf: Optional[float] = None  # 市现率
    p_fcf: Optional[float] = None  # 市值/自由现金流 (新增)
    dividend_yield: Optional[float] = None  # 股息率 (%)
    market_cap: Optional[float] = None  # 总市值 (亿)

    # 实时行情数据
    current_price: Optional[float] = None  # 当前价
    open_price: Optional[float] = None  # 开盘价
    close_price: Optional[float] = None  # 昨收价
    high_price: Optional[float] = None  # 最高价
    low_price: Optional[float] = None  # 最低价
    change_pct: Optional[float] = None  # 涨跌幅 (%)
    change_amount: Optional[float] = None  # 涨跌额 (元)
    amplitude: Optional[float] = None  # 振幅 (%)
    volume: Optional[float] = None  # 成交量 (股)
    amount: Optional[float] = None  # 成交额 (亿)
    turnover_rate: Optional[float] = None  # 换手率 (%)
    volume_ratio: Optional[float] = None  # 量比

    # 均线数据
    ma5: Optional[float] = None  # 5日均线
    ma10: Optional[float] = None  # 10日均线
    ma20: Optional[float] = None  # 20日均线
    ma60: Optional[float] = None  # 60日均线
    ma120: Optional[float] = None  # 120日均线
    ma250: Optional[float] = None  # 250日均线

    # 均线距离（当前价距离各均线的百分比）
    ma5_distance: Optional[float] = None  # 距离5日均线 (%)
    ma10_distance: Optional[float] = None  # 距离10日均线 (%)
    ma20_distance: Optional[float] = None  # 距离20日均线 (%)
    ma60_distance: Optional[float] = None  # 距离60日均线 (%)
    ma120_distance: Optional[float] = None  # 距离120日均线 (%)
    ma250_distance: Optional[float] = None  # 距离250日均线 (%)

    # 技术指标
    # MACD
    macd_dif: Optional[float] = None  # MACD DIF值
    macd_dea: Optional[float] = None  # MACD DEA值
    macd_hist: Optional[float] = None  # MACD柱状图值
    macd_signal: Optional[str] = None  # MACD信号（金叉/死叉）

    # RSI
    rsi_6: Optional[float] = None  # 6日RSI
    rsi_12: Optional[float] = None  # 12日RSI
    rsi_24: Optional[float] = None  # 24日RSI

    # KDJ
    kdj_k: Optional[float] = None  # K值
    kdj_d: Optional[float] = None  # D值
    kdj_j: Optional[float] = None  # J值

    # CCI
    cci: Optional[float] = None  # CCI商品通道指标

    # 核心财务指标
    # 盈利能力
    roe: Optional[float] = None  # 净资产收益率 (%)
    gross_margin: Optional[float] = None  # 毛利率 (%)
    net_margin: Optional[float] = None  # 净利率 (%)
    eps: Optional[float] = None  # 每股收益 (元)
    bps: Optional[float] = None  # 每股净资产 (元)

    # 成长性指标
    revenue_yoy: Optional[float] = None  # 营收同比增长率 (%)
    revenue_qoq: Optional[float] = None  # 营收环比增长率 (%)
    profit_yoy: Optional[float] = None  # 净利润同比增长率 (%)
    profit_qoq: Optional[float] = None  # 净利润环比增长率 (%)
    eps_yoy: Optional[float] = None  # EPS同比增长率 (%)

    # 财务健康度
    debt_asset_ratio: Optional[float] = None  # 资产负债率 (%)
    current_ratio: Optional[float] = None  # 流动比率
    quick_ratio: Optional[float] = None  # 速动比率
    ocf_to_profit: Optional[float] = None  # 经营现金流/净利润比

    # 股本结构
    total_shares: Optional[float] = None  # 总股本 (亿股)
    float_shares: Optional[float] = None  # 流通股本 (亿股)
    float_ratio: Optional[float] = None  # 流通比例 (%)

    # 资金流向（多时间维度）
    # 当天资金流向
    main_net_inflow_1d: Optional[float] = None  # 当日主力净流入 (亿)
    super_net_inflow_1d: Optional[float] = None  # 当日超大单净流入 (亿)
    big_net_inflow_1d: Optional[float] = None  # 当日大单净流入 (亿)
    medium_net_inflow_1d: Optional[float] = None  # 当日中单净流入 (亿)
    small_net_inflow_1d: Optional[float] = None  # 当日小单净流入 (亿)
    main_net_inflow_pct_1d: Optional[float] = None  # 当日主力净流入占比 (%)

    # 3日资金流向
    main_net_inflow_3d: Optional[float] = None  # 3日主力净流入 (亿)
    super_net_inflow_3d: Optional[float] = None  # 3日超大单净流入 (亿)
    big_net_inflow_3d: Optional[float] = None  # 3日大单净流入 (亿)
    medium_net_inflow_3d: Optional[float] = None  # 3日中单净流入 (亿)
    small_net_inflow_3d: Optional[float] = None  # 3日小单净流入 (亿)

    # 7日（1周）资金流向
    main_net_inflow_7d: Optional[float] = None  # 7日主力净流入 (亿)
    super_net_inflow_7d: Optional[float] = None  # 7日超大单净流入 (亿)
    big_net_inflow_7d: Optional[float] = None  # 7日大单净流入 (亿)
    medium_net_inflow_7d: Optional[float] = None  # 7日中单净流入 (亿)
    small_net_inflow_7d: Optional[float] = None  # 7日小单净流入 (亿)

    # PE 历史分位 (%)
    pe_percentile_10y: Optional[float] = None
    pe_percentile_5y: Optional[float] = None
    pe_percentile_3y: Optional[float] = None
    pe_percentile_1y: Optional[float] = None

    # PB 历史分位 (%)
    pb_percentile_10y: Optional[float] = None
    pb_percentile_5y: Optional[float] = None
    pb_percentile_3y: Optional[float] = None
    pb_percentile_1y: Optional[float] = None

    # PS 历史分位 (%)
    ps_percentile_10y: Optional[float] = None
    ps_percentile_5y: Optional[float] = None
    ps_percentile_3y: Optional[float] = None
    ps_percentile_1y: Optional[float] = None

    # 元数据
    stock_name: str = ""
    stock_code: str = ""
    update_time: str = ""
    data_source: str = ""  # 数据来源
    warnings: list = field(default_factory=list)

    # 近20日行情数据
    recent_20d_data: List[Dict[str, Any]] = field(default_factory=list)

    # 布林带
    boll_upper: Optional[float] = None  # 上轨
    boll_mid: Optional[float] = None  # 中轨
    boll_lower: Optional[float] = None  # 下轨
    boll_width: Optional[float] = None  # 带宽 (%)

    # 近8季度营收/利润趋势
    quarterly_trend: List[Dict[str, Any]] = field(default_factory=list)

    # 行业对比
    industry_name: Optional[str] = None  # 所属行业
    industry_comparison: Dict[str, Any] = field(default_factory=dict)

    # 十大流通股东变化
    top_holders_current: List[Dict[str, Any]] = field(default_factory=list)
    top_holders_previous: List[Dict[str, Any]] = field(default_factory=list)
    top_holders_report_date: Optional[str] = None
    top_holders_prev_date: Optional[str] = None

    # === 新增维度字段 ===

    # 数据时效性日期
    valuation_data_date: Optional[str] = None
    performance_data_date: Optional[str] = None
    sentiment_data_date: Optional[str] = None
    quarterly_trend_data_date: Optional[str] = None
    top_holders_data_date: Optional[str] = None
    consensus_data_date: Optional[str] = None
    market_env_data_date: Optional[str] = None
    lockup_data_date: Optional[str] = None
    chip_data_date: Optional[str] = None
    institution_data_date: Optional[str] = None
    competitor_data_date: Optional[str] = None

    # 分析师一致预期
    eps_forecast_current: Optional[str] = None
    eps_forecast_next: Optional[str] = None
    eps_growth_rate: Optional[str] = None
    eps_growth_rate_raw: Optional[float] = None
    peg: Optional[str] = None
    peg_raw: Optional[float] = None
    peg_signal: Optional[str] = None
    rating_buy: Optional[int] = None
    rating_overweight: Optional[int] = None
    rating_hold: Optional[int] = None
    target_price_avg: Optional[str] = None
    target_price_high: Optional[str] = None
    target_price_low: Optional[str] = None
    target_upside: Optional[str] = None
    consensus_summary: Optional[str] = None

    # 大盘/板块环境
    market_index_change_5d: Optional[str] = None
    market_index_change_20d: Optional[str] = None
    market_index_above_ma20: Optional[bool] = None
    market_sentiment: Optional[str] = None
    sector_name: Optional[str] = None
    sector_change_today: Optional[str] = None
    sector_rank: Optional[str] = None
    sector_main_inflow: Optional[str] = None
    market_env_summary: Optional[str] = None

    # 解禁/减持风险
    lockup_events: List[Dict[str, Any]] = field(default_factory=list)
    lockup_nearest_date: Optional[str] = None
    lockup_6m_total_pct: Optional[str] = None
    lockup_risk_level: Optional[str] = None
    lockup_summary: Optional[str] = None

    # 筹码分布
    chip_profit_ratio: Optional[str] = None
    chip_profit_ratio_raw: Optional[float] = None
    chip_avg_cost: Optional[str] = None
    chip_avg_cost_raw: Optional[float] = None
    chip_concentration_70: Optional[str] = None
    chip_concentration_90: Optional[str] = None
    chip_signal: Optional[str] = None
    chip_summary: Optional[str] = None

    # 机构持仓变化
    fund_holding_count: Optional[int] = None
    fund_holding_count_prev: Optional[int] = None
    fund_holding_change: Optional[str] = None
    fund_holding_pct: Optional[str] = None
    fund_holding_change_pct: Optional[str] = None
    top_funds: List[Dict[str, Any]] = field(default_factory=list)
    institution_summary: Optional[str] = None

    # 竞争对手对比
    competitors: List[Dict[str, Any]] = field(default_factory=list)
    industry_peer_count: Optional[int] = None
    competitor_summary: Optional[str] = None

    # [14/17] 聪明钱动向
    smart_money_data_date: Optional[str] = None
    north_consecutive_days: Optional[int] = None       # 正=加仓, 负=减仓
    north_change_pct_3d: Optional[float] = None
    north_holding_ratio: Optional[float] = None
    margin_balance: Optional[float] = None              # 亿
    margin_balance_trend: Optional[str] = None           # 增/减/平
    short_selling_ratio: Optional[float] = None          # %
    short_selling_level: Optional[str] = None            # 高位/低位/正常
    smart_money_summary: Optional[str] = None

    # [15/17] 情绪与题材
    theme_sentiment_data_date: Optional[str] = None
    stock_sentiment: Optional[str] = None                # 偏多/偏空/中性
    hot_concepts: List[str] = field(default_factory=list)
    hot_concepts_change: List[str] = field(default_factory=list)
    theme_sentiment_summary: Optional[str] = None

    # [16/17] 支撑压力与风险
    resistance_price: Optional[float] = None
    resistance_type: Optional[str] = None
    support_price: Optional[float] = None
    support_type: Optional[str] = None
    fx_sensitivity: Optional[str] = None
    support_resistance_summary: Optional[str] = None

    # [17/17] 舆情数据
    news_summary: Optional[str] = None          # "[东财公告] 15条"
    news_context: Optional[str] = None          # 完整新闻列表
    news_source: Optional[str] = None           # "东财公告" / "财联社电报" / etc
    news_data_date: Optional[str] = None

    # 派生技术指标（从已有数据计算，无需新API）
    boll_position: Optional[float] = None       # 价格在BOLL带中的位置 0-100%
    boll_status: Optional[str] = None           # "突破上轨" / "接近上轨" / "中轨附近" / etc
    ma_alignment: Optional[str] = None          # "多头排列" / "空头排列" / "均线纠缠"
    trend_position: Optional[str] = None        # "年线上方(强势)" / "月线下方" / etc
    change_5d: Optional[float] = None           # 5日涨跌幅%
    change_20d: Optional[float] = None          # 20日涨跌幅%
    high_20d: Optional[float] = None            # 20日最高
    low_20d: Optional[float] = None             # 20日最低
    dist_to_high: Optional[float] = None        # 距20日高点%
    dist_to_low: Optional[float] = None         # 距20日低点%
    volatility_20d: Optional[float] = None      # 20日波动率


class ValuationAnalyzer:
    """估值分析器"""

    # 请求头
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
    }

    def __init__(self, cache=None):
        """
        初始化估值分析器

        Args:
            cache: 缓存实例（可选）
        """
        self.cache = cache
        # 如果没有传入缓存，尝试导入
        if self.cache is None:
            try:
                from data_cache import DataCache
                self.cache = DataCache()
            except ImportError:
                logger.warning("缓存模块不可用，将不使用缓存")

    def _safe_float(self, value) -> Optional[float]:
        """安全转换为浮点数"""
        if value is None or pd.isna(value):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _convert_symbol(self, symbol: str, market: str = 'A') -> str:
        """转换代码格式为雪球格式"""
        if market == 'HK':
            # 港股代码格式：直接返回5位代码
            return symbol.zfill(5)
        # A股代码格式
        if symbol.startswith(('000', '001', '002', '003', '300')):
            return f"SZ{symbol}"
        else:
            return f"SH{symbol}"

    def fetch_current_valuation(self, symbol: str, stock_name: str) -> Dict[str, Any]:
        """
        获取当前估值数据（多数据源 + 降级策略）

        数据源优先级：
        1. 雪球 API（主数据源）
        2. 百度股市通 + 东方财富（备用数据源）

        Args:
            symbol: 股票代码
            stock_name: 股票名称

        Returns:
            估值数据字典
        """
        data = {}

        # 尝试数据源1: 雪球 API
        try:
            logger.info(f"📊 获取当前估值: {stock_name} ({symbol})")
            logger.info(f"🔍 数据源1: 雪球API（优先）")
            xq_symbol = self._convert_symbol(symbol)

            # 从环境变量获取 token
            xq_token = os.getenv('XUEQIU_TOKEN')
            if not xq_token:
                logger.warning("⚠️  雪球 API Token 未配置（XUEQIU_TOKEN 环境变量缺失）")
                raise ValueError("XUEQIU_TOKEN not set")

            spot_df = ak.stock_individual_spot_xq(symbol=xq_symbol, token=xq_token)

            if not spot_df.empty:
                spot_dict = dict(zip(spot_df['item'], spot_df['value']))

                # 提取估值指标
                data['pe_ttm'] = self._safe_float(spot_dict.get('市盈率(TTM)'))
                data['pb'] = self._safe_float(spot_dict.get('市净率'))
                data['dividend_yield'] = self._safe_float(spot_dict.get('股息率(TTM)'))

                # 总市值（雪球返回的可能是"资产净值/总市值"或其他字段）
                market_cap = spot_dict.get('总市值') or spot_dict.get('资产净值/总市值')
                if market_cap:
                    data['market_cap'] = self._safe_float(market_cap)
                    if data['market_cap']:
                        data['market_cap_yi'] = data['market_cap'] / 1e8  # 转换为亿

                logger.info(f"✅ 数据来源: 雪球API | PE={data.get('pe_ttm')}, PB={data.get('pb')}, "
                           f"股息率={data.get('dividend_yield')}%")
                data['source'] = 'xueqiu'
                return data
            else:
                logger.warning(f"⚠️  雪球 API 返回空数据 (symbol={xq_symbol})")
                raise ValueError("Empty dataframe from xueqiu")

        except Exception as e:
            error_msg = str(e)[:100]
            logger.warning(f"⚠️  数据源1失败: 雪球API - {type(e).__name__}: {error_msg}")
            logger.info(f"🔄 切换到备用数据源...")

        # 降级到备用数据源: 百度股市通 + 东方财富
        try:
            logger.info("🔍 数据源2: 百度股市通 + 东方财富（备用）")

            # 1. 百度股市通获取 PE、PB
            try:
                df_pe = ak.stock_zh_valuation_baidu(symbol=symbol, indicator='市盈率(TTM)', period='近一年')
                if not df_pe.empty:
                    data['pe_ttm'] = self._safe_float(df_pe.iloc[-1]['value'])
            except Exception as e:
                logger.debug(f"PE 获取失败: {e}")

            try:
                df_pb = ak.stock_zh_valuation_baidu(symbol=symbol, indicator='市净率', period='近一年')
                if not df_pb.empty:
                    data['pb'] = self._safe_float(df_pb.iloc[-1]['value'])
            except Exception as e:
                logger.debug(f"PB 获取失败: {e}")

            # 2. 东方财富获取市值
            try:
                df_info = ak.stock_individual_info_em(symbol=symbol)
                if not df_info.empty:
                    info_dict = dict(zip(df_info['item'], df_info['value']))
                    market_cap = self._safe_float(info_dict.get('总市值'))
                    if market_cap:
                        data['market_cap'] = market_cap
                        data['market_cap_yi'] = market_cap / 1e8
            except Exception as e:
                logger.debug(f"市值获取失败: {e}")

            # 3. 计算股息率(TTM)
            dividend_yield = self._calculate_dividend_yield(symbol)
            if dividend_yield:
                data['dividend_yield'] = dividend_yield

            if data.get('pe_ttm') or data.get('pb'):
                logger.info(f"✅ 数据来源: 百度股市通+东方财富 | PE={data.get('pe_ttm')}, PB={data.get('pb')}, "
                           f"市值={data.get('market_cap_yi')}亿")
                data['source'] = 'baidu_eastmoney'
            else:
                logger.error("❌ 数据源2失败: 百度股市通+东方财富 - 未获取到有效估值数据")

        except Exception as e:
            logger.error(f"❌ 数据源2异常: 百度股市通+东方财富 - {type(e).__name__}: {str(e)[:100]}")

        return data

    def _calculate_pe_static(self, symbol: str, current_price: float) -> Optional[float]:
        """
        计算PE-静态

        PE-静态 = 当前股价 / 上年度全年每股收益

        Args:
            symbol: 股票代码
            current_price: 当前股价

        Returns:
            PE-静态值，失败返回None
        """
        try:
            # 获取财务指标数据
            from analyst_data import fetch_performance_data
            perf_data = fetch_performance_data(symbol, symbol)  # 使用symbol作为名称参数

            # 获取上年度每股收益
            eps_static = perf_data.get('eps_raw')  # 这里获取的是最新财报的每股收益

            if eps_static and eps_static > 0 and current_price:
                pe_static = current_price / eps_static
                logger.info(f"PE-静态: {pe_static:.2f} (股价{current_price:.2f} / EPS{eps_static:.2f})")
                return round(pe_static, 2)
            else:
                logger.debug(f"PE-静态计算失败: EPS={eps_static}, 股价={current_price}")

        except Exception as e:
            logger.debug(f"PE-静态计算失败: {e}")

        return None

    def fetch_fund_flow(self, symbol: str, stock_name: str) -> Dict[str, Any]:
        """
        获取资金流向数据（多时间维度）

        同时获取1日、3日、7日的资金流向数据

        Args:
            symbol: 股票代码
            stock_name: 股票名称

        Returns:
            资金流向数据字典，包含1d/3d/7d三个时间维度
        """
        data = {}

        try:
            logger.info(f"💰 获取资金流向: {stock_name} ({symbol})")

            # 判断市场
            market = "sh" if symbol.startswith(("6", "68")) else "sz"

            # 获取资金流向数据
            fund_flow = ak.stock_individual_fund_flow(stock=symbol, market=market)

            if not fund_flow.empty:
                # 定义需要统计的时间维度
                periods = [
                    (1, '1d', '当日'),
                    (3, '3d', '3日'),
                    (7, '7d', '7日'),
                ]

                for days, suffix, desc in periods:
                    # 取最近N天的数据
                    recent = fund_flow.tail(days)

                    if not recent.empty:
                        # 计算各类资金净流入总额
                        data[f'main_net_inflow_{suffix}'] = recent['主力净流入-净额'].sum() / 1e8  # 转换为亿

                        if '超大单净流入-净额' in recent.columns:
                            data[f'super_net_inflow_{suffix}'] = recent['超大单净流入-净额'].sum() / 1e8

                        if '大单净流入-净额' in recent.columns:
                            data[f'big_net_inflow_{suffix}'] = recent['大单净流入-净额'].sum() / 1e8

                        if '中单净流入-净额' in recent.columns:
                            data[f'medium_net_inflow_{suffix}'] = recent['中单净流入-净额'].sum() / 1e8

                        if '小单净流入-净额' in recent.columns:
                            data[f'small_net_inflow_{suffix}'] = recent['小单净流入-净额'].sum() / 1e8

                        # 计算主力净流入占比（仅当日）
                        if days == 1:
                            latest = recent.iloc[-1]
                            if '主力净流入-净占比' in latest:
                                data['main_net_inflow_pct_1d'] = self._safe_float(latest['主力净流入-净占比'])

                        flow_status = "流入" if data[f'main_net_inflow_{suffix}'] > 0 else "流出"
                        logger.info(f"  ✓ {desc}主力{flow_status}: {abs(data[f'main_net_inflow_{suffix}']):.2f}亿")

                data['source'] = 'eastmoney'
                logger.info(f"✅ 资金流向数据获取完成（1日/3日/7日）")
            else:
                logger.warning(f"⚠️  资金流向数据为空")

        except Exception as e:
            logger.error(f"❌ 获取资金流向失败: {type(e).__name__}: {str(e)[:100]}")

        return data

    def fetch_realtime_quote(self, symbol: str, stock_name: str) -> Dict[str, Any]:
        """
        获取实时行情数据（包含均线）

        包含：价格、涨跌幅、成交量、换手率、量比、均线等

        Args:
            symbol: 股票代码
            stock_name: 股票名称

        Returns:
            实时行情数据字典
        """
        data = {}

        try:
            logger.info(f"获取实时行情与均线数据: {stock_name} ({symbol})")

            # 获取历史数据用于计算均线（需要至少250+天的数据）
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=400)).strftime('%Y%m%d')

            hist_df = fetch_kline_multi_source(symbol, start_date, end_date, adjust='qfq')

            if hist_df is not None and not hist_df.empty:
                # 计算均线
                hist_df['MA5'] = hist_df['收盘'].rolling(window=5).mean()
                hist_df['MA10'] = hist_df['收盘'].rolling(window=10).mean()
                hist_df['MA20'] = hist_df['收盘'].rolling(window=20).mean()
                hist_df['MA60'] = hist_df['收盘'].rolling(window=60).mean()
                hist_df['MA120'] = hist_df['收盘'].rolling(window=120).mean()
                hist_df['MA250'] = hist_df['收盘'].rolling(window=250).mean()

                # 获取最新一行数据
                latest = hist_df.iloc[-1]

                # 基本价格数据
                data['current_price'] = self._safe_float(latest.get('收盘'))
                data['open_price'] = self._safe_float(latest.get('开盘'))
                data['high_price'] = self._safe_float(latest.get('最高'))
                data['low_price'] = self._safe_float(latest.get('最低'))
                data['volume'] = self._safe_float(latest.get('成交量'))
                data['amount'] = self._safe_float(latest.get('成交额'))
                data['turnover_rate'] = self._safe_float(latest.get('换手率'))

                # 计算昨收价和涨跌幅
                if len(hist_df) >= 2:
                    prev_close = self._safe_float(hist_df.iloc[-2].get('收盘'))
                    data['close_price'] = prev_close
                    if prev_close and data['current_price']:
                        data['change_pct'] = ((data['current_price'] - prev_close) / prev_close) * 100
                        data['change_amount'] = data['current_price'] - prev_close

                # 计算振幅
                if data['high_price'] and data['low_price'] and data['close_price']:
                    data['amplitude'] = ((data['high_price'] - data['low_price']) / data['close_price']) * 100

                # 计算量比
                if len(hist_df) >= 6 and data['volume']:
                    avg_volume_5d = hist_df.iloc[-6:-1]['成交量'].mean()
                    if avg_volume_5d > 0:
                        data['volume_ratio'] = data['volume'] / avg_volume_5d

                # 成交额转换为亿
                if data['amount']:
                    data['amount_yi'] = data['amount'] / 1e8

                # 提取近20日行情数据
                if len(hist_df) >= 20:
                    recent_20d = hist_df.tail(20).copy()
                    # 计算每日量比（当日成交量/前5日平均）
                    recent_20d['量比'] = recent_20d['成交量'] / recent_20d['成交量'].shift(1).rolling(window=5).mean()
                    # 计算振幅
                    recent_20d['振幅'] = ((recent_20d['最高'] - recent_20d['最低']) / recent_20d['收盘'].shift(1)) * 100

                    data['recent_20d_data'] = []
                    for _, row in recent_20d.iterrows():
                        day_data = {
                            'date': str(row.get('日期', ''))[:10],
                            'open': self._safe_float(row.get('开盘')),
                            'close': self._safe_float(row.get('收盘')),
                            'high': self._safe_float(row.get('最高')),
                            'low': self._safe_float(row.get('最低')),
                            'change_pct': self._safe_float(row.get('涨跌幅')),
                            'amplitude': self._safe_float(row.get('振幅')),
                            'volume': self._safe_float(row.get('成交量')),
                            'amount': self._safe_float(row.get('成交额')),
                            'turnover_rate': self._safe_float(row.get('换手率')),
                            'volume_ratio': self._safe_float(row.get('量比')),
                        }
                        data['recent_20d_data'].append(day_data)

                # 均线数据
                data['ma5'] = self._safe_float(latest.get('MA5'))
                data['ma10'] = self._safe_float(latest.get('MA10'))
                data['ma20'] = self._safe_float(latest.get('MA20'))
                data['ma60'] = self._safe_float(latest.get('MA60'))
                data['ma120'] = self._safe_float(latest.get('MA120'))
                data['ma250'] = self._safe_float(latest.get('MA250'))

                # 计算均线距离
                current_price = data['current_price']
                if current_price:
                    for ma_name in ['ma5', 'ma10', 'ma20', 'ma60', 'ma120', 'ma250']:
                        ma_value = data.get(ma_name)
                        if ma_value:
                            distance = ((current_price - ma_value) / ma_value) * 100
                            data[f'{ma_name}_distance'] = distance

                # 计算技术指标
                # 1. MACD (12, 26, 9)
                if len(hist_df) >= 35:
                    ema12 = hist_df['收盘'].ewm(span=12, adjust=False).mean()
                    ema26 = hist_df['收盘'].ewm(span=26, adjust=False).mean()
                    dif = ema12 - ema26
                    dea = dif.ewm(span=9, adjust=False).mean()
                    macd = (dif - dea) * 2

                    data['macd_dif'] = round(dif.iloc[-1], 3) if pd.notna(dif.iloc[-1]) else None
                    data['macd_dea'] = round(dea.iloc[-1], 3) if pd.notna(dea.iloc[-1]) else None
                    data['macd_hist'] = round(macd.iloc[-1], 3) if pd.notna(macd.iloc[-1]) else None

                    # MACD信号判断
                    if len(dif) >= 2 and pd.notna(dif.iloc[-1]) and pd.notna(dif.iloc[-2]):
                        if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]:
                            data['macd_signal'] = "金叉"
                        elif dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2]:
                            data['macd_signal'] = "死叉"
                        elif dif.iloc[-1] > dea.iloc[-1]:
                            data['macd_signal'] = "多头"
                        else:
                            data['macd_signal'] = "空头"

                # 2. RSI (6, 12, 24)
                for period in [6, 12, 24]:
                    if len(hist_df) >= period + 1:
                        delta = hist_df['收盘'].diff()
                        gain = delta.where(delta > 0, 0).rolling(period).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
                        rs = gain / loss
                        rsi = 100 - (100 / (1 + rs))
                        rsi_value = rsi.iloc[-1]
                        if pd.notna(rsi_value):
                            data[f'rsi_{period}'] = round(rsi_value, 2)

                # 3. KDJ (9, 3, 3)
                if len(hist_df) >= 9:
                    low_list = hist_df['最低'].rolling(9).min()
                    high_list = hist_df['最高'].rolling(9).max()
                    rsv = (hist_df['收盘'] - low_list) / (high_list - low_list) * 100

                    # 计算K值和D值
                    k = rsv.ewm(com=2, adjust=False).mean()
                    d = k.ewm(com=2, adjust=False).mean()
                    j = 3 * k - 2 * d

                    if pd.notna(k.iloc[-1]) and pd.notna(d.iloc[-1]) and pd.notna(j.iloc[-1]):
                        data['kdj_k'] = round(k.iloc[-1], 2)
                        data['kdj_d'] = round(d.iloc[-1], 2)
                        data['kdj_j'] = round(j.iloc[-1], 2)

                # 4. CCI (14)
                if len(hist_df) >= 14:
                    tp = (hist_df['最高'] + hist_df['最低'] + hist_df['收盘']) / 3
                    ma_tp = tp.rolling(14).mean()
                    md = tp.rolling(14).apply(lambda x: abs(x - x.mean()).mean())
                    cci = (tp - ma_tp) / (0.015 * md)

                    if pd.notna(cci.iloc[-1]):
                        data['cci'] = round(cci.iloc[-1], 2)

                # 5. BOLL布林带 (20, 2)
                if len(hist_df) >= 20:
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

                logger.info(f"实时行情: 价格={data.get('current_price')}, 涨跌幅={data.get('change_pct', 'N/A'):.2f}%" if data.get('change_pct') else f"实时行情: 价格={data.get('current_price')}")
                logger.info(f"均线: MA5={data.get('ma5')}, MA20={data.get('ma20')}, MA60={data.get('ma60')}")
                logger.info(f"技术指标: MACD={data.get('macd_signal')}, RSI(12)={data.get('rsi_12')}, KDJ({data.get('kdj_k')},{data.get('kdj_d')},{data.get('kdj_j')})")
                data['source'] = 'akshare_hist'
            else:
                logger.warning(f"未获取到历史数据")

        except Exception as e:
            logger.error(f"获取实时行情失败: {type(e).__name__}: {str(e)[:100]}")

        return data

    def _calculate_dividend_yield(self, symbol: str) -> Optional[float]:
        """
        计算股息率(TTM)

        股息率 = (每股分红 / 当前股价) * 100%

        Args:
            symbol: 股票代码

        Returns:
            股息率(%)，失败返回None
        """
        try:
            # 1. 获取最新分红数据
            df_dividend = ak.stock_dividend_cninfo(symbol=symbol)
            if df_dividend.empty:
                logger.debug("未找到分红数据")
                return None

            # 按公告日期排序，获取最新分红
            df_dividend = df_dividend.sort_values('实施方案公告日期', ascending=False)
            latest_div = df_dividend.iloc[0]
            dividend_per_10 = latest_div['派息比例']

            if pd.isna(dividend_per_10) or dividend_per_10 == 0:
                logger.debug("最新分红为空或为0")
                return None

            # 2. 获取当前股价（多源容错）
            df_price = fetch_kline_multi_source(
                symbol,
                (datetime.now() - pd.Timedelta(days=7)).strftime('%Y%m%d'),
                datetime.now().strftime('%Y%m%d'),
                adjust=''
            )

            if df_price is None or df_price.empty:
                logger.debug("未获取到最新股价")
                return None

            current_price = float(df_price.iloc[-1]['收盘'])

            # 3. 计算股息率
            dividend_per_share = float(dividend_per_10) / 10  # 每10股派息X元 -> 每股派息
            dividend_yield = (dividend_per_share / current_price) * 100

            logger.info(f"✓ 股息率(TTM): {dividend_yield:.2f}% "
                       f"(每股分红{dividend_per_share:.2f}元 / 股价{current_price:.2f}元)")

            return round(dividend_yield, 2)

        except Exception as e:
            logger.debug(f"股息率计算失败: {e}")
            return None

    def fetch_quarterly_trend(self, symbol: str, stock_name: str) -> List[Dict[str, Any]]:
        """获取近8季度营收/利润趋势"""
        result = []
        try:
            logger.info(f"📊 获取季度趋势: {stock_name} ({symbol})")
            # SH/SZ prefix
            prefix = 'SH' if symbol.startswith('6') else 'SZ'
            df = ak.stock_profit_sheet_by_report_em(symbol=f'{prefix}{symbol}')

            if df is not None and not df.empty:
                for _, row in df.head(8).iterrows():
                    report_date = str(row.get('REPORT_DATE', ''))[:10]
                    report_name = row.get('REPORT_DATE_NAME', '')
                    revenue = self._safe_float(row.get('OPERATE_INCOME'))
                    revenue_yoy = self._safe_float(row.get('OPERATE_INCOME_YOY'))
                    net_profit = self._safe_float(row.get('PARENT_NETPROFIT'))
                    net_profit_yoy = self._safe_float(row.get('PARENT_NETPROFIT_YOY'))

                    result.append({
                        'report_date': report_date,
                        'report_name': report_name,
                        'revenue': revenue,
                        'revenue_yoy': revenue_yoy,
                        'net_profit': net_profit,
                        'net_profit_yoy': net_profit_yoy,
                    })
                logger.info(f"✓ 季度趋势获取完成 ({len(result)}期)")
        except Exception as e:
            logger.warning(f"季度趋势获取失败: {type(e).__name__}: {str(e)[:100]}")
        return result

    def fetch_industry_comparison(self, symbol: str, stock_name: str, report_date: str = '20250930') -> Dict[str, Any]:
        """获取行业对比数据（基于业绩报表同行业排名）"""
        result = {}
        try:
            logger.info(f"📊 获取行业对比: {stock_name}")
            # 先获取行业分类
            info_df = ak.stock_individual_info_em(symbol=symbol)
            industry = None
            if info_df is not None and not info_df.empty:
                row = info_df[info_df['item'] == '行业']
                if not row.empty:
                    industry = row.iloc[0]['value']

            if not industry:
                logger.warning("未获取到行业分类")
                return result

            result['industry_name'] = industry

            # 获取业绩报表
            df = ak.stock_yjbb_em(date=report_date)
            if df is None or df.empty:
                return result

            # 筛选同行业
            peers = df[df['所处行业'] == industry].copy()
            if peers.empty:
                return result

            result['peer_count'] = len(peers)

            # 当前公司数据
            me = peers[peers['股票代码'] == symbol]

            # 计算行业中位数和个股排名
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
                result[f'{key}_median'] = round(median_val, 2)

                if not me.empty:
                    my_val = pd.to_numeric(me[col].iloc[0], errors='coerce')
                    if pd.notna(my_val):
                        rank = (valid < my_val).sum() + 1
                        result[f'{key}_rank'] = int(rank)
                        result[f'{key}_total'] = len(valid)
                        result[f'{key}_value'] = round(float(my_val), 2)

            logger.info(f"✓ 行业对比完成: {industry} ({result.get('peer_count', 0)}家)")
        except Exception as e:
            logger.warning(f"行业对比获取失败: {type(e).__name__}: {str(e)[:100]}")
        return result

    def fetch_top_holders(self, symbol: str, stock_name: str) -> Dict[str, Any]:
        """获取十大流通股东及变化"""
        result = {}
        try:
            logger.info(f"📊 获取十大流通股东: {stock_name} ({symbol})")
            df = ak.stock_circulate_stock_holder(symbol=symbol)

            if df is None or df.empty:
                return result

            # 获取所有报告期
            dates = df['截止日期'].unique()
            if len(dates) < 1:
                return result

            # 最新一期
            latest_date = dates[0]
            latest = df[df['截止日期'] == latest_date].head(10)
            result['current_date'] = str(latest_date)
            result['current'] = []
            for _, row in latest.iterrows():
                result['current'].append({
                    'name': row['股东名称'],
                    'shares': int(row['持股数量']),
                    'pct': float(row['占流通股比例']),
                    'type': row['股本性质'],
                })

            # 上一期（用于对比变化）
            if len(dates) >= 2:
                prev_date = dates[1]
                prev = df[df['截止日期'] == prev_date].head(10)
                result['previous_date'] = str(prev_date)
                prev_map = {}
                for _, row in prev.iterrows():
                    prev_map[row['股东名称']] = {
                        'shares': int(row['持股数量']),
                        'pct': float(row['占流通股比例']),
                    }
                result['previous_map'] = prev_map

            logger.info(f"✓ 十大流通股东获取完成 (截止{latest_date})")
        except Exception as e:
            logger.warning(f"十大流通股东获取失败: {type(e).__name__}: {str(e)[:100]}")
        return result

    def fetch_historical_percentile(self, symbol: str) -> Dict[str, Any]:
        """
        获取历史分位数据

        数据来源: 百度股市通 (ak.stock_zh_valuation_baidu)
        支持: PE(TTM), PB, 市现率的历史分位计算

        Args:
            symbol: 股票代码

        Returns:
            历史分位数据字典
        """
        data = {
            'pe_percentiles': {},
            'pb_percentiles': {},
            'ps_percentiles': {},
        }

        try:
            logger.info(f"🔍 获取历史分位数据（百度股市通）")

            # 获取各个周期的 PE 历史数据并计算分位
            pe_percentiles = self._calculate_percentile_from_baidu(symbol, '市盈率(TTM)')
            if pe_percentiles:
                data['pe_percentiles'] = pe_percentiles
                logger.info(f"✓ PE分位: 10年={pe_percentiles.get('10y')}%, 5年={pe_percentiles.get('5y')}%")

            # 获取各个周期的 PB 历史数据并计算分位
            pb_percentiles = self._calculate_percentile_from_baidu(symbol, '市净率')
            if pb_percentiles:
                data['pb_percentiles'] = pb_percentiles
                logger.info(f"✓ PB分位: 10年={pb_percentiles.get('10y')}%, 5年={pb_percentiles.get('5y')}%")

        except Exception as e:
            logger.error(f"❌ 历史分位获取失败: {e}")

        return data

    def _calculate_percentile_from_baidu(self, symbol: str, indicator: str) -> Dict[str, float]:
        """
        从百度股市通获取历史数据并计算分位

        Args:
            symbol: 股票代码
            indicator: 指标名称 ('市盈率(TTM)', '市净率', '市现率')

        Returns:
            各周期的分位数据 {'10y': xx.x, '5y': xx.x, '3y': xx.x, '1y': xx.x}
        """
        import numpy as np

        # 检查缓存
        if self.cache:
            data_type = f"percentile_{indicator}"
            cached_result = self.cache.get(symbol, data_type)
            if cached_result is not None:
                logger.debug(f"✓ 使用缓存的{indicator}历史分位数据")
                return cached_result

        percentiles = {}
        periods = [
            ('近十年', '10y'),
            ('近五年', '5y'),
            ('近三年', '3y'),
            ('近一年', '1y'),
        ]

        for period_name, period_key in periods:
            try:
                df = ak.stock_zh_valuation_baidu(
                    symbol=symbol,
                    indicator=indicator,
                    period=period_name
                )

                if df is not None and not df.empty:
                    # 过滤掉无效值
                    values = df['value'].dropna()
                    values = values[values > 0]  # 排除负值和零值

                    if len(values) > 10:  # 至少需要10个数据点
                        current_value = values.iloc[-1]  # 最新值
                        # 计算当前值在历史数据中的分位
                        percentile = (values < current_value).sum() / len(values) * 100
                        percentiles[period_key] = round(percentile, 1)

            except Exception as e:
                logger.debug(f"{indicator} {period_name} 数据获取失败: {e}")
                continue

        # 缓存结果（TTL=7天，因为历史分位变化不频繁）
        if self.cache and percentiles:
            data_type = f"percentile_{indicator}"
            self.cache.set(symbol, data_type, percentiles, ttl_seconds=604800)  # 7天
            logger.debug(f"✓ 已缓存{indicator}历史分位数据")

        return percentiles

    def _fetch_with_retry(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """带重试的网络请求"""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.HEADERS, timeout=15)
                response.raise_for_status()
                return response
            except requests.exceptions.Timeout:
                logger.warning(f"请求超时 (尝试 {attempt + 1}/{max_retries})")
                time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError:
                logger.warning(f"连接失败 (尝试 {attempt + 1}/{max_retries})")
                time.sleep(2 ** attempt)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    logger.warning(f"页面不存在: {url}")
                    return None
                elif e.response.status_code == 429:
                    logger.warning("请求过于频繁，等待后重试")
                    time.sleep(30)
                else:
                    logger.error(f"HTTP错误: {e}")
                    return None
            except Exception as e:
                logger.error(f"请求异常: {e}")
                return None

        logger.error(f"请求失败，已达最大重试次数: {url}")
        return None

    def _parse_jiucai_valuation(self, soup: BeautifulSoup, html: str) -> Dict[str, Any]:
        """解析韭圈儿页面的估值数据"""
        data = {
            'pe_percentiles': {},
            'pb_percentiles': {},
            'ps_percentiles': {},
        }

        try:
            # 方法1: 查找JSON数据（韭圈儿可能在script中嵌入数据）
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'percentile' in script.string.lower():
                    # 尝试提取JSON数据
                    pass

            # 方法2: 使用正则匹配分位数据
            # PE分位模式
            pe_pattern = r'PE[^\d]*?(\d+\.?\d*)\s*%'
            pb_pattern = r'PB[^\d]*?(\d+\.?\d*)\s*%'

            # 查找所有百分比数据
            pe_matches = re.findall(r'市盈率[^%]*?(\d+\.?\d*)\s*%', html)
            pb_matches = re.findall(r'市净率[^%]*?(\d+\.?\d*)\s*%', html)

            # 查找表格中的分位数据
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    cell_texts = [c.get_text(strip=True) for c in cells]

                    # 查找包含"分位"或"百分位"的行
                    if any('分位' in t or '百分位' in t for t in cell_texts):
                        # 提取数值
                        for i, text in enumerate(cell_texts):
                            if '%' in text:
                                try:
                                    value = float(text.replace('%', ''))
                                    # 根据列标题判断是哪个指标
                                    if i > 0 and cell_texts[0]:
                                        period = cell_texts[0]
                                        if '10' in period or '十' in period:
                                            data['pe_percentiles']['10y'] = value
                                        elif '5' in period or '五' in period:
                                            data['pe_percentiles']['5y'] = value
                                        elif '3' in period or '三' in period:
                                            data['pe_percentiles']['3y'] = value
                                        elif '1' in period or '一' in period:
                                            data['pe_percentiles']['1y'] = value
                                except ValueError:
                                    pass

            # 方法3: 查找特定class的元素
            percentile_divs = soup.find_all(['div', 'span'], class_=re.compile(r'percentile|分位'))
            for div in percentile_divs:
                text = div.get_text(strip=True)
                if '%' in text:
                    try:
                        value = float(re.search(r'(\d+\.?\d*)', text).group(1))
                        # 根据上下文判断指标和周期
                        parent_text = div.parent.get_text() if div.parent else ""
                        if 'PE' in parent_text or '市盈' in parent_text:
                            data['pe_percentiles']['current'] = value
                        elif 'PB' in parent_text or '市净' in parent_text:
                            data['pb_percentiles']['current'] = value
                    except (ValueError, AttributeError):
                        pass

        except Exception as e:
            logger.warning(f"解析韭圈儿页面失败: {e}")

        return data

    def _fetch_percentile_legulegu(self, symbol: str) -> Dict[str, Any]:
        """
        备用数据源：乐咕乐股

        URL: https://legulegu.com/stockdata/market-pe/{code}
        """
        data = {
            'pe_percentiles': {},
            'pb_percentiles': {},
            'ps_percentiles': {},
        }

        try:
            # 乐咕乐股的API可能需要不同的处理
            url = f"https://legulegu.com/stockdata/market-pe/{symbol}"
            logger.info(f"尝试备用源: {url}")

            response = self._fetch_with_retry(url, max_retries=2)
            if response:
                soup = BeautifulSoup(response.text, 'html.parser')
                # 解析乐咕乐股页面
                # 具体解析逻辑需要根据实际页面结构调整
                pass

        except Exception as e:
            logger.warning(f"备用源获取失败: {e}")

        return data

    def _fetch_operating_cashflow_direct(self, symbol: str) -> Optional[float]:
        """
        直接获取经营活动现金流净额（优先方法）

        数据源: 新浪财务报表 - 现金流量表
        返回最近报告期的经营现金流总额（元）

        Args:
            symbol: 股票代码

        Returns:
            经营现金流（元），失败返回None
        """
        try:
            # 转换股票代码格式（新浪格式：sh600519 或 sz000001）
            if symbol.startswith(('600', '601', '603', '688')):
                sina_symbol = f'sh{symbol}'
            else:
                sina_symbol = f'sz{symbol}'

            # 获取现金流量表
            df = ak.stock_financial_report_sina(stock=sina_symbol, symbol='现金流量表')

            # 查找目标列
            target_col = '经营活动产生的现金流量净额'
            if target_col in df.columns:
                # 过滤掉NaN，获取最新有效数据
                valid_data = df[df[target_col].notna()]

                if not valid_data.empty:
                    latest_cf = float(valid_data.iloc[0][target_col])
                    report_date = valid_data.iloc[0]['报告日']

                    logger.info(f"✓ 经营现金流（直接获取）: {latest_cf/1e8:.2f}亿 (报告期: {report_date})")
                    return latest_cf

            logger.debug(f"未找到有效的现金流数据: {target_col}")

        except Exception as e:
            logger.debug(f"直接获取现金流失败: {e}")

        return None

    def fetch_fundamental_data(self, symbol: str, stock_name: str) -> Dict[str, Any]:
        """
        获取核心财务指标数据

        包含：
        - 盈利能力：ROE、毛利率、净利率、EPS、BPS
        - 成长性：营收增长率、净利润增长率、EPS增长率
        - 财务健康度：资产负债率、流动比率、速动比率、现金流质量
        - 股本结构：总股本、流通股本、流通比例

        Args:
            symbol: 股票代码
            stock_name: 股票名称

        Returns:
            财务数据字典
        """
        data = {}

        try:
            logger.info(f"💼 获取财务数据: {stock_name} ({symbol})")

            # === 1. 从业绩报表获取核心指标 ===
            try:
                from analyst_data import fetch_performance_data
                perf_data = fetch_performance_data(symbol, stock_name)

                # 盈利能力指标
                if 'roe' in perf_data and perf_data['roe'] != 'N/A':
                    roe_str = perf_data['roe'].replace('%', '')
                    data['roe'] = self._safe_float(roe_str)

                if 'gross_margin' in perf_data and perf_data['gross_margin'] != 'N/A':
                    gm_str = perf_data['gross_margin'].replace('%', '')
                    data['gross_margin'] = self._safe_float(gm_str)

                if 'eps' in perf_data and perf_data['eps'] != 'N/A':
                    data['eps'] = self._safe_float(perf_data['eps'])

                # 成长性指标
                if 'revenue_yoy' in perf_data and perf_data['revenue_yoy'] != 'N/A':
                    rev_yoy_str = perf_data['revenue_yoy'].replace('%', '')
                    data['revenue_yoy'] = self._safe_float(rev_yoy_str)

                if 'revenue_qoq' in perf_data and perf_data['revenue_qoq'] != 'N/A':
                    rev_qoq_str = perf_data['revenue_qoq'].replace('%', '')
                    data['revenue_qoq'] = self._safe_float(rev_qoq_str)

                if 'profit_yoy' in perf_data and perf_data['profit_yoy'] != 'N/A':
                    profit_yoy_str = perf_data['profit_yoy'].replace('%', '')
                    data['profit_yoy'] = self._safe_float(profit_yoy_str)

                if 'profit_qoq' in perf_data and perf_data['profit_qoq'] != 'N/A':
                    profit_qoq_str = perf_data['profit_qoq'].replace('%', '')
                    data['profit_qoq'] = self._safe_float(profit_qoq_str)

                # 现金流质量
                if 'cf_profit_ratio' in perf_data and perf_data['cf_profit_ratio'] != 'N/A':
                    data['ocf_to_profit'] = self._safe_float(perf_data['cf_profit_ratio'])

                logger.info(f"✓ 业绩指标获取完成")

            except Exception as e:
                logger.warning(f"业绩指标获取失败: {type(e).__name__}: {str(e)[:100]}")

            # === 2. 获取资产负债表数据 ===
            try:
                # 转换股票代码格式
                if symbol.startswith(('600', '601', '603', '688')):
                    sina_symbol = f'sh{symbol}'
                else:
                    sina_symbol = f'sz{symbol}'

                # 获取资产负债表
                df_balance = ak.stock_financial_report_sina(stock=sina_symbol, symbol='资产负债表')

                if not df_balance.empty:
                    # 获取最新数据（第一行）
                    latest = df_balance.iloc[0]

                    # 资产负债率 = 负债合计 / 资产总计 * 100%
                    total_liabilities_col = None
                    total_assets_col = None

                    # 查找列名（可能的变体）
                    for col in df_balance.columns:
                        if '负债合计' in col or '负债总计' in col:
                            total_liabilities_col = col
                        if '资产总计' in col or '资产合计' in col:
                            total_assets_col = col

                    if total_liabilities_col and total_assets_col:
                        total_liabilities = self._safe_float(latest[total_liabilities_col])
                        total_assets = self._safe_float(latest[total_assets_col])

                        if total_assets and total_assets > 0:
                            data['debt_asset_ratio'] = round((total_liabilities / total_assets) * 100, 2)
                            logger.info(f"✓ 资产负债率: {data['debt_asset_ratio']}%")

                    # 流动比率 = 流动资产合计 / 流动负债合计
                    current_assets_col = None
                    current_liabilities_col = None

                    for col in df_balance.columns:
                        if '流动资产合计' in col:
                            current_assets_col = col
                        if '流动负债合计' in col:
                            current_liabilities_col = col

                    if current_assets_col and current_liabilities_col:
                        current_assets = self._safe_float(latest[current_assets_col])
                        current_liabilities = self._safe_float(latest[current_liabilities_col])

                        if current_liabilities and current_liabilities > 0:
                            data['current_ratio'] = round(current_assets / current_liabilities, 2)
                            logger.info(f"✓ 流动比率: {data['current_ratio']}")

                    # 速动比率 = (流动资产 - 存货) / 流动负债
                    inventory_col = None
                    for col in df_balance.columns:
                        if '存货' in col and '合计' not in col:
                            inventory_col = col
                            break

                    if current_assets_col and current_liabilities_col and inventory_col:
                        inventory = self._safe_float(latest[inventory_col])
                        if current_assets and current_liabilities and current_liabilities > 0:
                            quick_assets = current_assets - (inventory if inventory else 0)
                            data['quick_ratio'] = round(quick_assets / current_liabilities, 2)
                            logger.info(f"✓ 速动比率: {data['quick_ratio']}")

                    # 每股净资产 (BPS)
                    equity_col = None
                    for col in df_balance.columns:
                        if '股东权益合计' in col or '所有者权益合计' in col:
                            equity_col = col
                            break

                    if equity_col:
                        total_equity = self._safe_float(latest[equity_col])
                        # 需要总股本来计算BPS，稍后从股本结构数据获取

            except Exception as e:
                logger.warning(f"资产负债表获取失败: {type(e).__name__}: {str(e)[:100]}")

            # === 3. 获取股本结构数据 ===
            try:
                df_info = ak.stock_individual_info_em(symbol=symbol)

                if not df_info.empty:
                    info_dict = dict(zip(df_info['item'], df_info['value']))

                    # 总股本（单位：股 -> 转换为亿股）
                    total_shares = info_dict.get('总股本')
                    if total_shares:
                        data['total_shares'] = self._safe_float(total_shares) / 1e8
                        logger.info(f"✓ 总股本: {data['total_shares']:.2f}亿股")

                    # 流通股本（单位：股 -> 转换为亿股）
                    float_shares = info_dict.get('流通股')
                    if float_shares:
                        data['float_shares'] = self._safe_float(float_shares) / 1e8
                        logger.info(f"✓ 流通股本: {data['float_shares']:.2f}亿股")

                    # 计算流通比例
                    if data.get('total_shares') and data.get('float_shares'):
                        data['float_ratio'] = round((data['float_shares'] / data['total_shares']) * 100, 2)
                        logger.info(f"✓ 流通比例: {data['float_ratio']}%")

                    # 计算 BPS（如果有总股本和净资产）
                    # 已在资产负债表中获取了 total_equity
                    # BPS = 净资产 / 总股本

            except Exception as e:
                logger.warning(f"股本结构获取失败: {type(e).__name__}: {str(e)[:100]}")

            # === 4. 获取利润表数据（补充净利率） ===
            try:
                df_profit = ak.stock_financial_report_sina(stock=sina_symbol, symbol='利润表')

                if not df_profit.empty:
                    latest = df_profit.iloc[0]

                    # 净利率 = 净利润 / 营业收入 * 100%
                    net_profit_col = None
                    revenue_col = None

                    for col in df_profit.columns:
                        if '净利润' in col and '合计' not in col and '少数' not in col:
                            net_profit_col = col
                        if '营业收入' in col or '营业总收入' in col:
                            revenue_col = col

                    if net_profit_col and revenue_col:
                        net_profit = self._safe_float(latest[net_profit_col])
                        revenue = self._safe_float(latest[revenue_col])

                        if net_profit is not None and revenue and revenue > 0:
                            data['net_margin'] = round((net_profit / revenue) * 100, 2)
                            logger.info(f"✓ 净利率: {data['net_margin']}%")

                    # EPS 增长率（需要历史数据对比）
                    # 如果有多期数据，计算同比增长
                    if len(df_profit) >= 2 and 'eps' in data:
                        # 这里简化处理，可以从业绩报表获取更准确的增长率
                        pass

            except Exception as e:
                logger.warning(f"利润表获取失败: {type(e).__name__}: {str(e)[:100]}")

            logger.info(f"✅ 财务数据获取完成")

        except Exception as e:
            logger.error(f"❌ 财务数据获取失败: {type(e).__name__}: {str(e)[:100]}")

        return data

    def calculate_ps_pcf(self, symbol: str, stock_name: str, market_cap: float) -> Dict[str, Any]:
        """
        计算 PS-TTM、PCF 和 P/FCF（优化版：多数据源 + 降级策略）

        Args:
            symbol: 股票代码
            stock_name: 股票名称
            market_cap: 总市值（元）

        Returns:
            包含 PS、PCF、P/FCF 的字典
        """
        data = {'ps_ttm': None, 'pcf': None, 'p_fcf': None, 'pcf_source': None}

        if not market_cap or market_cap <= 0:
            return data

        try:
            # 获取业绩数据
            from analyst_data import fetch_performance_data
            perf_data = fetch_performance_data(symbol, stock_name)

            # 计算 PS-TTM = 总市值 / TTM营收
            revenue_ttm = perf_data.get('revenue_ttm_raw')
            if revenue_ttm and revenue_ttm > 0:
                data['ps_ttm'] = market_cap / revenue_ttm
                logger.info(f"✓ PS-TTM: {data['ps_ttm']:.2f}")

            # 计算 PCF = 总市值 / 经营现金流
            # 【优化】优先级1: 直接获取经营现金流总额
            operating_cf = self._fetch_operating_cashflow_direct(symbol)

            if operating_cf and operating_cf > 0:
                data['pcf'] = market_cap / operating_cf
                data['pcf_source'] = 'direct'
                logger.info(f"✓ PCF（直接数据）: {data['pcf']:.2f}")
            elif operating_cf and operating_cf < 0:
                data['pcf'] = None
                data['pcf_note'] = "经营现金流为负"
                logger.info(f"⚠️  经营现金流为负: {operating_cf/1e8:.2f}亿")
            else:
                # 【优化】优先级2: 降级到原逻辑（反推计算）
                logger.debug("直接获取失败，降级到反推逻辑")

                cf_per_share = perf_data.get('cf_per_share_raw')
                eps = perf_data.get('eps_raw')
                pe_ttm = perf_data.get('pe_ttm_raw')

                if cf_per_share and cf_per_share != 0:
                    # 如果有PE和市值，可以反推股本，进而计算PCF
                    # 股本 = 市值 / 股价 ≈ 市值 / (EPS * PE)
                    if eps and eps > 0 and pe_ttm and pe_ttm > 0:
                        stock_price = eps * pe_ttm
                        shares = market_cap / stock_price if stock_price > 0 else 0
                        if shares > 0:
                            operating_cf_fallback = cf_per_share * shares
                            if operating_cf_fallback > 0:
                                data['pcf'] = market_cap / operating_cf_fallback
                                data['pcf_source'] = 'estimated'
                                logger.info(f"✓ PCF（反推估算）: {data['pcf']:.2f}")
                            elif operating_cf_fallback < 0:
                                data['pcf'] = None
                                data['pcf_note'] = "经营现金流为负"

            # 【新增】计算 P/FCF = 总市值 / 自由现金流
            # 自由现金流 = 经营现金流 - 资本开支
            fcf = self._calculate_free_cashflow(symbol)
            if fcf and fcf > 0:
                data['p_fcf'] = market_cap / fcf
                logger.info(f"✓ P/FCF（自由现金流）: {data['p_fcf']:.2f}")
            elif fcf and fcf < 0:
                data['p_fcf'] = None
                data['fcf_note'] = "自由现金流为负"
                logger.info(f"⚠️  自由现金流为负: {fcf/1e8:.2f}亿")

        except ImportError:
            logger.warning("analyst_data 模块不可用，跳过 PS/PCF 计算")
        except Exception as e:
            logger.warning(f"PS/PCF/FCF 计算失败: {e}")

        return data

    def _calculate_free_cashflow(self, symbol: str) -> Optional[float]:
        """
        计算自由现金流（Free Cash Flow）

        FCF = 经营活动现金流净额 - 资本性支出（购建固定资产等支付的现金）

        Args:
            symbol: 股票代码

        Returns:
            自由现金流（元），失败返回None
        """
        try:
            # 转换股票代码格式
            if symbol.startswith(('600', '601', '603', '688')):
                sina_symbol = f'sh{symbol}'
            else:
                sina_symbol = f'sz{symbol}'

            # 获取现金流量表
            df = ak.stock_financial_report_sina(stock=sina_symbol, symbol='现金流量表')

            # 查找经营现金流列
            operating_cf_col = '经营活动产生的现金流量净额'

            # 模糊匹配资本开支列名（处理不同表述）
            capex_col = None
            capex_candidates = [col for col in df.columns if '购' in col and '固定资产' in col and '支付' in col]
            if capex_candidates:
                capex_col = capex_candidates[0]
                logger.debug(f"找到资本开支列: {capex_col}")
            else:
                logger.debug("未找到资本开支列，尝试其他变体")
                # 尝试其他可能的列名
                for col in df.columns:
                    if ('购建' in col or '购置' in col) and '固定资产' in col:
                        capex_col = col
                        logger.debug(f"使用备用资本开支列: {capex_col}")
                        break

            if operating_cf_col in df.columns and capex_col:
                # 过滤掉NaN
                valid_data = df[
                    df[operating_cf_col].notna() &
                    df[capex_col].notna()
                ]

                if not valid_data.empty:
                    latest = valid_data.iloc[0]
                    operating_cf = float(latest[operating_cf_col])
                    capex = float(latest[capex_col])

                    # 自由现金流 = 经营现金流 - 资本开支
                    fcf = operating_cf - capex

                    report_date = latest['报告日']
                    logger.info(
                        f"✓ 自由现金流: 经营{operating_cf/1e8:.2f}亿 - "
                        f"资本开支{capex/1e8:.2f}亿 = {fcf/1e8:.2f}亿 "
                        f"(报告期: {report_date})"
                    )

                    return fcf

        except Exception as e:
            logger.debug(f"自由现金流计算失败: {e}")

        return None

    def analyze(self, symbol: str, stock_name: str = None, market: str = 'A') -> Tuple[ValuationMetrics, str]:
        """
        执行完整估值分析

        Args:
            symbol: 股票代码
            stock_name: 股票名称（可选）
            market: 市场类型 ('A' 或 'HK')

        Returns:
            (ValuationMetrics, 文本摘要)
        """
        metrics = ValuationMetrics()
        metrics.stock_code = symbol
        metrics.stock_name = stock_name or symbol
        metrics.update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        market_tag = "[港股]" if market == 'HK' else ""
        print(f"\n{'='*60}")
        print(f"📊 快速估值分析: {market_tag}{metrics.stock_name} ({symbol})")
        print(f"{'='*60}")

        # 港股使用专用的数据获取逻辑
        if market == 'HK':
            return self._analyze_hk_stock(symbol, stock_name, metrics)

        # A股分析逻辑（保持原有代码）
        # === 数据获取（统一抑制内部 logger 噪音，完成后打印完整进度行）===
        _val_logger = logging.getLogger('valuation_analyzer')
        _root_logger = logging.getLogger()
        _saved_val_level = _val_logger.level
        _saved_root_level = _root_logger.level

        def _quiet():
            _val_logger.setLevel(logging.CRITICAL)
            _root_logger.setLevel(logging.CRITICAL)
            os.environ['TQDM_DISABLE'] = '1'

        def _restore():
            _val_logger.setLevel(_saved_val_level)
            _root_logger.setLevel(_saved_root_level)
            os.environ.pop('TQDM_DISABLE', None)

        def _fmt(val, suffix='', precision=2):
            """格式化数值：None->'N/A', float->保留精度+后缀"""
            if val is None:
                return 'N/A'
            if isinstance(val, float):
                return f"{val:.{precision}f}{suffix}"
            return f"{val}{suffix}"

        # Step 1: 获取当前估值（必须成功）
        _quiet()
        current_data = self.fetch_current_valuation(symbol, metrics.stock_name)
        _restore()
        if not current_data.get('pe_ttm') and not current_data.get('pb'):
            metrics.warnings.append("当前估值数据获取失败")
            print(f"  [ 1/17] 获取估值数据... ❌ 不可用")
        else:
            metrics.pe_ttm = current_data.get('pe_ttm')
            metrics.pb = current_data.get('pb')
            metrics.dividend_yield = current_data.get('dividend_yield')
            metrics.market_cap = current_data.get('market_cap_yi')
            source_map = {
                'xueqiu': '雪球API',
                'baidu_eastmoney': '百度+东财'
            }
            metrics.data_source = source_map.get(current_data.get('source', ''), '未知')
            print(f"  [ 1/17] 获取估值数据... ✅ PE={_fmt(metrics.pe_ttm)} PB={_fmt(metrics.pb)} ({metrics.data_source})")

        # Step 2: 获取实时行情
        _quiet()
        quote_data = self.fetch_realtime_quote(symbol, metrics.stock_name)
        _restore()
        if quote_data:
            metrics.current_price = quote_data.get('current_price')
            metrics.open_price = quote_data.get('open_price')
            metrics.close_price = quote_data.get('close_price')
            metrics.high_price = quote_data.get('high_price')
            metrics.low_price = quote_data.get('low_price')
            metrics.change_pct = quote_data.get('change_pct')
            metrics.change_amount = quote_data.get('change_amount')
            metrics.amplitude = quote_data.get('amplitude')
            metrics.volume = quote_data.get('volume')
            metrics.amount = quote_data.get('amount_yi')  # 已转换为亿
            metrics.turnover_rate = quote_data.get('turnover_rate')
            metrics.volume_ratio = quote_data.get('volume_ratio')

            # 近20日行情
            metrics.recent_20d_data = quote_data.get('recent_20d_data', [])

            # 均线数据
            metrics.ma5 = quote_data.get('ma5')
            metrics.ma10 = quote_data.get('ma10')
            metrics.ma20 = quote_data.get('ma20')
            metrics.ma60 = quote_data.get('ma60')
            metrics.ma120 = quote_data.get('ma120')
            metrics.ma250 = quote_data.get('ma250')

            # 均线距离
            metrics.ma5_distance = quote_data.get('ma5_distance')
            metrics.ma10_distance = quote_data.get('ma10_distance')
            metrics.ma20_distance = quote_data.get('ma20_distance')
            metrics.ma60_distance = quote_data.get('ma60_distance')
            metrics.ma120_distance = quote_data.get('ma120_distance')
            metrics.ma250_distance = quote_data.get('ma250_distance')

            # 技术指标
            metrics.macd_dif = quote_data.get('macd_dif')
            metrics.macd_dea = quote_data.get('macd_dea')
            metrics.macd_hist = quote_data.get('macd_hist')
            metrics.macd_signal = quote_data.get('macd_signal')
            metrics.rsi_6 = quote_data.get('rsi_6')
            metrics.rsi_12 = quote_data.get('rsi_12')
            metrics.rsi_24 = quote_data.get('rsi_24')
            metrics.kdj_k = quote_data.get('kdj_k')
            metrics.kdj_d = quote_data.get('kdj_d')
            metrics.kdj_j = quote_data.get('kdj_j')
            metrics.cci = quote_data.get('cci')

            # 布林带
            metrics.boll_upper = quote_data.get('boll_upper')
            metrics.boll_mid = quote_data.get('boll_mid')
            metrics.boll_lower = quote_data.get('boll_lower')
            metrics.boll_width = quote_data.get('boll_width')
            _chg = f" {metrics.change_pct:+.2f}%" if metrics.change_pct else ""
            print(f"  [ 2/17] 获取实时行情... ✅ {metrics.current_price}元{_chg} MACD={metrics.macd_signal or 'N/A'}")
        else:
            print(f"  [ 2/17] 获取实时行情... ⚠️  跳过")

        # Step 1.5.1: 计算PE-静态
        if metrics.current_price:
            pe_static = self._calculate_pe_static(symbol, metrics.current_price)
            if pe_static:
                metrics.pe_static = pe_static

        # Step 2.5: 计算派生技术指标（纯计算，无API调用）
        if metrics.current_price:
            # boll_position & boll_status
            if metrics.boll_upper and metrics.boll_lower:
                boll_range = metrics.boll_upper - metrics.boll_lower
                if boll_range > 0:
                    metrics.boll_position = round((metrics.current_price - metrics.boll_lower) / boll_range * 100, 1)
                    if metrics.boll_position > 100:
                        metrics.boll_status = "突破上轨，极强"
                    elif metrics.boll_position > 80:
                        metrics.boll_status = "接近上轨，偏强"
                    elif metrics.boll_position > 50:
                        metrics.boll_status = "中轨上方"
                    elif metrics.boll_position > 20:
                        metrics.boll_status = "中轨下方"
                    elif metrics.boll_position > 0:
                        metrics.boll_status = "接近下轨，偏弱"
                    else:
                        metrics.boll_status = "跌破下轨，极弱"

            # ma_alignment
            ma_vals = [v for v in [metrics.ma5, metrics.ma10, metrics.ma20, metrics.ma60] if v is not None]
            if len(ma_vals) >= 3:
                if ma_vals == sorted(ma_vals, reverse=True):
                    metrics.ma_alignment = "多头排列"
                elif ma_vals == sorted(ma_vals):
                    metrics.ma_alignment = "空头排列"
                else:
                    metrics.ma_alignment = "均线纠缠"

            # trend_position
            if metrics.ma250:
                metrics.trend_position = "年线上方(强势)" if metrics.current_price > metrics.ma250 else "年线下方(弱势)"
            elif metrics.ma20:
                metrics.trend_position = "月线上方" if metrics.current_price > metrics.ma20 else "月线下方"

            # change_5d/20d, high/low, volatility — 从 recent_20d_data 计算
            r20 = metrics.recent_20d_data
            if r20 and len(r20) >= 5:
                try:
                    metrics.change_5d = round((metrics.current_price / r20[-5]['close'] - 1) * 100, 2)
                except (KeyError, ZeroDivisionError, TypeError):
                    pass
            if r20 and len(r20) >= 20:
                try:
                    metrics.change_20d = round((metrics.current_price / r20[0]['close'] - 1) * 100, 2)
                    highs = [d['high'] for d in r20]
                    lows = [d['low'] for d in r20]
                    metrics.high_20d = round(max(highs), 2)
                    metrics.low_20d = round(min(lows), 2)
                    if metrics.current_price > 0:
                        metrics.dist_to_high = round((metrics.high_20d / metrics.current_price - 1) * 100, 1)
                        metrics.dist_to_low = round((metrics.current_price / metrics.low_20d - 1) * 100, 1)
                    # 波动率
                    amplitudes = [d.get('amplitude', 0) for d in r20 if d.get('amplitude')]
                    if amplitudes:
                        metrics.volatility_20d = round(sum(amplitudes) / len(amplitudes), 2)
                except (KeyError, ZeroDivisionError, TypeError):
                    pass

        # Step 3: 获取核心财务数据
        _quiet()
        fundamental_data = self.fetch_fundamental_data(symbol, metrics.stock_name)
        _restore()
        if fundamental_data:
            # 盈利能力指标
            metrics.roe = fundamental_data.get('roe')
            metrics.gross_margin = fundamental_data.get('gross_margin')
            metrics.net_margin = fundamental_data.get('net_margin')
            metrics.eps = fundamental_data.get('eps')
            metrics.bps = fundamental_data.get('bps')

            # 成长性指标
            metrics.revenue_yoy = fundamental_data.get('revenue_yoy')
            metrics.revenue_qoq = fundamental_data.get('revenue_qoq')
            metrics.profit_yoy = fundamental_data.get('profit_yoy')
            metrics.profit_qoq = fundamental_data.get('profit_qoq')
            metrics.eps_yoy = fundamental_data.get('eps_yoy')

            # 财务健康度
            metrics.debt_asset_ratio = fundamental_data.get('debt_asset_ratio')
            metrics.current_ratio = fundamental_data.get('current_ratio')
            metrics.quick_ratio = fundamental_data.get('quick_ratio')
            metrics.ocf_to_profit = fundamental_data.get('ocf_to_profit')

            # 股本结构
            metrics.total_shares = fundamental_data.get('total_shares')
            metrics.float_shares = fundamental_data.get('float_shares')
            metrics.float_ratio = fundamental_data.get('float_ratio')
            print(f"  [ 3/17] 获取财务数据... ✅ ROE={_fmt(metrics.roe, '%')} 毛利率={_fmt(metrics.gross_margin, '%')}")
        else:
            print(f"  [ 3/17] 获取财务数据... ⚠️  跳过")

        # Step 4: 获取资金流向（多时间维度）
        _quiet()
        fund_flow_data = self.fetch_fund_flow(symbol, metrics.stock_name)
        _restore()
        if fund_flow_data:
            # 1日数据
            metrics.main_net_inflow_1d = fund_flow_data.get('main_net_inflow_1d')
            metrics.super_net_inflow_1d = fund_flow_data.get('super_net_inflow_1d')
            metrics.big_net_inflow_1d = fund_flow_data.get('big_net_inflow_1d')
            metrics.medium_net_inflow_1d = fund_flow_data.get('medium_net_inflow_1d')
            metrics.small_net_inflow_1d = fund_flow_data.get('small_net_inflow_1d')
            metrics.main_net_inflow_pct_1d = fund_flow_data.get('main_net_inflow_pct_1d')

            # 3日数据
            metrics.main_net_inflow_3d = fund_flow_data.get('main_net_inflow_3d')
            metrics.super_net_inflow_3d = fund_flow_data.get('super_net_inflow_3d')
            metrics.big_net_inflow_3d = fund_flow_data.get('big_net_inflow_3d')
            metrics.medium_net_inflow_3d = fund_flow_data.get('medium_net_inflow_3d')
            metrics.small_net_inflow_3d = fund_flow_data.get('small_net_inflow_3d')

            # 7日数据
            metrics.main_net_inflow_7d = fund_flow_data.get('main_net_inflow_7d')
            metrics.super_net_inflow_7d = fund_flow_data.get('super_net_inflow_7d')
            metrics.big_net_inflow_7d = fund_flow_data.get('big_net_inflow_7d')
            metrics.medium_net_inflow_7d = fund_flow_data.get('medium_net_inflow_7d')
            metrics.small_net_inflow_7d = fund_flow_data.get('small_net_inflow_7d')
            _inflow = metrics.main_net_inflow_1d
            _inflow_str = f"{_inflow:+.2f}亿" if _inflow else "N/A"
            print(f"  [ 4/17] 获取资金流向... ✅ 主力净流入(1日)={_inflow_str}")
        else:
            print(f"  [ 4/17] 获取资金流向... ⚠️  跳过")

        # Step 5: 获取历史分位（可降级）
        _quiet()
        percentile_data = self.fetch_historical_percentile(symbol)
        _restore()
        if percentile_data.get('pe_percentiles'):
            pe_pcts = percentile_data['pe_percentiles']
            metrics.pe_percentile_10y = pe_pcts.get('10y')
            metrics.pe_percentile_5y = pe_pcts.get('5y')
            metrics.pe_percentile_3y = pe_pcts.get('3y')
            metrics.pe_percentile_1y = pe_pcts.get('1y')
        else:
            metrics.warnings.append("历史分位数据不可用（网站可能需要登录或结构变化）")

        if percentile_data.get('pb_percentiles'):
            pb_pcts = percentile_data['pb_percentiles']
            metrics.pb_percentile_10y = pb_pcts.get('10y')
            metrics.pb_percentile_5y = pb_pcts.get('5y')
            metrics.pb_percentile_3y = pb_pcts.get('3y')
            metrics.pb_percentile_1y = pb_pcts.get('1y')

        if metrics.pe_percentile_3y or metrics.pb_percentile_3y:
            print(f"  [ 5/17] 获取历史分位... ✅ PE分位(3y)={_fmt(metrics.pe_percentile_3y, '%')} PB分位(3y)={_fmt(metrics.pb_percentile_3y, '%')}")
        else:
            print(f"  [ 5/17] 获取历史分位... ⚠️  不可用")

        # Step 6: 计算 PS、PCF 和 P/FCF（可降级）
        print(f"  [ 6/17] 计算PS/PCF...", end="", flush=True)
        if current_data.get('market_cap'):
            _quiet()
            ps_pcf_data = self.calculate_ps_pcf(symbol, metrics.stock_name, current_data['market_cap'])
            _restore()
            metrics.ps_ttm = ps_pcf_data.get('ps_ttm')
            metrics.pcf = ps_pcf_data.get('pcf')
            metrics.p_fcf = ps_pcf_data.get('p_fcf')  # 新增
            if ps_pcf_data.get('pcf_note'):
                metrics.warnings.append(ps_pcf_data['pcf_note'])
            if ps_pcf_data.get('fcf_note'):
                metrics.warnings.append(ps_pcf_data['fcf_note'])
            print(f" ✅ PS={_fmt(metrics.ps_ttm)} PCF={_fmt(metrics.pcf)}")
        else:
            print(" ⚠️  跳过(无市值)")

        # Step 7: 获取季度趋势
        _quiet()
        metrics.quarterly_trend = self.fetch_quarterly_trend(symbol, metrics.stock_name)
        _restore()
        _qt_len = len(metrics.quarterly_trend) if metrics.quarterly_trend else 0
        print(f"  [ 7/17] 获取季度趋势... ✅ {_qt_len}个季度" if _qt_len else "  [ 7/17] 获取季度趋势... ⚠️  跳过")

        # Step 8: 获取行业对比
        _quiet()
        industry_data = self.fetch_industry_comparison(symbol, metrics.stock_name)
        _restore()
        if industry_data:
            metrics.industry_name = industry_data.get('industry_name')
            metrics.industry_comparison = industry_data
            print(f"  [ 8/17] 获取行业对比... ✅ {metrics.industry_name or '未知行业'} ({industry_data.get('peer_count', '?')}家)")
        else:
            print(f"  [ 8/17] 获取行业对比... ⚠️  跳过")

        # Step 9: 获取十大流通股东
        _quiet()
        holders_data = self.fetch_top_holders(symbol, metrics.stock_name)
        _restore()
        if holders_data:
            metrics.top_holders_current = holders_data.get('current', [])
            metrics.top_holders_report_date = holders_data.get('current_date')
            metrics.top_holders_prev_date = holders_data.get('previous_date')
            metrics.top_holders_previous = holders_data.get('previous_map', {})
            metrics.top_holders_data_date = holders_data.get('current_date')
            print(f"  [ 9/17] 获取股东数据... ✅ {len(metrics.top_holders_current)}位股东 ({metrics.top_holders_report_date or ''})")
        else:
            print(f"  [ 9/17] 获取股东数据... ⚠️  跳过")

        # Step 10: 获取分析师一致预期
        _quiet()
        try:
            consensus_data = fetch_consensus_data(symbol, metrics.stock_name)
            if consensus_data:
                metrics.consensus_data_date = consensus_data.get('consensus_data_date')
                metrics.eps_forecast_current = consensus_data.get('eps_forecast_current')
                metrics.eps_forecast_next = consensus_data.get('eps_forecast_next')
                metrics.eps_growth_rate = consensus_data.get('eps_growth_rate')
                metrics.eps_growth_rate_raw = consensus_data.get('eps_growth_rate_raw')
                metrics.rating_buy = consensus_data.get('rating_buy')
                metrics.rating_overweight = consensus_data.get('rating_overweight')
                metrics.rating_hold = consensus_data.get('rating_hold')
                metrics.target_price_avg = consensus_data.get('target_price_avg')
                metrics.target_price_high = consensus_data.get('target_price_high')
                metrics.target_price_low = consensus_data.get('target_price_low')
                metrics.peg_signal = consensus_data.get('peg_signal')
                metrics.consensus_summary = consensus_data.get('consensus_summary')
                _tp = f" 目标价={_fmt(metrics.target_price_avg)}" if metrics.target_price_avg else ""
                _restore()
                print(f"  [10/17] 获取分析师预期... ✅ 买入={metrics.rating_buy or 0} 增持={metrics.rating_overweight or 0}{_tp}")
            else:
                _restore()
                print(f"  [10/17] 获取分析师预期... ⚠️  无数据")
        except Exception as e:
            _restore()
            print(f"  [10/17] 获取分析师预期... ⚠️  失败")

        # Step 11: 获取大盘/板块环境
        _quiet()
        try:
            market_env_data = fetch_market_env_data(symbol, metrics.stock_name)
            if market_env_data:
                metrics.market_env_data_date = market_env_data.get('market_env_data_date')
                metrics.market_index_change_5d = market_env_data.get('market_index_change_5d')
                metrics.market_index_change_20d = market_env_data.get('market_index_change_20d')
                metrics.market_index_above_ma20 = market_env_data.get('market_index_above_ma20')
                metrics.market_sentiment = market_env_data.get('market_sentiment')
                metrics.sector_name = market_env_data.get('sector_name')
                metrics.sector_change_today = market_env_data.get('sector_change_today')
                metrics.sector_rank = market_env_data.get('sector_rank')
                metrics.sector_main_inflow = market_env_data.get('sector_main_inflow')
                metrics.market_env_summary = market_env_data.get('market_env_summary')
                _restore()
                print(f"  [11/17] 获取大盘环境... ✅ {metrics.market_sentiment or ''} 板块={metrics.sector_name or 'N/A'}")
            else:
                _restore()
                print(f"  [11/17] 获取大盘环境... ⚠️  无数据")
        except Exception as e:
            _restore()
            print(f"  [11/17] 获取大盘环境... ⚠️  失败")

        # Step 12: 获取解禁/筹码/机构
        _quiet()
        _sub_ok = []
        try:
            lockup_data = fetch_lockup_data(symbol, metrics.stock_name)
            if lockup_data:
                metrics.lockup_data_date = lockup_data.get('lockup_data_date')
                metrics.lockup_events = lockup_data.get('lockup_events', [])
                metrics.lockup_nearest_date = lockup_data.get('lockup_nearest_date')
                metrics.lockup_6m_total_pct = lockup_data.get('lockup_6m_total_pct')
                metrics.lockup_risk_level = lockup_data.get('lockup_risk_level')
                metrics.lockup_summary = lockup_data.get('lockup_summary')
                _sub_ok.append("解禁")
        except Exception as e:
            logger.debug(f"解禁数据获取失败: {e}")

        # Step 10: 获取筹码分布
        try:
            chip_data = fetch_chip_data(symbol, metrics.stock_name)
            if chip_data:
                metrics.chip_data_date = chip_data.get('chip_data_date')
                metrics.chip_profit_ratio = chip_data.get('chip_profit_ratio')
                metrics.chip_profit_ratio_raw = chip_data.get('chip_profit_ratio_raw')
                metrics.chip_avg_cost = chip_data.get('chip_avg_cost')
                metrics.chip_avg_cost_raw = chip_data.get('chip_avg_cost_raw')
                metrics.chip_concentration_70 = chip_data.get('chip_concentration_70')
                metrics.chip_concentration_90 = chip_data.get('chip_concentration_90')
                metrics.chip_signal = chip_data.get('chip_signal')
                metrics.chip_summary = chip_data.get('chip_summary')
                _sub_ok.append("筹码")
        except Exception as e:
            logger.debug(f"筹码数据获取失败: {e}")

        # Step 11: 获取机构持仓变化
        try:
            institution_data = fetch_institution_data(symbol, metrics.stock_name)
            if institution_data:
                metrics.institution_data_date = institution_data.get('institution_data_date')
                metrics.fund_holding_count = institution_data.get('fund_holding_count')
                metrics.fund_holding_count_prev = institution_data.get('fund_holding_count_prev')
                metrics.fund_holding_change = institution_data.get('fund_holding_change')
                metrics.fund_holding_pct = institution_data.get('fund_holding_pct')
                metrics.top_funds = institution_data.get('top_funds', [])
                metrics.institution_summary = institution_data.get('institution_summary')
                _sub_ok.append("机构")
        except Exception as e:
            pass

        _restore()
        print(f"  [12/17] 获取解禁/筹码/机构... ✅ {'/'.join(_sub_ok)}" if _sub_ok else "  [12/17] 获取解禁/筹码/机构... ⚠️  跳过")

        # Step 13: 获取竞争对手对比
        _quiet()
        try:
            competitor_data = fetch_competitor_data(symbol, metrics.stock_name)
            if competitor_data:
                metrics.competitor_data_date = competitor_data.get('competitor_data_date')
                metrics.competitors = competitor_data.get('competitors', [])
                metrics.industry_peer_count = competitor_data.get('industry_peer_count')
                metrics.competitor_summary = competitor_data.get('competitor_summary')
                _restore()
                print(f"  [13/17] 获取竞争对手... ✅ {metrics.industry_peer_count or len(metrics.competitors)}家同行")
            else:
                _restore()
                print(f"  [13/17] 获取竞争对手... ⚠️  无数据")
        except Exception as e:
            _restore()
            print(f"  [13/17] 获取竞争对手... ⚠️  失败")

        # Step 14: 获取聪明钱动向
        _quiet()
        try:
            smart_money_data = fetch_smart_money_data(symbol, metrics.stock_name)
            if smart_money_data:
                metrics.smart_money_data_date = smart_money_data.get('smart_money_data_date')
                metrics.north_consecutive_days = smart_money_data.get('north_consecutive_days')
                metrics.north_change_pct_3d = smart_money_data.get('north_change_pct_3d')
                metrics.north_holding_ratio = smart_money_data.get('north_holding_ratio')
                metrics.margin_balance = smart_money_data.get('margin_balance')
                metrics.margin_balance_trend = smart_money_data.get('margin_balance_trend')
                metrics.short_selling_ratio = smart_money_data.get('short_selling_ratio')
                metrics.short_selling_level = smart_money_data.get('short_selling_level')
                metrics.smart_money_summary = smart_money_data.get('smart_money_summary')
                _restore()
                print(f"  [14/17] 获取聪明钱动向... ✅ {metrics.smart_money_summary or ''}")
            else:
                _restore()
                print(f"  [14/17] 获取聪明钱动向... ⚠️  无数据")
        except Exception as e:
            _restore()
            print(f"  [14/17] 获取聪明钱动向... ⚠️  失败")

        # Step 15: 获取情绪与题材
        _quiet()
        try:
            theme_data = fetch_theme_sentiment_data(symbol, metrics.stock_name)
            if theme_data:
                metrics.theme_sentiment_data_date = theme_data.get('theme_sentiment_data_date')
                metrics.stock_sentiment = theme_data.get('stock_sentiment')
                metrics.hot_concepts = theme_data.get('hot_concepts', [])
                metrics.hot_concepts_change = theme_data.get('hot_concepts_change', [])
                metrics.theme_sentiment_summary = theme_data.get('theme_sentiment_summary')
                _restore()
                print(f"  [15/17] 获取情绪与题材... ✅ {metrics.theme_sentiment_summary or ''}")
            else:
                _restore()
                print(f"  [15/17] 获取情绪与题材... ⚠️  无数据")
        except Exception as e:
            _restore()
            print(f"  [15/17] 获取情绪与题材... ⚠️  失败")

        # Step 16: 计算支撑压力与风险（无需新API，从已有数据计算）
        try:
            sr_context = {
                'current_price': metrics.current_price,
                'ma20': metrics.ma20, 'ma60': metrics.ma60,
                'ma120': metrics.ma120, 'ma250': metrics.ma250,
                'boll_upper': metrics.boll_upper, 'boll_lower': metrics.boll_lower,
                'chip_avg_cost_raw': metrics.chip_avg_cost_raw,
                'recent_20d_data': metrics.recent_20d_data,
                'industry_name': metrics.industry_name,
                'sector_name': metrics.sector_name,
            }
            sr_data = fetch_support_resistance_data(symbol, metrics.stock_name, sr_context)
            if sr_data:
                metrics.resistance_price = sr_data.get('resistance_price')
                metrics.resistance_type = sr_data.get('resistance_type')
                metrics.support_price = sr_data.get('support_price')
                metrics.support_type = sr_data.get('support_type')
                metrics.fx_sensitivity = sr_data.get('fx_sensitivity')
                metrics.support_resistance_summary = sr_data.get('support_resistance_summary')
                print(f"  [16/17] 计算支撑压力位... ✅ {metrics.support_resistance_summary or ''}")
            else:
                print(f"  [16/17] 计算支撑压力位... ⚠️  无数据")
        except Exception as e:
            print(f"  [16/17] 计算支撑压力位... ⚠️  失败")

        # Step 17: 获取舆情数据
        try:
            _quiet()
            news_data = fetch_news_data(symbol, stock_name)
            _restore()
            if news_data and news_data.get('news_summary'):
                metrics.news_summary = news_data.get('news_summary')
                metrics.news_context = news_data.get('news_context')
                metrics.news_source = news_data.get('news_source')
                metrics.news_data_date = news_data.get('news_data_date')
                print(f"  [17/17] 获取舆情数据... ✅ {metrics.news_summary or ''}")
            else:
                _restore()
                print(f"  [17/17] 获取舆情数据... ⚠️  无数据")
        except Exception as e:
            _restore()
            print(f"  [17/17] 获取舆情数据... ⚠️  失败")

        # 计算PEG
        if metrics.pe_ttm and metrics.eps_growth_rate_raw and metrics.eps_growth_rate_raw > 0:
            peg = metrics.pe_ttm / metrics.eps_growth_rate_raw
            metrics.peg = f"{peg:.2f}"
            metrics.peg_raw = peg
            if peg < 0.5:
                metrics.peg_signal = f"极度低估(PEG={peg:.2f}<0.5)"
            elif peg < 1:
                metrics.peg_signal = f"偏低估(PEG={peg:.2f}<1)"
            elif peg < 1.5:
                metrics.peg_signal = f"合理(PEG={peg:.2f})"
            elif peg < 2:
                metrics.peg_signal = f"偏高估(PEG={peg:.2f})"
            else:
                metrics.peg_signal = f"高估(PEG={peg:.2f}>2)"

        # 设置数据时效性日期
        metrics.valuation_data_date = datetime.now().strftime('%Y-%m-%d %H:%M')
        metrics.sentiment_data_date = datetime.now().strftime('%Y-%m-%d %H:%M')

        # 生成文本摘要
        summary = self._generate_summary(metrics)

        print(f"{'='*60}")
        print(f"✅ 估值分析完成！\n")

        return metrics, summary

    def _analyze_hk_stock(self, symbol: str, stock_name: str, metrics: ValuationMetrics) -> Tuple[ValuationMetrics, str]:
        """
        港股专用分析方法

        Args:
            symbol: 股票代码（5位）
            stock_name: 股票名称
            metrics: 估值指标对象

        Returns:
            (ValuationMetrics, 文本摘要)
        """
        logger.info("🇭🇰 使用港股数据获取逻辑...")

        try:
            # 获取港股实时行情数据
            df_hk = ak.stock_hk_main_board_spot_em()
            symbol_5d = symbol.zfill(5)

            # 查找对应股票
            stock_row = df_hk[df_hk['代码'] == symbol_5d]

            if stock_row.empty:
                logger.warning(f"⚠️  未找到港股 {symbol_5d}")
                metrics.warnings.append(f"未找到港股数据: {symbol_5d}")
            else:
                row = stock_row.iloc[0]

                # 基本行情数据
                metrics.current_price = self._safe_float(row.get('最新价'))
                metrics.close_price = self._safe_float(row.get('昨收'))
                metrics.high_price = self._safe_float(row.get('最高'))
                metrics.low_price = self._safe_float(row.get('最低'))
                metrics.open_price = self._safe_float(row.get('今开'))
                metrics.change_pct = self._safe_float(row.get('涨跌幅'))
                metrics.change_amount = self._safe_float(row.get('涨跌额'))

                # 成交数据
                volume = self._safe_float(row.get('成交量'))
                if volume:
                    metrics.volume = volume
                amount = self._safe_float(row.get('成交额'))
                if amount:
                    metrics.amount = amount / 1e8  # 转换为亿

                # 换手率
                metrics.turnover_rate = self._safe_float(row.get('换手率'))

                # 估值指标
                metrics.pe_ttm = self._safe_float(row.get('市盈率'))
                metrics.pb = self._safe_float(row.get('市净率'))

                # 市值
                market_cap = self._safe_float(row.get('总市值'))
                if market_cap:
                    metrics.market_cap = market_cap / 1e8  # 转换为亿港元

                metrics.data_source = '东方财富(港股)'
                logger.info(f"✅ 港股数据获取成功: 价格={metrics.current_price}, PE={metrics.pe_ttm}, PB={metrics.pb}")

        except Exception as e:
            logger.error(f"❌ 港股数据获取失败: {e}")
            metrics.warnings.append(f"港股数据获取异常: {str(e)[:50]}")

        # 生成摘要
        summary = self._generate_hk_summary(metrics)

        logger.info(f"\n✅ 港股估值分析完成！")

        return metrics, summary

    def _generate_hk_summary(self, metrics: ValuationMetrics) -> str:
        """生成港股估值摘要"""
        lines = []

        lines.append(f"## [港股] {metrics.stock_name} ({metrics.stock_code}) 估值摘要")
        lines.append(f"更新时间: {metrics.update_time}")
        if metrics.data_source:
            lines.append(f"数据来源: {metrics.data_source}")
        lines.append("")

        # 股票基本信息
        if metrics.current_price:
            lines.append("### 股票基本信息")
            lines.append(f"- 当前价: {metrics.current_price:.3f} 港元")
            if metrics.close_price:
                lines.append(f"- 昨收价: {metrics.close_price:.3f} 港元")
            if metrics.change_pct is not None:
                lines.append(f"- 涨跌幅: {metrics.change_pct:+.2f}%")
            if metrics.change_amount is not None:
                lines.append(f"- 涨跌额: {metrics.change_amount:+.3f} 港元")
            if metrics.open_price:
                lines.append(f"- 开盘价: {metrics.open_price:.3f} 港元")
            if metrics.high_price and metrics.low_price:
                lines.append(f"- 最高价: {metrics.high_price:.3f} 港元")
                lines.append(f"- 最低价: {metrics.low_price:.3f} 港元")
            if metrics.volume:
                volume_wan = metrics.volume / 10000
                lines.append(f"- 成交量: {volume_wan:.2f}万股")
            if metrics.amount:
                lines.append(f"- 成交额: {metrics.amount:.2f}亿港元")
            if metrics.turnover_rate:
                lines.append(f"- 换手率: {metrics.turnover_rate:.2f}%")
            lines.append("")

        # 估值指标
        if metrics.pe_ttm or metrics.pb or metrics.market_cap:
            lines.append("### 估值指标")
            if metrics.pe_ttm:
                lines.append(f"- 市盈率(PE): {metrics.pe_ttm:.2f}")
            if metrics.pb:
                lines.append(f"- 市净率(PB): {metrics.pb:.2f}")
            if metrics.market_cap:
                lines.append(f"- 总市值: {metrics.market_cap:.2f}亿港元")
            lines.append("")

        # 警告信息
        if metrics.warnings:
            lines.append("### ⚠️ 数据说明")
            for warning in metrics.warnings:
                lines.append(f"- {warning}")
            lines.append("")

        lines.append("---")
        lines.append("*注：港股数据来自东方财富，PE/PB等指标可能与其他数据源略有差异*")
        lines.append("*港股历史分位数据暂不支持*")

        return "\n".join(lines)

    def _generate_summary(self, metrics: ValuationMetrics) -> str:
        """生成估值摘要文本（按投资决策优先级排序）"""
        lines = []

        lines.append(f"## {metrics.stock_name} ({metrics.stock_code}) 估值摘要")
        lines.append(f"更新时间: {metrics.update_time}")
        if metrics.data_source:
            lines.append(f"数据来源: {metrics.data_source}")
        lines.append("")

        # ===== 第一优先级：核心估值 =====

        # 股票基本信息（价格、涨跌幅等）
        if metrics.current_price or metrics.change_pct:
            lines.append("### 📊 核心估值与行情")
            if metrics.current_price:
                lines.append(f"- 当前价: {metrics.current_price:.2f}元")
            if metrics.change_pct is not None:
                lines.append(f"- 涨跌幅: {metrics.change_pct:+.2f}%")
            if metrics.market_cap:
                lines.append(f"- 总市值: {metrics.market_cap:.0f}亿")
            lines.append("")

        # 当前估值指标
        lines.append("#### 估值指标")
        lines.append(f"- PE-TTM: {metrics.pe_ttm or 'N/A'}")
        if metrics.pe_static:
            lines.append(f"- PE-静态: {metrics.pe_static:.2f}")
        lines.append(f"- PB: {metrics.pb or 'N/A'}")
        lines.append(f"- PS-TTM: {f'{metrics.ps_ttm:.2f}' if metrics.ps_ttm else 'N/A'}")
        lines.append(f"- PCF: {f'{metrics.pcf:.2f}' if metrics.pcf else 'N/A'}")
        lines.append(f"- P/FCF: {f'{metrics.p_fcf:.2f}' if metrics.p_fcf else 'N/A'}")
        lines.append(f"- 股息率(TTM): {f'{metrics.dividend_yield:.2f}%' if metrics.dividend_yield else 'N/A'}")
        if metrics.peg:
            lines.append(f"- PEG: {metrics.peg} ({metrics.peg_signal or 'N/A'})")
        lines.append("")

        # 历史分位
        lines.append("#### PE历史分位")
        lines.append(f"- 10年: {f'{metrics.pe_percentile_10y:.1f}%' if metrics.pe_percentile_10y else 'N/A'} | 5年: {f'{metrics.pe_percentile_5y:.1f}%' if metrics.pe_percentile_5y else 'N/A'} | 3年: {f'{metrics.pe_percentile_3y:.1f}%' if metrics.pe_percentile_3y else 'N/A'} | 1年: {f'{metrics.pe_percentile_1y:.1f}%' if metrics.pe_percentile_1y else 'N/A'}")
        lines.append("#### PB历史分位")
        lines.append(f"- 10年: {f'{metrics.pb_percentile_10y:.1f}%' if metrics.pb_percentile_10y else 'N/A'} | 5年: {f'{metrics.pb_percentile_5y:.1f}%' if metrics.pb_percentile_5y else 'N/A'} | 3年: {f'{metrics.pb_percentile_3y:.1f}%' if metrics.pb_percentile_3y else 'N/A'} | 1年: {f'{metrics.pb_percentile_1y:.1f}%' if metrics.pb_percentile_1y else 'N/A'}")
        lines.append("")

        # ===== 第二优先级：趋势与技术面 =====

        # 均线信息
        if metrics.ma5 or metrics.ma20 or metrics.ma60:
            lines.append("### 📈 趋势与技术面")
            if metrics.ma5:
                dist_str = f" (距离{metrics.ma5_distance:+.2f}%)" if metrics.ma5_distance else ""
                lines.append(f"- MA5: {metrics.ma5:.2f}元{dist_str}")
            if metrics.ma10:
                dist_str = f" (距离{metrics.ma10_distance:+.2f}%)" if metrics.ma10_distance else ""
                lines.append(f"- MA10: {metrics.ma10:.2f}元{dist_str}")
            if metrics.ma20:
                dist_str = f" (距离{metrics.ma20_distance:+.2f}%)" if metrics.ma20_distance else ""
                lines.append(f"- MA20: {metrics.ma20:.2f}元{dist_str}")
            if metrics.ma60:
                dist_str = f" (距离{metrics.ma60_distance:+.2f}%)" if metrics.ma60_distance else ""
                lines.append(f"- MA60: {metrics.ma60:.2f}元{dist_str}")
            if metrics.ma120:
                dist_str = f" (距离{metrics.ma120_distance:+.2f}%)" if metrics.ma120_distance else ""
                lines.append(f"- MA120: {metrics.ma120:.2f}元{dist_str}")
            if metrics.ma250:
                dist_str = f" (距离{metrics.ma250_distance:+.2f}%)" if metrics.ma250_distance else ""
                lines.append(f"- MA250: {metrics.ma250:.2f}元{dist_str}")
            lines.append("")

        # 技术指标
        if any([metrics.macd_signal, metrics.rsi_12, metrics.kdj_k, metrics.cci]):
            lines.append("#### 技术指标")
            if metrics.macd_signal:
                lines.append(f"- MACD: {metrics.macd_signal}")
                if metrics.macd_dif and metrics.macd_dea:
                    lines.append(f"  - DIF: {metrics.macd_dif:.3f}, DEA: {metrics.macd_dea:.3f}, HIST: {metrics.macd_hist:.3f}")
            if metrics.rsi_6 or metrics.rsi_12 or metrics.rsi_24:
                rsi_parts = []
                if metrics.rsi_6:
                    rsi_parts.append(f"RSI(6): {metrics.rsi_6:.2f}")
                if metrics.rsi_12:
                    rsi_parts.append(f"RSI(12): {metrics.rsi_12:.2f}")
                if metrics.rsi_24:
                    rsi_parts.append(f"RSI(24): {metrics.rsi_24:.2f}")
                lines.append(f"- {', '.join(rsi_parts)}")
            if metrics.kdj_k and metrics.kdj_d and metrics.kdj_j:
                lines.append(f"- KDJ: K={metrics.kdj_k:.2f}, D={metrics.kdj_d:.2f}, J={metrics.kdj_j:.2f}")
            if metrics.cci:
                lines.append(f"- CCI: {metrics.cci:.2f}")
            if metrics.boll_mid:
                price = metrics.current_price or 0
                if price and metrics.boll_upper and metrics.boll_lower:
                    boll_range = metrics.boll_upper - metrics.boll_lower
                    if boll_range > 0:
                        pos_pct = (price - metrics.boll_lower) / boll_range * 100
                        if pos_pct > 100:
                            pos_desc = "突破上轨，极强"
                        elif pos_pct > 80:
                            pos_desc = "接近上轨，偏强"
                        elif pos_pct < 0:
                            pos_desc = "跌破下轨，极弱"
                        elif pos_pct < 20:
                            pos_desc = "接近下轨，偏弱"
                        else:
                            pos_desc = "中轨附近"
                    else:
                        pos_pct = 50
                        pos_desc = "窄幅"
                    lines.append(f"- BOLL(20,2): 上轨={metrics.boll_upper:.2f}, 中轨={metrics.boll_mid:.2f}, 下轨={metrics.boll_lower:.2f}")
                    lines.append(f"  - 当前位置: {pos_pct:.0f}% ({pos_desc}), 带宽={metrics.boll_width:.1f}%")
            # 派生技术信号
            if metrics.ma_alignment:
                lines.append(f"- 均线状态: {metrics.ma_alignment}")
            if metrics.trend_position:
                lines.append(f"- 趋势位置: {metrics.trend_position}")
            if metrics.boll_status:
                lines.append(f"- 布林位置: {metrics.boll_status} ({metrics.boll_position:.0f}%)")
            if metrics.change_5d is not None:
                _c20 = f"{metrics.change_20d:+.2f}%" if metrics.change_20d is not None else "N/A"
                lines.append(f"- 涨跌幅: 5日{metrics.change_5d:+.2f}% | 20日{_c20}")
            if metrics.volatility_20d:
                lines.append(f"- 20日波动率: {metrics.volatility_20d:.2f}%")
            lines.append("")

        # 支撑压力
        if metrics.support_resistance_summary:
            lines.append("#### 支撑压力位")
            lines.append(f"- {metrics.support_resistance_summary}")
            if metrics.resistance_price:
                lines.append(f"- 压力位: {metrics.resistance_price:.2f}元 ({metrics.resistance_type or ''})")
            if metrics.support_price:
                lines.append(f"- 支撑位: {metrics.support_price:.2f}元 ({metrics.support_type or ''})")
            lines.append("")

        # ===== 第三优先级：资金面 =====

        if metrics.main_net_inflow_1d is not None or metrics.main_net_inflow_3d is not None or metrics.main_net_inflow_7d is not None:
            lines.append("### 💰 资金面")

            if metrics.main_net_inflow_1d is not None:
                lines.append("#### 当日")
                flow_status = "净流入" if metrics.main_net_inflow_1d > 0 else "净流出"
                lines.append(f"- 主力资金: {flow_status} {abs(metrics.main_net_inflow_1d):.2f}亿")
                if metrics.main_net_inflow_pct_1d:
                    lines.append(f"  - 主力净流入占比: {metrics.main_net_inflow_pct_1d:.2f}%")
                if metrics.super_net_inflow_1d is not None:
                    lines.append(f"  - 超大单: {metrics.super_net_inflow_1d:+.2f}亿")
                if metrics.big_net_inflow_1d is not None:
                    lines.append(f"  - 大单: {metrics.big_net_inflow_1d:+.2f}亿")
                if metrics.medium_net_inflow_1d is not None:
                    lines.append(f"  - 中单: {metrics.medium_net_inflow_1d:+.2f}亿")
                if metrics.small_net_inflow_1d is not None:
                    lines.append(f"  - 小单: {metrics.small_net_inflow_1d:+.2f}亿")
            if metrics.main_net_inflow_3d is not None:
                lines.append("#### 近3日")
                flow_status = "净流入" if metrics.main_net_inflow_3d > 0 else "净流出"
                lines.append(f"- 主力资金: {flow_status} {abs(metrics.main_net_inflow_3d):.2f}亿")
                if metrics.super_net_inflow_3d is not None:
                    lines.append(f"  - 超大单: {metrics.super_net_inflow_3d:+.2f}亿 | 大单: {metrics.big_net_inflow_3d:+.2f}亿" if metrics.big_net_inflow_3d else f"  - 超大单: {metrics.super_net_inflow_3d:+.2f}亿")
            if metrics.main_net_inflow_7d is not None:
                lines.append("#### 近7日（1周）")
                flow_status = "净流入" if metrics.main_net_inflow_7d > 0 else "净流出"
                lines.append(f"- 主力资金: {flow_status} {abs(metrics.main_net_inflow_7d):.2f}亿")
                if metrics.super_net_inflow_7d is not None:
                    lines.append(f"  - 超大单: {metrics.super_net_inflow_7d:+.2f}亿 | 大单: {metrics.big_net_inflow_7d:+.2f}亿" if metrics.big_net_inflow_7d else f"  - 超大单: {metrics.super_net_inflow_7d:+.2f}亿")
            lines.append("")

        # 聪明钱动向
        if metrics.smart_money_summary:
            lines.append("#### 聪明钱动向")
            lines.append(f"- {metrics.smart_money_summary}")
            if metrics.north_consecutive_days is not None:
                direction = "加仓" if metrics.north_consecutive_days > 0 else "减仓"
                lines.append(f"- 北向连续{abs(metrics.north_consecutive_days)}日{direction}")
            if metrics.north_holding_ratio is not None:
                lines.append(f"- 北向持股占比: {metrics.north_holding_ratio:.2f}%")
            if metrics.margin_balance is not None:
                lines.append(f"- 融资余额: {metrics.margin_balance:.1f}亿 (趋势: {metrics.margin_balance_trend or 'N/A'})")
            lines.append("")

        # 筹码分布
        if metrics.chip_summary:
            lines.append(f"#### 筹码分布 (数据截至: {metrics.chip_data_date or 'N/A'})")
            lines.append(f"- {metrics.chip_summary}")
            if metrics.chip_concentration_70:
                lines.append(f"- 70%集中度: {metrics.chip_concentration_70}")
            if metrics.chip_concentration_90:
                lines.append(f"- 90%集中度: {metrics.chip_concentration_90}")
            lines.append("")

        # ===== 第四优先级：基本面 =====

        if any([metrics.roe, metrics.gross_margin, metrics.net_margin, metrics.revenue_yoy,
                metrics.profit_yoy, metrics.debt_asset_ratio, metrics.total_shares]):
            lines.append("### 📋 基本面")

            if metrics.roe or metrics.gross_margin or metrics.net_margin or metrics.eps:
                lines.append("#### 盈利能力")
                if metrics.roe is not None:
                    lines.append(f"- ROE: {metrics.roe:.2f}%")
                if metrics.gross_margin is not None:
                    lines.append(f"- 毛利率: {metrics.gross_margin:.2f}%")
                if metrics.net_margin is not None:
                    lines.append(f"- 净利率: {metrics.net_margin:.2f}%")
                if metrics.eps is not None:
                    lines.append(f"- EPS: {metrics.eps:.2f}元")
                if metrics.bps is not None:
                    lines.append(f"- BPS: {metrics.bps:.2f}元")

            if metrics.revenue_yoy or metrics.profit_yoy:
                lines.append("#### 成长性")
                if metrics.revenue_yoy is not None:
                    lines.append(f"- 营收同比: {metrics.revenue_yoy:+.2f}%")
                if metrics.revenue_qoq is not None:
                    lines.append(f"- 营收环比: {metrics.revenue_qoq:+.2f}%")
                if metrics.profit_yoy is not None:
                    lines.append(f"- 净利润同比: {metrics.profit_yoy:+.2f}%")
                if metrics.profit_qoq is not None:
                    lines.append(f"- 净利润环比: {metrics.profit_qoq:+.2f}%")

            if metrics.debt_asset_ratio or metrics.current_ratio or metrics.ocf_to_profit:
                lines.append("#### 财务健康度")
                if metrics.debt_asset_ratio is not None:
                    lines.append(f"- 资产负债率: {metrics.debt_asset_ratio:.2f}%")
                if metrics.current_ratio is not None:
                    lines.append(f"- 流动比率: {metrics.current_ratio:.2f}")
                if metrics.quick_ratio is not None:
                    lines.append(f"- 速动比率: {metrics.quick_ratio:.2f}")
                if metrics.ocf_to_profit is not None:
                    quality = "优质" if metrics.ocf_to_profit > 1.2 else ("较低" if metrics.ocf_to_profit < 0.8 else "正常")
                    lines.append(f"- 现金流/利润比: {metrics.ocf_to_profit:.2f} ({quality})")

            if metrics.total_shares or metrics.float_shares:
                lines.append("#### 股本结构")
                if metrics.total_shares is not None:
                    lines.append(f"- 总股本: {metrics.total_shares:.2f}亿股")
                if metrics.float_shares is not None:
                    lines.append(f"- 流通股本: {metrics.float_shares:.2f}亿股")
                if metrics.float_ratio is not None:
                    lines.append(f"- 流通比例: {metrics.float_ratio:.2f}%")

            lines.append("")

        # 季度趋势
        if metrics.quarterly_trend:
            lines.append("#### 近8季度营收/利润趋势")
            lines.append("")
            lines.append("| 报告期 | 营业收入(亿) | 营收同比 | 归母净利润(亿) | 利润同比 |")
            lines.append("|--------|-------------|----------|---------------|----------|")
            for q in metrics.quarterly_trend:
                name = q.get('report_name', '-')
                rev = f"{q['revenue']/1e8:.2f}" if q.get('revenue') else '-'
                rev_yoy = f"{q['revenue_yoy']:+.2f}%" if q.get('revenue_yoy') is not None else '-'
                profit = f"{q['net_profit']/1e8:.2f}" if q.get('net_profit') else '-'
                profit_yoy = f"{q['net_profit_yoy']:+.2f}%" if q.get('net_profit_yoy') is not None else '-'
                lines.append(f"| {name} | {rev} | {rev_yoy} | {profit} | {profit_yoy} |")
            lines.append("")

        # ===== 第五优先级：分析师预期 =====

        if metrics.consensus_summary:
            lines.append(f"### 🎯 分析师预期 (数据截至: {metrics.consensus_data_date or 'N/A'})")
            lines.append(f"- {metrics.consensus_summary}")
            if metrics.eps_forecast_current or metrics.eps_forecast_next:
                lines.append(f"- 预测EPS: 当期{metrics.eps_forecast_current or 'N/A'} / 下期{metrics.eps_forecast_next or 'N/A'}")
            if metrics.target_price_avg:
                lines.append(f"- 目标均价: {metrics.target_price_avg}元 (区间: {metrics.target_price_low or 'N/A'} ~ {metrics.target_price_high or 'N/A'})")
            lines.append("")

        # 机构持仓变化
        if metrics.institution_summary:
            lines.append(f"#### 机构持仓变化 (数据截至: {metrics.institution_data_date or 'N/A'})")
            lines.append(f"- {metrics.institution_summary}")
            if metrics.top_funds:
                lines.append("- 前5大基金:")
                for f in metrics.top_funds[:5]:
                    lines.append(f"  - {f.get('name', 'N/A')}: {f.get('shares', 'N/A')} {f.get('change', '')}")
            lines.append("")

        # ===== 第六优先级：风险与环境 =====

        has_risk = any([metrics.lockup_summary, metrics.competitor_summary,
                       metrics.market_env_summary, metrics.top_holders_current])
        if has_risk:
            lines.append("### ⚠️ 风险与环境")

        # 解禁风险
        if metrics.lockup_summary:
            lines.append(f"#### 解禁风险 (数据截至: {metrics.lockup_data_date or 'N/A'})")
            lines.append(f"- {metrics.lockup_summary}")
            if metrics.lockup_events:
                for evt in metrics.lockup_events[:3]:
                    lines.append(f"  - {evt.get('date', 'N/A')} {evt.get('shares_display', '')} ({evt.get('pct_of_float', '')})")
            lines.append("")

        # 竞争对手
        if metrics.competitor_summary:
            lines.append(f"#### 竞争对手 (数据截至: {metrics.competitor_data_date or 'N/A'})")
            lines.append(f"- {metrics.competitor_summary}")
            if metrics.competitors:
                lines.append("")
                lines.append("| 公司 | ROE | 营收增速 | 毛利率 |")
                lines.append("|------|-----|----------|--------|")
                for c in metrics.competitors[:5]:
                    lines.append(f"| {c.get('name', 'N/A')} | {c.get('roe', 'N/A')} | {c.get('revenue_yoy', 'N/A')} | {c.get('gross_margin', 'N/A')} |")
            lines.append("")

        # 大盘环境
        if metrics.market_env_summary:
            lines.append(f"#### 大盘环境 (数据截至: {metrics.market_env_data_date or 'N/A'})")
            lines.append(f"- {metrics.market_env_summary}")
            if metrics.market_index_change_5d:
                lines.append(f"- 上证指数: 5日{metrics.market_index_change_5d} | 20日{metrics.market_index_change_20d or 'N/A'}")
            if metrics.sector_name:
                lines.append(f"- 所属板块: {metrics.sector_name} 排名{metrics.sector_rank or 'N/A'} 今日{metrics.sector_change_today or 'N/A'}")
            lines.append("")

        # 十大股东
        if metrics.top_holders_current:
            lines.append(f"#### 十大流通股东 (截止{metrics.top_holders_report_date or '?'})")
            lines.append("")
            lines.append("| 序号 | 股东名称 | 持股(万) | 占比 | 较上期变动 |")
            lines.append("|------|----------|----------|------|------------|")
            prev_map = metrics.top_holders_previous or {}
            for i, h in enumerate(metrics.top_holders_current, 1):
                name = h['name']
                if len(name) > 18:
                    name = name[:18] + '...'
                shares_wan = h['shares'] / 10000
                pct = h['pct']
                prev = prev_map.get(h['name'])
                if prev:
                    diff = h['shares'] - prev['shares']
                    if diff > 0:
                        change_str = f"+{diff/10000:.0f}万"
                    elif diff < 0:
                        change_str = f"{diff/10000:.0f}万"
                    else:
                        change_str = "不变"
                else:
                    change_str = "新进" if metrics.top_holders_prev_date else '-'
                lines.append(f"| {i} | {name} | {shares_wan:.0f} | {pct:.2f}% | {change_str} |")
            lines.append("")

        # 行业对比
        if metrics.industry_comparison and metrics.industry_name:
            comp = metrics.industry_comparison
            lines.append(f"#### 行业对比 ({metrics.industry_name}，共{comp.get('peer_count', '?')}家)")
            lines.append("")
            lines.append("| 指标 | 本公司 | 行业中位数 | 行业排名 |")
            lines.append("|------|--------|------------|----------|")
            for key, label in [('roe', 'ROE'), ('gross_margin', '毛利率'), ('revenue_yoy', '营收增速'), ('profit_yoy', '利润增速')]:
                my_val = comp.get(f'{key}_value')
                median_val = comp.get(f'{key}_median')
                rank = comp.get(f'{key}_rank')
                total = comp.get(f'{key}_total')
                my_str = f"{my_val:.2f}%" if my_val is not None else 'N/A'
                med_str = f"{median_val:.2f}%" if median_val is not None else 'N/A'
                rank_str = f"{rank}/{total}" if rank and total else 'N/A'
                lines.append(f"| {label} | {my_str} | {med_str} | {rank_str} |")
            lines.append("")

        # ===== 第七优先级：舆情与题材 =====

        # 情绪与题材
        if metrics.theme_sentiment_summary:
            lines.append(f"### 📰 舆情与题材")
            lines.append(f"- {metrics.theme_sentiment_summary}")
            if metrics.hot_concepts:
                concepts_str = '、'.join(metrics.hot_concepts[:3])
                lines.append(f"- 热门概念: {concepts_str}")

        # 舆情动态
        if metrics.news_summary:
            lines.append(f"#### 舆情动态 (数据截至: {metrics.news_data_date or 'N/A'})")
            lines.append(f"- 来源: {metrics.news_source} | {metrics.news_summary}")
            lines.append("")

        # 汇率敏感
        if metrics.fx_sensitivity:
            lines.append(f"- 汇率敏感: {metrics.fx_sensitivity}")

        # 近20日行情数据（附录）
        if metrics.recent_20d_data and len(metrics.recent_20d_data) > 0:
            lines.append("")
            lines.append("### 附录：近20日行情")
            lines.append("")
            lines.append("| 日期 | 开盘 | 收盘 | 涨跌幅 | 振幅 | 成交量(万) | 成交额(亿) | 换手率 | 量比 |")
            lines.append("|------|------|------|--------|------|------------|------------|--------|------|")
            for day in reversed(metrics.recent_20d_data):
                date_str = day.get('date', '-')
                open_p = f"{day['open']:.2f}" if day.get('open') else '-'
                close_p = f"{day['close']:.2f}" if day.get('close') else '-'
                chg = f"{day['change_pct']:+.2f}%" if day.get('change_pct') is not None else '-'
                amp = f"{day['amplitude']:.2f}%" if day.get('amplitude') else '-'
                vol = f"{day['volume']/10000:.1f}" if day.get('volume') else '-'
                amt = f"{day['amount']/1e8:.2f}" if day.get('amount') else '-'
                turn = f"{day['turnover_rate']:.2f}%" if day.get('turnover_rate') else '-'
                vr = f"{day['volume_ratio']:.2f}" if day.get('volume_ratio') else '-'
                lines.append(f"| {date_str} | {open_p} | {close_p} | {chg} | {amp} | {vol} | {amt} | {turn} | {vr} |")
            lines.append("")

        # 警告信息
        if metrics.warnings:
            lines.append("")
            lines.append("### 数据说明")
            for warning in metrics.warnings:
                lines.append(f"- {warning}")

        return "\n".join(lines)

    def generate_llm_prompt(self, metrics: ValuationMetrics) -> str:
        """
        生成发送给 DeepSeek 的估值分析 Prompt

        Args:
            metrics: 估值指标数据

        Returns:
            完整的 Prompt 字符串
        """
        # 估值解读辅助函数
        def interpret_percentile(value: Optional[float]) -> str:
            if value is None:
                return "N/A"
            if value < 20:
                return "极低（历史低位）"
            elif value < 40:
                return "偏低"
            elif value < 60:
                return "中等"
            elif value < 80:
                return "偏高"
            else:
                return "极高（历史高位）"

        prompt = f"""你是一位专业的价值投资分析师，擅长估值分析。请对【{metrics.stock_name}】({metrics.stock_code}) 进行快速估值分析。

> **数据来源**: {metrics.data_source or '未知'}
> **更新时间**: {metrics.update_time}

## 实时行情

| 指标 | 当前值 | 说明 |
|------|--------|------|
| 当前价 | {f'{metrics.current_price:.2f}元' if metrics.current_price else 'N/A'} | 最新交易价格 |
| 开盘价 | {f'{metrics.open_price:.2f}元' if metrics.open_price else 'N/A'} | 今日开盘价 |
| 昨收价 | {f'{metrics.close_price:.2f}元' if metrics.close_price else 'N/A'} | 昨日收盘价 |
| 今日振幅 | {f'{metrics.low_price:.2f}~{metrics.high_price:.2f}元' if metrics.high_price and metrics.low_price else 'N/A'} | 今日最高/最低价 |
| 涨跌幅 | {f'{metrics.change_pct:+.2f}%' if metrics.change_pct is not None else 'N/A'} | 相对昨收价涨跌 |
| 成交量 | {f'{metrics.volume/10000:.2f}万股' if metrics.volume else 'N/A'} | 当日成交量 |
| 成交额 | {f'{metrics.amount:.2f}亿元' if metrics.amount else 'N/A'} | 当日成交金额 |
| 换手率 | {f'{metrics.turnover_rate:.2f}%' if metrics.turnover_rate else 'N/A'} | 当日换手率 |
| 量比 | {f'{metrics.volume_ratio:.2f}' if metrics.volume_ratio else 'N/A'} | 当日量比（>2放量，<0.5缩量） |

## 均线分析

| 均线 | 价格 | 距离当前价 | 说明 |
|------|------|-----------|------|
| MA5 | {f'{metrics.ma5:.2f}元' if metrics.ma5 else 'N/A'} | {f'{metrics.ma5_distance:+.2f}%' if metrics.ma5_distance is not None else 'N/A'} | 5日均线 |
| MA10 | {f'{metrics.ma10:.2f}元' if metrics.ma10 else 'N/A'} | {f'{metrics.ma10_distance:+.2f}%' if metrics.ma10_distance is not None else 'N/A'} | 10日均线 |
| MA20 | {f'{metrics.ma20:.2f}元' if metrics.ma20 else 'N/A'} | {f'{metrics.ma20_distance:+.2f}%' if metrics.ma20_distance is not None else 'N/A'} | 20日均线（月线） |
| MA60 | {f'{metrics.ma60:.2f}元' if metrics.ma60 else 'N/A'} | {f'{metrics.ma60_distance:+.2f}%' if metrics.ma60_distance is not None else 'N/A'} | 60日均线（季线） |
| MA120 | {f'{metrics.ma120:.2f}元' if metrics.ma120 else 'N/A'} | {f'{metrics.ma120_distance:+.2f}%' if metrics.ma120_distance is not None else 'N/A'} | 120日均线（半年线） |
| MA250 | {f'{metrics.ma250:.2f}元' if metrics.ma250 else 'N/A'} | {f'{metrics.ma250_distance:+.2f}%' if metrics.ma250_distance is not None else 'N/A'} | 250日均线（年线） |

> **均线距离说明**: 正值表示当前价在均线上方（强势），负值表示在均线下方（弱势）

## 技术指标

### MACD (Moving Average Convergence Divergence)

| 指标 | 当前值 | 信号 |
|------|--------|------|
| DIF | {f'{metrics.macd_dif:.3f}' if metrics.macd_dif is not None else 'N/A'} | 快线（12日EMA - 26日EMA） |
| DEA | {f'{metrics.macd_dea:.3f}' if metrics.macd_dea is not None else 'N/A'} | 慢线（DIF的9日EMA） |
| HIST | {f'{metrics.macd_hist:.3f}' if metrics.macd_hist is not None else 'N/A'} | 柱状图（(DIF-DEA)*2） |
| 信号 | {metrics.macd_signal if metrics.macd_signal else 'N/A'} | 金叉=看涨，死叉=看跌 |

### RSI (Relative Strength Index)

| 周期 | 当前值 | 状态 |
|------|--------|------|
| RSI(6) | {f'{metrics.rsi_6:.2f}' if metrics.rsi_6 is not None else 'N/A'} | {'超买(>70)' if metrics.rsi_6 and metrics.rsi_6 > 70 else ('超卖(<30)' if metrics.rsi_6 and metrics.rsi_6 < 30 else '正常(30-70)')} |
| RSI(12) | {f'{metrics.rsi_12:.2f}' if metrics.rsi_12 is not None else 'N/A'} | {'超买(>70)' if metrics.rsi_12 and metrics.rsi_12 > 70 else ('超卖(<30)' if metrics.rsi_12 and metrics.rsi_12 < 30 else '正常(30-70)')} |
| RSI(24) | {f'{metrics.rsi_24:.2f}' if metrics.rsi_24 is not None else 'N/A'} | {'超买(>70)' if metrics.rsi_24 and metrics.rsi_24 > 70 else ('超卖(<30)' if metrics.rsi_24 and metrics.rsi_24 < 30 else '正常(30-70)')} |

### KDJ (Stochastic Oscillator)

| 指标 | 当前值 | 说明 |
|------|--------|------|
| K值 | {f'{metrics.kdj_k:.2f}' if metrics.kdj_k is not None else 'N/A'} | 快速指标 |
| D值 | {f'{metrics.kdj_d:.2f}' if metrics.kdj_d is not None else 'N/A'} | 慢速指标 |
| J值 | {f'{metrics.kdj_j:.2f}' if metrics.kdj_j is not None else 'N/A'} | 方向指标(3K-2D) |

> **KDJ信号**: K>D且向上=金叉看涨，K<D且向下=死叉看跌；K/D>80超买，K/D<20超卖

### CCI (Commodity Channel Index)

| 指标 | 当前值 | 状态 |
|------|--------|------|
| CCI(14) | {f'{metrics.cci:.2f}' if metrics.cci is not None else 'N/A'} | {'>100超买，<-100超卖，±100之间正常' if metrics.cci is not None else 'N/A'} |

### 派生技术信号

| 指标 | 数值 | 说明 |
|------|------|------|
| 均线状态 | {metrics.ma_alignment or 'N/A'} | 多头/空头/纠缠 |
| 趋势位置 | {metrics.trend_position or 'N/A'} | 年线/月线参照 |
| BOLL位置 | {f'{metrics.boll_position:.0f}%' if metrics.boll_position is not None else 'N/A'} ({metrics.boll_status or 'N/A'}) | 0%=下轨, 100%=上轨 |
| 5日涨跌 | {f'{metrics.change_5d:+.2f}%' if metrics.change_5d is not None else 'N/A'} | 短期动量 |
| 20日涨跌 | {f'{metrics.change_20d:+.2f}%' if metrics.change_20d is not None else 'N/A'} | 中期动量 |
| 20日波动率 | {f'{metrics.volatility_20d:.2f}%' if metrics.volatility_20d is not None else 'N/A'} | 日均振幅 |
| 20日高/低 | {f'{metrics.high_20d:.2f}' if metrics.high_20d else 'N/A'} / {f'{metrics.low_20d:.2f}' if metrics.low_20d else 'N/A'} | 近期压力/支撑 |

## 资金流向（多时间维度）

### 当日资金流向

| 资金类型 | 净流入/流出 | 说明 |
|----------|-------------|------|
| 主力资金 | {f'{metrics.main_net_inflow_1d:+.2f}亿' if metrics.main_net_inflow_1d is not None else 'N/A'} | 大单+超大单合计 |
| 主力占比 | {f'{metrics.main_net_inflow_pct_1d:.2f}%' if metrics.main_net_inflow_pct_1d else 'N/A'} | 主力净流入占比 |
| 超大单 | {f'{metrics.super_net_inflow_1d:+.2f}亿' if metrics.super_net_inflow_1d is not None else 'N/A'} | 特大资金流向 |
| 大单 | {f'{metrics.big_net_inflow_1d:+.2f}亿' if metrics.big_net_inflow_1d is not None else 'N/A'} | 大额资金流向 |
| 中单 | {f'{metrics.medium_net_inflow_1d:+.2f}亿' if metrics.medium_net_inflow_1d is not None else 'N/A'} | 中等资金流向 |
| 小单 | {f'{metrics.small_net_inflow_1d:+.2f}亿' if metrics.small_net_inflow_1d is not None else 'N/A'} | 散户资金流向 |

### 近3日资金流向

| 资金类型 | 净流入/流出 | 趋势判断 |
|----------|-------------|----------|
| 主力资金 | {f'{metrics.main_net_inflow_3d:+.2f}亿' if metrics.main_net_inflow_3d is not None else 'N/A'} | {'持续流入' if metrics.main_net_inflow_3d and metrics.main_net_inflow_3d > 0 else ('持续流出' if metrics.main_net_inflow_3d and metrics.main_net_inflow_3d < 0 else 'N/A')} |
| 超大单 | {f'{metrics.super_net_inflow_3d:+.2f}亿' if metrics.super_net_inflow_3d is not None else 'N/A'} | - |
| 大单 | {f'{metrics.big_net_inflow_3d:+.2f}亿' if metrics.big_net_inflow_3d is not None else 'N/A'} | - |

### 近7日（1周）资金流向

| 资金类型 | 净流入/流出 | 趋势判断 |
|----------|-------------|----------|
| 主力资金 | {f'{metrics.main_net_inflow_7d:+.2f}亿' if metrics.main_net_inflow_7d is not None else 'N/A'} | {'中期持续流入' if metrics.main_net_inflow_7d and metrics.main_net_inflow_7d > 0 else ('中期持续流出' if metrics.main_net_inflow_7d and metrics.main_net_inflow_7d < 0 else 'N/A')} |
| 超大单 | {f'{metrics.super_net_inflow_7d:+.2f}亿' if metrics.super_net_inflow_7d is not None else 'N/A'} | - |
| 大单 | {f'{metrics.big_net_inflow_7d:+.2f}亿' if metrics.big_net_inflow_7d is not None else 'N/A'} | - |

## 当前估值指标

| 指标 | 当前值 | 说明 |
|------|--------|------|
| PE-TTM | {metrics.pe_ttm or 'N/A'} | 滚动市盈率（股价/每股收益） |
| PE-静态 | {f'{metrics.pe_static:.2f}' if metrics.pe_static else 'N/A'} | 静态市盈率（基于上年度全年收益） |
| PB | {metrics.pb or 'N/A'} | 市净率（股价/每股净资产） |
| PS-TTM | {f'{metrics.ps_ttm:.2f}' if metrics.ps_ttm else 'N/A'} | 市销率（市值/营收） |
| PCF | {f'{metrics.pcf:.2f}' if metrics.pcf else 'N/A'} | 市现率（市值/经营现金流） |
| P/FCF | {f'{metrics.p_fcf:.2f}' if metrics.p_fcf else 'N/A'} | 市值/自由现金流（FCF=经营现金流-资本开支） |
| 股息率(TTM) | {f'{metrics.dividend_yield:.2f}%' if metrics.dividend_yield else 'N/A'} | 滚动股息率 |
| 总市值 | {f'{metrics.market_cap:.0f}亿' if metrics.market_cap else 'N/A'} | - |

## 核心财务指标

### 盈利能力指标

| 指标 | 数值 | 说明 |
|------|------|------|
| ROE | {f'{metrics.roe:.2f}%' if metrics.roe is not None else 'N/A'} | 净资产收益率，巴菲特最看重的指标 |
| 毛利率 | {f'{metrics.gross_margin:.2f}%' if metrics.gross_margin is not None else 'N/A'} | 产品竞争力和定价能力 |
| 净利率 | {f'{metrics.net_margin:.2f}%' if metrics.net_margin is not None else 'N/A'} | 盈利质量指标 |
| EPS | {f'{metrics.eps:.2f}元' if metrics.eps is not None else 'N/A'} | 每股收益 |
| BPS | {f'{metrics.bps:.2f}元' if metrics.bps is not None else 'N/A'} | 每股净资产 |

> **ROE解读**: >15%优秀，10-15%良好，<10%一般；持续高ROE说明公司具有强护城河

### 成长性指标

| 指标 | 数值 | 趋势 |
|------|------|------|
| 营收同比增长 | {f'{metrics.revenue_yoy:+.2f}%' if metrics.revenue_yoy is not None else 'N/A'} | {'高增长(>20%)' if metrics.revenue_yoy and metrics.revenue_yoy > 20 else ('稳定增长(5-20%)' if metrics.revenue_yoy and metrics.revenue_yoy > 5 else ('低增长(<5%)' if metrics.revenue_yoy and metrics.revenue_yoy > 0 else '负增长'))} |
| 营收环比增长 | {f'{metrics.revenue_qoq:+.2f}%' if metrics.revenue_qoq is not None else 'N/A'} | 短期趋势 |
| 净利润同比增长 | {f'{metrics.profit_yoy:+.2f}%' if metrics.profit_yoy is not None else 'N/A'} | {'高增长(>20%)' if metrics.profit_yoy and metrics.profit_yoy > 20 else ('稳定增长(5-20%)' if metrics.profit_yoy and metrics.profit_yoy > 5 else ('低增长(<5%)' if metrics.profit_yoy and metrics.profit_yoy > 0 else '负增长'))} |
| 净利润环比增长 | {f'{metrics.profit_qoq:+.2f}%' if metrics.profit_qoq is not None else 'N/A'} | 短期趋势 |

> **成长性判断**: 营收和利润增速是否匹配？环比数据是否显示加速/减速？

### 财务健康度指标

| 指标 | 数值 | 评级 |
|------|------|------|
| 资产负债率 | {f'{metrics.debt_asset_ratio:.2f}%' if metrics.debt_asset_ratio is not None else 'N/A'} | {'健康(<50%)' if metrics.debt_asset_ratio and metrics.debt_asset_ratio < 50 else ('中等(50-70%)' if metrics.debt_asset_ratio and metrics.debt_asset_ratio < 70 else '偏高(>70%)')} |
| 流动比率 | {f'{metrics.current_ratio:.2f}' if metrics.current_ratio is not None else 'N/A'} | {'优秀(>2)' if metrics.current_ratio and metrics.current_ratio > 2 else ('良好(1-2)' if metrics.current_ratio and metrics.current_ratio > 1 else '风险(<1)')} |
| 速动比率 | {f'{metrics.quick_ratio:.2f}' if metrics.quick_ratio is not None else 'N/A'} | {'优秀(>1.5)' if metrics.quick_ratio and metrics.quick_ratio > 1.5 else ('良好(1-1.5)' if metrics.quick_ratio and metrics.quick_ratio > 1 else '风险(<1)')} |
| 现金流/利润比 | {f'{metrics.ocf_to_profit:.2f}' if metrics.ocf_to_profit is not None else 'N/A'} | {'优质(>1.2)' if metrics.ocf_to_profit and metrics.ocf_to_profit > 1.2 else ('正常(0.8-1.2)' if metrics.ocf_to_profit and metrics.ocf_to_profit > 0.8 else '较低(<0.8)')} |

> **财务风险**: 负债率<50%+流动比率>1.5+现金流充足 = 财务稳健

### 股本结构

| 指标 | 数值 | 说明 |
|------|------|------|
| 总股本 | {f'{metrics.total_shares:.2f}亿股' if metrics.total_shares is not None else 'N/A'} | - |
| 流通股本 | {f'{metrics.float_shares:.2f}亿股' if metrics.float_shares is not None else 'N/A'} | - |
| 流通比例 | {f'{metrics.float_ratio:.2f}%' if metrics.float_ratio is not None else 'N/A'} | {'全流通' if metrics.float_ratio and metrics.float_ratio > 95 else ('高流通(80-95%)' if metrics.float_ratio and metrics.float_ratio > 80 else '部分流通(<80%)')} |

## PE-TTM 历史分位

| 区间 | 当前分位 | 解读 |
|------|----------|------|
| 10年 | {f'{metrics.pe_percentile_10y:.1f}%' if metrics.pe_percentile_10y else 'N/A'} | {interpret_percentile(metrics.pe_percentile_10y)} |
| 5年 | {f'{metrics.pe_percentile_5y:.1f}%' if metrics.pe_percentile_5y else 'N/A'} | {interpret_percentile(metrics.pe_percentile_5y)} |
| 3年 | {f'{metrics.pe_percentile_3y:.1f}%' if metrics.pe_percentile_3y else 'N/A'} | {interpret_percentile(metrics.pe_percentile_3y)} |
| 1年 | {f'{metrics.pe_percentile_1y:.1f}%' if metrics.pe_percentile_1y else 'N/A'} | {interpret_percentile(metrics.pe_percentile_1y)} |

## PB 历史分位

| 区间 | 当前分位 | 解读 |
|------|----------|------|
| 10年 | {f'{metrics.pb_percentile_10y:.1f}%' if metrics.pb_percentile_10y else 'N/A'} | {interpret_percentile(metrics.pb_percentile_10y)} |
| 5年 | {f'{metrics.pb_percentile_5y:.1f}%' if metrics.pb_percentile_5y else 'N/A'} | {interpret_percentile(metrics.pb_percentile_5y)} |
| 3年 | {f'{metrics.pb_percentile_3y:.1f}%' if metrics.pb_percentile_3y else 'N/A'} | {interpret_percentile(metrics.pb_percentile_3y)} |
| 1年 | {f'{metrics.pb_percentile_1y:.1f}%' if metrics.pb_percentile_1y else 'N/A'} | {interpret_percentile(metrics.pb_percentile_1y)} |

## 分析师一致预期 (数据截至: {metrics.consensus_data_date or 'N/A'})

| 指标 | 数值 | 说明 |
|------|------|------|
| 预测EPS(当期) | {metrics.eps_forecast_current or 'N/A'} | 分析师预测 |
| 预测EPS(下期) | {metrics.eps_forecast_next or 'N/A'} | 分析师预测 |
| EPS预期增速 | {metrics.eps_growth_rate or 'N/A'} | 同比增长 |
| 评级分布 | 买入{metrics.rating_buy or 0}/增持{metrics.rating_overweight or 0}/持有{metrics.rating_hold or 0} | 机构评级 |
| 目标均价 | {metrics.target_price_avg or 'N/A'}元 | 分析师目标价 |
| 目标价区间 | {metrics.target_price_low or 'N/A'} ~ {metrics.target_price_high or 'N/A'}元 | 高低目标 |
| PEG | {metrics.peg or 'N/A'} | {metrics.peg_signal or 'N/A'} |

## 大盘/板块环境 (数据截至: {metrics.market_env_data_date or 'N/A'})

| 指标 | 数值 | 说明 |
|------|------|------|
| 上证5日涨跌 | {metrics.market_index_change_5d or 'N/A'} | 短期市场趋势 |
| 上证20日涨跌 | {metrics.market_index_change_20d or 'N/A'} | 中期市场趋势 |
| 市场情绪 | {metrics.market_sentiment or 'N/A'} | {'偏暖=指数在MA20上方' if metrics.market_index_above_ma20 else '偏冷=指数在MA20下方'} |
| 所属板块 | {metrics.sector_name or 'N/A'} | 行业分类 |
| 板块排名 | {metrics.sector_rank or 'N/A'} | 今日板块涨幅排名 |
| 板块涨跌 | {metrics.sector_change_today or 'N/A'} | 板块今日表现 |
| 板块主力流入 | {metrics.sector_main_inflow or 'N/A'} | 板块资金流向 |

## 解禁/减持风险 (数据截至: {metrics.lockup_data_date or 'N/A'})

| 指标 | 数值 | 说明 |
|------|------|------|
| 风险等级 | {metrics.lockup_risk_level or 'N/A'} | 高(>5%或6月>10%)/中(6月3-10%)/低(<3%) |
| 最近解禁日 | {metrics.lockup_nearest_date or 'N/A'} | 下一个解禁日期 |
| 6月累计解禁 | {metrics.lockup_6m_total_pct or 'N/A'} | 未来6个月累计解禁占比 |

## 筹码分布 (数据截至: {metrics.chip_data_date or 'N/A'})

| 指标 | 数值 | 说明 |
|------|------|------|
| 获利比例 | {metrics.chip_profit_ratio or 'N/A'} | >80%注意回调风险，<20%下方有支撑 |
| 平均成本 | {metrics.chip_avg_cost or 'N/A'}元 | 市场平均持仓成本 |
| 70%集中度 | {metrics.chip_concentration_70 or 'N/A'} | 70%筹码分布区间 |
| 90%集中度 | {metrics.chip_concentration_90 or 'N/A'} | 90%筹码分布区间 |
| 筹码信号 | {metrics.chip_signal or 'N/A'} | 综合判断 |

## 机构持仓变化 (数据截至: {metrics.institution_data_date or 'N/A'})

| 指标 | 数值 | 说明 |
|------|------|------|
| 持仓基金数 | {metrics.fund_holding_count or 'N/A'} | 当期持仓基金家数 |
| 较上期变动 | {metrics.fund_holding_change or 'N/A'} | 基金数量变化 |
| 合计持仓占比 | {metrics.fund_holding_pct or 'N/A'} | 基金合计占流通股比例 |

## 竞争对手对比 (数据截至: {metrics.competitor_data_date or 'N/A'})

行业：{metrics.sector_name or 'N/A'} (同业{metrics.industry_peer_count or 'N/A'}家)

| 公司 | ROE | 营收增速 | 利润增速 | 毛利率 |
|------|-----|----------|----------|--------|
"""

        # 添加竞争对手数据
        if metrics.competitors:
            for c in metrics.competitors[:5]:
                prompt += f"| {c.get('name', 'N/A')} | {c.get('roe', 'N/A')} | {c.get('revenue_yoy', 'N/A')} | {c.get('profit_yoy', 'N/A')} | {c.get('gross_margin', 'N/A')} |\n"
        else:
            prompt += "| 暂无数据 | - | - | - | - |\n"

        # 添加聪明钱动向
        prompt += f"""
## 聪明钱动向 (数据截至: {metrics.smart_money_data_date or 'N/A'})

| 指标 | 数值 | 说明 |
|------|------|------|
| 北向连续加/减仓 | {f'{metrics.north_consecutive_days}日' if metrics.north_consecutive_days is not None else 'N/A'} | 正=连续加仓，负=连续减仓 |
| 北向3日变动 | {f'{metrics.north_change_pct_3d:+.2f}%' if metrics.north_change_pct_3d is not None else 'N/A'} | 近3日北向持股变化 |
| 北向持股占比 | {f'{metrics.north_holding_ratio:.2f}%' if metrics.north_holding_ratio is not None else 'N/A'} | 占流通股比例 |
| 融资余额 | {f'{metrics.margin_balance:.1f}亿' if metrics.margin_balance is not None else 'N/A'} | 趋势: {metrics.margin_balance_trend or 'N/A'} |
| 融券占比 | {f'{metrics.short_selling_ratio:.2f}%' if metrics.short_selling_ratio is not None else 'N/A'} | {metrics.short_selling_level or 'N/A'} |

## 情绪与题材 (数据截至: {metrics.theme_sentiment_data_date or 'N/A'})

| 指标 | 数值 | 说明 |
|------|------|------|
| 机构情绪 | {metrics.stock_sentiment or 'N/A'} | 偏多/中性/偏空 |
| 热门概念 | {'、'.join(metrics.hot_concepts[:3]) if metrics.hot_concepts else 'N/A'} | 今日涨幅前3概念板块 |

## 支撑压力与风险

| 指标 | 数值 | 说明 |
|------|------|------|
| 上方压力位 | {f'{metrics.resistance_price:.2f}元' if metrics.resistance_price else 'N/A'} | {metrics.resistance_type or 'N/A'} |
| 下方支撑位 | {f'{metrics.support_price:.2f}元' if metrics.support_price else 'N/A'} | {metrics.support_type or 'N/A'} |
| 汇率敏感性 | {metrics.fx_sensitivity or '不敏感'} | 基于行业分类判断 |

## 舆情动态 (来源: {metrics.news_source or 'N/A'}, 截至: {metrics.news_data_date or 'N/A'})

{metrics.news_context or '无舆情数据'}
"""

        prompt += f"""
## 数据时效性说明

**重要：数据时效性权重**
- 实时数据（估值/行情/资金/筹码）：权重最高，直接影响短期判断 | 截至: {metrics.valuation_data_date or 'N/A'}
- 近期数据（1周内研报/解禁日程）：权重高 | 截至: {metrics.consensus_data_date or 'N/A'}
- 季度数据（财报/机构持仓/股东）：权重中，注意可能已滞后数月 | 截至: {metrics.institution_data_date or 'N/A'}
- 年度数据（历史分位/年报）：权重低，仅作背景参考
请在分析中明确指出哪些结论基于滞后数据，可能存在偏差。
"""

        # 添加数据说明（如果有警告）
        if metrics.warnings:
            prompt += "## 数据说明\n"
            for warning in metrics.warnings:
                prompt += f"- {warning}\n"
            prompt += "\n"

        prompt += """## 分析要求

请从以下维度进行估值分析：

### 1. 基本面健康度评估
- **交易活跃度**: 成交量、换手率、量比是否正常？是否存在异常放量/缩量？
- **资金流向**: 主力资金是流入还是流出？超大单、大单与中小单的动向是否一致？
- **价格走势**: 当前涨跌幅如何？是否处于合理波动范围？

### 2. 技术面分析
- **均线系统**: 当前价格与各周期均线的相对位置，多头/空头排列状态
- **MACD指标**: 金叉/死叉，DIF/DEA位置，是否存在背离
- **RSI指标**: 是否超买(>70)或超卖(<30)
- **KDJ指标**: K/D/J位置关系，是否形成金叉或死叉
- **筹码分布**: 获利比例、平均成本、集中度信号

### 3. 估值健康度评估
- 当前PE/PB/PS/PCF/P_FCF估值是否合理？与历史相比处于什么位置？
- **PEG评估**: PEG是否合理？成长性是否匹配估值？
- **PE-TTM vs PE-静态**: 两者差异说明了什么？盈利是增长还是下滑？
- 股息率是否具有吸引力？是否提供安全边际？

### 4. 分析师预期分析（新增）
- **评级分布**: 买入/增持/持有比例如何？整体偏乐观还是谨慎？
- **目标价空间**: 当前价格距离目标均价有多少上涨空间？
- **EPS预期**: 分析师预期EPS增速如何？与历史增速是否匹配？
- **PEG判断**: 基于预期EPS计算的PEG是否具有吸引力？

### 5. 市场环境分析（新增）
- **大盘趋势**: 上证指数5日/20日走势如何？市场整体情绪偏暖还是偏冷？
- **板块地位**: 所属板块今日排名如何？板块资金是否流入？
- **系统性风险**: 大盘环境是否支持个股上涨？

### 6. 风险评估（新增）
- **解禁风险**: 近期是否有大额解禁？6个月内累计解禁比例多高？
- **机构动向**: 基金持仓数量是增加还是减少？主力机构态度如何？
- **竞争格局**: 与同行业竞争对手相比，ROE、增速、毛利率处于什么水平？

### 7. 聪明钱与情绪分析
- **北向资金**: 北向是否连续加仓/减仓？3日变动幅度如何？持股占比？
- **融资融券**: 融资余额趋势如何？融券占比是否处于高位（看空信号）？
- **机构情绪**: 机构参与度偏多还是偏空？
- **热门题材**: 当前市场热门概念与个股是否相关？

### 8. 支撑压力分析
- **关键压力位**: 上方最近的均线/BOLL上轨/套牢盘密集区在哪？
- **关键支撑位**: 下方最近的均线/BOLL下轨在哪？
- **汇率敏感性**: 是否属于人民币贬值/升值受益行业？

### 8.5 舆情与催化剂
- **公告事件**: 近期是否有重大公告（定增、并购、减持等）？
- **行业政策**: 是否受益于近期政策或题材催化？
- **舆论倾向**: 新闻整体偏正面还是负面？

### 9. 综合风险识别
- 是否存在"估值陷阱"？（如PE低但业绩下滑、周期股见顶等）
- 历史分位的参考局限性是什么？（行业周期、公司发展阶段变化）
- 当前估值隐含了什么市场预期？
- **解禁压力**: 近期解禁是否会造成抛压？
- **机构减仓**: 机构是否在减仓？说明什么问题？

### 10. 投资建议
- 当前估值是否适合买入/持有/卖出？
- 如果买入，合理的估值区间是多少？参考均线支撑位和PEG
- 需要重点关注的风险指标是什么？
- **技术面是否支持**: 技术指标、均线系统、筹码分布是否支持当前操作建议？
- **资金面是否支持**: 1日/3日/7日资金流向是否支持操作建议？
- **解禁/机构风险**: 是否需要规避解禁期或机构减仓期？

## 输出格式

### 综合评级
**[明显低估/低估/合理/高估/明显高估]** | 置信度：[高/中/低]

### 核心结论
[用2-3句大白话总结估值状况，适合非专业投资者理解]

### 关键发现
1. [发现1 - 估值与PEG：当前估值水平，PEG是否合理]
2. [发现2 - 技术面信号：MACD/RSI/KDJ/均线/筹码的综合信号]
3. [发现3 - 资金流向趋势：1日/3日/7日资金是流入还是流出？]
4. [发现4 - 分析师预期：目标价空间、评级分布] *(注明数据时效性)*
5. [发现5 - 聪明钱动向：北向资金方向、融资融券信号] *(注明数据时效性)*
6. [发现6 - 风险因素：解禁风险、机构动向、竞争格局、支撑压力位] *(注明数据时效性)*

### 投资建议
- **估值吸引力**: [描述当前估值是否有吸引力，PE-TTM vs PE-静态的对比，PEG估值]
- **技术面判断**: [MACD、RSI、KDJ、均线系统、筹码分布的综合信号]
- **资金面判断**: [结合1日/3日/7日资金流向，判断主力意图]
- **聪明钱信号**: [北向资金加/减仓方向、融券余额水平、机构情绪]
- **分析师预期**: [目标价空间、评级分布支持的操作方向]
- **风险提示**: [解禁风险、机构动向、竞争压力等] *(注明数据滞后性)*
- **操作建议**: [买入/持有/卖出，并说明是短线还是中长线]
- **参考买入区间**: [给出具体的PE或价格区间，结合均线支撑位和PEG]
- **关键支撑/压力位**: [基于均线、筹码成本、BOLL给出关键价位，注明压力/支撑类型]
- **汇率敏感性**: [如适用，说明人民币汇率变动对该股的影响]
- **主要风险**: [列出1-2个主要风险，注明数据时效性]

---
**免责声明**：本分析基于历史数据和统计方法，不构成投资建议。股市有风险，投资需谨慎。部分数据（如财报、机构持仓）可能存在滞后，请结合最新公告综合判断。
"""
        return prompt


# ==================== 测试代码 ====================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # 测试：贵州茅台
    analyzer = ValuationAnalyzer()
    metrics, summary = analyzer.analyze("600519", "贵州茅台")

    print("\n" + "="*60)
    print("估值摘要:")
    print("="*60)
    print(summary)

    print("\n" + "="*60)
    print("LLM Prompt 预览 (前1000字符):")
    print("="*60)
    prompt = analyzer.generate_llm_prompt(metrics)
    print(prompt[:1000] + "\n...[截断]...")
