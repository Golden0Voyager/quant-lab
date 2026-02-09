import os
os.environ['TQDM_DISABLE'] = '1'

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time
import json
from ddgs import DDGS
import logging
import requests
from contextlib import contextmanager
from functools import wraps

# --- 配置日志系统 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

# === 新闻数量配置 ===
NEWS_CONFIG = {
    'eastmoney_announcements': 15,  # 东财公告数量（详尽模式：15条）
    'cls_telegraph_items': 8,       # 财联社电报数量（详尽模式：8条）
    'duckduckgo_results': 15,       # DuckDuckGo搜索结果（详尽模式：15条）
}

# === 保留系统代理设置（本地代理如Clash是数据接口的必要通道） ===

# --- 重试装饰器（指数退避） ---
def retry_on_failure(max_retries=3, delay=1, backoff=2):
    """
    失败重试装饰器，使用指数退避策略

    Args:
        max_retries: 最大重试次数（默认3次）
        delay: 初始延迟时间（秒，默认1秒）
        backoff: 退避系数（默认2，即每次重试等待时间翻倍）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        # 最后一次尝试仍失败，抛出异常
                        logging.error(f"❌ {func.__name__} 失败（已重试{max_retries}次）: {type(e).__name__}")
                        raise
                    # 计算等待时间（指数退避）
                    wait_time = delay * (backoff ** attempt)
                    logging.warning(f"⚠️ {func.__name__} 第{attempt+1}次失败，{wait_time:.1f}秒后重试... ({type(e).__name__})")
                    time.sleep(wait_time)
            return None
        return wrapper
    return decorator

# --- 辅助函数：东财公告获取（带重试） ---
@retry_on_failure(max_retries=3, delay=1, backoff=2)
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

# --- 辅助函数：K线数据获取（带重试 + 雪球优先策略） ---
@retry_on_failure(max_retries=3, delay=1, backoff=2)
def fetch_kline_data(asset_type, clean_symbol, start_date, end_date):
    """
    获取K线数据（雪球优先方案）
    """
    xq_token = os.getenv('XUEQIU_TOKEN') or os.getenv('XQ_TOKEN')
    
    # 1. 指数逻辑 (指数目前东财较稳，维持现状)
    if asset_type == 'index':
        df = ak.stock_zh_index_daily(symbol=clean_symbol)
        df.rename(columns={'close': '收盘', 'open': '开盘', 'high': '最高', 'low': '最低', 'volume': '成交量'}, inplace=True)
        return df

    # 2. 个股与 ETF — 直接使用东财（stock_zh_a_hist_xq 已在 akshare 1.17 移除）

    # 3. 降级回东财 (使用带直连的 context)
    try:
        from analyst_data import no_proxy
    except ImportError:
        @contextmanager
        def no_proxy(): yield

    if asset_type == 'etf':
        return ak.fund_etf_hist_em(symbol=clean_symbol, period="daily", start_date=start_date.strftime("%Y%m%d"), end_date=end_date.strftime("%Y%m%d"), adjust="qfq")
    else:
        return ak.stock_zh_a_hist(symbol=clean_symbol, period="daily", start_date=start_date.strftime("%Y%m%d"), end_date=end_date.strftime("%Y%m%d"), adjust="qfq")

# --- 辅助函数：资金流向获取（带重试） ---
@retry_on_failure(max_retries=3, delay=1, backoff=2)
def fetch_fund_flow_data(clean_symbol, market):
    """
    获取资金流向数据（带重试机制）

    Args:
        clean_symbol: 清洗后的股票代码
        market: 市场代码（sh/sz）

    Returns:
        DataFrame: 资金流向数据
    """
    return ak.stock_individual_fund_flow(stock=clean_symbol, market=market)

# === 财联社电报集成逻辑 (内聚版) ===

INDUSTRY_KEYWORDS = {
    "半导体": ["半导体", "芯片", "集成电路", "IC", "晶圆", "光刻", "EDA", "封测", "存储芯片", "模拟芯片", "功率半导体", "IGBT", "MCU", "FPGA", "GPU", "AI芯片"],
    "军工": ["军工", "航空", "航天", "国防", "导弹", "雷达", "无人机", "卫星", "航发", "军品", "装备", "舰船", "战机", "火箭"],
    "新能源": ["新能源", "光伏", "风电", "储能", "锂电池", "充电桩", "电池", "太阳能", "风力发电", "氢能", "核电", "清洁能源"],
    "电力设备": ["电力", "电网", "变压器", "配电", "输电", "特高压", "智能电网", "电力设备"],
    "化工": ["化工", "化学", "聚氨酯", "MDI", "TDI", "化学制品", "精细化工", "农药", "化肥"],
    "新材料": ["碳纤维", "复合材料", "柔性材料", "石墨烯", "新材料", "高分子", "陶瓷", "特种材料", "稀土", "钛合金", "碳材料"],
    "医药": ["医药", "医疗", "生物", "疫苗", "创新药", "仿制药", "CXO", "医疗器械", "诊断", "试剂", "中药"],
    "消费": ["消费", "零售", "白酒", "食品", "饮料", "家电", "家居", "服装", "化妆品"],
    "金融": ["银行", "保险", "证券", "信托", "基金", "金融科技", "支付", "理财"],
    "房地产": ["房地产", "地产", "物业", "租赁", "保障房", "商业地产"],
    "互联网": ["互联网", "电商", "游戏", "社交", "短视频", "云计算", "大数据", "软件", "SaaS", "CAD", "工业软件"],
    "汽车": ["汽车", "新能源车", "智能驾驶", "自动驾驶", "车联网", "零部件", "整车", "电动车"],
    "机械": ["机械", "工程机械", "机床", "机器人", "自动化", "液压", "工业母机", "数控", "精密制造"],
}

MACRO_POLICY_KEYWORDS = ["降息", "降准", "加息", "货币政策", "财政政策", "经济工作会议", "政治局会议", "国务院", "发改委", "证监会", "央行", "银保监", "国资委", "减税", "刺激", "扩内需", "稳增长", "房地产调控", "股市政策", "注册制", "退市"]

def get_stock_industry(stock_code: str, stock_name: str) -> list:
    """根据名称推断所属行业"""
    name_industry_map = {
        "紫光国微": ["半导体"], "中望软件": ["互联网"], "华大九天": ["半导体"], "茂莱光学": ["半导体"], "南大光电": ["半导体"],
        "中信特钢": ["新材料"], "奕瑞科技": ["医药"], "恒立液压": ["机械"], "广东宏大": ["军工"], "中航光电": ["军工"],
        "中航高科": ["军工"], "航天电器": ["军工"], "斯瑞新材": ["军工", "新材料"], "华秦科技": ["军工"],
        "西部超导": ["军工", "新材料"], "中国船舶": ["军工"], "思维列控": ["机械"], "帝尔激光": ["新能源"],
        "光威复材": ["新材料", "军工"], "宁德时代": ["新能源"], "横店东磁": ["新材料", "新能源"], "万华化学": ["化工"],
        "泰和新材": ["化工", "新材料"], "陕天然气": ["电力设备"], "长江电力": ["电力设备"], "平高电气": ["电力设备"],
        "立讯精密": ["消费"], "麦格米特": ["机械"], "扬杰科技": ["半导体"], "英维克": ["机械"],
    }
    if stock_name in name_industry_map: return name_industry_map[stock_name]
    industries = []
    if any(kw in stock_name for kw in ["电", "能源", "电力"]): industries.append("电力设备")
    if any(kw in stock_name for kw in ["航", "军", "国防"]): industries.append("军工")
    if any(kw in stock_name for kw in ["芯", "微", "电子", "半导体"]): industries.append("半导体")
    if any(kw in stock_name for kw in ["材", "复材", "纤维"]): industries.append("新材料")
    return industries if industries else ["未分类"]

@retry_on_failure(max_retries=2, delay=2)
def fetch_cls_telegraph(hours: int = 24, max_items: int = 50) -> list:
    """抓取财联社电报"""
    try:
        from bs4 import BeautifulSoup
        url = "https://www.cls.cn/telegraph"
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200: return []
        soup = BeautifulSoup(r.text, 'html.parser')
        telegraph_list = soup.find_all(['div', 'li'], class_=re.compile(r'telegraph|flash|brief|live-item'))
        if not telegraph_list: telegraph_list = soup.find_all(['div', 'article'], attrs={'data-time': True})
        news_items = []
        for item in telegraph_list[:max_items]:
            try:
                time_elem = item.find(['span', 'time'], class_=re.compile(r'time|date'))
                content_elem = item.find(['p', 'div'], class_=re.compile(r'content|title|text'))
                content = content_elem.get_text(strip=True) if content_elem else item.get_text(strip=True)
                if content and len(content) > 10:
                    news_items.append({"time": time_elem.get_text(strip=True) if time_elem else "", "content": content[:500], "type": "快讯"})
            except: continue
        return news_items
    except: return []

def calculate_cls_relevance(item, stock_code, stock_name, industries):
    """计算相关性得分"""
    content = item.get("content", "")
    if stock_name in content or stock_code in content: return 10, "直接相关"
    for ind in industries:
        if ind in INDUSTRY_KEYWORDS:
            for kw in INDUSTRY_KEYWORDS[ind]:
                if kw in content: return 6, f"行业相关({kw})"
    for kw in MACRO_POLICY_KEYWORDS:
        if kw in content: return 3, f"政策相关({kw})"
    return 0, "无关"

def match_relevant_telegraphs(stock_code, stock_name, hours=24, min_score=3, max_items=5):
    """匹配相关电报"""
    industries = get_stock_industry(stock_code, stock_name)
    telegraphs = fetch_cls_telegraph(hours=hours)
    matched = []
    for item in telegraphs:
        score, mtype = calculate_cls_relevance(item, stock_code, stock_name, industries)
        if score >= min_score:
            matched.append({**item, "relevance_score": score, "match_type": mtype})
    matched.sort(key=lambda x: x["relevance_score"], reverse=True)
    return matched[:max_items]

def format_telegraph_for_report(matched_items):
    """格式化报告文本"""
    if not matched_items: return ""
    lines = []
    for item in matched_items:
        prefix = "🔥【重要】" if item["relevance_score"] >= 8 else ("⚡【行业】" if item["relevance_score"] >= 5 else "📊【背景】")
        lines.append(f"{prefix} {item['match_type']} ({item.get('time', '')})\n  {item['content']}")
    return "\n\n".join(lines)

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

        # 🎯 使用带重试的K线数据获取函数
        df = fetch_kline_data(asset_type, clean_symbol, start_date, end_date)

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
            # 🎯 使用带重试的资金流向获取函数
            fund_flow = fetch_fund_flow_data(clean_symbol, market)
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

    # === C. 舆情面 (四引擎策略) ===
    news_list = []
    news_source = "无"
    cls_telegraphs = []  # 财联社电报（可能作为补充）

    if asset_type == 'stock':
        # --- 引擎0: 东方财富公告 (最高优先级) ⚡个股直接公告 ---
        try:
            logging.info(f"尝试东财公告接口: {stock_name}")
            announcements = get_eastmoney_announcements(
                symbol,
                limit=NEWS_CONFIG['eastmoney_announcements']
            )
            if announcements:
                news_list = announcements
                news_source = "东财公告"
                logging.info(f"✓ 东财公告获取 {len(news_list)} 条")
        except Exception as e:
            logging.warning(f"✗ 东财公告异常: {type(e).__name__}")

        # --- 引擎1: 财联社电报 (智能匹配) ⚡宏观+行业视角 ---
        try:
            logging.info(f"尝试财联社电报智能匹配: {stock_name}")
            cls_telegraphs = match_relevant_telegraphs(
                stock_code=symbol,
                stock_name=stock_name,
                hours=24,        # 最近24小时
                min_score=5,     # 最低相关性得分（5分以上才展示）
                max_items=NEWS_CONFIG['cls_telegraph_items']  # 使用配置的数量
            )

            if cls_telegraphs:
                # 判断是否已有东财公告
                if news_list:
                    # 有公告，财联社电报作为补充
                    news_source = "东财公告+财联社电报"
                    logging.info(f"✓ 财联社电报（补充）: {len(cls_telegraphs)} 条相关")
                else:
                    # 无公告，财联社电报作为主要新闻源
                    cls_formatted = format_telegraph_for_report(cls_telegraphs)
                    news_list = [cls_formatted]
                    news_source = "财联社电报"
                    logging.info(f"✓ 财联社电报（主要）: {len(cls_telegraphs)} 条相关")
        except Exception as e:
            logging.warning(f"✗ 财联社电报失败: {type(e).__name__}")

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
                        max_results=NEWS_CONFIG['duckduckgo_results']  # 使用配置的数量
                    ))

                    # 放宽过滤条件
                    for r in results:
                        title = r.get('title', '')
                        body = r.get('body', '')
                        # 只要标题或正文包含股票名或代码，就收录
                        full_text = title + ' ' + body
                        if stock_name in full_text or symbol in full_text:
                            news_list.append(f"{title}")
                            if len(news_list) >= NEWS_CONFIG['duckduckgo_results']:  # 使用配置的数量
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
    if news_list or cls_telegraphs:
        # 合并新闻内容
        all_news = []

        # 1. 添加东财公告或其他新闻源
        if news_list:
            for item in news_list:
                all_news.append(f"- {item}")

        # 2. 添加财联社电报（如果有且作为补充）
        if cls_telegraphs and news_source == "东财公告+财联社电报":
            # format_telegraph_for_report 已在本文件内定义
            all_news.append("\n【财联社行业/政策快讯】")
            cls_formatted = format_telegraph_for_report(cls_telegraphs)
            all_news.append(cls_formatted)

        # 统计新闻条数
        total_count = len(news_list) + len(cls_telegraphs)

        data['news_summary'] = f"[{news_source}] {total_count}条"
        data['news_context'] = "\n".join(all_news)
        data['news_source'] = news_source
    else:
        data['news_summary'] = "静默"
        data['news_context'] = "当前无任何新闻或资讯"
        data['news_source'] = "无"
        logging.warning(f"✗ {stock_name} 所有新闻源均失败")

    return data