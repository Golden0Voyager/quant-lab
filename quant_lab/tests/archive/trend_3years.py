import os

# --- 强制禁用系统代理 ---
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''

import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
import datetime

# --- 设置参数 ---
stock_code = "002683"  # 广东宏大
stock_name = "Guangdong Hongda"

# 1. 自动计算时间范围 (过去3年)
end_date = datetime.datetime.now()
start_date = end_date - datetime.timedelta(days=365 * 3)

# 转为 akshare 需要的字符串格式 'YYYYMMDD'
str_start = start_date.strftime("%Y%m%d")
str_end = end_date.strftime("%Y%m%d")

print(f"🚀 正在拉取 [{stock_name}] 从 {str_start} 到 {str_end} 的数据...")

# 2. 调用接口获取数据 (前复权)
# period="daily" 表示日线
df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date=str_start, end_date=str_end, adjust="qfq")

# 3. 数据清洗
# 只要日期和收盘价
df = df[['日期', '收盘', '最高', '最低']]
df['日期'] = pd.to_datetime(df['日期']) # 把字符串转为时间格式，方便画图
df.set_index('日期', inplace=True)

# 4. 简单的统计分析
max_price = df['最高'].max()
min_price = df['最低'].min()
current_price = df['收盘'].iloc[-1]
total_return = (current_price - df['收盘'].iloc[0]) / df['收盘'].iloc[0] * 100

print("-" * 30)
print(f"📊 统计报告 ({str_start} - {str_end})")
print(f"最高价: {max_price}")
print(f"最低价: {min_price}")
print(f"现价:   {current_price}")
print(f"区间涨幅: {total_return:.2f}%")
print("-" * 30)

# 5. 画图 (Mac 可能会需要设置字体，这里用英文避免乱码)
plt.figure(figsize=(12, 6))
plt.plot(df.index, df['收盘'], label='Close Price', color='#1f77b4', linewidth=1.5)

# 标记最高点和最低点
plt.axhline(max_price, color='red', linestyle='--', alpha=0.5, label=f'Max: {max_price}')
plt.axhline(min_price, color='green', linestyle='--', alpha=0.5, label=f'Min: {min_price}')

plt.title(f"{stock_name} - 3 Year Trend", fontsize=14)
plt.grid(True, alpha=0.3)
plt.legend()
plt.tight_layout()

# 保存图片到当前目录
plt.savefig(f"{stock_name}_trend.png")
print(f"✅ 图表已保存为 {stock_name}_trend.png，请在文件夹中查看！")

# 如果在 VS Code 中支持弹窗，也可以取消下面这行的注释
# plt.show()