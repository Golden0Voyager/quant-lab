import os
import sys
import select
import akshare as ak
import pandas as pd
from openai import OpenAI
from datetime import datetime, timedelta
from ddgs import DDGS  # <--- 改成新名字
import time

# --- 环境设置 ---
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('all_proxy', None)

# 🔴 替换 Key
API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-你的Key") 
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 🎯 目标: 长江电力 (可以随时改)
SYMBOL = "600900" 
STOCK_NAME = "长江电力"

# 辅助函数: Crontab 兼容的倒计时
def wait_for_confirmation(timeout=15):
    if not sys.stdin.isatty():
        print("🤖 检测到后台运行 (Crontab)，跳过等待，立即执行分析...")
        return True

    print(f"\n⏳ 正在等待指令 (默认 {timeout}秒后自动执行)...")
    print("👉 按 [Enter] 或输入 'y' 立即开始")
    print("👉 输入 'n' 取消本次分析")
    print("> ", end="", flush=True)

    rlist, _, _ = select.select([sys.stdin], [], [], timeout)
    if rlist:
        user_input = sys.stdin.readline().strip().lower()
        if user_input in ['n', 'no']:
            print("🚫 用户取消分析。")
            return False
        return True
    else:
        print(f"\n⏰ 超时 ({timeout}s)，自动开始...")
        return True

# 辅助函数: DuckDuckGo 联网搜索 (修正版)
def search_web_news(keyword, limit=3):
    print(f"   🔍 正在联网搜索: {keyword} ...")
    results = []
    try:
        # 使用 DDGS
        with DDGS() as ddgs:
            # 构造精准搜索词
            query_str = f'"{keyword}" (股价 OR 业绩 OR 资金 OR 研报)'
            
            # 🛠️ 修复点：直接把 query_str 放在第一个位置，不写 keywords=...
            # 这样无论参数名是 keywords 还是 query，都能兼容
            ddgs_gen = ddgs.text(
                query_str,       # <--- 改动在这里：直接传变量
                region='cn-zh', 
                timelimit='w', 
                max_results=limit
            )
            
            for r in ddgs_gen:
                title = r['title']
                body = r['body']
                # 过滤掉无关结果
                if keyword not in title and keyword not in body:
                    continue
                results.append(f"[{title}] - {body[:80]}...")
                
    except Exception as e:
        print(f"   ⚠️ 联网搜索失败: {e}")
        
    if not results:
        return []
    return results

# ================= 1. 数据收集阶段 =================

print(f"📥 [1/4] 初始化: {STOCK_NAME} ({SYMBOL})...")

# --- A. 技术面 ---
end_date = datetime.now()
start_date_6y = end_date - timedelta(days=365 * 6)
try:
    df = ak.stock_zh_a_hist(symbol=SYMBOL, period="daily", start_date=start_date_6y.strftime("%Y%m%d"), end_date=end_date.strftime("%Y%m%d"), adjust="qfq")
    current_price = df.iloc[-1]['收盘']
    ma20 = df['收盘'].rolling(window=20).mean().iloc[-1]
    ma250 = df['收盘'].rolling(window=250).mean().iloc[-1]
    tech_summary = f"现价 {current_price} | MA20 {ma20:.2f} | MA250 {ma250:.2f}"
    tech_context = f"- 现价: {current_price}\n- 月线(MA20): {ma20:.2f}\n- 年线(MA250): {ma250:.2f}"
except:
    tech_summary = "❌ 获取失败"
    tech_context = "技术面数据缺失"

# --- B. 资金面 ---
try:
    market = "sh" if SYMBOL.startswith("6") else "sz"
    fund_flow = ak.stock_individual_fund_flow(stock=SYMBOL, market=market)
    recent_flow = fund_flow.tail(3)
    total_net = recent_flow['主力净流入-净额'].sum()
    total_str = f"{total_net/1e8:.2f}亿" if abs(total_net) > 1e8 else f"{total_net/10000:.2f}万"
    flow_status = "🔴流入" if total_net > 0 else "🟢流出"
    money_summary = f"3日主力净{flow_status} {total_str}"
    
    flow_text = ""
    for _, row in recent_flow.iterrows():
        d = str(row['日期'])[:10]
        net = row['主力净流入-净额']
        s = "流入" if net > 0 else "流出"
        v = f"{net/1e8:.2f}亿" if abs(net) > 1e8 else f"{net/10000:.2f}万"
        flow_text += f"- {d}: {s} {v}\n"
    money_context = f"【主力资金】\n{flow_text}"
except:
    money_summary = "❌ 获取失败"
    money_context = "资金流向缺失"

# --- C. 舆情面 (AkShare + 联网搜索双引擎) ---
print(f"📰 [2/4] 拉取舆情 (本地接口 + 联网搜索)...")
news_items = []
news_source = "无"

# 1. 优先尝试本地接口 (AkShare 新闻)
try:
    news_df = ak.stock_news_em(symbol=SYMBOL)
    if not news_df.empty:
        news_items = news_df['title'].head(3).tolist()
        news_source = "东方财富接口"
except:
    pass

# 2. 如果本地接口没数据，启动【联网搜索】(DuckDuckGo)
if not news_items:
    print("   👉 本地接口未获取到数据，启动联网搜索...")
    web_results = search_web_news(STOCK_NAME)
    if web_results:
        news_items = web_results
        news_source = "全网搜索(DuckDuckGo)"

# 3. 实在不行，看大盘
if not news_items:
    try:
        sh_index = ak.stock_zh_index_daily(symbol="sh000001").iloc[-1]
        change = sh_index['close'] - sh_index['open']
        status = "上涨" if change > 0 else "下跌"
        news_items = [f"无个股新闻，市场背景: 上证指数今日{status}"]
        news_source = "大盘背景"
    except:
        pass

if news_items:
    news_summary = f"[{news_source}] 共 {len(news_items)} 条"
    news_context = f"【舆情 ({news_source})】\n" + "\n".join([f"- {t}" for t in news_items])
else:
    news_summary = "⚠️ 彻底静默"
    news_context = "当前无任何信息。"

# ================= 2. 预览与决策 =================

print("\n" + "="*15 + " 📊 投研数据摘要 " + "="*15)
print(f"📌 标的: {STOCK_NAME} ({SYMBOL})")
print(f"📈 趋势: {tech_summary}")
print(f"💸 资金: {money_summary}")
print(f"📰 舆情: {news_summary}")
if news_items:
    for i, title in enumerate(news_items, 1):
        # 截取长标题，防止刷屏
        print(f"   {i}. {title[:40]}...")
print("="*46)

if not wait_for_confirmation(15):
    sys.exit(0)

# ================= 3. 大模型分析 =================

prompt = f"""
你是一位实战派基金经理。请基于以下数据简评【{STOCK_NAME}】：

1. 资金面: {money_context}
2. 技术面: {tech_context}
3. 舆情面: {news_context}
(注：如果是全网搜索结果，请重点鉴别新闻时效性和相关性)

请给出：
1. 资金评分(0-10):
2. 一句话核心逻辑:
3. 操作建议(短线/长线):
"""

print(f"\n🧠 [3/4] 正在调用 GLM-4.6...")
try:
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    completion = client.chat.completions.create(
        model="glm-4.6",
        messages=[{"role": "user", "content": prompt}],
        extra_body={"enable_thinking": True},
        stream=True
    )

    full_response = ""
    print("\n" + "-" * 20 + " 思考与输出 " + "-" * 20)
    for chunk in completion:
        delta = chunk.choices[0].delta
        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
            print(delta.reasoning_content, end="", flush=True)
        if hasattr(delta, "content") and delta.content:
            full_response += delta.content
            print(delta.content, end="", flush=True)

    filename = f"研报_{STOCK_NAME}_{datetime.now().strftime('%Y%m%d')}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# {STOCK_NAME} 研报\n\n{full_response}")
    print(f"\n\n✅ [4/4] 完成: {filename}")

except Exception as e:
    print(f"\n❌ AI 调用失败: {e}")