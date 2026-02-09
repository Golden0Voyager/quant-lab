#!/usr/bin/env python3
"""
三引擎方案性能对比测试
"""
import time
from analyst_base import fetch_stock_data
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

test_stocks = [
    ("德赛西威", "002920"),
    ("华工科技", "000988"),
    ("贵州茅台", "600519"),
]

print("="*70)
print("⚡ 三引擎方案性能测试")
print("="*70)

total_time = 0
success_count = 0
source_stats = {"东财公告": 0, "全网搜索": 0, "大盘背景": 0, "无": 0}

for name, code in test_stocks:
    print(f"\n{'='*70}")
    print(f"测试: {name} ({code})")
    print('='*70)

    start_time = time.time()

    try:
        data = fetch_stock_data(code, name)
        elapsed = time.time() - start_time
        total_time += elapsed

        source = data.get('news_source', '无')
        source_stats[source] = source_stats.get(source, 0) + 1

        print(f"\n⏱️  响应时间: {elapsed:.2f}秒")
        print(f"📊 数据源: {source}")
        print(f"📰 新闻概要: {data['news_summary']}")
        print(f"\n详细内容:")
        for line in data['news_context'].split('\n')[:3]:  # 只显示前3条
            if line.strip():
                print(f"  {line}")

        if data.get('news_source') in ['东财公告', '全网搜索']:
            print(f"\n✅ 成功获取")
            success_count += 1
        elif data.get('news_source') == '大盘背景':
            print(f"\n⚠️  降级到大盘背景")
            success_count += 1
        else:
            print(f"\n❌ 失败")

    except Exception as e:
        print(f"\n❌ 异常: {e}")
        elapsed = time.time() - start_time
        total_time += elapsed

print(f"\n{'='*70}")
print("📊 测试总结")
print('='*70)
print(f"总测试: {len(test_stocks)} 只股票")
print(f"成功: {success_count} 只")
print(f"平均响应时间: {total_time/len(test_stocks):.2f}秒")
print(f"\n数据源分布:")
for source, count in source_stats.items():
    if count > 0:
        print(f"  {source}: {count} 只")

print(f"\n性能评估:")
avg_time = total_time / len(test_stocks)
if avg_time < 2:
    print(f"  ⭐⭐⭐⭐⭐ 优秀 (平均 {avg_time:.2f}秒)")
elif avg_time < 3:
    print(f"  ⭐⭐⭐⭐ 良好 (平均 {avg_time:.2f}秒)")
elif avg_time < 5:
    print(f"  ⭐⭐⭐ 一般 (平均 {avg_time:.2f}秒)")
else:
    print(f"  ⭐⭐ 偏慢 (平均 {avg_time:.2f}秒)")

success_rate = (success_count / len(test_stocks)) * 100
print(f"\n成功率: {success_rate:.1f}%")

print("="*70)
