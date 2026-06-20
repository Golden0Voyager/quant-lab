import functools
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import numpy as np
from openbb import obb

from ai_config import YAHOO_PROXY_URL, _yahoo_proxy


def retry(max_retries=3, delay=2):
    """简单的重试装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    print(f"警告: {func.__name__} 尝试第 {i+1} 次失败: {e}")
                    if i < max_retries - 1:
                        time.sleep(delay)
            print(f"错误: {func.__name__} 在 {max_retries} 次尝试后最终失败。")
            return None
        return wrapper
    return decorator


def _enable_yahoo_proxy():
    """在当前线程启用 Yahoo Finance 代理（线程安全）"""
    _yahoo_proxy.active = True
    _yahoo_proxy.proxy_url = YAHOO_PROXY_URL

def _disable_yahoo_proxy():
    """在当前线程关闭 Yahoo Finance 代理"""
    _yahoo_proxy.active = False


class OpenBBAnalyst:
    """
    OpenBB 数据集成模块 (Code-Expert 优化版)
    功能: 提供全球宏观和行业视野，带缓存、重试、并行获取和严格类型检查

    性能优化:
    - 13个 Yahoo Finance 指标并行获取（ThreadPoolExecutor, max_workers=6）
    - 线程局部代理注入（Yahoo Finance 走代理 ~1s/个，直连 ~7s/个）
    - 60分钟内存缓存（全球宏观数据日内变化缓慢）
    """
    # 类级别缓存：所有实例共享，避免每只股票重复拉取
    _macro_cache = None
    _last_macro_update = None
    _cache_lock = threading.Lock()
    _fetch_lock = threading.Lock()  # 确保只有一个线程执行实际抓取

    def __init__(self, cache_expire_minutes=60):
        self.cache_expire_minutes = cache_expire_minutes

    def _to_float(self, value):
        """严格的类型转换，支持 Numpy 类型和异常处理"""
        try:
            if value is None:
                return None
            if isinstance(value, (np.float64, np.float32, np.int64, np.int32)):
                return float(value)
            if isinstance(value, str):
                if value.upper() in ("N/A", "NONE", ""):
                    return None
                return float(value)
            return float(value)
        except (ValueError, TypeError):
            return None

    @retry(max_retries=2, delay=3)
    def _fetch_index_price(self, symbol):
        """内部方法: 获取指数价格（自动启用 Yahoo 代理）"""
        _enable_yahoo_proxy()
        try:
            return obb.index.price.historical(symbol=symbol, provider="yfinance").to_df()
        finally:
            _disable_yahoo_proxy()

    @retry(max_retries=2, delay=3)
    def _fetch_equity_price(self, symbol):
        """内部方法: 获取股票价格（自动启用 Yahoo 代理）"""
        _enable_yahoo_proxy()
        try:
            return obb.equity.price.historical(symbol=symbol, provider="yfinance").to_df()
        finally:
            _disable_yahoo_proxy()

    def _fetch_single_indicator(self, indicator_tuple):
        """
        获取单个指标的数据（供并行调用）

        Args:
            indicator_tuple: (symbol, key, display_name, decimals, is_required, fetch_type)

        Returns:
            (key, result_dict, is_required, success)
        """
        symbol, key, display_name, decimals, is_required, fetch_type = indicator_tuple
        result = {}
        try:
            fetch_fn = self._fetch_index_price if fetch_type == "index" else self._fetch_equity_price
            df = fetch_fn(symbol)
            if df is not None and not df.empty:
                val = self._to_float(df['close'].iloc[-1])
                if val is not None:
                    result[key] = round(val, decimals)
                    if len(df) >= 2:
                        prev = self._to_float(df['close'].iloc[-2])
                        if prev and prev > 0:
                            result[f"{key}_chg"] = round((val / prev - 1) * 100, 2)
                    return (key, result, is_required, True)
            result[key] = "N/A"
            return (key, result, is_required, False)
        except Exception as e:
            print(f"警告: {display_name}({symbol}) 获取失败: {e}")
            result[key] = "N/A"
            return (key, result, is_required, False)

    def fetch_global_macro(self, force_refresh=False):
        """
        获取对 A 股有显著影响的全球及亚太宏观指标

        优化: 13个指标并行获取 + 60分钟内存缓存
        串行模式: 13 × 7s = 91s → 并行模式: ceil(13/6) × ~2s ≈ 6-10s

        指标体系:
        - 美国: 10Y国债收益率、美元指数
        - 美股: 标普500、纳斯达克、道琼斯
        - 汇率: 美元/人民币
        - 亚太: 恒生指数、日经225
        - 风险: VIX恐慌指数
        - 大宗: WTI原油、黄金、白银
        - 加密: 比特币
        """
        now = datetime.now()
        cls = OpenBBAnalyst

        # 检查缓存是否有效（类级别，线程安全）
        with cls._cache_lock:
            if not force_refresh and cls._macro_cache and cls._last_macro_update:
                if now - cls._last_macro_update < timedelta(minutes=self.cache_expire_minutes):
                    return cls._macro_cache

        # 只让一个线程执行实际抓取，其余等待后读缓存
        with cls._fetch_lock:
            # 双重检查：等待期间其他线程可能已完成抓取
            with cls._cache_lock:
                if not force_refresh and cls._macro_cache and cls._last_macro_update:
                    if now - cls._last_macro_update < timedelta(minutes=self.cache_expire_minutes):
                        return cls._macro_cache

            print(f"[{now.strftime('%H:%M:%S')}] 正在从 OpenBB 并行刷新全球宏观数据 (13个指标)...")
            t_start = time.time()

            macro_summary = {"update_time": now.strftime("%Y-%m-%d %H:%M:%S")}

            # 定义所有指标：(symbol, key, display_name, decimals, is_required, fetch_type)
            indicators = [
                # 美国利率与美元
                ("^TNX",     "us10y_yield", "美债10Y",     3, True,  "index"),
                ("DX-Y.NYB", "dxy_index",   "美元指数",    3, True,  "index"),
                # 美股三大指数
                ("^GSPC",    "sp500",       "标普500",     2, False, "index"),
                ("^IXIC",    "nasdaq",      "纳斯达克",    2, False, "index"),
                ("^DJI",     "dowjones",    "道琼斯",      2, False, "index"),
                # 汇率
                ("CNY=X",    "usdcny",      "美元/人民币", 4, False, "equity"),
                # 亚太股市
                ("^HSI",     "hsi_index",   "恒指",        2, True,  "index"),
                ("^N225",    "nikkei225",   "日经225",     2, False, "index"),
                # 风险指标
                ("^VIX",     "vix_index",   "VIX",         2, False, "index"),
                # 大宗商品
                ("CL=F",     "wti_crude",   "WTI原油",     2, False, "equity"),
                ("GC=F",     "gold",        "黄金",        2, False, "equity"),
                ("SI=F",     "silver",      "白银",        2, False, "equity"),
                # 加密货币
                ("BTC-USD",  "btc",         "比特币",      0, False, "equity"),
            ]

            # 并行获取所有指标
            required_failed = False
            success_count = 0

            with ThreadPoolExecutor(max_workers=6) as executor:
                future_map = {
                    executor.submit(self._fetch_single_indicator, ind): ind
                    for ind in indicators
                }
                for future in as_completed(future_map):
                    ind = future_map[future]
                    try:
                        key, result, is_required, success = future.result()
                        macro_summary.update(result)
                        if success:
                            success_count += 1
                        elif is_required:
                            required_failed = True
                    except Exception as e:
                        print(f"警告: {ind[2]}({ind[0]}) 并行获取异常: {e}")
                        macro_summary[ind[1]] = "N/A"
                        if ind[4]:  # is_required
                            required_failed = True

            elapsed = time.time() - t_start
            print(f"[{datetime.now().strftime('%H:%M:%S')}] OpenBB 并行获取完成: "
                  f"{success_count}/{len(indicators)} 成功, 耗时 {elapsed:.1f}s")

            if required_failed:
                print("错误: 核心宏观指标（美债/美元/恒指）部分获取失败")
                with cls._cache_lock:
                    if cls._macro_cache:
                        print("警告: 回退到过期缓存数据")
                        return cls._macro_cache

            # VIX 风险等级判定
            vix = macro_summary.get('vix_index')
            if vix and vix != 'N/A':
                if vix > 30:
                    macro_summary['vix_level'] = '恐慌'
                elif vix > 20:
                    macro_summary['vix_level'] = '偏高'
                elif vix > 15:
                    macro_summary['vix_level'] = '正常'
                else:
                    macro_summary['vix_level'] = '贪婪'

            # 更新缓存（类级别）
            with cls._cache_lock:
                cls._macro_cache = macro_summary
                cls._last_macro_update = now
            return macro_summary

    def fetch_industry_comparison(self, us_ticker):
        """
        获取美股对标公司的表现
        """
        try:
            data = self._fetch_equity_price(us_ticker)
            if data is not None and not data.empty:
                last_price = self._to_float(data['close'].iloc[-1])
                prev_price = self._to_float(data['close'].iloc[-2])

                if last_price and prev_price:
                    change = (last_price / prev_price - 1) * 100
                    return {
                        "ticker": us_ticker,
                        "last_price": round(last_price, 2),
                        "daily_change": round(change, 2),
                        "status": "success"
                    }
            return {"ticker": us_ticker, "status": "failed", "reason": "Data empty or invalid"}
        except Exception as e:
            print(f"错误: 获取对标美股 {us_ticker} 失败: {e}")
            return {"ticker": us_ticker, "status": "error", "reason": str(e)}

    # ==================== --global 模式：完整个股分析 ====================

    def fetch_stock_analysis(self, symbol):
        """
        获取全球股票完整分析数据（K线 + 技术指标 + 基本面概要）
        用于 --global 模式

        Args:
            symbol: 股票代码，如 TSLA, AAPL, 0700.HK

        Returns:
            结构化数据字典，格式对齐 A 股 data dict
        """
        data = {
            'type': 'global_stock',
            'name': symbol,
            'code': symbol,
        }

        # 1. K线数据 + 技术指标
        try:
            df = self._fetch_equity_price(symbol)
            if df is not None and not df.empty and len(df) >= 5:
                data['price'] = round(self._to_float(df['close'].iloc[-1]), 2)
                data['open'] = round(self._to_float(df['open'].iloc[-1]), 2)
                data['high'] = round(self._to_float(df['high'].iloc[-1]), 2)
                data['low'] = round(self._to_float(df['low'].iloc[-1]), 2)
                data['volume'] = int(df['volume'].iloc[-1])

                prev_close = self._to_float(df['close'].iloc[-2])
                if data['price'] and prev_close:
                    data['change_pct'] = round((data['price'] / prev_close - 1) * 100, 2)

                # 均线计算
                closes = df['close'].astype(float)
                for period, key in [(5, 'ma5'), (10, 'ma10'), (20, 'ma20'), (60, 'ma60'), (120, 'ma120'), (250, 'ma250')]:
                    if len(closes) >= period:
                        data[key] = round(float(closes.rolling(period).mean().iloc[-1]), 2)

                # MA 排列判断
                if all(k in data for k in ['ma5', 'ma10', 'ma20']):
                    if data['ma5'] > data['ma10'] > data['ma20']:
                        data['ma_alignment'] = '多头排列 ✅'
                    elif data['ma5'] < data['ma10'] < data['ma20']:
                        data['ma_alignment'] = '空头排列 ⚠️'
                    else:
                        data['ma_alignment'] = '均线纠缠'

                # 涨跌幅统计
                if len(closes) >= 5:
                    data['change_5d'] = round((float(closes.iloc[-1]) / float(closes.iloc[-5]) - 1) * 100, 2)
                if len(closes) >= 20:
                    data['change_20d'] = round((float(closes.iloc[-1]) / float(closes.iloc[-20]) - 1) * 100, 2)
                if len(closes) >= 60:
                    data['change_60d'] = round((float(closes.iloc[-1]) / float(closes.iloc[-60]) - 1) * 100, 2)

                # RSI(14)
                if len(closes) >= 15:
                    delta = closes.diff()
                    gain = delta.where(delta > 0, 0).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                    rsi_val = round(float(rsi.iloc[-1]), 1)
                    data['rsi'] = rsi_val
                    if rsi_val > 70:
                        data['rsi_signal'] = f'超买({rsi_val})'
                    elif rsi_val < 30:
                        data['rsi_signal'] = f'超卖({rsi_val})'
                    else:
                        data['rsi_signal'] = f'正常({rsi_val})'

                # MACD(12, 26, 9)
                if len(closes) >= 35:
                    ema12 = closes.ewm(span=12, adjust=False).mean()
                    ema26 = closes.ewm(span=26, adjust=False).mean()
                    dif = ema12 - ema26
                    dea = dif.ewm(span=9, adjust=False).mean()
                    data['macd_dif'] = round(float(dif.iloc[-1]), 3)
                    data['macd_dea'] = round(float(dea.iloc[-1]), 3)
                    macd_hist = dif.iloc[-1] - dea.iloc[-1]
                    if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]:
                        data['macd_signal'] = '金叉 ✅'
                    elif dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2]:
                        data['macd_signal'] = '死叉 ⚠️'
                    elif dif.iloc[-1] > dea.iloc[-1]:
                        data['macd_signal'] = '多头运行'
                    else:
                        data['macd_signal'] = '空头运行'

                # 成交量比 (5日均量)
                if len(df) >= 6:
                    vol_5d_avg = float(df['volume'].iloc[-6:-1].mean())
                    if vol_5d_avg > 0:
                        data['volume_ratio'] = round(float(df['volume'].iloc[-1]) / vol_5d_avg, 2)

                # 20日波动率
                if len(closes) >= 21:
                    returns = closes.pct_change().dropna()
                    data['volatility_20d'] = round(float(returns.tail(20).std() * (252 ** 0.5) * 100), 1)

                # 构建技术面摘要
                trend = ''
                if 'ma250' in data and data['price']:
                    trend = '年线上方(强势)' if data['price'] > data['ma250'] else '年线下方(弱势)'
                data['tech_summary'] = (
                    f"现价 {data.get('price', 'N/A')} | "
                    f"日涨跌 {data.get('change_pct', 'N/A')}% | "
                    f"MA20 {data.get('ma20', 'N/A')} | "
                    f"{data.get('ma_alignment', '')} | "
                    f"{trend}"
                )
            else:
                data['tech_summary'] = 'K线数据不足'

        except Exception as e:
            print(f"错误: 获取 {symbol} K线数据失败: {e}")
            data['tech_summary'] = f'数据获取失败: {e}'

        # 2. 基本面数据（通过 OpenBB fundamental，如 provider 支持）
        fundamentals = self.fetch_stock_fundamentals(symbol)
        data.update(fundamentals)

        data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return data

    @retry(max_retries=2, delay=3)
    def _fetch_equity_profile(self, symbol):
        """内部方法: 获取公司概况（自动启用 Yahoo 代理）"""
        _enable_yahoo_proxy()
        try:
            return obb.equity.profile(symbol=symbol, provider="yfinance").to_df()
        finally:
            _disable_yahoo_proxy()

    def fetch_stock_fundamentals(self, symbol):
        """
        获取全球股票基本面指标（PE/PB/市值/股息率等）

        Args:
            symbol: 股票代码

        Returns:
            基本面数据字典
        """
        data = {}
        try:
            df = self._fetch_equity_profile(symbol)
            if df is not None and not df.empty:
                row = df.iloc[0]

                # 公司名称
                name = row.get('name') or row.get('long_name')
                if name:
                    data['name'] = str(name)

                # 市值
                market_cap = self._to_float(row.get('market_cap'))
                if market_cap:
                    data['market_cap'] = market_cap
                    if market_cap >= 1e12:
                        data['market_cap_display'] = f"{market_cap/1e12:.2f}万亿"
                    elif market_cap >= 1e8:
                        data['market_cap_display'] = f"{market_cap/1e8:.0f}亿"
                    else:
                        data['market_cap_display'] = f"{market_cap/1e6:.0f}百万"

                # 行业/板块
                sector = row.get('sector')
                if sector:
                    data['sector_name'] = str(sector)
                industry = row.get('industry')
                if industry:
                    data['industry_name'] = str(industry)

                # 估值摘要
                parts = []
                if data.get('market_cap_display'):
                    parts.append(f"市值: {data['market_cap_display']}")
                if data.get('sector_name'):
                    parts.append(f"行业: {data['sector_name']}")
                data['fundamental_summary'] = ' | '.join(parts) if parts else 'N/A'

                print(f"✓ 基本面: {data.get('fundamental_summary', 'N/A')}")
        except Exception as e:
            print(f"警告: 获取 {symbol} 基本面失败: {e}")
            data['fundamental_summary'] = 'N/A'

        return data

    def build_global_prompt(self, data):
        """
        构建全球股票分析 AI prompt

        Args:
            data: 包含 K 线、基本面、宏观数据的完整字典

        Returns:
            完整 prompt 字符串
        """
        symbol = data.get('code', 'N/A')
        name = data.get('name', symbol)
        macro = data.get('macro', {})

        # 宏观背景
        macro_text = ""
        if macro:
            macro_text = f"""
### 全球宏观环境
**利率与货币:**
- 美国10Y国债收益率: {macro.get('us10y_yield', 'N/A')}% (日变动: {macro.get('us10y_yield_chg', 'N/A')}%)
- 美元指数(DXY): {macro.get('dxy_index', 'N/A')} (日变动: {macro.get('dxy_index_chg', 'N/A')}%)
- 美元/人民币: {macro.get('usdcny', 'N/A')} (日变动: {macro.get('usdcny_chg', 'N/A')}%)

**美股指数:**
- 标普500: {macro.get('sp500', 'N/A')} (日变动: {macro.get('sp500_chg', 'N/A')}%)
- 纳斯达克: {macro.get('nasdaq', 'N/A')} (日变动: {macro.get('nasdaq_chg', 'N/A')}%)
- 道琼斯: {macro.get('dowjones', 'N/A')} (日变动: {macro.get('dowjones_chg', 'N/A')}%)

**亚太股市:**
- 恒生指数: {macro.get('hsi_index', 'N/A')} (日变动: {macro.get('hsi_index_chg', 'N/A')}%)
- 日经225: {macro.get('nikkei225', 'N/A')} (日变动: {macro.get('nikkei225_chg', 'N/A')}%)

**风险与大宗:**
- VIX恐慌指数: {macro.get('vix_index', 'N/A')} ({macro.get('vix_level', 'N/A')})
- WTI原油: {macro.get('wti_crude', 'N/A')}$ (日变动: {macro.get('wti_crude_chg', 'N/A')}%)
- 黄金: {macro.get('gold', 'N/A')}$ (日变动: {macro.get('gold_chg', 'N/A')}%)
- 白银: {macro.get('silver', 'N/A')}$ (日变动: {macro.get('silver_chg', 'N/A')}%)
- 比特币: {macro.get('btc', 'N/A')}$ (日变动: {macro.get('btc_chg', 'N/A')}%)

- 数据更新: {macro.get('update_time', 'N/A')}
"""

        # 技术面
        tech_text = f"""
### 技术面
{data.get('tech_summary', 'N/A')}

**均线系统**:
- MA5: {data.get('ma5', 'N/A')} | MA10: {data.get('ma10', 'N/A')} | MA20: {data.get('ma20', 'N/A')}
- MA60: {data.get('ma60', 'N/A')} | MA120: {data.get('ma120', 'N/A')} | MA250: {data.get('ma250', 'N/A')}
- 均线状态: {data.get('ma_alignment', 'N/A')}

**涨跌幅**:
- 5日: {data.get('change_5d', 'N/A')}% | 20日: {data.get('change_20d', 'N/A')}% | 60日: {data.get('change_60d', 'N/A')}%

**技术指标**:
- RSI(14): {data.get('rsi_signal', 'N/A')}
- MACD: DIF={data.get('macd_dif', 'N/A')} DEA={data.get('macd_dea', 'N/A')} — {data.get('macd_signal', 'N/A')}
- 量比: {data.get('volume_ratio', 'N/A')}
- 20日年化波动率: {data.get('volatility_20d', 'N/A')}%
"""

        # 基本面
        fund_text = f"""
### 基本面
- {data.get('fundamental_summary', 'N/A')}
"""

        prompt = f"""你是一位专业的全球市场分析师，请对【{name}】({symbol}) 进行客观分析。
请用中文回答。

## 数据矩阵
{macro_text}
{tech_text}
{fund_text}

## 分析要求

### 综合评级
**[看多/中性偏多/中性/中性偏空/看空]** | 置信度：[X]%

### 核心逻辑
[2-3句话，概括投资论点]

### 关键信号
1. [技术面信号 — 趋势、均线、动量]
2. [基本面信号 — 估值、行业地位]
3. [宏观面信号 — 利率环境、美元走势对该标的的影响]

### 操作策略
- **短线（1-4周）**: [具体建议]
- **中线（1-6个月）**: [建仓区间/持仓策略]

### 风险提示
1. [技术面风险]
2. [基本面/宏观风险]
"""
        return prompt

if __name__ == "__main__":
    import time as _time

    # 初始化全局网络（激活代理注入）
    from ai_config import init_global_network
    init_global_network()

    analyst = OpenBBAnalyst(cache_expire_minutes=1)  # 测试时设为1分钟

    print("\n--- 第一次获取 (触发并行刷新) ---")
    t0 = _time.time()
    result = analyst.fetch_global_macro()
    t1 = _time.time()
    print(f"耗时: {t1-t0:.1f}s")
    for k, v in sorted(result.items()):
        print(f"  {k}: {v}")

    print("\n--- 第二次获取 (触发缓存) ---")
    t0 = _time.time()
    result2 = analyst.fetch_global_macro()
    t1 = _time.time()
    print(f"耗时: {t1-t0:.3f}s (缓存)")

    print("\n--- 美股对标分析 (TSLA) ---")
    print(analyst.fetch_industry_comparison("TSLA"))

    print("\n--- 全球个股完整分析 (AAPL) ---")
    stock_data = analyst.fetch_stock_analysis("AAPL")
    for k, v in stock_data.items():
        print(f"  {k}: {v}")

    print("\n--- 全球分析 Prompt 预览 ---")
    macro = analyst.fetch_global_macro()
    prompt = analyst.build_global_prompt({**stock_data, 'macro': macro})
    print(prompt[:1000] + "\n...")
