import os
import akshare as ak
import pandas as pd
from openai import OpenAI
from datetime import datetime, timedelta

# --- 1. 强制直连 (防止 VPN 干扰) ---
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('all_proxy', None)


import os
# --- 新增：专门处理 Key 的部分 ---
# 优先从系统变量拿，如果拿不到（比如在 Crontab 里），就用后面这个默认值
# 请把你的 Key 填在后面这个字符串里，作为"保底"
API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-fd00c57b4db04bafb22800b3497701bd") 

# 如果还是没拿到，就报错提醒
if not API_KEY or API_KEY.startswith("sk-你的Key"):
    print("❌ 错误：未找到有效的 API Key！")
    exit(1)
# --- 配置区 ---
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
SYMBOL = "002683" # 广东宏大

# --- 2. 获取“超全景”数据 (6年) ---
print(f"🚀 正在拉取 [{SYMBOL}] 的跨周期数据 (过去6年)...")

end_date = datetime.now()
start_date_6y = end_date - timedelta(days=365 * 6) # 拉取 6 年

# 拉取数据
df = ak.stock_zh_a_hist(
    symbol=SYMBOL, 
    period="daily", 
    start_date=start_date_6y.strftime("%Y%m%d"), 
    end_date=end_date.strftime("%Y%m%d"), 
    adjust="qfq"
)

# 确保日期列是 datetime 格式，方便切片
df['日期'] = pd.to_datetime(df['日期'])

# --- 3. 计算多周期宏观指标 ---

# A. 计算 [6年周期] (大循环)
price_max_6y = df['最高'].max()
price_min_6y = df['最低'].min()
high_date_6y = df.loc[df['最高'].idxmax(), '日期'].strftime('%Y-%m-%d')
low_date_6y = df.loc[df['最低'].idxmin(), '日期'].strftime('%Y-%m-%d')

# B. 计算 [3年周期] (中循环)
start_date_3y = end_date - timedelta(days=365 * 3)
df_3y = df[df['日期'] >= start_date_3y]
price_max_3y = df_3y['最高'].max()
price_min_3y = df_3y['最低'].min()

# C. 均线系统 (基于全量数据)
df['MA20'] = df['收盘'].rolling(window=20).mean()
df['MA60'] = df['收盘'].rolling(window=60).mean()
df['MA120'] = df['收盘'].rolling(window=120).mean()
df['MA250'] = df['收盘'].rolling(window=250).mean() # 年线

current_price = df.iloc[-1]['收盘']
ma250 = df.iloc[-1]['MA250']

# 简单的位置定性
position_rank = (current_price - price_min_6y) / (price_max_6y - price_min_6y) * 100

# --- 4. 构建“三层”数据 Prompt ---

# 层1：6年大周期 (历史大底/大顶)
macro_6y = f"""
【6年大周期 (历史极限)】
- 历史最高: {price_max_6y} ({high_date_6y})
- 历史最低: {price_min_6y} ({low_date_6y})
- 当前分位: 处于6年历史区间的 {position_rank:.1f}% 位置
- 牛熊分界(MA250): {ma250:.2f} (现价{'站上' if current_price > ma250 else '跌破'}年线)
"""

# 层2：3年本轮周期 (近期强弱)
macro_3y = f"""
【3年本轮周期】
- 周期内最高: {price_max_3y}
- 周期内最低: {price_min_3y}
- 累计涨幅: {((current_price - df_3y.iloc[0]['收盘'])/df_3y.iloc[0]['收盘']*100):.2f}%
"""

# 层3：90天微观形态 (季度走势)
# 截取最后 90 行
micro_df = df.iloc[-90:].copy()
# 为了节省 token，只保留关键列，并将日期转回字符串
micro_df['日期'] = micro_df['日期'].dt.strftime('%Y-%m-%d')
micro_context = micro_df[['日期', '开盘', '收盘', '最高', '最低', '涨跌幅', 'MA20', 'MA60']].to_csv(index=False, sep="\t")

# --- 5. 组合 Prompt ---
prompt = f"""
你是一位擅长"周期共振"分析的资深基金经理。请结合【6年历史大底】、【3年近期趋势】和【90天季度形态】对 {SYMBOL} 进行战略分析。

=== 数据层 1：6年大周期 (历史坐标) ===
{macro_6y}

=== 数据层 2：3年本轮周期 (中期强弱) ===
{macro_3y}

=== 数据层 3：90天微观数据 (季度形态) ===
(格式：日期, 开盘, 收盘, 最高, 最低, 涨跌幅, MA20, MA60)
{micro_context}

=== 分析任务 (请开启深度思考) ===
1. **历史定位**: 结合6年高低点和当前分位，判断该股是处于"历史底部区域"、"山腰"还是"山顶"？
2. **趋势共振**: 
   - 长期(MA250)是否走平或向上？
   - 中期(3年)是否创出新高或止跌？
3. **季度形态**: 仔细观察最近90天数据，是否存在主力吸筹痕迹（如：缩量下跌、放量上涨、红肥绿瘦）？
4. **决策结论**: 
   - 给出具体的支撑位（防守）和压力位（目标）。
   - 给出最终评级：【战略性建仓 / 中线持有 / 短线博弈 / 离场观望】。

请开始你的深度推演：
"""

print(f"🧠 正在调用 GLM-4.6 进行 [6年-3年-90天] 跨周期分析...")

# --- 6. 调用 API ---
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

completion = client.chat.completions.create(
    model="glm-4.6",
    messages=[{"role": "user", "content": prompt}],
    extra_body={"enable_thinking": True},
    stream=True
)

# --- 7. 打印输出 (支持 Markdown 写入 + 终端显示) ---
full_thinking = ""
full_response = ""
is_answering = False

print("\n" + "=" * 20 + " 🧠 AI 深度思考中 " + "=" * 20)

for chunk in completion:
    delta = chunk.choices[0].delta
    
    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
        text = delta.reasoning_content
        full_thinking += text
        if not is_answering:
            print(text, end="", flush=True)

    if hasattr(delta, "content") and delta.content:
        text = delta.content
        full_response += text
        if not is_answering:
            print("\n\n" + "=" * 20 + " 📊 最终决策报告 " + "=" * 20)
            is_answering = True
        print(text, end="", flush=True)

# 保存研报
report_date = datetime.now().strftime("%Y-%m-%d")
filename = f"研报_全周期_{SYMBOL}_{report_date}.md"
with open(filename, "w", encoding="utf-8") as f:
    final_md = f"# 📈 智投·Alpha 全周期研报: {SYMBOL}\n\n## 🧠 思考过程\n{full_thinking}\n\n## 📊 最终决策\n{full_response}"
    f.write(final_md)

print(f"\n\n✅ [全周期] 研报已生成: {filename}")
print("=" * 60)

import requests

# --- 8. 智能推送模块 (Smart Notification) ---
import requests
import urllib.parse # 用来处理中文URL编码

def push_to_phone(title, content):
    # Bark 的 URL 不支持直接放中文空格和特殊符号，需要编码
    encoded_title = urllib.parse.quote(title)
    encoded_content = urllib.parse.quote(content)
    
    # 替换你的 Key
    key = "9eboKb4iRG7KotqDAmzC7a" 
    url = f"https://api.day.app/{key}/{encoded_title}/{encoded_content}?group=AlphaInvest"
    
    try:
        requests.get(url, timeout=5)
        print(f"📱 推送成功: {title}")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

# --- 智能关键词触发 ---
# 定义一组触发词，只要出现任意一个，就视为"利好"
buy_signals = ["买入", "建仓", "低吸", "增持", "做多", "持有"]

# 简单的清洗逻辑：从完整回复中提取最后一段建议，避免推送太长
# 假设 AI 的回复通常最后是结论，我们截取最后 100 个字作为摘要
summary = full_response[-100:].replace("\n", " ") 

triggered = False
for signal in buy_signals:
    if signal in full_response:
        # 发现信号！
        push_to_phone(f"🔥 {SYMBOL} 出现【{signal}】信号", f"AI观点摘要：{summary}")
        triggered = True
        break

if not triggered:
    # 如果没有买入信号，也可以选择推一个"日报已生成"
    push_to_phone(f"📋 {SYMBOL} 日报已生成", "AI建议观望或离场，详情请看电脑研报。")