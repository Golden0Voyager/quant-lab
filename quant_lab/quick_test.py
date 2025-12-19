#!/usr/bin/env python3
"""
快速测试单只股票
用法: python quick_test.py
"""
from analyst_core import fetch_stock_data

# 👇 修改这里测试你想要的股票
TEST_CODE = "002920"   # 股票代码
TEST_NAME = "德赛西威"  # 股票名称

print(f"\n{'='*60}")
print(f"🔍 测试股票: {TEST_NAME} ({TEST_CODE})")
print('='*60)

# 获取数据
data = fetch_stock_data(TEST_CODE, TEST_NAME)

# 打印结果
print(f"\n📊 技术面:")
print(f"  {data['tech_summary']}")

print(f"\n💰 资金面:")
print(f"  {data['money_summary']}")

print(f"\n📰 舆情面:")
print(f"  概要: {data['news_summary']}")

print(f"  来源: {data.get('news_source', '未知')}")
print(f"\n  详细内容:")
for line in data['news_context'].split('\n'):
    if line.strip():
        print(f"  {line}")

# 判断测试结果
print(f"\n{'='*60}")
if data.get('news_source') in ['东方财富', '全网搜索']:
    print(f"✅ 测试成功: 成功获取新闻数据")
elif data.get('news_source') == '大盘背景':
    
    print(f"⚠️  降级成功: 使用大盘背景（个股新闻未获取到）")
else:
    print(f"❌ 测试失败: 未能获取任何数据")
print('='*60 + '\n')
