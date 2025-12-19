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
def detect_asset_type(code):
    # 指数: 1A(上证), 399(深证), 000001(上证), sh/sz开头
    if code.startswith(("1A", "399", "sh000", "sz399")) or code == "000001":
        return "index"
    # ETF/LOF: 15/16(深), 51/56/58(沪)
    if code.startswith(("15", "16", "51", "56", "58")):
        return "etf"
    return "stock"

# --- 2. 市场代码清洗 (关键修复) ---
def clean_code_for_akshare(code, asset_type):
    if asset_type == 'index':
        # 上证指数处理
        if code == "1A0001" or code == "000001": return "sh000001"
        # 深证/创业板处理 (AkShare指数接口通常需要 sz 前缀)
        if code.startswith("399"): return f"sz{code}"
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
            # 计算简单的均线
            df['MA20'] = df['收盘'].rolling(20).mean()
            df['MA250'] = df['收盘'].rolling(250).mean()
            
            ma20 = df.iloc[-1]['MA20']
            ma250 = df.iloc[-1]['MA250']
            
            # 这里的逻辑判断要健壮一点，防止刚上市没年线
            pos = "数据不足"
            if pd.notna(ma250):
                pos = "年线上方(强势)" if price > ma250 else "年线下方(弱势)"
            elif pd.notna(ma20):
                pos = "月线上方" if price > ma20 else "月线下方"

            data['tech_summary'] = f"现价 {price:.2f} | MA20 {ma20:.2f} | {pos}"
            data['tech_context'] = f"当前价格: {price:.2f}, 20日线: {ma20:.2f}, 250日线: {ma250:.2f}。趋势判断: {pos}"
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