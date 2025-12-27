import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import os
import time
import json
from ddgs import DDGS
import logging
import requests

# --- 配置日志系统 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

# === 全局强制直连 (国内环境) ===
proxy_vars = ['http_proxy', 'https_proxy', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY']
for k in proxy_vars:
    if k in os.environ:
        del os.environ[k]

# --- 辅助函数：东财公告获取 ---
def get_eastmoney_announcements(symbol: str, limit: int = 5) -> list:
    """
    从东方财富获取公司公告

    Args:
        symbol: 股票代码（如"002920"）
        limit: 获取公告数量，默认5条

    Returns:
        公告标题列表
    """
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
    params = {
        "sr": -1,
        "page_size": limit,
        "page_index": 1,
        "ann_type": "A",           # 所有公告
        "client_source": "web",
        "stock_list": symbol
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if 'data' in data and 'list' in data['data']:
                ann_list = data['data']['list']
                # 提取标题，限制长度避免过长
                titles = []
                for item in ann_list:
                    title = item.get('title', item.get('art_title', ''))
                    if title:
                        # 清理标题：移除公司名前缀，限制长度
                        if ':' in title:
                            title = title.split(':', 1)[1]
                        if len(title) > 60:
                            title = title[:60] + '...'
                        titles.append(title)
                return titles[:limit]
    except Exception as e:
        logging.warning(f"东财公告获取失败: {type(e).__name__}")

    return []

# --- 1. 资产类型识别器 (精准版) ---
# 上证指数代码白名单 (000开头的指数，避免与深圳主板股票冲突)
SH_INDEX_CODES = {
    "000001",  # 上证综指
    "000002",  # 上证A股
    "000003",  # 上证B股
    "000016",  # 上证50
    "000300",  # 沪深300
    "000688",  # 科创50
    "000852",  # 中证1000
    "000905",  # 中证500
    "000906",  # 中证800
    "000932",  # 中证消费
    "000985",  # 中证全指
    "000991",  # 全指医药
    "000993",  # 全指信息
}

def detect_asset_type(code):
    # 指数检测:
    # - 1A/1B: 上证指数别名格式
    # - 399: 深证/创业板指数
    # - 931/930: 中证指数
    # - H30: 港股通指数
    # - sh000/sz399: 带交易所前缀的指数
    # - SH_INDEX_CODES: 000开头的上证指数白名单
    if code.startswith(("1A", "1B", "399", "931", "930", "H30", "sh000", "sz399")):
        return "index"
    if code in SH_INDEX_CODES:
        return "index"
    # ETF/LOF: 15/16(深), 51/56/58(沪)
    if code.startswith(("15", "16", "51", "56", "58")):
        return "etf"
    return "stock"

# --- 2. 市场代码清洗 (关键修复) ---
def clean_code_for_akshare(code, asset_type):
    if asset_type == 'index':
        # 1A0001 格式转换为 sh000001
        if code == "1A0001":
            return "sh000001"
        # 000开头的上证指数 (如 000001, 000300, 000905)
        if code in SH_INDEX_CODES:
            return f"sh{code}"
        # 深证/创业板/中证指数处理 (399开头)
        if code.startswith("399"):
            return f"sz{code}"
    return code

# --- 3. 核心获取函数 (分层策略) ---
def fetch_stock_data(symbol, stock_name):
    asset_type = detect_asset_type(symbol)
    clean_symbol = clean_code_for_akshare(symbol, asset_type)
    
    print(f"📥 [{asset_type.upper()}] 拉取: {stock_name} ({clean_symbol})...")
    data = {'type': asset_type, 'name': stock_name, 'code': symbol}
    
    # === A. 技术面 (分接口获取) ===
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        df = pd.DataFrame()

        # 🎯 策略分流
        if asset_type == 'index':
            # 指数接口
            df = ak.stock_zh_index_daily(symbol=clean_symbol)
            df.rename(columns={'close': '收盘'}, inplace=True)
        
        elif asset_type == 'etf':
            # ETF 接口 (东方财富源)
            df = ak.fund_etf_hist_em(symbol=clean_symbol, period="daily", start_date=start_date.strftime("%Y%m%d"), end_date=end_date.strftime("%Y%m%d"), adjust="qfq")
        
        else:
            # 个股接口
            df = ak.stock_zh_a_hist(symbol=clean_symbol, period="daily", start_date=start_date.strftime("%Y%m%d"), end_date=end_date.strftime("%Y%m%d"), adjust="qfq")

        # 数据清洗与计算
        if not df.empty:
            price = df.iloc[-1]['收盘']

            # ==================== 多周期均线 ====================
            df['MA5'] = df['收盘'].rolling(5).mean()
            df['MA10'] = df['收盘'].rolling(10).mean()
            df['MA20'] = df['收盘'].rolling(20).mean()
            df['MA60'] = df['收盘'].rolling(60).mean()
            df['MA120'] = df['收盘'].rolling(120).mean()
            df['MA250'] = df['收盘'].rolling(250).mean()

            # 获取最新均线值
            ma5 = df.iloc[-1]['MA5']
            ma10 = df.iloc[-1]['MA10']
            ma20 = df.iloc[-1]['MA20']
            ma60 = df.iloc[-1]['MA60']
            ma120 = df.iloc[-1]['MA120']
            ma250 = df.iloc[-1]['MA250']

            # 存储均线数据
            data['price'] = round(price, 2)
            data['ma5'] = round(ma5, 2) if pd.notna(ma5) else None
            data['ma10'] = round(ma10, 2) if pd.notna(ma10) else None
            data['ma20'] = round(ma20, 2) if pd.notna(ma20) else None
            data['ma60'] = round(ma60, 2) if pd.notna(ma60) else None
            data['ma120'] = round(ma120, 2) if pd.notna(ma120) else None
            data['ma250'] = round(ma250, 2) if pd.notna(ma250) else None

            # ==================== 均线排列状态 ====================
            ma_values = [v for v in [ma5, ma10, ma20, ma60] if pd.notna(v)]
            if len(ma_values) >= 3:
                if ma_values == sorted(ma_values, reverse=True):
                    data['ma_alignment'] = "多头排列 ✅"
                elif ma_values == sorted(ma_values):
                    data['ma_alignment'] = "空头排列 ⚠️"
                else:
                    data['ma_alignment'] = "均线纠缠"
            else:
                data['ma_alignment'] = "数据不足"

            # ==================== 涨跌幅计算 ====================
            if len(df) >= 5:
                data['change_5d'] = round((price / df.iloc[-5]['收盘'] - 1) * 100, 2)
            else:
                data['change_5d'] = None

            if len(df) >= 20:
                data['change_20d'] = round((price / df.iloc[-20]['收盘'] - 1) * 100, 2)
            else:
                data['change_20d'] = None

            if len(df) >= 60:
                data['change_60d'] = round((price / df.iloc[-60]['收盘'] - 1) * 100, 2)
            else:
                data['change_60d'] = None

            # ==================== 量比计算 ====================
            if '成交量' in df.columns and len(df) >= 5:
                today_vol = df.iloc[-1]['成交量']
                avg_vol_5d = df['成交量'].iloc[-6:-1].mean()  # 前5日均量
                if avg_vol_5d > 0:
                    volume_ratio = today_vol / avg_vol_5d
                    data['volume_ratio'] = round(volume_ratio, 2)
                    if volume_ratio > 2.0:
                        data['volume_alert'] = f"放量异动 ({volume_ratio:.1f}倍)"
                    elif volume_ratio < 0.5:
                        data['volume_alert'] = f"显著缩量 ({volume_ratio:.1f}倍)"
                    else:
                        data['volume_alert'] = f"量能正常 ({volume_ratio:.1f}倍)"
                else:
                    data['volume_ratio'] = None
                    data['volume_alert'] = "N/A"
            else:
                data['volume_ratio'] = None
                data['volume_alert'] = "N/A"

            # ==================== RSI计算 (14日) ====================
            if len(df) >= 15:
                delta = df['收盘'].diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                rsi_value = rsi.iloc[-1]
                data['rsi'] = round(rsi_value, 1) if pd.notna(rsi_value) else None
                if pd.notna(rsi_value):
                    if rsi_value > 70:
                        data['rsi_signal'] = f"超买区 ({rsi_value:.0f}) ⚠️"
                    elif rsi_value < 30:
                        data['rsi_signal'] = f"超卖区 ({rsi_value:.0f}) 🔥"
                    else:
                        data['rsi_signal'] = f"正常 ({rsi_value:.0f})"
                else:
                    data['rsi_signal'] = "N/A"
            else:
                data['rsi'] = None
                data['rsi_signal'] = "数据不足"

            # ==================== MACD计算 ====================
            if len(df) >= 35:
                ema12 = df['收盘'].ewm(span=12, adjust=False).mean()
                ema26 = df['收盘'].ewm(span=26, adjust=False).mean()
                dif = ema12 - ema26
                dea = dif.ewm(span=9, adjust=False).mean()
                macd = (dif - dea) * 2

                data['macd_dif'] = round(dif.iloc[-1], 3) if pd.notna(dif.iloc[-1]) else None
                data['macd_dea'] = round(dea.iloc[-1], 3) if pd.notna(dea.iloc[-1]) else None
                data['macd_hist'] = round(macd.iloc[-1], 3) if pd.notna(macd.iloc[-1]) else None

                # 判断金叉/死叉
                if len(dif) >= 2 and pd.notna(dif.iloc[-1]) and pd.notna(dif.iloc[-2]):
                    if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]:
                        data['macd_signal'] = "金叉 ✅"
                    elif dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2]:
                        data['macd_signal'] = "死叉 ⚠️"
                    elif dif.iloc[-1] > dea.iloc[-1]:
                        data['macd_signal'] = "多头运行"
                    else:
                        data['macd_signal'] = "空头运行"
                else:
                    data['macd_signal'] = "N/A"
            else:
                data['macd_dif'] = None
                data['macd_dea'] = None
                data['macd_hist'] = None
                data['macd_signal'] = "数据不足"

            # ==================== 支撑压力位 (近20日高低点) ====================
            if len(df) >= 20:
                recent_20d = df.tail(20)
                data['high_20d'] = round(recent_20d['最高'].max(), 2) if '最高' in df.columns else None
                data['low_20d'] = round(recent_20d['最低'].min(), 2) if '最低' in df.columns else None

                # 计算距离压力位/支撑位的百分比
                if data['high_20d'] and data['low_20d']:
                    data['dist_to_high'] = round((data['high_20d'] / price - 1) * 100, 1)
                    data['dist_to_low'] = round((price / data['low_20d'] - 1) * 100, 1)
            else:
                data['high_20d'] = None
                data['low_20d'] = None
                data['dist_to_high'] = None
                data['dist_to_low'] = None

            # 60日高低点
            if len(df) >= 60:
                recent_60d = df.tail(60)
                data['high_60d'] = round(recent_60d['最高'].max(), 2) if '最高' in df.columns else None
                data['low_60d'] = round(recent_60d['最低'].min(), 2) if '最低' in df.columns else None
            else:
                data['high_60d'] = None
                data['low_60d'] = None

            # ==================== 波动率 (20日振幅均值) ====================
            if len(df) >= 20 and '最高' in df.columns and '最低' in df.columns:
                df['振幅'] = (df['最高'] - df['最低']) / df['收盘'].shift(1) * 100
                volatility = df['振幅'].tail(20).mean()
                data['volatility_20d'] = round(volatility, 2) if pd.notna(volatility) else None
            else:
                data['volatility_20d'] = None

            # ==================== 趋势位置判断 ====================
            pos = "数据不足"
            if pd.notna(ma250):
                pos = "年线上方(强势)" if price > ma250 else "年线下方(弱势)"
            elif pd.notna(ma20):
                pos = "月线上方" if price > ma20 else "月线下方"
            data['trend_position'] = pos

            # ==================== 生成摘要 ====================
            # 简洁版摘要
            data['tech_summary'] = f"现价 {price:.2f} | MA20 {ma20:.2f} | {pos}"

            # 详细版上下文 (供LLM分析)
            ma_str = f"MA5={data['ma5']} MA10={data['ma10']} MA20={data['ma20']} MA60={data['ma60']} MA120={data['ma120']} MA250={data['ma250']}"
            change_str = f"5日涨跌={data['change_5d']}% 20日涨跌={data['change_20d']}% 60日涨跌={data['change_60d']}%"

            data['tech_context'] = f"""当前价格: {price:.2f}
均线系统: {ma_str}
均线状态: {data['ma_alignment']}
涨跌幅: {change_str}
量比: {data.get('volume_alert', 'N/A')}
RSI(14): {data.get('rsi_signal', 'N/A')}
MACD: {data.get('macd_signal', 'N/A')}
20日高点: {data.get('high_20d')} (距离+{data.get('dist_to_high')}%)
20日低点: {data.get('low_20d')} (距离-{data.get('dist_to_low')}%)
趋势判断: {pos}"""
        else:
            raise ValueError("Empty DataFrame")

    except Exception as e:
        logging.error(f"✗ K线获取失败 [{stock_name}]: {type(e).__name__} - {str(e)[:100]}")
        data['tech_summary'] = "K线缺失"
        data['tech_context'] = "无法获取K线数据，可能代码格式有误。"

    # === B. 资金面 (仅个股) ===
    if asset_type == 'stock':
        try:
            market = "sh" if clean_symbol.startswith(("6", "68")) else "sz"
            fund_flow = ak.stock_individual_fund_flow(stock=clean_symbol, market=market)
            recent = fund_flow.tail(3)
            total_net = recent['主力净流入-净额'].sum()
            # 使用符合直觉的标记：流入用绿色✅（利好），流出用红色❌（利空）
            status = "✅流入" if total_net > 0 else "❌流出"
            amt = f"{total_net/1e8:.2f}亿" if abs(total_net) > 1e8 else f"{total_net/10000:.0f}万"
            data['money_summary'] = f"3日主力{status} {amt}"
            
            txt = ""
            for _, r in recent.iterrows():
                txt += f"- {str(r['日期'])[:10]}: {'流入' if r['主力净流入-净额']>0 else '流出'}\n"
            data['money_context'] = txt
        except Exception as e:
            logging.warning(f"✗ 资金流向获取失败 [{stock_name}]: {type(e).__name__}")
            data['money_summary'] = "资金缺失"
            data['money_context'] = "无"
    elif asset_type == 'index':
         data['money_summary'] = "关注成交量"
         data['money_context'] = "大盘指数请重点关注'成交量'变化，而非单一个股资金流向。"
    else:
        data['money_summary'] = "不适用"
        data['money_context'] = "ETF资金流向需查询份额变化，暂不支持直读。"

    # === C. 舆情面 (三引擎策略) ===
    news_list = []
    news_source = "无"

    if asset_type == 'stock':
        # --- 引擎1: 东方财富公告 (优先) ⚡快速 ---
        try:
            logging.info(f"尝试东财公告接口: {stock_name}")
            announcements = get_eastmoney_announcements(symbol, limit=5)
            if announcements:
                news_list = announcements
                news_source = "东财公告"
                logging.info(f"✓ 东财公告获取 {len(news_list)} 条")
        except Exception as e:
            logging.warning(f"✗ 东财公告异常: {type(e).__name__}")

        # --- 引擎2: DuckDuckGo 联网搜索 (备用) ---
        if not news_list:
            try:
                logging.info(f"启动DuckDuckGo联网搜索: {stock_name}")
                with DDGS() as ddgs:
                    # 简化搜索词，提高命中率
                    query = f'{stock_name} 股票'
                    results = list(ddgs.text(
                        query,
                        region='cn-zh',
                        timelimit='w',
                        max_results=10  # 增加结果数
                    ))

                    # 放宽过滤条件
                    for r in results:
                        title = r.get('title', '')
                        body = r.get('body', '')
                        # 只要标题或正文包含股票名或代码，就收录
                        full_text = title + ' ' + body
                        if stock_name in full_text or symbol in full_text:
                            news_list.append(f"{title}")
                            if len(news_list) >= 5:  # 限制5条
                                break

                    if news_list:
                        news_source = "全网搜索"
                        logging.info(f"✓ DuckDuckGo获取 {len(news_list)} 条资讯")
                    else:
                        logging.info(f"DuckDuckGo搜索到 {len(results)} 条结果，但无相关内容")
            except Exception as e:
                logging.warning(f"✗ DuckDuckGo搜索失败: {type(e).__name__} - {str(e)[:50]}")

        # --- 引擎3: 大盘背景 (保底) ---
        if not news_list:
            try:
                logging.info("使用大盘背景作为替代")
                sh_index = ak.stock_zh_index_daily(symbol="sh000001")
                last_day = sh_index.iloc[-1]
                change = last_day['close'] - last_day['open']
                status = "上涨" if change > 0 else "下跌"
                news_list = [f"无个股新闻/公告。市场背景: 上证指数近期{status}"]
                news_source = "大盘背景"
                logging.info(f"✓ 使用大盘背景信息")
            except Exception as e:
                logging.warning(f"✗ 大盘数据获取失败: {type(e).__name__}")

    # === 数据整合 ===
    if news_list:
        data['news_summary'] = f"[{news_source}] {len(news_list)}条"
        data['news_context'] = "\n".join([f"- {item}" for item in news_list])
        data['news_source'] = news_source
    else:
        data['news_summary'] = "静默"
        data['news_context'] = "当前无任何新闻或资讯"
        data['news_source'] = "无"
        logging.warning(f"✗ {stock_name} 所有新闻源均失败")

    return data