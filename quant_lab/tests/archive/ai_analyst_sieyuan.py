import os
import akshare as ak
import pandas as pd
from openai import OpenAI
from datetime import datetime, timedelta
import requests
import urllib.parse
import time

# --- 环境设置 ---
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('all_proxy', None)

# 🔴 替换 Key
API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-fd00c57b4db04bafb22800b3497701bd") 
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 🎯 目标更换为：思源电气
SYMBOL = "002028" 
STOCK_NAME = "思源电气"

# 辅助函数：自动判断市场
def get_market_code(symbol):
    if symbol.startswith("6"): return "sh"
    return "sz"

# ================= 数据获取区 =================

# 1. 技术面
print(f"🚀 [1/4] 拉取 {STOCK_NAME} ({SYMBOL}) 技术数据...")
end_date = datetime.now()
start_date_6y = end_date - timedelta(days=365 * 6)
df = ak.stock_zh_a_hist(symbol=SYMBOL, period="daily", start_date=start_date_6y.strftime("%Y%m%d"), end_date=end_date.strftime("%Y%m%d"), adjust="qfq")
current_price = df.iloc[-1]['收盘']
df['MA20'] = df['收盘'].rolling(window=20).mean()
df['MA250'] = df['收盘'].rolling(window=250).mean()
ma20 = df.iloc[-1]['MA20']
ma250 = df.iloc[-1]['MA250']

tech_context = f"""
- 现价: {current_price}
- 短期趋势(MA20): {ma20:.2f} ({'站上' if current_price > ma20 else '跌破'})
- 长期牛熊(MA250): {ma250:.2f} ({'站上' if current_price > ma250 else '跌破'})
- 6年位置: 最高{df['最高'].max()} / 最低{df['最低'].min()}
"""

# 2. 基本面
print(f"💰 [2/4] 拉取财务估值...")
try:
    spot_df = ak.stock_zh_a_spot_em()
    target = spot_df[spot_df['代码'] == SYMBOL].iloc[0]
    fund_context = f"""
    - 总市值: {target['总市值']/1e8:.2f} 亿
    - 动态市盈率(PE-TTM): {target['市盈率-动态']}
    - 市净率(PB): {target['市净率']}
    - 换手率: {target['换手率']}%
    """
except:
    fund_context = "基本面数据获取失败。"

# 3. 资金面
print(f"💸 [3/4] 拉取资金流向...")
try:
    market_code = get_market_code(SYMBOL)
    fund_flow = ak.stock_individual_fund_flow(stock=SYMBOL, market=market_code)
    recent_flow = fund_flow.tail(3)
    
    flow_text = ""
    for index, row in recent_flow.iterrows():
        d = str(row['日期'])[:10]
        net_in = row['主力净流入-净额']
        # 格式化
        net_in_str = f"{net_in/10000:.2f}万" if abs(net_in) < 1e8 else f"{net_in/1e8:.2f}亿"
        status = "流入🔴" if net_in > 0 else "流出🟢"
        flow_text += f"- {d}: 主力{status} {net_in_str}\n"
    
    money_context = f"【近3日主力资金】\n{flow_text}"
except:
    money_context = "资金流向暂不可用。"

# 4. 舆情面 (增强版：新闻 -> 公告 -> 股吧)
print(f"📰 [4/4] 拉取深度舆情 (新闻/公告/股吧)...")
news_context = ""
has_news = False

# 尝试A: 官方新闻
try:
    news_df = ak.stock_news_em(symbol=SYMBOL)
    if not news_df.empty:
        titles = news_df['title'].head(3).tolist()
        news_context += "【媒体新闻】\n" + "\n".join([f"- {t}" for t in titles]) + "\n"
        has_news = True
        print(f"   -> 抓取到媒体新闻")
except:
    pass

# 尝试B: 公司公告
try:
    notice_df = ak.stock_notice_report(symbol=SYMBOL)
    if not notice_df.empty:
        notices = notice_df['公告标题'].head(3).tolist()
        news_context += "【公司公告】\n" + "\n".join([f"- {t}" for t in notices]) + "\n"
        has_news = True
        print(f"   -> 抓取到公司公告")
except:
    pass

# 尝试C: 股吧社区 (作为最后防线)
try:
    # 股吧是散户聚集地，数据非常多，几乎必有
    guba_df = ak.stock_zh_a_guba_em(symbol=SYMBOL)
    if not guba_df.empty:
        # 过滤掉阅读量太小的水贴，只取前几条热门
        posts = guba_df['title'].head(5).tolist()
        news_context += "【股吧散户热议】(注意辨别情绪)\n" + "\n".join([f"- {t}" for t in posts])
        has_news = True
        print(f"   -> 抓取到股吧热议")
except Exception as e:
    print(f"   ⚠️ 股吧接口报错: {e}")

if not has_news:
    news_context = "【舆情】\n全网静默，无新闻、无公告、无讨论。"

# ================= 🔍 调试输出 =================
print("\n" + "="*10 + " 数据自检 " + "="*10)
print(f"标的: {STOCK_NAME} ({SYMBOL})")
print(money_context)
print(news_context)
print("="*30 + "\n")

# ================= 思考提示词 =================
prompt = f"""
你是一位顶级基金经理。请分析【{STOCK_NAME} ({SYMBOL})】：

=== 1. 资金面 (Smart Money) ===
{money_context}
(主力是买是卖？连续性如何？)

=== 2. 舆情与情绪 (Sentiment) ===
{news_context}
(如果是【媒体新闻】，关注利好利空；如果是【股吧热议】，关注散户情绪是恐慌还是亢奋？)

=== 3. 估值与技术 ===
{fund_context}
{tech_context}

=== 最终决策 ===
1. **资金评分** (0-10):
2. **舆情定性** (利好/利空/嘈杂/平静):
3. **操作建议** (激进 vs 稳健):

开始分析：
"""

print(f"🧠 正在调用 GLM-4.6 分析 {STOCK_NAME}...")
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
completion = client.chat.completions.create(
    model="glm-4.6",
    messages=[{"role": "user", "content": prompt}],
    extra_body={"enable_thinking": True},
    stream=True
)

full_response = ""
print("\n" + "=" * 20 + " 🧠 AI 思考中 " + "=" * 20)
for chunk in completion:
    delta = chunk.choices[0].delta
    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
        print(delta.reasoning_content, end="", flush=True)
    if hasattr(delta, "content") and delta.content:
        full_response += delta.content
        print(delta.content, end="", flush=True)

# 写入文件
with open(f"研报_{STOCK_NAME}.md", "w", encoding="utf-8") as f:
    f.write(f"# {STOCK_NAME} 深度研报\n\n{full_response}")