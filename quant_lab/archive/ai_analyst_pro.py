import os
import akshare as ak
import pandas as pd
from openai import OpenAI
from datetime import datetime, timedelta
import requests
import urllib.parse

# --- 环境设置 ---
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('all_proxy', None)

# 🔴 替换 Key
API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-fd00c57b4db04bafb22800b3497701bd") 
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
SYMBOL = "002683" # 广东宏大

# 辅助函数：自动判断市场 (sh/sz)
def get_market_code(symbol):
    if symbol.startswith("6"):
        return "sh"
    return "sz" # 00开头的、30开头的都是深圳

# ================= 数据获取区 =================

# 1. 技术面 (K线 & 均线)
print(f"🚀 [1/4] 拉取技术数据...")
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
- 短期趋势(MA20): {ma20:.2f} (现价{'站上' if current_price > ma20 else '跌破'}月线)
- 长期牛熊(MA250): {ma250:.2f} (现价{'站上' if current_price > ma250 else '跌破'}年线)
- 6年位置: 最高{df['最高'].max()} / 最低{df['最低'].min()}
"""

# 2. 基本面 (估值 + 成长性)
print(f"💰 [2/4] 拉取财务与估值...")
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
    fund_context = "基本面数据暂时缺失。"

# 3. 资金面 (修复了 Market 参数问题)
print(f"💸 [3/4] 拉取主力资金流向...")
try:
    # 自动判断市场
    market_code = get_market_code(SYMBOL)
    # 加上 market 参数
    fund_flow = ak.stock_individual_fund_flow(stock=SYMBOL, market=market_code)
    
    recent_flow = fund_flow.tail(3)
    flow_text = ""
    for index, row in recent_flow.iterrows():
        # 日期格式化 (akshare返回的可能是datetime对象，转str)
        d = str(row['日期'])[:10] 
        net_in = row['主力净流入-净额'] # 注意：不同接口列名可能不同，这里根据诊断结果修正
        
        # 诊断结果显示列名是 '主力净流入-净额'
        net_in_str = f"{net_in/10000:.2f}万" if abs(net_in) < 1e8 else f"{net_in/1e8:.2f}亿"
        status = "流入🔴" if net_in > 0 else "流出🟢"
        flow_text += f"- {d}: 主力{status} {net_in_str}\n"
    
    money_context = f"""
    【近3日主力资金表现】
    {flow_text}
    """
except Exception as e:
    print(f"   ⚠️ 资金流向报错: {e}")
    money_context = "资金流向数据获取失败。"

# --- 模块 D: 舆情面 (最终容错版) ---
print(f"📰 [4/4] 拉取公告舆情...")

news_context = "【最新舆情】\n暂无近期重大新闻或公告 (数据源访问受限)。"

try:
    # 尝试 1: 公告接口
    notice_df = ak.stock_notice_report(symbol=SYMBOL)
    if not notice_df.empty:
        notices = notice_df['公告标题'].head(5).tolist()
        notice_text = "\n".join([f"- [公告] {t}" for t in notices])
        news_context = f"【最新公司公告】\n{notice_text}"
        print(f"   -> 抓取到 {len(notice_df)} 条公告")
    else:
        print(f"   -> 公告数据为空 (正常现象)")

except Exception as e:
    # 捕获所有错误，不让程序崩溃，也不显示红字报错
    print(f"   -> 公告接口暂时不可用 (跳过)")
    # 这里我们尝试用一个更基础的接口作为替补：个股信息
    try:
        info_df = ak.stock_individual_info_em(symbol=SYMBOL)
        # 提取行业信息作为替代
        industry = info_df[info_df['item'] == '行业板块']['value'].values[0]
        news_context = f"【基本信息】\n当前无具体新闻。该股属于 [{industry}] 板块，请结合行业走势分析。"
    except:
        pass

# 再次确认资金面数据是否成功，如果成功，新闻的重要性就下降了
if "主力流入" in money_context:
    news_context += "\n(注：虽无新闻，但主力资金持续活跃，请以资金面信号为主。)"
# ================= 🔍 最终核查 (Debug Print) =================
print("\n" + "="*10 + " 🔍 数据核查 " + "="*10)
print(money_context)
print(news_context)
print("="*30 + "\n")

# ================= 终极 Prompt =================
prompt = f"""
你是一位【实战派】基金经理。请基于以下维度对 {SYMBOL} 进行分析。

=== 1. 资金面 (Smart Money) ===
{money_context}
(分析：主力资金是在吸筹还是出货？)

=== 2. 基本面 (Valuation) ===
{fund_context}

=== 3. 技术面 (Trend) ===
{tech_context}

=== 4. 舆情面 (Sentiment) ===
{news_context}
(注意：重点关注公告中是否有减持、业绩预告等关键信息。若无，视为消息真空期。)

=== 决策任务 ===
1. **资金评分**：(0-10分)
2. **核心逻辑**：一句话概括。
3. **操作计划**：(激进 vs 稳健)

请开始分析：
"""

# --- 调用与输出 ---
print(f"\n🧠 正在调用 GLM-4.6 ...")
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
completion = client.chat.completions.create(
    model="glm-4.6",
    messages=[{"role": "user", "content": prompt}],
    extra_body={"enable_thinking": True},
    stream=True
)

full_response = ""
print("\n" + "=" * 20 + " 🧠 AI 思考过程 " + "=" * 20)
for chunk in completion:
    delta = chunk.choices[0].delta
    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
        print(delta.reasoning_content, end="", flush=True)
    if hasattr(delta, "content") and delta.content:
        full_response += delta.content
        print(delta.content, end="", flush=True)

# 写入文件
with open(f"ProMax_Fixed_{SYMBOL}.md", "w", encoding="utf-8") as f:
    f.write(f"# 深度研报 {SYMBOL}\n\n{full_response}")
print(f"\n\n✅ 研报已生成！")

# Bark 推送 (简版)
try:
    summary = full_response[-100:].replace("\n", " ")
    requests.get(f"https://api.day.app/你的Key/AI研报生成/{urllib.parse.quote(summary)}?group=Alpha", timeout=3)
except:
    pass