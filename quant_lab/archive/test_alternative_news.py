#!/usr/bin/env python3
"""
测试 AkShare 的其他新闻接口
"""
import akshare as ak

test_symbols = ["002920", "000988"]

print("="*60)
print("🧪 测试 stock_news_main_cx 接口")
print("="*60)

for symbol in test_symbols:
    print(f"\n测试: {symbol}")
    try:
        df = ak.stock_news_main_cx(symbol=symbol)
        if df.empty:
            print(f"  ⚠️ 返回空数据")
        else:
            print(f"  ✅ 成功获取 {len(df)} 条新闻")
            print(f"  列名: {list(df.columns)}")
            print(f"  前2条新闻:")
            for idx, row in df.head(2).iterrows():
                print(f"    {idx+1}. {row.get('title', row.get('标题', 'N/A'))}")
    except Exception as e:
        print(f"  ❌ 失败: {e}")

print("\n" + "="*60)
print("🧪 测试 news_cctv 接口（央视新闻）")
print("="*60)

try:
    df = ak.news_cctv()
    if df.empty:
        print(f"⚠️ 返回空数据")
    else:
        print(f"✅ 成功获取 {len(df)} 条新闻")
        print(f"列名: {list(df.columns)}")
        print(f"前3条新闻:")
        for idx, row in df.head(3).iterrows():
            print(f"  {idx+1}. {row.iloc[0]}")  # 打印第一列
except Exception as e:
    print(f"❌ 失败: {e}")
