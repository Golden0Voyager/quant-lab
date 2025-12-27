"""
快速估值分析模块
功能：获取当前估值 + 历史分位数据，生成 LLM 可读的估值报告

数据来源：
- 当前估值: 雪球 API (ak.stock_individual_spot_xq)
- 历史分位: 韭圈儿网站爬虫
- PS/PCF: 自行计算
"""

import logging
import time
import re
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

import akshare as ak
import pandas as pd
import requests
from bs4 import BeautifulSoup

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class ValuationMetrics:
    """估值指标数据类"""
    # 当前估值
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    ps_ttm: Optional[float] = None
    pcf: Optional[float] = None  # 市现率
    p_fcf: Optional[float] = None  # 市值/自由现金流 (新增)
    dividend_yield: Optional[float] = None  # 股息率 (%)
    market_cap: Optional[float] = None  # 总市值 (亿)

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
    warnings: list = field(default_factory=list)


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

    def _convert_symbol(self, symbol: str) -> str:
        """转换代码格式为雪球格式"""
        if symbol.startswith(('000', '001', '002', '003', '300')):
            return f"SZ{symbol}"
        else:
            return f"SH{symbol}"

    def fetch_current_valuation(self, symbol: str, stock_name: str) -> Dict[str, Any]:
        """
        获取当前估值数据（雪球 API）

        Args:
            symbol: 股票代码
            stock_name: 股票名称

        Returns:
            估值数据字典
        """
        data = {}
        xq_symbol = self._convert_symbol(symbol)

        try:
            logger.info(f"📊 获取当前估值: {stock_name} ({symbol})")

            # 调用雪球 API
            spot_df = ak.stock_individual_spot_xq(symbol=xq_symbol)

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

                logger.info(f"✓ 当前估值: PE={data.get('pe_ttm')}, PB={data.get('pb')}, "
                           f"股息率={data.get('dividend_yield')}%")
            else:
                logger.warning("雪球数据为空")

        except Exception as e:
            logger.error(f"❌ 当前估值获取失败: {e}")

        return data

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
            from analyst_core_enhanced import fetch_performance_data
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
            logger.warning("analyst_core_enhanced 模块不可用，跳过 PS/PCF 计算")
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

    def analyze(self, symbol: str, stock_name: str = None) -> Tuple[ValuationMetrics, str]:
        """
        执行完整估值分析

        Args:
            symbol: 股票代码
            stock_name: 股票名称（可选）

        Returns:
            (ValuationMetrics, 文本摘要)
        """
        metrics = ValuationMetrics()
        metrics.stock_code = symbol
        metrics.stock_name = stock_name or symbol
        metrics.update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        logger.info(f"\n{'='*60}")
        logger.info(f"📊 快速估值分析: {metrics.stock_name} ({symbol})")
        logger.info(f"{'='*60}\n")

        # Step 1: 获取当前估值（必须成功）
        current_data = self.fetch_current_valuation(symbol, metrics.stock_name)
        if not current_data.get('pe_ttm') and not current_data.get('pb'):
            metrics.warnings.append("当前估值数据获取失败")
            logger.error("❌ 当前估值数据不可用")
        else:
            metrics.pe_ttm = current_data.get('pe_ttm')
            metrics.pb = current_data.get('pb')
            metrics.dividend_yield = current_data.get('dividend_yield')
            metrics.market_cap = current_data.get('market_cap_yi')

        # Step 2: 获取历史分位（可降级）
        percentile_data = self.fetch_historical_percentile(symbol)
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

        # Step 3: 计算 PS、PCF 和 P/FCF（可降级）
        if current_data.get('market_cap'):
            ps_pcf_data = self.calculate_ps_pcf(symbol, metrics.stock_name, current_data['market_cap'])
            metrics.ps_ttm = ps_pcf_data.get('ps_ttm')
            metrics.pcf = ps_pcf_data.get('pcf')
            metrics.p_fcf = ps_pcf_data.get('p_fcf')  # 新增
            if ps_pcf_data.get('pcf_note'):
                metrics.warnings.append(ps_pcf_data['pcf_note'])
            if ps_pcf_data.get('fcf_note'):
                metrics.warnings.append(ps_pcf_data['fcf_note'])

        # 生成文本摘要
        summary = self._generate_summary(metrics)

        logger.info(f"\n✅ 估值分析完成！")

        return metrics, summary

    def _generate_summary(self, metrics: ValuationMetrics) -> str:
        """生成估值摘要文本"""
        lines = []

        lines.append(f"## {metrics.stock_name} ({metrics.stock_code}) 估值摘要")
        lines.append(f"更新时间: {metrics.update_time}")
        lines.append("")

        # 当前估值
        lines.append("### 当前估值指标")
        lines.append(f"- PE-TTM: {metrics.pe_ttm or 'N/A'}")
        lines.append(f"- PB: {metrics.pb or 'N/A'}")
        lines.append(f"- PS-TTM: {f'{metrics.ps_ttm:.2f}' if metrics.ps_ttm else 'N/A'}")
        lines.append(f"- PCF: {f'{metrics.pcf:.2f}' if metrics.pcf else 'N/A'}")
        lines.append(f"- P/FCF: {f'{metrics.p_fcf:.2f}' if metrics.p_fcf else 'N/A'}")
        lines.append(f"- 股息率(TTM): {f'{metrics.dividend_yield:.2f}%' if metrics.dividend_yield else 'N/A'}")
        lines.append(f"- 总市值: {f'{metrics.market_cap:.0f}亿' if metrics.market_cap else 'N/A'}")
        lines.append("")

        # 历史分位
        lines.append("### PE历史分位")
        lines.append(f"- 10年分位: {f'{metrics.pe_percentile_10y:.1f}%' if metrics.pe_percentile_10y else 'N/A'}")
        lines.append(f"- 5年分位: {f'{metrics.pe_percentile_5y:.1f}%' if metrics.pe_percentile_5y else 'N/A'}")
        lines.append(f"- 3年分位: {f'{metrics.pe_percentile_3y:.1f}%' if metrics.pe_percentile_3y else 'N/A'}")
        lines.append(f"- 1年分位: {f'{metrics.pe_percentile_1y:.1f}%' if metrics.pe_percentile_1y else 'N/A'}")
        lines.append("")

        lines.append("### PB历史分位")
        lines.append(f"- 10年分位: {f'{metrics.pb_percentile_10y:.1f}%' if metrics.pb_percentile_10y else 'N/A'}")
        lines.append(f"- 5年分位: {f'{metrics.pb_percentile_5y:.1f}%' if metrics.pb_percentile_5y else 'N/A'}")
        lines.append(f"- 3年分位: {f'{metrics.pb_percentile_3y:.1f}%' if metrics.pb_percentile_3y else 'N/A'}")
        lines.append(f"- 1年分位: {f'{metrics.pb_percentile_1y:.1f}%' if metrics.pb_percentile_1y else 'N/A'}")

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

## 当前估值指标

| 指标 | 当前值 | 说明 |
|------|--------|------|
| PE-TTM | {metrics.pe_ttm or 'N/A'} | 滚动市盈率（股价/每股收益） |
| PB | {metrics.pb or 'N/A'} | 市净率（股价/每股净资产） |
| PS-TTM | {f'{metrics.ps_ttm:.2f}' if metrics.ps_ttm else 'N/A'} | 市销率（市值/营收） |
| PCF | {f'{metrics.pcf:.2f}' if metrics.pcf else 'N/A'} | 市现率（市值/经营现金流） |
| P/FCF | {f'{metrics.p_fcf:.2f}' if metrics.p_fcf else 'N/A'} | 市值/自由现金流（FCF=经营现金流-资本开支） |
| 股息率(TTM) | {f'{metrics.dividend_yield:.2f}%' if metrics.dividend_yield else 'N/A'} | 滚动股息率 |
| 总市值 | {f'{metrics.market_cap:.0f}亿' if metrics.market_cap else 'N/A'} | - |

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

"""

        # 添加数据说明（如果有警告）
        if metrics.warnings:
            prompt += "## 数据说明\n"
            for warning in metrics.warnings:
                prompt += f"- {warning}\n"
            prompt += "\n"

        prompt += """## 分析要求

请从以下维度进行估值分析：

### 1. 估值健康度评估
- 当前PE/PB/PS/PCF/P_FCF估值是否合理？与历史相比处于什么位置？
- 多个估值指标是否一致？有无矛盾信号？（如PE低但PB高，或PCF高但P/FCF低）
- 股息率是否具有吸引力？是否提供安全边际？
- **现金流质量**：PCF与P/FCF的差异说明了什么？资本开支是否过高？

### 2. 估值风险识别
- 是否存在"估值陷阱"？（如PE低但业绩下滑、周期股见顶等）
- 历史分位的参考局限性是什么？（行业周期、公司发展阶段变化）
- 当前估值隐含了什么市场预期？

### 3. 投资建议
- 当前估值是否适合买入/持有/卖出？
- 如果买入，合理的估值区间是多少？
- 需要重点关注的风险指标是什么？

## 输出格式

### 综合估值评级
**[明显低估/低估/合理/高估/明显高估]** | 置信度：[高/中/低]

### 核心结论
[用2-3句大白话总结估值状况，适合非专业投资者理解]

### 关键发现
1. [发现1 - 带数据支撑]
2. [发现2 - 带数据支撑]
3. [发现3 - 带数据支撑]

### 投资建议
- **估值吸引力**: [描述当前估值是否有吸引力]
- **合理买入区间**: [给出具体的PE或价格区间]
- **主要风险**: [列出1-2个主要风险]

---
**免责声明**：本分析基于历史数据和统计方法，不构成投资建议。股市有风险，投资需谨慎。
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
